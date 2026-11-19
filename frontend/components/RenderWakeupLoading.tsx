"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Cloud,
  Cpu,
  RefreshCw,
  Server,
  ShieldCheck,
  Sparkles,
  Zap,
  Info,
} from "lucide-react";

interface RenderWakeupLoadingProps {
  title?: string;
  subtitle?: string;
  onRetry?: () => void;
  error?: string | null;
  loginPath?: string;
}

export function RenderWakeupLoading({
  title = "Wallet AI Engine",
  subtitle = "Connecting to Autonomous BDT Money Movement Platform",
  onRetry,
  error = null,
  loginPath = "/login",
}: RenderWakeupLoadingProps) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Compute realistic progress estimate for a 35s cold-start
  const progressPercent = Math.min(
    95,
    seconds <= 3 ? 15 + seconds * 5 : 30 + Math.min(65, (seconds - 3) * 2.2)
  );

  // Dynamic phase messaging
  let phaseBadge = "Connecting";
  let phaseBadgeColor = "bg-peach-500/15 border-peach-500/30 text-peach-300";
  let statusMessage = "Initiating handshake with secure backend gateway…";

  if (seconds >= 4 && seconds < 16) {
    phaseBadge = "Waking Cloud Container";
    phaseBadgeColor = "bg-amber-500/15 border-amber-500/30 text-amber-300";
    statusMessage = "Waking up Render backend container from sleep…";
  } else if (seconds >= 16 && seconds < 30) {
    phaseBadge = "Booting Engine";
    phaseBadgeColor = "bg-blue-500/15 border-blue-500/30 text-blue-300";
    statusMessage = "Initializing FastAPI, SQLite ACID ledger & ML fraud detector…";
  } else if (seconds >= 30) {
    phaseBadge = "Finalizing";
    phaseBadgeColor = "bg-emerald-500/15 border-emerald-500/30 text-emerald-300";
    statusMessage = "Almost ready! Waking complete, loading your financial dashboard…";
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-6 bg-plum-gradient text-cream">
      <div className="w-full max-w-md glass-strong rounded-2xl p-6 sm:p-8 shadow-2xl border border-white/10 flex flex-col items-center text-center relative overflow-hidden">
        {/* Ambient Top Glow */}
        <div className="absolute -top-20 left-1/2 -translate-x-1/2 w-56 h-56 bg-peach-500/20 rounded-full blur-3xl pointer-events-none" />

        {/* Brand Icon with dual pulsing aura */}
        <div className="relative mb-5 mt-1">
          <div className="absolute inset-0 rounded-2xl bg-peach-500/25 blur-md animate-pulse" />
          <div className="relative w-16 h-16 rounded-2xl bg-white/10 border border-peach-500/40 flex items-center justify-center text-peach-300 shadow-glow-peach">
            <ShieldCheck className="w-8 h-8 text-peach-400" />
            <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-plum-950 flex items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-cream animate-ping" />
            </div>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-cream">
          {title}
        </h1>
        <p className="text-xs sm:text-sm text-lavender mt-1.5 mb-6 max-w-xs leading-relaxed">
          {subtitle}
        </p>

        {/* Phase Pill */}
        <div
          className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-semibold mb-4 transition-all duration-300 ${phaseBadgeColor}`}
        >
          <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
          <span>{phaseBadge}</span>
          <span className="opacity-70 font-mono text-[11px]">({seconds}s)</span>
        </div>

        {/* Progress Bar Container */}
        <div className="w-full bg-white/5 rounded-full h-2 mb-3 border border-white/10 overflow-hidden relative">
          <div
            className="h-full bg-gradient-to-r from-peach-500 via-peach-400 to-amber-300 rounded-full transition-all duration-500 ease-out shadow-glow-peach"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Status Text */}
        <p className="text-xs sm:text-sm text-lavender font-medium min-h-[40px] flex items-center justify-center px-2">
          {statusMessage}
        </p>

        {/* Render Cold-Start Alert / Hint Box */}
        <div className="mt-5 w-full bg-plum-900/60 border border-white/10 rounded-xl p-3.5 text-left text-xs leading-relaxed">
          <div className="flex items-start gap-2.5">
            <Cloud className="w-4 h-4 text-peach-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-peach-300 flex items-center gap-1.5">
                <span>Render Cloud Backend Wake-Up</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-peach-500/20 text-peach-200 border border-peach-500/30">
                  Free Tier
                </span>
              </div>
              <p className="text-lavender/80 mt-1 text-[11px] leading-normal">
                Render free-tier instances sleep automatically after inactivity. On first visit, container boot takes about <strong>20–40 seconds</strong>. Subsequent operations run with zero wait.
              </p>
            </div>
          </div>
        </div>

        {/* Error message or Long Wait Actions */}
        {(error || seconds >= 35) && (
          <div className="mt-5 w-full flex flex-col items-center gap-2.5 pt-4 border-t border-white/10">
            {error && (
              <p className="text-xs text-rose-300 font-mono bg-rose-500/10 border border-rose-500/20 px-3 py-1.5 rounded-lg w-full text-center">
                {error}
              </p>
            )}
            <div className="flex items-center gap-3 w-full">
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="flex-1 btn-peach py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Retry Connection
                </button>
              )}
              <Link
                href={loginPath}
                className="flex-1 btn-ghost py-2 rounded-xl text-xs font-medium flex items-center justify-center gap-1.5 text-lavender hover:text-cream"
              >
                Switch Account
              </Link>
            </div>
          </div>
        )}

        {/* Footer Technical Badges */}
        <div className="mt-6 flex items-center justify-center gap-3 text-[10px] text-lavender/60 font-mono">
          <span className="flex items-center gap-1">
            <Server className="w-3 h-3 text-peach-400/80" /> FastAPI
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Cpu className="w-3 h-3 text-emerald-400/80" /> LightGBM + Hybrid ML
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Zap className="w-3 h-3 text-amber-400/80" /> ACID Ledger
          </span>
        </div>
      </div>
    </div>
  );
}
