"use client";

import { useEffect, useState } from "react";
import { AgentActResponse, api, maskPhone } from "@/lib/api";
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
      <div className="flex items-center justify-between mb-2.5">
        <div className="text-sm text-secondary uppercase tracking-wider font-bold">
          Confirm Action
        </div>
        {card.risk_level && (
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold uppercase flex items-center gap-1.5 ${
              card.risk_level === "high"
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                : card.risk_level === "medium"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
            }`}
          >
            {card.risk_level === "high" ? (
              <AlertTriangle size={13} strokeWidth={2.5} />
            ) : (
              <ShieldCheck size={13} strokeWidth={2.5} />
            )}
            {card.risk_level} risk
          </span>
        )}
      </div>

      <div className="text-cream text-lg font-medium leading-relaxed mb-3">
        {resp.text}
      </div>

      <div className="text-base text-secondary border-t border-white/10 pt-3 mb-4">
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
              <span className="text-lavender font-mono"> · {maskPhone(card.recipient_phone)}</span>
            ) : null}
          </>
        ) : card.recipient_label ? (
          <>
            {card.note === "Mobile Recharge" ? (
              <>Recharge for </>
            ) : card.note === "Cash Out via Agent" ? (
              <>Cash Out to Agent </>
            ) : (
              <>To </>
            )}
            <span className="text-peach-500 font-semibold">@{card.recipient_label}</span>
            {card.recipient_phone ? (
              <span className="text-lavender font-mono"> · {maskPhone(card.recipient_phone)}</span>
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
            <span className="text-cream font-bold">
              ৳{Number(card.resulting_balance_bdt).toLocaleString("en-IN")}
            </span>
          </>
        ) : null}
      </div>

      {/* User-facing Security Insights Timeline (Requirement 7) */}
      {showDetailedTimeline && (
        <div className="mb-4 pt-3 border-t border-white/10">
          <div className="text-xs font-bold text-cream mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-secondary">
              <ShieldCheck size={14} className="text-peach-400" />
              Security Verification Timeline
            </span>
            <span className="text-xs text-lavender font-mono">
              Score: {card.risk_score?.toFixed(2) ?? "0.00"}
            </span>
          </div>

          <div className="space-y-2 bg-black/20 rounded-xl p-3.5 border border-white/5 text-xs">
            <div className="flex items-center gap-2 text-emerald-400 font-medium">
              <CheckCircle2 size={14} />
              <span>Transaction request received & validated</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-400 font-medium">
              <CheckCircle2 size={14} />
              <span>Recipient verification & account integrity checked</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-400 font-medium">
              <CheckCircle2 size={14} />
              <span>
                Behavioral velocity & amount pattern evaluated (
                <span className="font-bold capitalize">{card.risk_level || "low"}</span>)
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
              <div className="mt-2 flex items-center gap-1.5 text-peach-300 font-semibold">
                <ShieldCheck size={14} className="text-peach-400" />
                <span>Biometric Face ID confirmation will authorize this transaction</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onConfirm}
          disabled={pending}
          className="btn-peach rounded-xl px-6 py-3 flex-1 text-base font-bold disabled:opacity-40"
        >
          {pending ? "Working…" : "Confirm"}
        </button>
        <button
          type="button"
          onClick={onDecline}
          disabled={pending}
          className="btn-ghost rounded-xl px-6 py-3 text-base font-semibold disabled:opacity-40"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
