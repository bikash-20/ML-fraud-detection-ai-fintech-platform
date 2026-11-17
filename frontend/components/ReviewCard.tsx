"use client";

import { useEffect, useState } from "react";
import { AgentActResponse, api } from "@/lib/api";
import { readActiveUserId } from "@/lib/session";
import { AlertTriangle, CheckCircle2, ShieldCheck } from "lucide-react";

export function ReviewCard({
  resp,
  onConfirm,
  onDecline,
  pending,
}: {
  resp: AgentActResponse;
  onConfirm: () => void;
  onDecline: () => void;
  pending?: boolean;
}) {
  const card = resp.card;
  const [showAnalysisPref, setShowAnalysisPref] = useState(false);

  useEffect(() => {
    const uid = readActiveUserId();
    if (uid !== null) {
      api
        .getUserSecurityPreference(uid)
        .then((res) => setShowAnalysisPref(res.show_security_analysis))
        .catch(() => {});
    }
  }, []);

  if (!card) return null;

  const isElevatedRisk = card.risk_level === "medium" || card.risk_level === "high";
  const showDetailedTimeline = showAnalysisPref || isElevatedRisk;

  return (
    <div className={`glass-strong rounded-2xl p-5 border-l-4 ${
      card.risk_level === "high"
        ? "border-l-rose-500 shadow-lg shadow-rose-900/30"
        : card.risk_level === "medium"
        ? "border-l-amber-500 shadow-lg shadow-amber-900/30"
        : "border-l-peach-500 shadow-glow-peach"
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs text-secondary uppercase tracking-wider font-semibold">
          Confirm Action
        </div>
        {card.risk_level && (
          <span
            className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase flex items-center gap-1 ${
              card.risk_level === "high"
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                : card.risk_level === "medium"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
            }`}
          >
            {card.risk_level === "high" ? (
              <AlertTriangle size={11} strokeWidth={2.5} />
            ) : (
              <ShieldCheck size={11} strokeWidth={2.5} />
            )}
            {card.risk_level} risk
          </span>
        )}
      </div>

      <div className="text-cream text-base leading-relaxed mb-3">
        {resp.text}
      </div>

      <div className="text-sm text-secondary border-t border-white/10 pt-3 mb-4">
        {card.kind === "split" && card.recipients ? (
          <>
            Splitting <span className="text-peach-500 font-semibold">৳{Number(card.amount_bdt).toLocaleString("en-IN")}</span>{" "}
            equally among {card.recipients.join(", ")}.
          </>
        ) : card.kind === "request" ? (
          <>
            Requesting <span className="text-peach-500 font-semibold">৳{Number(card.amount_bdt).toLocaleString("en-IN")}</span>{" "}
            from <span className="text-peach-500">@{card.recipient_label}</span>
            {card.recipient_phone ? (
              <span className="text-lavender"> · {card.recipient_phone}</span>
            ) : null}
          </>
        ) : card.recipient_label ? (
          <>
            To <span className="text-peach-500 font-semibold">@{card.recipient_label}</span>
            {card.recipient_phone ? (
              <span className="text-lavender"> · {card.recipient_phone}</span>
            ) : null}
            {" — "}৳{Number(card.amount_bdt).toLocaleString("en-IN")}
          </>
        ) : (
          <>
            ৳{Number(card.amount_bdt).toLocaleString("en-IN")} payment
          </>
        )}
        {card.kind !== "request" ? (
          <>
            <br />
            New balance:{" "}
            <span className="text-cream font-medium">
              ৳{Number(card.resulting_balance_bdt).toLocaleString("en-IN")}
            </span>
          </>
        ) : null}
      </div>

      {/* User-facing Security Insights Timeline (Requirement 7) */}
      {showDetailedTimeline && (
        <div className="mb-4 pt-3 border-t border-white/10">
          <div className="text-[11px] font-semibold text-cream mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-secondary">
              <ShieldCheck size={13} className="text-peach-400" />
              Security Verification Timeline
            </span>
            <span className="text-[10px] text-lavender font-mono">
              Score: {card.risk_score?.toFixed(2) ?? "0.00"}
            </span>
          </div>

          <div className="space-y-1.5 bg-black/20 rounded-xl p-3 border border-white/5 text-[11px]">
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 size={13} />
              <span>Transaction request received & validated</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 size={13} />
              <span>Recipient verification & account integrity checked</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 size={13} />
              <span>
                Behavioral velocity & amount pattern evaluated (
                <span className="font-semibold capitalize">{card.risk_level || "low"}</span>)
              </span>
            </div>

            {/* Plain language explanation factors */}
            {card.security_analysis && card.security_analysis.length > 0 && (
              <div className="mt-2 pt-2 border-t border-white/10 pl-5 space-y-1 text-secondary">
                {card.security_analysis.map((r, i) => (
                  <div key={i}>• {r}</div>
                ))}
              </div>
            )}

            {card.requires_biometric && (
              <div className="mt-2 flex items-center gap-1.5 text-peach-300 font-medium">
                <ShieldCheck size={13} className="text-peach-400" />
                <span>Biometric Face ID confirmation will authorize this transaction</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={pending}
          className="btn-peach rounded-lg px-5 py-2 flex-1 disabled:opacity-40"
        >
          {pending ? "Working…" : "Confirm"}
        </button>
        <button
          type="button"
          onClick={onDecline}
          disabled={pending}
          className="btn-ghost rounded-lg px-5 py-2 disabled:opacity-40"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
