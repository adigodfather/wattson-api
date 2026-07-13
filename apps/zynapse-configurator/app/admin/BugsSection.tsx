"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Sectiunea BUG-URI din dashboardul admin (Faza 1.5): lista rapoartelor + acordarea MANUALA de
// Z-coins (anti-abuz: Dan verifica bug-ul intai). Datele vin server-side (service role, doar
// admin); acordarea -> /api/admin/award-bug -> functia DB atomica -> router.refresh().

export type BugRow = {
  id: string;
  email: string;
  content: string;
  status: string;
  z_coins_awarded: number;
  created_at: string;
};

export default function BugsSection({ bugs }: { bugs: BugRow[] }) {
  const router = useRouter();
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function award(bugId: string) {
    const amount = Math.floor(Number(amounts[bugId] || 0));
    if (!(amount > 0) || busy) return;
    setBusy(bugId);
    setErr(null);
    try {
      const res = await fetch("/api/admin/award-bug", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bug_id: bugId, amount }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { setErr(String(data?.error || "Acordarea a eșuat.")); return; }
      router.refresh();   // re-randare server-side: statusul + suma apar imediat
    } catch {
      setErr("Eroare de rețea.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Rapoarte de bug (chat)</h2>
        <p className="text-xs text-slate-500">
          Trimise din widgetul de chat. Verifică bug-ul, apoi acordă Z-coins (intră în sold + ledger, o singură dată per raport).
        </p>
        {err && <p className="mt-2 text-xs font-medium text-red-600">{err}</p>}
      </div>
      {bugs.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-slate-400">Niciun raport încă.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-5 py-3 font-medium">Data</th>
              <th className="px-5 py-3 font-medium">User</th>
              <th className="px-5 py-3 font-medium">Raport</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 text-right font-medium">Z-coins</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {bugs.map(b => (
              <tr key={b.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-5 py-3 text-slate-500">
                  {new Date(b.created_at).toLocaleString("ro-RO", { dateStyle: "short", timeStyle: "short" })}
                </td>
                <td className="px-5 py-3 font-medium text-slate-800">{b.email}</td>
                <td className="max-w-md whitespace-pre-wrap px-5 py-3 text-slate-700">{b.content}</td>
                <td className="whitespace-nowrap px-5 py-3">
                  <span className={
                    b.status === "rezolvat" ? "rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700"
                    : b.status === "respins" ? "rounded bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-600"
                    : "rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700"
                  }>
                    {b.status}
                  </span>
                </td>
                <td className="whitespace-nowrap px-5 py-3 text-right">
                  {b.z_coins_awarded > 0 ? (
                    <span className="font-semibold tabular-nums text-emerald-700">+{b.z_coins_awarded}</span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5">
                      <input
                        type="number" min={1} max={10000} placeholder="Z-coins"
                        value={amounts[b.id] ?? ""}
                        onChange={e => setAmounts(a => ({ ...a, [b.id]: e.target.value }))}
                        className="w-20 rounded border border-slate-300 px-2 py-1 text-right text-xs"
                      />
                      <button type="button" onClick={() => void award(b.id)}
                        disabled={busy === b.id || !(Math.floor(Number(amounts[b.id] || 0)) > 0)}
                        className="rounded bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300">
                        {busy === b.id ? "..." : "Acordă"}
                      </button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
