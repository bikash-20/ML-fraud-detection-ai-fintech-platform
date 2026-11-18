"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { clearAdminToken, readAdminToken } from "@/lib/session";
import {
  ShieldCheck,
  LogOut,
  Sparkles,
  ExternalLink,
  Activity,
  Layers,
  Search,
  Users,
  AlertOctagon,
  Cpu,
} from "lucide-react";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [admin, setAdmin] = useState<{
    id: number;
    phone: string;
    display_name: string;
    role: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  // Skip auth check on login page
  const isLoginPage = pathname === "/admin/login";

  useEffect(() => {
    if (isLoginPage) {
      setLoading(false);
      return;
    }

    const token = readAdminToken();
    if (!token) {
      router.replace("/admin/login");
      return;
    }

    api
      .adminMe()
      .then((data) => {
        setAdmin(data);
        setLoading(false);
      })
      .catch(() => {
        clearAdminToken();
        router.replace("/admin/login");
      });
  }, [router, isLoginPage]);

  function handleLogout() {
    api.adminLogout().catch(() => {});
    clearAdminToken();
    router.push("/admin/login");
  }

  if (isLoginPage) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-2 border-peach-500 border-t-transparent rounded-full animate-spin" />
          <div className="text-sm text-lavender font-semibold tracking-wide">
            Verifying Admin Authorization…
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Admin Navigation Header */}
      <header className="glass-strong border-b border-white/10 sticky top-0 z-40 px-4 sm:px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          {/* Logo & Product Brand */}
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-peach-500/15 border border-peach-500/30 flex items-center justify-center text-peach-400 shadow-glow-peach shrink-0">
              <ShieldCheck size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="font-extrabold text-cream tracking-tight text-lg sm:text-xl">
                  Wallet <span className="text-peach-400 font-normal">Fraud Intelligence</span>
                </span>
                <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  Live Engine
                </span>
              </div>
              <p className="text-xs sm:text-sm text-lavender hidden sm:block">
                Dedicated FinTech Risk & Anomaly Monitoring Platform
              </p>
            </div>
          </div>

          {/* Admin Profile & Actions */}
          <div className="flex items-center gap-3">
            {/* Admin identity badge */}
            <div className="hidden md:flex flex-col items-end mr-1">
              <div className="text-sm font-bold text-cream">
                {admin?.display_name || "talukder"}
              </div>
              <div className="text-xs text-peach-300 font-medium capitalize">
                {admin?.role || "Super Admin"} • {admin?.phone}
              </div>
            </div>

            {/* Back to User App */}
            <Link
              href="/"
              className="btn-ghost px-3.5 py-2 rounded-xl text-sm font-medium flex items-center gap-2 hover:text-cream transition"
              title="Open User Wallet Dashboard"
            >
              <ExternalLink size={15} />
              <span className="hidden sm:inline">User Wallet</span>
            </Link>

            {/* Logout button */}
            <button
              onClick={handleLogout}
              className="btn-ghost px-3.5 py-2 rounded-xl text-sm font-medium flex items-center gap-2 text-lavender hover:text-rose-300 hover:border-rose-500/30 transition"
              title="Sign out of Admin Platform"
            >
              <LogOut size={15} />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {children}
      </main>
    </div>
  );
}
