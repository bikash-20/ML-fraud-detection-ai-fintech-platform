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
  KeyRound,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  Users,
  Zap,
} from "lucide-react";

// Deterministic pastel-from-hash so each tile gets a consistent accent ring
function accentFromHandle(h: string): string {
  let n = 0;
  for (let i = 0; i < h.length; i++) n = (n * 31 + h.charCodeAt(i)) | 0;
  const palette = ["#f0a585", "#c89bd9", "#8db9d9", "#a8c89b", "#e8b86a", "#d98db3"];
  return palette[Math.abs(n) % palette.length];
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);

  // Form credentials state
  const [email, setEmail] = useState("bikash@wallet.com");
  const [password, setPassword] = useState("wallet2026");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Layout mode: "form" (standard credentials) or "demo" (quick picker)
  const [activeTab, setActiveTab] = useState<"credentials" | "demo">("credentials");
  const [showDemoDrawer, setShowDemoDrawer] = useState(false);

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

  function pickUser(u: User) {
    setLoadingId(u.id);
    writeActiveUserId(u.id);
    setTimeout(() => router.push("/"), 180);
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
      setLoadingId(primary.id);
      writeActiveUserId(primary.id);
      setTimeout(() => router.push("/"), 200);
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden flex flex-col items-center justify-center p-4 md:p-8 bg-plum-950 text-cream selection:bg-peach-500/30">
      {/* Ambient background glow orbs */}
      <div className="absolute top-1/4 -left-32 w-96 h-96 bg-peach-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Main card */}
      <div className="relative w-full max-w-lg glass-strong rounded-3xl p-6 md:p-8 border border-white/10 shadow-2xl backdrop-blur-2xl">
        {/* Brand header */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-peach-500/15 border border-peach-500/30 text-peach-400 text-xs font-medium mb-3">
            <Sparkles size={13} className="text-peach-400" />
            <span>AI-First BDT Ledger</span>
          </div>

          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">
            <span className="text-cream">Wallet</span>
            <span className="text-peach-500">.</span>
          </h1>
          <p className="text-sm text-secondary mt-1 max-w-xs">
            Sign in to access your autonomous balance, voice assistant, and instant transfers.
          </p>
        </div>

        {/* Tab switcher: Credentials vs Quick Switch */}
        <div className="grid grid-cols-2 p-1 bg-white/5 border border-white/10 rounded-xl mb-6 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab("credentials")}
            className={
              "py-2.5 rounded-lg transition-all flex items-center justify-center gap-2 " +
              (activeTab === "credentials"
                ? "bg-peach-500 text-plum-950 shadow-md font-bold"
                : "text-lavender hover:text-cream")
            }
          >
            <KeyRound size={14} />
            <span>Email & Password</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("demo")}
            className={
              "py-2.5 rounded-lg transition-all flex items-center justify-center gap-2 " +
              (activeTab === "demo"
                ? "bg-peach-500 text-plum-950 shadow-md font-bold"
                : "text-lavender hover:text-cream")
            }
          >
            <Users size={14} />
            <span>Quick Trigger ({users.length || 6})</span>
          </button>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-xl bg-red-500/15 border border-red-500/30 text-red-200 text-xs flex items-center gap-2 animate-in fade-in">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0" />
            <span className="flex-1">{error}</span>
          </div>
        )}

        {/* MODE 1: Email & Password Form */}
        {activeTab === "credentials" && (
          <form onSubmit={handleFormLogin} className="space-y-4">
            {/* Quick autofill suggestion chips */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] text-secondary">
              <span className="shrink-0 text-peach-500/80 font-medium flex items-center gap-1">
                <Zap size={11} /> Autofill:
              </span>
              <button
                type="button"
                onClick={() => autofill("bikash")}
                className="px-2 py-0.5 rounded-full bg-white/5 hover:bg-peach-500/20 border border-white/10 hover:border-peach-500/40 text-cream/90 transition-all shrink-0"
              >
                bikash (Boss)
              </button>
              <button
                type="button"
                onClick={() => autofill("rishad")}
                className="px-2 py-0.5 rounded-full bg-white/5 hover:bg-peach-500/20 border border-white/10 hover:border-peach-500/40 text-cream/90 transition-all shrink-0"
              >
                rishad
              </button>
              <button
                type="button"
                onClick={() => autofill("arman")}
                className="px-2 py-0.5 rounded-full bg-white/5 hover:bg-peach-500/20 border border-white/10 hover:border-peach-500/40 text-cream/90 transition-all shrink-0"
              >
                arman
              </button>
            </div>

            {/* Email / Username */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-cream/90 block">
                Email or Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-lavender">
                  <Mail size={16} />
                </div>
                <input
                  type="text"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="bikash@wallet.com or bikash"
                  required
                  disabled={submitting}
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-cream placeholder:text-secondary focus:outline-none focus:border-peach-500 focus:ring-1 focus:ring-peach-500 transition-all"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-cream/90 block">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setError("Demo password: enter any text or 'wallet2026'")}
                  className="text-[11px] text-peach-400 hover:text-peach-300 transition-colors"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-lavender">
                  <Lock size={16} />
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  disabled={submitting}
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-10 py-2.5 text-sm text-cream placeholder:text-secondary focus:outline-none focus:border-peach-500 focus:ring-1 focus:ring-peach-500 transition-all font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-lavender hover:text-cream transition-colors"
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Remember Me */}
            <div className="flex items-center justify-between text-xs pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-lavender hover:text-cream select-none">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="rounded border-white/20 bg-white/5 text-peach-500 focus:ring-0 focus:ring-offset-0"
                />
                <span>Remember this device</span>
              </label>
              <span className="text-[11px] text-secondary flex items-center gap-1">
                <ShieldCheck size={12} className="text-peach-400" /> Face ID ready
              </span>
            </div>

            {/* Submit button */}
            <button
              type="submit"
              disabled={submitting || !email.trim()}
              className="w-full btn-peach rounded-xl py-3 text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition-all mt-2 shadow-lg shadow-peach-500/20"
            >
              {submitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-plum-950 border-t-transparent rounded-full animate-spin" />
                  <span>Signing in…</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            {/* Divider */}
            <div className="relative my-4 flex items-center justify-center">
              <div className="border-t border-white/10 w-full" />
              <span className="bg-plum-950/80 px-3 text-[11px] text-secondary uppercase tracking-wider shrink-0">
                or sign in with
              </span>
              <div className="border-t border-white/10 w-full" />
            </div>

            {/* Google OAuth Button */}
            <button
              type="button"
              onClick={handleGoogleLogin}
              disabled={submitting}
              className="w-full bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl py-2.5 px-4 text-xs font-semibold flex items-center justify-center gap-2.5 transition-all hover:border-white/20"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
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

            {/* Quick Trigger Button to open accounts list */}
            <div className="pt-2 text-center">
              <button
                type="button"
                onClick={() => setActiveTab("demo")}
                className="text-xs text-lavender hover:text-peach-400 transition-colors inline-flex items-center gap-1"
              >
                <span>Or switch to instant 1-click demo accounts</span>
                <span className="text-peach-500 font-bold">→</span>
              </button>
            </div>
          </form>
        )}

        {/* MODE 2: Quick Trigger Demo User Tiles */}
        {activeTab === "demo" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-secondary mb-1">
              <span>Select any demo account to sign in immediately:</span>
              <button
                type="button"
                onClick={() => setActiveTab("credentials")}
                className="text-peach-400 hover:text-peach-300 font-medium"
              >
                ← Back to form
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 max-h-[380px] overflow-y-auto pr-1">
              {users.length === 0 && !error ? (
                <div className="col-span-2 text-center text-lavender py-8 text-sm">
                  Loading accounts…
                </div>
              ) : (
                users.map((u) => {
                  const accent = accentFromHandle(u.handle);
                  const isLoading = loadingId === u.id;
                  const isBoss = u.handle === "bikash";
                  return (
                    <button
                      type="button"
                      key={u.id}
                      onClick={() => pickUser(u)}
                      disabled={loadingId !== null}
                      className="group glass rounded-2xl p-3.5 flex flex-col items-center gap-2 text-center transition-all hover:bg-white/10 hover:border-peach-500/40 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed relative"
                    >
                      {isBoss && (
                        <span className="absolute top-2 right-2 px-1.5 py-0.5 bg-peach-500/20 text-peach-400 text-[10px] font-bold rounded-md uppercase tracking-wider">
                          Boss
                        </span>
                      )}
                      <div
                        className="w-11 h-11 rounded-xl flex items-center justify-center text-sm font-bold text-plum-950 shrink-0 transition-transform group-hover:scale-105"
                        style={{ background: accent }}
                      >
                        {initials(u.display_name)}
                      </div>
                      <div className="min-w-0 w-full">
                        <div className="text-sm font-bold text-cream truncate">
                          {u.display_name}
                        </div>
                        <div className="text-[11px] text-peach-400/90 truncate font-mono">
                          @{u.handle}
                        </div>
                        <div className="text-[10px] text-secondary truncate mt-0.5">
                          {u.phone}
                        </div>
                      </div>
                      <div className="w-full pt-1 border-t border-white/5 flex items-center justify-center text-[11px] text-lavender group-hover:text-peach-400 transition-colors">
                        {isLoading ? (
                          <span className="text-peach-500 font-bold">Signing in…</span>
                        ) : (
                          <span className="flex items-center gap-1">
                            Sign in <ArrowRight size={11} />
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer hint */}
      <div className="mt-6 text-center text-xs text-secondary flex items-center gap-2">
        <CheckCircle2 size={13} className="text-emerald-400" />
        <span>Connected to local ledger backend at 127.0.0.1:8000</span>
      </div>
    </div>
  );
}
