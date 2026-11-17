"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { api } from "@/lib/api";
import { VoiceButton } from "./VoiceButton";
import { ArrowUp } from "lucide-react";
import { speakText, subscribeSpeaking } from "@/lib/speech";

export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  pending?: boolean;
  typing?: boolean;
};

export type ChatBarHandle = {
  sendPrompt: (text: string) => void;
  focus: () => void;
};

let _id = 0;
const nextId = () => ++_id;

export const ChatBar = forwardRef<
  ChatBarHandle,
  {
    userId: number;
    onCommand: (text: string) => Promise<{ text: string } | null>; // command to /agent/act
    disabled?: boolean;
    placeholder?: string;
  }
>(function ChatBar(
  {
    userId,
    onCommand,
    disabled,
    placeholder = "Say something, e.g. 'send 500 to rishad'",
  },
  ref
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useImperativeHandle(ref, () => ({
    sendPrompt: (text: string) => {
      sendText(text);
    },
    focus: () => {
      inputRef.current?.focus();
    },
  }));

  useEffect(() => {
    return subscribeSpeaking(setSpeaking);
  }, []);

  useEffect(() => {
    // Auto-scroll on new message or as text is typed.
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function typewrite(msgId: number, fullText: string) {
    if (!fullText) {
      setMessages((m) =>
        m.map((x) =>
          x.id === msgId ? { ...x, text: "", pending: false, typing: false } : x
        )
      );
      return;
    }
    const step = fullText.length > 200 ? 3 : fullText.length > 80 ? 2 : 1;
    let current = "";
    for (let i = 0; i < fullText.length; i += step) {
      current = fullText.slice(0, i + step);
      setMessages((m) =>
        m.map((x) =>
          x.id === msgId
            ? { ...x, text: current, pending: false, typing: true }
            : x
        )
      );
      await new Promise((r) => setTimeout(r, 16));
    }
    setMessages((m) =>
      m.map((x) =>
        x.id === msgId
          ? { ...x, text: fullText, pending: false, typing: false }
          : x
      )
    );
  }

  async function sendText(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy || disabled) return;
    setInput("");
    const userMsg: ChatMessage = { id: nextId(), role: "user", text: trimmed };
    setMessages((m) => [...m, userMsg]);
    setBusy(true);

    // First, classify whether this is a money command or small talk.
    // The bar is: an orchestrator command needs a real money/ledger signal
    // — either a movement verb sitting next to a digit ("send 300 to srijan"),
    // or the bare ledger keywords "balance" / "history". Phrases like
    // "request help", "pay attention", "send me a joke", "split the bill"
    // are small talk and go to /agent/chat.
    const norm = trimmed.toLowerCase();
    const hasDigit = /\d/.test(norm);
    const movementVerb = /\b(send|transfer|pay|request|split)\b/.test(norm);
    const isBudgetCmd = /^\s*(set budget|fix budget|save for|manage budget)\b/.test(norm);
    // Allow short ledger phrases like "balance?", "show my history", "balance
    // please" — but not "history of rome" (a general knowledge question).
    const ledgerKeyword =
      /^\s*(balance|history)\b/.test(norm) &&
      !/\b(history of|balance sheet)\b/.test(norm);
    const isCommand =
      (movementVerb && (hasDigit || /\b(to|from|with|between|money|taka|bdt)\b/.test(norm))) ||
      ledgerKeyword ||
      isBudgetCmd;

    if (isCommand) {
      // Defer to the orchestrator and show a thinking reply.
      const thinkId = nextId();
      const think: ChatMessage = {
        id: thinkId,
        role: "assistant",
        text: "…",
        pending: true,
      };
      setMessages((m) => [...m, think]);
      try {
        const response = await onCommand(trimmed);
        const replyText = response?.text || "I couldn't complete that request.";
        speakText(replyText);
        await typewrite(thinkId, replyText);
      } catch (e) {
        const errMsg = `Couldn't reach the assistant: ${(e as Error).message}`;
        await typewrite(thinkId, errMsg);
      } finally {
        setBusy(false);
      }
      return;
    }

    // Pure chat — use the conversational endpoint.
    const assistantId = nextId();
    const think: ChatMessage = {
      id: assistantId,
      role: "assistant",
      text: "…",
      pending: true,
    };
    setMessages((m) => [...m, think]);
    try {
      const r = await api.agentChat({ user_id: userId, text: trimmed });
      speakText(r.text);
      await typewrite(assistantId, r.text);
    } catch (e) {
      const errMsg = `Couldn't reach the assistant: ${(e as Error).message}`;
      await typewrite(assistantId, errMsg);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendText(input);
  }

  function onVoice(transcript: string) {
    if (!transcript) return;
    sendText(transcript);
  }

  // While the bot is speaking, the mic must be disabled to avoid the
  // bot's own audio being transcribed as a new user command.
  const micDisabled = busy || disabled || speaking;

  return (
    // The card itself has a fixed max-height so it never grows past
    // ~22rem no matter how long the thread gets. The thread scrolls
    // inside; the input row stays pinned at the bottom. This keeps
    // the dashboard layout stable as the conversation lengthens.
    <div className="glass rounded-2xl p-4 flex flex-col gap-3 max-h-[22rem] min-h-[16rem]">
      {/* Thread */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto pr-1 flex flex-col gap-2"
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 text-center">
            <div className="text-xs text-secondary mb-3">
              Ask the Financial Assistant, get budget recommendations, or run money commands:
            </div>
            <div className="flex flex-wrap justify-center gap-1.5 max-w-md">
              {[
                "💡 Budget recommendations",
                "📊 Analyze my spending habits",
                "🛡️ How does fraud detection protect me?",
                "📚 Explain the 50/30/20 rule",
                "💰 What is an emergency fund?",
              ].map((chip) => (
                <button
                  key={chip}
                  type="button"
                  onClick={() => sendText(chip.replace(/^[^\s]+\s/, ""))}
                  disabled={busy || disabled}
                  className="text-[11px] px-2.5 py-1 rounded-full bg-white/5 hover:bg-peach-500/20 text-cream/80 hover:text-white border border-white/10 hover:border-peach-500/30 transition-all text-left"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={
                "rounded-xl px-3 py-2 text-sm max-w-[85%] whitespace-pre-wrap " +
                (m.role === "user"
                  ? "self-end bg-peach-500/20 text-cream"
                  : "self-start bg-white/5 text-cream/90")
              }
            >
              {m.role === "assistant" && !m.pending ? (
                <span>
                  <span className="text-peach-500/80 text-xs uppercase tracking-wider mr-2 font-mono">
                    wallet
                  </span>
                  {m.text}
                  {m.typing && (
                    <span className="inline-block w-1.5 h-3.5 ml-1 bg-peach-500 animate-pulse align-middle" />
                  )}
                </span>
              ) : (
                m.text
              )}
            </div>
          ))
        )}
      </div>

      {/* Input row */}
      <form onSubmit={onSubmit} className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          disabled={busy || disabled}
          className="flex-1 bg-white/5 border border-white/10 rounded-full px-4 py-2.5 text-sm text-cream placeholder:text-secondary focus:outline-none focus:border-peach-500/50"
        />
        <VoiceButton
          disabled={micDisabled}
          onTranscript={onVoice}
        />
        <button
          type="submit"
          disabled={busy || disabled || !input.trim()}
          className="btn-peach rounded-full px-4 py-2.5 text-sm font-semibold disabled:opacity-40 flex items-center gap-1.5"
        >
          Send <ArrowUp size={15} strokeWidth={2.2} />
        </button>
      </form>
    </div>
  );
});