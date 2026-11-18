"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ShieldCheck, ShieldAlert, Sparkles } from "lucide-react";
import { User, api, maskPhone } from "@/lib/api";

export function BalanceCard({
  userId,
  displayName,
  phone,
  user,
}: {
  userId: number;
  displayName: string;
  phone: string;
  user?: User | null;
}) {
  const [balance, setBalance] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.getBalance(userId).then(
      (r) => alive && setBalance(r.balance_bdt),
      () => alive && setBalance(null)
    );
    return () => {
      alive = false;
    };
  }, [userId]);

  const tier = user?.effective_tier || user?.account_tier || "personal";
  const isKyc = user?.kyc_status === "verified";

  return (
    <div className="glass rounded-2xl p-6 flex flex-col gap-2 relative overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-secondary text-sm font-bold uppercase tracking-wider">
            Balance
          </span>
          <span className="px-2.5 py-0.5 rounded-full text-xs uppercase font-bold bg-peach-500/15 text-peach-300 border border-peach-500/25">
            {tier} tier
          </span>
          {isKyc ? (
            <span
              title="KYC Verified"
              className="flex items-center gap-1 text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20"
            >
              <ShieldCheck size={12} /> Verified
            </span>
          ) : (
            <span
              title="KYC Unverified"
              className="flex items-center gap-1 text-xs font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20"
            >
              <ShieldAlert size={12} /> Unverified
            </span>
          )}
        </div>
        <div className="text-sm text-lavender font-mono font-medium">{maskPhone(phone)}</div>
      </div>
      <div className="text-4xl sm:text-5xl font-extrabold text-cream tracking-tight my-1">
        ৳
        <span className="text-peach-500">
          {balance === null ? "—" : Number(balance).toLocaleString("en-IN")}
        </span>
      </div>
      <div className="flex items-center justify-between text-base text-lavender pt-1">
        <div className="font-semibold text-cream">
          @{displayName.toLowerCase()}
          {user?.user_type && (
            <span className="ml-2 text-xs text-secondary font-mono capitalize">({user.user_type})</span>
          )}
        </div>
        <Link
          href="/profile"
          className="text-sm text-peach-400 hover:text-peach-300 flex items-center gap-1.5 font-semibold transition"
        >
          <Sparkles size={13} />
          <span>View Limits</span>
        </Link>
      </div>
    </div>
  );
}