"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { User, api } from "@/lib/api";
import { writeActiveUserId } from "@/lib/session";
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Form credentials state
  const [email, setEmail] = useState("bikash@wallet.com");
  const [password, setPassword] = useState("wallet2026");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .listUsers()
      .then((u) => setUsers(u))
      .catch((e) => setError(`Couldn't reach server: ${(e as Error).message}`));
  }, []);

  async function handleFormLogin(e: React.FormEvent) {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError("Please enter your email or username");
      return;
    }
    setError(null);
    setSubmitting(true);

    try {
      const user = await api.login(cleanEmail, password);
      writeActiveUserId(user.id);
      setTimeout(() => router.push("/"), 150);
    } catch (err) {
      setError((err as Error).message || "Invalid credentials");
      setSubmitting(false);
    }
  }

  function autofill(handle: string) {
    setEmail(`${handle}@wallet.com`);
    setPassword("wallet2026");
    setError(null);
  }

  function handleGoogleLogin() {
    setError(null);
    const primary = users.find((u) => u.handle === "bikash") || users[0];
    if (primary) {
      setSubmitting(true);
      writeActiveUserId(primary.id);
      setTimeout(() => router.push("/"), 200);
    }
  }

  return (
    <main className="relative min-h-screen w-full flex items-center justify-center p-4 sm:p-8 lg:p-12 overflow-x-hidden text-cream selection:bg-peach-500/30">
      {/* Background image: Neon Blue Global Banking Network */}
      <div
        className="fixed inset-0 w-full h-full bg-cover bg-center bg-no-repeat -z-20 transform scale-105 transition-transform duration-1000"
        style={{ backgroundImage: "url('/image/bg.png')" }}
      />

      {/* Dark overlay with plum gradient tint for high contrast & elegance */}
      <div className="fixed inset-0 bg-gradient-to-tr from-plum-950/95 via-plum-950/85 to-plum-950/60 backdrop-blur-[2px] -z-10" />

      {/* Full viewport container: 2-column layout on large screens */}
      <div className="w-full max-w-7xl min-h-[85vh] grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
        {/* Left Column: Brand showcase / Value proposition */}
        <div className="hidden lg:flex lg:col-span-6 xl:col-span-7 flex-col justify-between py-6 pr-6 space-y-10">
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-peach-500/15 border border-peach-500/30 text-peach-300 text-sm font-semibold tracking-wide backdrop-blur-md">
              <Sparkles size={16} className="text-peach-400" />
              <span>Autonomous Global Financial Ledger</span>
            </div>

            <h1 className="text-6xl xl:text-7xl font-extrabold tracking-tight leading-[1.08] text-white">
              Next-Gen <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-peach-400 via-peach-500 to-peach-300">
                AI Banking
              </span>{" "}
              Platform<span className="text-peach-500">.</span>
            </h1>

            <p className="text-lg xl:text-xl text-lavender max-w-xl font-normal leading-relaxed">
              Experience real-time double-entry BDT accounting, biometric Face ID authorization,
              and low-latency ElevenLabs conversational voice assistants.
            </p>
          </div>

          {/* Feature Badges */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg pt-4">
            <div className="glass rounded-2xl p-4 flex items-start gap-3.5 border border-white/10">
              <div className="w-10 h-10 rounded-xl bg-peach-500/20 text-peach-400 flex items-center justify-center shrink-0">
                <ShieldCheck size={22} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-cream">Biometric Face ID</h3>
                <p className="text-xs text-lavender mt-0.5">Real-time browser-verified facial recognition.</p>
              </div>
            </div>

            <div className="glass rounded-2xl p-4 flex items-start gap-3.5 border border-white/10">
              <div className="w-10 h-10 rounded-xl bg-peach-500/20 text-peach-400 flex items-center justify-center shrink-0">
                <Zap size={22} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-cream">ElevenLabs Voice</h3>
                <p className="text-xs text-lavender mt-0.5">Instant TTS voice synthesis and STT commands.</p>
              </div>
            </div>
          </div>

          {/* System status pill */}
          <div className="flex items-center gap-2.5 text-xs text-lavender font-mono">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse" />
            <span>Node Core Online • Local Server 127.0.0.1:8000</span>
          </div>
        </div>

        {/* Right Column: Full-height expansive Login Card */}
        <div className="lg:col-span-6 xl:col-span-5 w-full flex justify-center">
          <div className="w-full max-w-xl glass-strong rounded-3xl p-8 sm:p-10 md:p-12 border border-white/15 shadow-2xl backdrop-blur-2xl">
            {/* Header */}
            <div className="mb-8">
              <div className="lg:hidden inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-peach-500/15 border border-peach-500/30 text-peach-300 text-xs font-semibold mb-3">
                <Sparkles size={13} className="text-peach-400" />
                <span>AI-First BDT Ledger</span>
              </div>

              <h2 className="text-4xl sm:text-5xl font-black text-white tracking-tight">
                Sign In<span className="text-peach-500">.</span>
              </h2>
              <p className="text-base sm:text-lg text-lavender mt-2">
                Enter your credentials to manage your balance, bills, and transfers.
              </p>
            </div>

            {error && (
              <div className="mb-6 p-4 rounded-2xl bg-red-500/20 border border-red-500/40 text-red-200 text-sm flex items-center gap-3 animate-in fade-in">
                <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" />
                <span className="flex-1 font-medium">{error}</span>
              </div>
            )}

            {/* Login Form */}
            <form onSubmit={handleFormLogin} className="space-y-6">
              {/* Quick autofill suggestion chips */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs text-secondary">
                <span className="shrink-0 text-peach-400 font-semibold flex items-center gap-1 text-sm">
                  <Zap size={14} /> Fill:
                </span>
                <button
                  type="button"
                  onClick={() => autofill("bikash")}
                  className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-peach-500/20 border border-white/10 hover:border-peach-500/40 text-cream text-xs font-medium transition-all shrink-0"
                >
                  bikash (Boss)
                </button>
                <button
                  type="button"
                  onClick={() => autofill("rishad")}
                  className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-peach-500/20 border border-white/10 hover:border-peach-500/40 text-cream text-xs font-medium transition-all shrink-0"
                >
                  rishad
                </button>
                <button
                  type="button"
                  onClick={() => autofill("arman")}
                  className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-peach-500/20 border border-white/10 hover:border-peach-500/40 text-cream text-xs font-medium transition-all shrink-0"
                >
                  arman
                </button>
              </div>

              {/* Email / Username */}
              <div className="space-y-2">
                <label className="text-sm font-semibold text-cream block tracking-wide">
                  Email or Username
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-lavender">
                    <Mail size={20} />
                  </div>
                  <input
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="bikash@wallet.com or bikash"
                    required
                    disabled={submitting}
                    className="w-full bg-white/5 border border-white/15 rounded-2xl pl-12 pr-4 py-3.5 text-base sm:text-lg text-cream placeholder:text-secondary focus:outline-none focus:border-peach-500 focus:ring-2 focus:ring-peach-500/30 transition-all shadow-inner"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-semibold text-cream block tracking-wide">
                    Password
                  </label>
                  <button
                    type="button"
                    onClick={() => setError("Demo password: enter any text or 'wallet2026'")}
                    className="text-xs sm:text-sm text-peach-400 hover:text-peach-300 transition-colors font-medium"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-lavender">
                    <Lock size={20} />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    disabled={submitting}
                    className="w-full bg-white/5 border border-white/15 rounded-2xl pl-12 pr-12 py-3.5 text-base sm:text-lg text-cream placeholder:text-secondary focus:outline-none focus:border-peach-500 focus:ring-2 focus:ring-peach-500/30 transition-all font-mono shadow-inner"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-lavender hover:text-cream transition-colors"
                    title={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>

              {/* Options Row */}
              <div className="flex items-center justify-between text-sm pt-1">
                <label className="flex items-center gap-2.5 cursor-pointer text-lavender hover:text-cream select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-white/5 text-peach-500 focus:ring-0 focus:ring-offset-0"
                  />
                  <span className="font-medium">Remember this device</span>
                </label>
                <span className="text-xs text-lavender flex items-center gap-1.5 font-medium">
                  <ShieldCheck size={15} className="text-peach-400" /> Face ID ready
                </span>
              </div>

              {/* Submit button */}
              <button
                type="submit"
                disabled={submitting || !email.trim()}
                className="w-full btn-peach rounded-2xl py-4 text-base sm:text-lg font-bold flex items-center justify-center gap-3 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-xl shadow-peach-500/25 active:scale-[0.99]"
              >
                {submitting ? (
                  <>
                    <span className="w-5 h-5 border-2 border-plum-950 border-t-transparent rounded-full animate-spin" />
                    <span>Authenticating…</span>
                  </>
                ) : (
                  <>
                    <span>Sign In to Account</span>
                    <ArrowRight size={20} />
                  </>
                )}
              </button>

              {/* Divider */}
              <div className="relative my-6 flex items-center justify-center">
                <div className="border-t border-white/10 w-full" />
                <span className="bg-plum-950/80 px-4 text-xs font-semibold text-secondary uppercase tracking-wider shrink-0">
                  or continue with
                </span>
                <div className="border-t border-white/10 w-full" />
              </div>

              {/* Google OAuth Button */}
              <button
                type="button"
                onClick={handleGoogleLogin}
                disabled={submitting}
                className="w-full bg-white/5 hover:bg-white/10 border border-white/15 rounded-2xl py-3.5 px-4 text-sm sm:text-base font-semibold flex items-center justify-center gap-3 transition-all hover:border-white/25 active:scale-[0.99]"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <span>Continue with Google</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </main>
  );
}
