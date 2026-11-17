"use client";

import { useEffect, useState } from "react";
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
          <div className="text-xs text-lavender font-medium">
            Verifying Admin Authorization…
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Admin Navigation Header */}
      <header className="glass-strong border-b border-white/10 sticky top-0 z-40 px-4 sm:px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          {/* Logo & Product Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-peach-500/15 border border-peach-500/30 flex items-center justify-center text-peach-400 shadow-glow-peach">
              <ShieldCheck size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-cream tracking-tight text-base sm:text-lg">
                  Wallet <span className="text-peach-400 font-normal">Fraud Intelligence</span>
                </span>
                <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-[10px] font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Live Engine
                </span>
              </div>
              <p className="text-[11px] text-lavender hidden sm:block">
                Dedicated FinTech Risk & Anomaly Monitoring Platform
              </p>
            </div>
          </div>

          {/* Admin Profile & Actions */}
          <div className="flex items-center gap-2.5">
            {/* Admin identity badge */}
            <div className="hidden md:flex flex-col items-end mr-1">
              <div className="text-xs font-semibold text-cream">
                {admin?.display_name || "talukder"}
              </div>
              <div className="text-[10px] text-peach-300 font-medium capitalize">
                {admin?.role || "Super Admin"} • {admin?.phone}
              </div>
            </div>

            {/* Back to User App */}
            <a
              href="/"
              target="_blank"
              rel="noreferrer"
              className="btn-ghost px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 hover:text-cream transition"
              title="Open User Wallet Dashboard in new tab"
            >
              <ExternalLink size={13} />
              <span className="hidden sm:inline">User Wallet</span>
            </a>

            {/* Logout button */}
            <button
              onClick={handleLogout}
              className="btn-ghost px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 text-lavender hover:text-rose-300 hover:border-rose-500/30 transition"
              title="Sign out of Admin Platform"
            >
              <LogOut size={13} />
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
