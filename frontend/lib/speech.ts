// Browser-side playback of TTS audio synthesized by the backend.
//
// Dual-layer voice architecture:
//   1. Primary: POSTs text to /api/voice/speak (Edge TTS / Qwen3 / ElevenLabs).
//   2. Auto-detects audio format (MPEG vs WAV) to ensure browser HTMLAudioElement
//      never errors on decoding.
//   3. Auto-unlocks AudioContext on user interaction to satisfy browser autoplay policies.
//   4. Resilient Fallback: If network, backend container wake-up (502/504), or browser
//      autoplay blocks the audio element, seamlessly falls back to window.speechSynthesis
//      so the user never experiences broken silence.
//   5. Exposes isSpeaking / subscribeSpeaking to prevent mic-speaker feedback loops.

export type SpeakingListener = (speaking: boolean) => void;

type Job = {
  text: string;
  onError?: (err: Error) => void;
  onEnd?: () => void;
  generation: number;
};

const listeners = new Set<SpeakingListener>();
let activeAudio: HTMLAudioElement | null = null;
let cooldownTimer: ReturnType<typeof setTimeout> | null = null;
let pending: Job | null = null;
let draining = false;
let currentGeneration = 0;
let audioUnlocked = false;

// Audio unlock helper for modern browsers (Chrome/Safari/Edge/Firefox)
export function unlockAudio(): void {
  if (typeof window === "undefined" || audioUnlocked) return;
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioCtx) {
      const ctx = new AudioCtx();
      if (ctx.state === "suspended") {
        ctx.resume();
      }
    }
    audioUnlocked = true;
  } catch {
    /* ignore */
  }
}

// Auto-register unlock listener once window is available
if (typeof window !== "undefined") {
  const onInteraction = () => {
    unlockAudio();
    window.removeEventListener("click", onInteraction);
    window.removeEventListener("keydown", onInteraction);
    window.removeEventListener("touchstart", onInteraction);
  };
  window.addEventListener("click", onInteraction, { passive: true });
  window.addEventListener("keydown", onInteraction, { passive: true });
  window.addEventListener("touchstart", onInteraction, { passive: true });
}

export function isSpeaking(): boolean {
  return (
    activeAudio !== null ||
    (typeof window !== "undefined" && window.speechSynthesis?.speaking === true)
  );
}

export function subscribeSpeaking(fn: SpeakingListener): () => void {
  listeners.add(fn);
  fn(isSpeaking());
  return () => {
    listeners.delete(fn);
  };
}

function setSpeaking(value: boolean) {
  listeners.forEach((l) => l(value));
}

function enterCooldown() {
  if (cooldownTimer) clearTimeout(cooldownTimer);
  cooldownTimer = setTimeout(() => {
    cooldownTimer = null;
    setSpeaking(false);
  }, 350);
}

function clearActiveAudio() {
  if (activeAudio) {
    try {
      activeAudio.pause();
      activeAudio.src = "";
    } catch {
      /* ignore */
    }
    activeAudio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* ignore */
    }
  }
}

/**
 * Speak `text` through the backend's configured TTS engine with automatic
 * browser speech synthesis fallback.
 */
export function speakText(
  text: string,
  options?: { onError?: (err: Error) => void; onEnd?: () => void }
): void {
  // Normalize symbols for clean, natural speech pronunciation
  const clean = (text || "")
    .replace(/[`*_#]/g, " ")
    .replace(/৳\s*([\d,]+(?:\.\d+)?)/g, "$1 Taka")
    .replace(/BDT\s*([\d,]+(?:\.\d+)?)/gi, "$1 Taka")
    .replace(/@([a-zA-Z0-9_]+)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();

  if (!clean) return;
  if (typeof window === "undefined") return;

  unlockAudio();

  // Stop anything currently playing so the new utterance takes over
  if (activeAudio || window.speechSynthesis?.speaking) {
    clearActiveAudio();
    if (cooldownTimer) {
      clearTimeout(cooldownTimer);
      cooldownTimer = null;
    }
  }

  currentGeneration += 1;
  pending = {
    text: clean,
    onError: options?.onError,
    onEnd: options?.onEnd,
    generation: currentGeneration,
  };
  void drain();
}

async function drain(): Promise<void> {
  if (draining) return;
  draining = true;
  try {
    while (pending) {
      const job = pending;
      pending = null;
      const myGen = job.generation;
      try {
        const audioBlob = await fetchWav(job.text);
        if (myGen !== currentGeneration) continue;
        const played = await playBlob(audioBlob, job);
        if (!played) {
          // Playback rejected by browser autoplay policy -> fallback to speechSynthesis
          console.info("[TTS] Playback rejected, using browser speech synthesis fallback");
          await playFallbackSpeechSynthesis(job.text, job);
        }
      } catch (e) {
        if (myGen !== currentGeneration) continue;
        const err = e instanceof Error ? e : new Error(String(e));
        console.warn("[TTS] Backend synthesis failed, using speech synthesis fallback:", err.message);
        // Fallback so user always hears the spoken response
        await playFallbackSpeechSynthesis(job.text, job);
      }
    }
  } finally {
    draining = false;
  }
}

async function fetchWav(text: string): Promise<Blob> {
  const res = await fetch("/api/voice/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j?.detail) detail += `: ${JSON.stringify(j.detail)}`;
    } catch {
      /* ignore */
    }
    throw new Error(`tts ${detail}`);
  }

  const arrayBuffer = await res.arrayBuffer();
  if (arrayBuffer.byteLength === 0) throw new Error("tts returned empty audio");

  // Inspect magic bytes to give the browser the EXACT valid MIME type
  const header = new Uint8Array(arrayBuffer.slice(0, 4));
  let mimeType = res.headers.get("content-type") || "audio/wav";

  // Check for MP3 sync word (0xFF 0xFB, 0xFF 0xF3, 0xFF 0xF2) or ID3 tag
  if (
    (header[0] === 0xff && (header[1] === 0xfb || header[1] === 0xf3 || header[1] === 0xf2)) ||
    (header[0] === 0x49 && header[1] === 0x44 && header[2] === 0x33)
  ) {
    mimeType = "audio/mpeg";
  } else if (
    header[0] === 0x52 &&
    header[1] === 0x49 &&
    header[2] === 0x46 &&
    header[3] === 0x46
  ) {
    mimeType = "audio/wav";
  }

  return new Blob([arrayBuffer], { type: mimeType });
}

async function playBlob(blob: Blob, job: Job): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    let settled = false;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    activeAudio = audio;
    setSpeaking(true);

    const finish = (success: boolean) => {
      if (settled) return;
      settled = true;
      URL.revokeObjectURL(url);
      if (activeAudio === audio) {
        clearActiveAudio();
        enterCooldown();
      }
      if (success) {
        job.onEnd?.();
      }
      resolve(success);
    };

    audio.onended = () => finish(true);
    audio.onerror = (e) => {
      console.warn("[TTS] audio element error:", e);
      finish(false);
    };

    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.catch((err) => {
        console.warn("[TTS] audio.play rejected (autoplay policy?):", err);
        finish(false);
      });
    }
  });
}

async function playFallbackSpeechSynthesis(text: string, job: Job): Promise<void> {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    job.onEnd?.();
    return;
  }

  return new Promise<void>((resolve) => {
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;

      // Select natural English voice if available
      const voices = window.speechSynthesis.getVoices();
      const preferredVoice =
        voices.find(
          (v) =>
            (v.name.includes("Natural") ||
              v.name.includes("Online") ||
              v.name.includes("Samantha") ||
              v.name.includes("Google") ||
              v.name.includes("Daniel")) &&
            v.lang.startsWith("en")
        ) || voices.find((v) => v.lang.startsWith("en"));

      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      setSpeaking(true);
      utterance.onend = () => {
        enterCooldown();
        job.onEnd?.();
        resolve();
      };
      utterance.onerror = () => {
        enterCooldown();
        job.onEnd?.();
        resolve();
      };

      window.speechSynthesis.speak(utterance);
    } catch {
      enterCooldown();
      job.onEnd?.();
      resolve();
    }
  });
}

export function stopSpeaking(): void {
  if (typeof window === "undefined") return;
  if (cooldownTimer) {
    clearTimeout(cooldownTimer);
    cooldownTimer = null;
  }
  clearActiveAudio();
  pending = null;
  currentGeneration += 1;
  setSpeaking(false);
}
