"use client";

import { FormEvent, useState } from "react";

export function SendForm({
  recipients,
  onSubmit,
  disabled,
  pending,
}: {
  recipients: string[];
  onSubmit: (args: { recipient: string; amount: string; note: string }) => void;
  disabled?: boolean;
  pending?: boolean;
}) {
  const [recipient, setRecipient] = useState(recipients[0] ?? "");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  function handle(e: FormEvent) {
    e.preventDefault();
    if (!recipient || !amount) return;
    onSubmit({ recipient, amount, note });
    setAmount("");
  }

  return (
    <form onSubmit={handle} className="flex flex-col gap-3.5">
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-secondary uppercase tracking-wider font-bold">
          Send to
        </label>
        <select
          value={recipient}
          onChange={(e) => setRecipient(e.target.value)}
          disabled={disabled || pending}
          className="bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-base text-cream focus:outline-none focus:border-peach-500/50 transition font-medium"
        >
          {recipients.map((r) => (
            <option key={r} value={r} className="bg-plum-900">
              {r}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-secondary uppercase tracking-wider font-bold">
          Amount (৳)
        </label>
        <input
          type="number"
          inputMode="numeric"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0"
          min="1"
          disabled={disabled || pending}
          className="bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-cream text-xl font-bold focus:outline-none focus:border-peach-500/50 transition"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-secondary uppercase tracking-wider font-bold">
          Note (optional)
        </label>
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="chai, bill, etc."
          maxLength={140}
          disabled={disabled || pending}
          className="bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-base text-cream focus:outline-none focus:border-peach-500/50 transition"
        />
      </div>
      <button
        type="submit"
        disabled={disabled || pending || !recipient || !amount}
        className="btn-peach rounded-xl px-4 py-3 text-base font-bold mt-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {pending ? "Working…" : "Send"}
      </button>
    </form>
  );
}