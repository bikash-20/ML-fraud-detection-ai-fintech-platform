"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { writeAdminToken } from "@/lib/session";
import { Lock, Phone, ShieldCheck, ArrowRight, ShieldAlert } from "lucide-react";

export default function AdminLoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("01926240062");
  const [password, setPassword] = useState("1234");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await api.adminLogin({ phone, password });
      writeAdminToken(res.token);
      router.push("/admin");
    } catch (err) {
      setError((err as Error).message || "Invalid administrative credentials");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background radial glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-peach-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md">
        {/* Card Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-peach-500/15 border border-peach-500/30 text-peach-400 mb-3 shadow-glow-peach">
            <ShieldCheck size={28} />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-cream tracking-tight">
            Fraud Intelligence & Security
          </h1>
          <p className="text-sm text-lavender mt-1.5">
            Dedicated Administrative Monitoring Platform
          </p>
        </div>

        {/* Login Glass Card */}
        <div className="glass-strong rounded-3xl p-6 sm:p-8 shadow-2xl border border-white/10 relative">
          <div className="flex items-center justify-between pb-4 mb-5 border-b border-white/10">
            <span className="text-sm font-bold uppercase tracking-wider text-secondary">
              Admin Portal Access
            </span>
            <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/20 font-semibold">
              Authorized Personnel
            </span>
          </div>

          {error && (
            <div className="mb-4 p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-200 text-sm flex items-center gap-2">
              <ShieldAlert size={18} className="text-rose-400 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-cream mb-2">
                Admin Phone Number
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-secondary">
                  <Phone size={18} />
                </div>
                <input
                  type="text"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="01926240062"
                  className="w-full pl-11 pr-3.5 py-3 rounded-xl bg-white/5 border border-white/10 text-cream placeholder-white/20 text-base focus:outline-none focus:border-peach-500/60 focus:ring-1 focus:ring-peach-500/60 transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-cream mb-2">
                Admin Security Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-secondary">
                  <Lock size={18} />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••"
                  className="w-full pl-11 pr-3.5 py-3 rounded-xl bg-white/5 border border-white/10 text-cream placeholder-white/20 text-base focus:outline-none focus:border-peach-500/60 focus:ring-1 focus:ring-peach-500/60 transition"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="btn-peach w-full py-3.5 rounded-xl text-base font-bold flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <span>Authenticating…</span>
                ) : (
                  <>
                    <span>Enter Intelligence Center</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Quick preset hint for verified admin talukder */}
          <div className="mt-6 pt-4 border-t border-white/10 text-center">
            <p className="text-xs text-secondary font-medium">
              Logged in as <span className="text-peach-400 font-bold">talukder</span> (Super Admin)
            </p>
            <div className="mt-2 text-xs text-lavender/80">
              Preset phone: <span className="font-mono text-cream font-semibold">01926240062</span> • Pass: <span className="font-mono text-cream font-semibold">1234</span>
            </div>
          </div>
        </div>

        {/* Back to user wallet link */}
        <div className="flex items-center justify-center gap-4 mt-5 text-sm font-medium">
          <Link
            href="/login"
            className="text-lavender hover:text-cream transition underline underline-offset-4"
          >
            ← User Login
          </Link>
          <span className="text-white/20">•</span>
          <Link
            href="/"
            className="text-lavender hover:text-cream transition underline underline-offset-4"
          >
            User Wallet
          </Link>
        </div>
      </div>
    </div>
  );
}
