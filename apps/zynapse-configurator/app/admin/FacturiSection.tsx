"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Secţiunea FACTURI din dashboardul admin. Răspunde la o întrebare la care până acum nu se putea
// răspunde deloc: „a primit clientul X factura?".
// Datele vin server-side (service role, doar admin). Reîncercarea -> /api/admin/invoice-resend ->
// `deliverInvoiceEmail` (claim atomic, PDF de la SmartBill, email de la noi) -> router.refresh().

export type FacturaRow = {
  order_id: string;
  email: string;                 // emailul CONTULUI (cine a plătit)
  series: string | null;
  number: string | null;
  amount_ron: number | null;
  created_at: string;
  email_status: string | null;   // null | sending | sent | failed
  email_to: string | null;       // adresa REALĂ la care a plecat
  email_at: string | null;
  email_error: string | null;
  email_attempts: number | null;
};

const ETICHETA: Record<string, { text: string; cls: string }> = {
  sent:    { text: "trimisă",    cls: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
  sending: { text: "în curs",    cls: "bg-amber-50 text-amber-700 ring-amber-600/20" },
  failed:  { text: "eșuată",     cls: "bg-red-50 text-red-700 ring-red-600/20" },
};
const NETRIMIS = { text: "netrimisă", cls: "bg-slate-100 text-slate-600 ring-slate-500/20" };

export default function FacturiSection({ facturi }: { facturi: FacturaRow[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function retrimite(orderId: string) {
    if (busy) return;
    setBusy(orderId); setErr(null); setOk(null);
    try {
      const res = await fetch("/api/admin/invoice-resend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: orderId }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { setErr(String(data?.error || "Trimiterea a eșuat.")); return; }
      setOk(`Trimisă către ${String(data?.to || "—")}.`);
      router.refresh();
    } catch {
      setErr("Eroare de rețea.");
    } finally {
      setBusy(null);
    }
  }

  const nelivrate = facturi.filter(f => f.email_status !== "sent").length;

  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Facturi emise</h2>
        <p className="text-xs text-slate-500">
          SmartBill emite factura și o transmite în SPV; emailul către client îl trimitem noi, cu PDF-ul atașat.
          {nelivrate > 0 && <strong className="text-red-600"> {nelivrate} nelivrate.</strong>}
        </p>
        {err && <p className="mt-2 text-xs font-medium text-red-600">{err}</p>}
        {ok && <p className="mt-2 text-xs font-medium text-emerald-700">{ok}</p>}
      </div>
      {facturi.length === 0 ? (
        <p className="px-5 py-6 text-sm text-slate-500">Nicio factură emisă încă.</p>
      ) : (
        <>
        {/* ── TELEFON (sub 768px): un rand = o cartela ─────────────────────────────────────────
            Capul cartelei e ce IDENTIFICA factura: numarul si suma. Apoi starea livrarii, care e
            singurul motiv pentru care Dan deschide ecranul asta din mers. Eroarea se vede INTREAGA
            (in tabel era taiata la 60 de caractere, fiindca nu incapea pe un rand). */}
        <div className="divide-y divide-slate-100 md:hidden">
          {facturi.map((f) => {
            const e = f.email_status ? (ETICHETA[f.email_status] || NETRIMIS) : NETRIMIS;
            return (
              <div key={f.order_id} className="px-5 py-4">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="font-semibold text-slate-900">{(f.series || "") + (f.number || "") || "Fără număr"}</p>
                  <p className="shrink-0 tabular-nums text-sm font-medium text-slate-700">
                    {f.amount_ron != null ? `${Number(f.amount_ron).toFixed(2)} lei` : "—"}
                  </p>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${e.cls}`}>{e.text}</span>
                  <span className="text-xs text-slate-400">{String(f.created_at).slice(0, 10)}</span>
                  {(f.email_attempts ?? 0) > 1 && <span className="text-xs text-slate-400">· {f.email_attempts} încercări</span>}
                </div>
                <p className="mt-2 break-all text-xs text-slate-600">
                  {f.email_to || <span className="text-slate-400">netrimisă · cont: {f.email}</span>}
                  {f.email_at && <span className="text-slate-400"> · {String(f.email_at).slice(0, 16).replace("T", " ")}</span>}
                </p>
                {f.email_error && <p className="mt-1 text-xs text-red-600">{f.email_error}</p>}
                {f.email_status !== "sent" && (
                  <button type="button" onClick={() => retrimite(f.order_id)} disabled={busy === f.order_id}
                    className="mt-3 min-h-[44px] w-full rounded-md bg-slate-900 px-3 text-sm font-medium text-white disabled:opacity-50">
                    {busy === f.order_id ? "Se trimite…" : "Trimite factura"}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3">Factură</th>
                <th className="px-5 py-3">Data</th>
                <th className="px-5 py-3 text-right">Sumă</th>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Trimisă către</th>
                <th className="px-5 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {facturi.map((f) => {
                const e = f.email_status ? (ETICHETA[f.email_status] || NETRIMIS) : NETRIMIS;
                return (
                  <tr key={f.order_id} className="border-b border-slate-100 last:border-0">
                    <td className="px-5 py-3 font-medium text-slate-900">
                      {(f.series || "") + (f.number || "") || "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">{String(f.created_at).slice(0, 10)}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-slate-700">
                      {f.amount_ron != null ? `${Number(f.amount_ron).toFixed(2)} lei` : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${e.cls}`}>
                        {e.text}
                      </span>
                      {f.email_error && (
                        <span className="ml-2 text-xs text-red-600" title={f.email_error}>
                          {f.email_error.slice(0, 60)}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {f.email_to || <span className="text-slate-400">— ({f.email})</span>}
                      {f.email_at && <span className="ml-2 text-xs text-slate-400">{String(f.email_at).slice(0, 16).replace("T", " ")}</span>}
                      {(f.email_attempts ?? 0) > 1 && <span className="ml-2 text-xs text-slate-400">· {f.email_attempts} încercări</span>}
                    </td>
                    <td className="px-5 py-3 text-right">
                      {f.email_status !== "sent" && (
                        <button
                          type="button"
                          onClick={() => retrimite(f.order_id)}
                          disabled={busy === f.order_id}
                          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                        >
                          {busy === f.order_id ? "Se trimite…" : "Trimite"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        </>
      )}
    </section>
  );
}
