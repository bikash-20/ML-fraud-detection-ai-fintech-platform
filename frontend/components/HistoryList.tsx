"use client";

import { Txn } from "@/lib/api";

export function HistoryList({ txns }: { txns: Txn[] }) {
  // Only display confirmed, completed transactions in recent history.
  // Any unconfirmed, pending, cancelled, or interrupted transfers are strictly excluded.
  const completedTxns = txns.filter(
    (t) => t.status === "completed" && t.completed_at
  );

  if (completedTxns.length === 0) {
    return (
      <div className="text-center text-lavender py-8 text-sm">
        No completed transactions yet. Send some ৳ to get started.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-1">
      {completedTxns.map((t) => {
        const isIn = t.direction === "in";
        const counterpartyDisplay =
          t.counterparty ??
          (t.kind === "savings"
            ? "Festival Savings"
            : t.kind === "bill"
            ? "Utility Bill"
            : "Wallet Transfer");

        return (
          <li
            key={t.id}
            className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-white/5 transition border-b border-white/5 last:border-b-0"
          >
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div
                className={
                  "w-9 h-9 rounded-full flex items-center justify-center text-base font-bold shrink-0 " +
                  (isIn
                    ? "bg-peach-500/20 text-peach-500"
                    : "bg-white/5 text-cream/70")
                }
              >
                {isIn ? "↓" : "↑"}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-cream text-sm font-medium truncate">
                  {counterpartyDisplay}
                </div>
                <div className="text-xs text-lavender">
                  {t.kind === "split_child" ? "split" : t.kind} · completed
                  {t.note ? ` · ${t.note}` : ""}
                </div>
              </div>
            </div>
            <div
              className={
                "text-base font-semibold tabular-nums shrink-0 " +
                (isIn ? "text-peach-500" : "text-cream/90")
              }
            >
              {isIn ? "+" : "−"}৳
              {Number(t.amount_bdt).toLocaleString("en-IN")}
            </div>
          </li>
        );
      })}
    </ul>
  );
}