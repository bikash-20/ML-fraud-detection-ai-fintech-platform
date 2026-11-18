"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BadgeCheck,
  Building2,
  Clock,
  CreditCard,
  FileText,
  Info,
  Send,
  Shield,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  User as UserIcon,
  Users,
} from "lucide-react";
import { UserProfileDetails, api, maskPhone } from "@/lib/api";
import { readActiveUserId } from "@/lib/session";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfileDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  const [requestedTier, setRequestedTier] = useState<"verified" | "business">("verified");
  const [businessName, setBusinessName] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const userId = readActiveUserId();
    if (!userId) {
      router.push("/login");
      return;
    }
    loadProfile(userId);
  }, [router]);

  async function loadProfile(userId: number) {
    setLoading(true);
    try {
      const data = await api.getUserProfile(userId);
      setProfile(data);
    } catch (e: any) {
      console.error("Failed to load user profile:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpgradeSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!profile?.user?.id) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const res = await api.requestUserUpgrade(profile.user.id, {
        requested_tier: requestedTier,
        business_name: requestedTier === "business" ? businessName : undefined,
        reason,
      });
      setMessage(res.message);
      setUpgradeModalOpen(false);
      // Reload profile to show updated requested_upgrade_tier
      await loadProfile(profile.user.id);
    } catch (e: any) {
      setMessage(`Upgrade request failed: ${e.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-plum-950 text-cream flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-2 border-peach-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-secondary text-sm">Loading dynamic profile & tier limits…</p>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-plum-950 text-cream flex items-center justify-center p-4">
        <div className="glass rounded-2xl p-6 text-center max-w-sm">
          <p className="text-secondary mb-4">Unable to load profile data.</p>
          <Link href="/" className="btn-peach px-4 py-2 rounded-xl text-sm font-semibold">
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const { user } = profile;
  const isKycVerified = user.kyc_status === "verified";
  const isTierRestricted = user.account_tier !== user.effective_tier;
  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    : "Verified Member";

  return (
    <div className="min-h-screen bg-plum-950 text-cream py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Top Navigation */}
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs font-semibold text-lavender hover:text-peach-400 transition"
          >
            <ArrowLeft size={16} />
            <span>Back to Dashboard</span>
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-secondary font-medium">
              ID #{user.id} • {user.handle}
            </span>
          </div>
        </div>

        {/* Status Toast */}
        {message && (
          <div className="glass rounded-2xl p-4 border border-peach-500/40 bg-peach-500/10 text-sm text-cream flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Info size={16} className="text-peach-400" />
              <span>{message}</span>
            </div>
            <button
              onClick={() => setMessage(null)}
              className="text-secondary hover:text-cream text-sm ml-4"
            >
              ✕
            </button>
          </div>
        )}

        {/* Hero User Identity Card */}
        <div className="glass rounded-3xl p-6 sm:p-8 border border-white/10 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-80 h-80 bg-peach-500/5 rounded-full blur-3xl -z-10 pointer-events-none" />

          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-peach-600 to-peach-400 flex items-center justify-center font-bold text-2xl text-plum-950 shadow-glow-peach">
                {user.display_name?.charAt(0) || "U"}
              </div>
              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-cream">
                    {user.display_name}
                  </h1>
                  {isKycVerified ? (
                    <span
                      title="KYC Verified"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-0.5 rounded-full"
                    >
                      <BadgeCheck size={14} /> KYC Verified
                    </span>
                  ) : (
                    <span
                      title="KYC Unverified"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-amber-400 bg-amber-500/15 border border-amber-500/30 px-2.5 py-0.5 rounded-full"
                    >
                      <ShieldAlert size={14} /> KYC Unverified
                    </span>
                  )}
                </div>
                {user.business_name && (
                  <div className="text-xs text-peach-300 font-semibold flex items-center gap-1 mt-0.5">
                    <Building2 size={14} /> {user.business_name}
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-3 text-xs text-lavender mt-1 font-mono">
                  <span>@{user.handle}</span>
                  <span>•</span>
                  <span>{user.masked_phone || maskPhone(user.phone)}</span>
                  <span>•</span>
                  <span>Member since {memberSince}</span>
                </div>
              </div>
            </div>

            {/* Current Balance */}
            <div className="text-left sm:text-right w-full sm:w-auto pt-4 sm:pt-0 border-t sm:border-t-0 border-white/5">
              <div className="text-xs uppercase tracking-wider text-secondary font-bold">
                Current Balance
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-peach-400 font-mono">
                ৳{Number(profile.current_balance_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <div className="text-xs text-lavender mt-1 font-medium">
                Effective Tier: <span className="font-bold uppercase text-cream">{user.effective_tier}</span>
              </div>
            </div>
          </div>

          {/* Tier Badges & Upgrade Action */}
          <div className="mt-6 pt-6 border-t border-white/5 flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-secondary font-medium mr-1">Role & Classification:</span>
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-white/5 text-cream border border-white/10 uppercase tracking-wide">
                {user.user_type}
              </span>
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-peach-500/20 text-peach-300 border border-peach-500/30 uppercase tracking-wide">
                {user.account_tier} tier
              </span>
              {user.requested_upgrade_tier && (
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  Upgrade to {user.requested_upgrade_tier.toUpperCase()} pending review
                </span>
              )}
            </div>

            <button
              onClick={() => setUpgradeModalOpen(true)}
              className="btn-peach px-4 py-2 rounded-xl text-xs font-semibold shadow-glow-peach flex items-center gap-1.5"
            >
              <Sparkles size={14} />
              <span>Request Verification / Upgrade</span>
            </button>
          </div>

          {/* Security Rule Alert if restricted */}
          {isTierRestricted && (
            <div className="mt-4 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-2.5 text-xs text-amber-200">
              <ShieldAlert size={16} className="text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Security Rule Active:</span> You requested{" "}
                <span className="uppercase font-bold text-cream">{user.account_tier} tier</span>, but
                because your KYC status is <span className="font-bold">unverified</span>, your account
                is temporarily restricted to{" "}
                <span className="uppercase font-bold text-cream">Personal Tier</span> limits. Full
                limits will activate upon administrator verification.
              </div>
            </div>
          )}
        </div>

        {/* Limits & Today's Usage Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Daily Usage Card */}
          <div className="glass rounded-2xl p-6 border border-white/5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-peach-500/15 text-peach-400">
                  <CreditCard size={18} />
                </div>
                <div>
                  <h2 className="text-base font-bold text-cream">Daily Transfer Limits</h2>
                  <p className="text-xs text-secondary mt-0.5 font-medium">
                    Cumulative 24h outbound spend vs Bangladesh Bank regulatory limits
                  </p>
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2 pt-2">
              <div className="flex justify-between text-xs font-mono font-medium">
                <span className="text-secondary">Today&apos;s Spend:</span>
                <span className="font-bold text-cream">
                  ৳{Number(profile.daily_spent_today_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="w-full bg-white/10 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    profile.daily_usage_pct > 80
                      ? "bg-rose-500"
                      : profile.daily_usage_pct > 50
                      ? "bg-amber-400"
                      : "bg-peach-500"
                  }`}
                  style={{ width: `${Math.min(100, profile.daily_usage_pct)}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-lavender font-mono font-medium">
                <span>{profile.daily_usage_pct}% used today</span>
                <span>
                  Remaining: ৳
                  {Number(profile.daily_remaining_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>

            <div className="pt-3 border-t border-white/5 grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-white/5">
                <div className="text-xs uppercase text-secondary font-bold">Single Txn Cap</div>
                <div className="font-extrabold text-base text-peach-300 font-mono mt-1">
                  ৳{Number(user.effective_single_limit || 50000).toLocaleString("en-IN")}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white/5">
                <div className="text-xs uppercase text-secondary font-bold">Daily Limit Cap</div>
                <div className="font-extrabold text-base text-peach-300 font-mono mt-1">
                  ৳{Number(user.effective_daily_limit || 100000).toLocaleString("en-IN")}
                </div>
              </div>
            </div>
          </div>

          {/* Spending Baseline & Fraud Intelligence */}
          <div className="glass rounded-2xl p-6 border border-white/5 space-y-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-emerald-500/15 text-emerald-400">
                <TrendingUp size={20} />
              </div>
              <div>
                <h2 className="text-base font-bold text-cream">30-Day Spending Baseline</h2>
                <p className="text-xs text-secondary mt-0.5 font-medium">
                  Median spend profile used by the Fraud Intelligence ML Engine
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-white/5 space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-secondary font-medium">Historical 30-Day Median:</span>
                <span className="text-2xl font-extrabold font-mono text-emerald-400">
                  ৳{Number(profile.baseline_median_30d).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
              </div>
              <p className="text-xs text-lavender leading-relaxed font-medium">
                Calculated causally from completed outbound transfers. Top-ups and cash_in credits
                are excluded to prevent baseline distortion. Transfers significantly deviating from
                this baseline trigger step-up biometric verification.
              </p>
            </div>

            <div className="pt-2 text-xs text-secondary flex items-center gap-1.5 font-medium">
              <Shield size={14} className="text-peach-400" />
              <span>Governed by Configurable Assumptions aligned with Bangladesh Bank Circulars.</span>
            </div>
          </div>
        </div>

        {/* Frequent Counterparties */}
        <div className="glass rounded-2xl p-6 border border-white/5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-peach-500/15 text-peach-400">
                <Users size={20} />
              </div>
              <div>
                <h2 className="text-base font-bold text-cream">Frequent Counterparties</h2>
                <p className="text-xs text-secondary mt-0.5 font-medium">
                  Established transfer relationships for fast & trusted verification
                </p>
              </div>
            </div>
          </div>

          {profile.frequent_recipients && profile.frequent_recipients.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              {profile.frequent_recipients.map((rec) => (
                <div
                  key={rec.user_id}
                  className="p-3.5 rounded-xl bg-white/5 border border-white/5 flex items-center justify-between hover:border-peach-500/30 transition"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-full bg-peach-500/20 text-peach-300 flex items-center justify-center font-bold text-xs">
                      {rec.display_name.charAt(0)}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-cream truncate max-w-[100px]">
                        {rec.display_name}
                      </div>
                      <div className="text-xs text-lavender font-mono">@{rec.handle}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs px-2.5 py-0.5 rounded-full bg-white/10 text-secondary font-mono font-semibold">
                      {rec.count} txns
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-sm text-secondary bg-white/5 rounded-xl font-medium">
              No frequent counterparty relationships recorded in the last 30 days yet.
            </div>
          )}
        </div>
      </div>

      {/* Request Upgrade Modal */}
      {upgradeModalOpen && (
        <div className="fixed inset-0 z-50 bg-plum-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass rounded-3xl p-6 sm:p-8 max-w-md w-full border border-white/10 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-peach-400">
                <Sparkles size={20} />
                <h3 className="text-lg font-bold text-cream">Request Tier Upgrade</h3>
              </div>
              <button
                onClick={() => setUpgradeModalOpen(false)}
                className="text-secondary hover:text-cream text-lg"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-lavender">
              Security Notice: Submitting this form requests an upgrade. In compliance with
              regulatory policy, higher limits activate only after administrator review.
            </p>

            <form onSubmit={handleUpgradeSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-wider text-secondary mb-1">
                  Target Account Tier
                </label>
                <select
                  value={requestedTier}
                  onChange={(e) => setRequestedTier(e.target.value as any)}
                  className="field-select w-full text-xs"
                >
                  <option value="verified">Verified Tier (৳100k single / ৳250k daily)</option>
                  <option value="business">Business Enterprise (৳1M single / ৳5M daily)</option>
                </select>
              </div>

              {requestedTier === "business" && (
                <div>
                  <label className="block text-xs uppercase tracking-wider text-secondary mb-1">
                    Registered Business / Trading Name
                  </label>
                  <input
                    type="text"
                    required
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                    placeholder="e.g. Acme Trading & Co. Ltd"
                    className="field-input w-full text-xs"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs uppercase tracking-wider text-secondary mb-1">
                  Reason / Document Reference (Optional)
                </label>
                <textarea
                  rows={2}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Trade license, NID verification, or expanding business volume"
                  className="field-input w-full text-xs resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setUpgradeModalOpen(false)}
                  className="btn-ghost px-4 py-2 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-peach px-5 py-2 rounded-xl text-xs font-semibold shadow-glow-peach disabled:opacity-50"
                >
                  {submitting ? "Submitting…" : "Submit Upgrade Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
