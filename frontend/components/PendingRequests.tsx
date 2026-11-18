"use client";

import { PendingRequest, maskPhone } from "@/lib/api";

export function PendingRequests({
  items,
  onPay,
  onDecline,
  pendingId,
}: {
  items: PendingRequest[];
  onPay: (id: number) => void;
  onDecline: (id: number) => void;
  pendingId?: number;
}) {
  if (!items.length) {
    return (
      <div className="text-center text-lavender py-6 text-sm">
        No pending requests.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((r) => {
        const isPending = pendingId === r.id;
        return (
          <li
            key={r.id}
            className="flex items-center justify-between gap-3 p-3 rounded-lg bg-white/5 border border-white/10"
          >
            <div className="min-w-0 flex-1">
              <div className="text-cream text-base font-semibold">
                <span className="text-peach-500 font-bold">{r.asker_handle}</span> asks
                you for ৳{Number(r.amount_bdt).toLocaleString("en-IN")}
              </div>
              <div className="text-xs text-lavender font-mono font-medium">{maskPhone(r.asker_phone)}</div>
              {r.note ? (
                <div className="text-xs text-secondary mt-0.5 italic">
                  &ldquo;{r.note}&rdquo;
                </div>
              ) : null}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={() => onPay(r.id)}
                disabled={isPending}
                className="btn-peach rounded-lg px-4 py-2 text-sm font-bold disabled:opacity-40"
              >
                Pay
              </button>
              <button
                type="button"
                onClick={() => onDecline(r.id)}
                disabled={isPending}
                className="btn-ghost rounded-lg px-3.5 py-2 text-sm font-bold disabled:opacity-40"
              >
                ✕
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}