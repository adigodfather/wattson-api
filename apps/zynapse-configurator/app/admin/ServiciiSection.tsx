"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Facturarea de SERVICII in dashboardul admin: clienti · abonamente · facturi emise.
// Raspunde la intrebarea „ce am facturat lui X si a primit?" — clientul, documentul si starea
// trimiterii stau pe acelasi ecran.
// Datele vin server-side (service role); actiunile trec prin rutele /api/admin/*.

export type ClientRow = {
  id: string; denumire: string; cui: string; reg_com: string | null;
  adresa: string; judet: string; localitate: string; email: string;
  persoana_contact: string | null; activ: boolean;
};
export type AbonamentRow = {
  id: string; client_id: string; client: string; descriere: string;
  suma_ron: number; zi_emitere: number; data_start: string; activ: boolean;
  urmatoarea: string;   // calculata server-side
  ultima_rulare: string | null;   // cand a trecut ultima data fluxul zilnic peste el
  ultima_eroare: string | null;   // motivul, daca n-a mers
};
export type FacturaServiciuRow = {
  id: string; client: string; descriere: string; suma_ron: number;
  status: string; serie: string | null; numar: string | null;
  smartbill_error: string | null; created_at: string;
  email_status: string | null; email_to: string | null; email_error: string | null;
  din_abonament: boolean;
};

const ETICHETA: Record<string, { text: string; cls: string }> = {
  emisa:   { text: "emisă",  cls: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
  emitere: { text: "în curs", cls: "bg-amber-50 text-amber-700 ring-amber-600/20" },
  esuata:  { text: "eșuată", cls: "bg-red-50 text-red-700 ring-red-600/20" },
  pending: { text: "neemisă", cls: "bg-slate-100 text-slate-600 ring-slate-500/20" },
};
const MAIL: Record<string, { text: string; cls: string }> = {
  sent:    { text: "trimisă",   cls: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
  sending: { text: "în curs",   cls: "bg-amber-50 text-amber-700 ring-amber-600/20" },
  failed:  { text: "eșuată",    cls: "bg-red-50 text-red-700 ring-red-600/20" },
};
const NETRIMIS = { text: "netrimisă", cls: "bg-slate-100 text-slate-600 ring-slate-500/20" };

// `min-h`/`text-base` doar pe telefon: sub 16px iOS mareste pagina la focus, iar 34px e sub
// pragul de atingere. Pe calculator `md:` le readuce exact la ce erau.
const inp = "w-full min-h-[44px] rounded-md border border-slate-300 px-2.5 py-1.5 text-base md:min-h-0 md:text-sm";
const lbl = "block text-xs font-medium text-slate-600 mb-1";

export default function ServiciiSection({ clienti, abonamente, facturi, serieConfigurata }: {
  clienti: ClientRow[]; abonamente: AbonamentRow[]; facturi: FacturaServiciuRow[];
  serieConfigurata: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cl, setCl] = useState({ denumire: "", cui: "", reg_com: "", adresa: "", judet: "", localitate: "", email: "", persoana_contact: "" });
  const [fa, setFa] = useState({ client_id: "", descriere: "", suma_ron: "" });
  const [ab, setAb] = useState({ client_id: "", descriere: "", suma_ron: "", zi_emitere: "10", data_start: new Date().toISOString().slice(0, 10) });

  const activi = clienti.filter(c => c.activ);

  async function cere(cale: string, metoda: string, corp: unknown, cheie: string, succes: string) {
    if (busy) return;
    setBusy(cheie); setErr(null); setOk(null);
    try {
      const res = await fetch(cale, { method: metoda, headers: { "Content-Type": "application/json" }, body: JSON.stringify(corp) });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) { setErr(String(d?.error || "Acțiunea a eșuat.")); return false; }
      setOk(succes + (d?.serie ? ` (${d.serie}${d.numar}${d.email === "sent" ? ", email trimis" : ", EMAILUL N-A PLECAT"})` : ""));
      router.refresh();
      return true;
    } catch { setErr("Eroare de rețea."); return false; }
    finally { setBusy(null); }
  }

  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Facturare servicii</h2>
        <p className="text-xs text-slate-500">
          Automatizări, softuri, site-uri. Serie separată de cea a creditelor; emiterea și trimiterea se fac într-un singur pas.
        </p>
        {!serieConfigurata && (
          <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-600/20">
            Seria de servicii nu e configurată: setează <code>SMARTBILL_SERIES_SERVICII=ZS</code> în Vercel (seria
            creată în SmartBill). Până atunci emiterea se oprește cu eroare — nu cade pe seria creditelor.
          </p>
        )}
        {err && <p className="mt-2 text-xs font-medium text-red-600">{err}</p>}
        {ok && <p className="mt-2 text-xs font-medium text-emerald-700">{ok}</p>}
      </div>

      {/* ── CLIENTI ─────────────────────────────────────────────────────── */}
      <div className="border-b border-slate-200 px-5 py-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-800">Client nou</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <label><span className={lbl}>Denumire *</span><input className={inp} value={cl.denumire} onChange={e => setCl({ ...cl, denumire: e.target.value })} placeholder="SCHRACK TECHNIK SRL" /></label>
          <label><span className={lbl}>CUI *</span><input className={inp} value={cl.cui} onChange={e => setCl({ ...cl, cui: e.target.value })} placeholder="RO12345678" /></label>
          <label><span className={lbl}>Nr. reg. comerțului</span><input className={inp} value={cl.reg_com} onChange={e => setCl({ ...cl, reg_com: e.target.value })} placeholder="J40/1234/2010" /></label>
          <label><span className={lbl}>Email *</span><input className={inp} value={cl.email} onChange={e => setCl({ ...cl, email: e.target.value })} placeholder="facturi@firma.ro" /></label>
          <label className="sm:col-span-2"><span className={lbl}>Adresă *</span><input className={inp} value={cl.adresa} onChange={e => setCl({ ...cl, adresa: e.target.value })} placeholder="Str. Exemplu nr. 1" /></label>
          <label><span className={lbl}>Județ *</span><input className={inp} value={cl.judet} onChange={e => setCl({ ...cl, judet: e.target.value })} placeholder="Cluj" /></label>
          <label><span className={lbl}>Localitate *</span><input className={inp} value={cl.localitate} onChange={e => setCl({ ...cl, localitate: e.target.value })} placeholder="Cluj-Napoca" /></label>
          <label className="sm:col-span-2"><span className={lbl}>Persoană de contact</span><input className={inp} value={cl.persoana_contact} onChange={e => setCl({ ...cl, persoana_contact: e.target.value })} placeholder="Ion Popescu" /></label>
        </div>
        <p className="mt-2 text-xs text-slate-500">Județul și localitatea sunt cerute de ANAF pentru e-Factură — fără ele factura se emite, dar nu se transmite.</p>
        <button type="button" disabled={busy === "client"}
          onClick={async () => { if (await cere("/api/admin/clienti-servicii", "POST", cl, "client", "Client salvat.")) setCl({ denumire: "", cui: "", reg_com: "", adresa: "", judet: "", localitate: "", email: "", persoana_contact: "" }); }}
          className="mt-3 min-h-[44px] w-full rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 md:min-h-0 md:w-auto">
          {busy === "client" ? "Se salvează…" : "Salvează clientul"}
        </button>

        {/* ── TELEFON: un client = o cartela. Capul e denumirea (dupa ea il cauti) + starea; sub ea
            CUI-ul si localitatea, apoi emailul. Butonul de dezactivare e o tinta de 44px, nu un
            link subliniat de 11px intr-o celula. */}
        {clienti.length > 0 && (
          <div className="mt-4 divide-y divide-slate-100 border-t border-slate-200 md:hidden">
            {clienti.map(c => (
              <div key={c.id} className="py-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="min-w-0 text-sm font-medium text-slate-900">{c.denumire}</p>
                  {!c.activ && <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">dezactivat</span>}
                </div>
                <p className="mt-1 text-xs text-slate-600">{c.cui} · {c.localitate}, {c.judet}</p>
                <p className="break-all text-xs text-slate-500">{c.email}</p>
                <button type="button" disabled={busy === c.id}
                  onClick={() => cere("/api/admin/clienti-servicii", "PATCH", { id: c.id, activ: !c.activ }, c.id, c.activ ? "Client dezactivat." : "Client reactivat.")}
                  className="mt-2 min-h-[44px] w-full rounded-md border border-slate-300 px-3 text-sm font-medium text-slate-700 disabled:opacity-50">
                  {c.activ ? "Dezactivează clientul" : "Reactivează clientul"}
                </button>
              </div>
            ))}
          </div>
        )}
        {clienti.length > 0 && (
          <div className="mt-4 hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="py-2">Client</th><th className="py-2">CUI</th><th className="py-2">Adresă</th><th className="py-2">Email</th><th /></tr>
            </thead>
            <tbody>
              {clienti.map(c => (
                <tr key={c.id} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 font-medium text-slate-900">{c.denumire}{!c.activ && <span className="ml-2 text-xs text-slate-400">(dezactivat)</span>}</td>
                  <td className="py-2 text-slate-600">{c.cui}</td>
                  <td className="py-2 text-slate-600">{c.localitate}, {c.judet}</td>
                  <td className="py-2 text-slate-600">{c.email}</td>
                  <td className="py-2 text-right">
                    <button type="button" disabled={busy === c.id}
                      onClick={() => cere("/api/admin/clienti-servicii", "PATCH", { id: c.id, activ: !c.activ }, c.id, c.activ ? "Client dezactivat." : "Client reactivat.")}
                      className="text-xs text-slate-500 underline">{c.activ ? "dezactivează" : "reactivează"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* ── FACTURA SINGULARA ───────────────────────────────────────────── */}
      <div className="border-b border-slate-200 px-5 py-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-800">Factură nouă</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <label><span className={lbl}>Client *</span>
            <select className={inp} value={fa.client_id} onChange={e => setFa({ ...fa, client_id: e.target.value })}>
              <option value="">Alege clientul…</option>
              {activi.map(c => <option key={c.id} value={c.id}>{c.denumire}</option>)}
            </select>
          </label>
          <label className="sm:col-span-2"><span className={lbl}>Descrierea serviciului *</span><input className={inp} value={fa.descriere} onChange={e => setFa({ ...fa, descriere: e.target.value })} placeholder="Automatizare citire scheme monofilare" /></label>
          <label><span className={lbl}>Sumă (lei) *</span><input className={inp} inputMode="decimal" value={fa.suma_ron} onChange={e => setFa({ ...fa, suma_ron: e.target.value })} placeholder="1500" /></label>
        </div>
        <button type="button" disabled={busy === "factura"}
          onClick={async () => { if (await cere("/api/admin/facturi-servicii", "POST", { ...fa, suma_ron: Number(fa.suma_ron) }, "factura", "Factură emisă.")) setFa({ client_id: "", descriere: "", suma_ron: "" }); }}
          className="mt-3 min-h-[44px] w-full rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 md:min-h-0 md:w-auto">
          {busy === "factura" ? "Se emite și se trimite…" : "Emite și trimite"}
        </button>
      </div>

      {/* ── ABONAMENTE ──────────────────────────────────────────────────── */}
      <div className="border-b border-slate-200 px-5 py-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-800">Abonament recurent</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
          <label><span className={lbl}>Client *</span>
            <select className={inp} value={ab.client_id} onChange={e => setAb({ ...ab, client_id: e.target.value })}>
              <option value="">Alege clientul…</option>
              {activi.map(c => <option key={c.id} value={c.id}>{c.denumire}</option>)}
            </select>
          </label>
          <label className="sm:col-span-2"><span className={lbl}>Descriere *</span><input className={inp} value={ab.descriere} onChange={e => setAb({ ...ab, descriere: e.target.value })} placeholder="Mentenanță lunară" /></label>
          <label><span className={lbl}>Sumă/lună (lei) *</span><input className={inp} inputMode="decimal" value={ab.suma_ron} onChange={e => setAb({ ...ab, suma_ron: e.target.value })} placeholder="100" /></label>
          <label><span className={lbl}>Ziua emiterii *</span><input className={inp} inputMode="numeric" value={ab.zi_emitere} onChange={e => setAb({ ...ab, zi_emitere: e.target.value })} /></label>
          <label><span className={lbl}>Data de start *</span><input className={inp} type="date" value={ab.data_start} onChange={e => setAb({ ...ab, data_start: e.target.value })} /></label>
        </div>
        <p className="mt-2 text-xs text-slate-500">Ziua e între 1 și 25, ca scadența să existe în orice lună. Factura se emite și pleacă singură.</p>
        <button type="button" disabled={busy === "abonament"}
          onClick={async () => { if (await cere("/api/admin/abonamente-servicii", "POST", { ...ab, suma_ron: Number(ab.suma_ron), zi_emitere: Number(ab.zi_emitere) }, "abonament", "Abonament creat.")) setAb({ ...ab, client_id: "", descriere: "", suma_ron: "" }); }}
          className="mt-3 min-h-[44px] w-full rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 md:min-h-0 md:w-auto">
          {busy === "abonament" ? "Se salvează…" : "Creează abonamentul"}
        </button>

        {/* ── TELEFON: un abonament = o cartela. Capul e clientul + suma lunara; imediat sub el
            SCADENTA, fiindca asta intrebi („cand iese urmatoarea?"). Eroarea ultimei rulari ramane
            vizibila fara sa atingi nimic — ea e motivul pentru care exista ecranul. */}
        {abonamente.length > 0 && (
          <div className="mt-4 divide-y divide-slate-100 border-t border-slate-200 md:hidden">
            {abonamente.map(a => (
              <div key={a.id} className="py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="min-w-0 text-sm font-medium text-slate-900">{a.client}</p>
                  <p className="shrink-0 tabular-nums text-sm text-slate-700">{Number(a.suma_ron).toFixed(2)} lei/lună</p>
                </div>
                <p className="mt-0.5 text-xs text-slate-600">{a.descriere}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {a.activ ? <>Următoarea: <span className="font-medium text-slate-700">{a.urmatoarea}</span></> : <span className="text-slate-400">oprit</span>}
                  {a.ultima_rulare && <span className="text-slate-400"> · rulat {a.ultima_rulare}</span>}
                </p>
                {a.ultima_eroare && (
                  <p className="mt-1 text-xs text-red-700">
                    <span className="font-medium">Ultima rulare a eșuat:</span> {a.ultima_eroare}
                  </p>
                )}
                <button type="button" disabled={busy === a.id}
                  onClick={() => cere("/api/admin/abonamente-servicii", "PATCH", { id: a.id, activ: !a.activ }, a.id, a.activ ? "Abonament oprit." : "Abonament repornit.")}
                  className="mt-2 min-h-[44px] w-full rounded-md border border-slate-300 px-3 text-sm font-medium text-slate-700 disabled:opacity-50">
                  {a.activ ? "Oprește abonamentul" : "Repornește abonamentul"}
                </button>
              </div>
            ))}
          </div>
        )}
        {abonamente.length > 0 && (
          <div className="mt-4 hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="py-2">Client</th><th className="py-2">Serviciu</th><th className="py-2 text-right">Sumă/lună</th><th className="py-2">Următoarea</th><th /></tr>
            </thead>
            <tbody>
              {abonamente.flatMap(a => [
                <tr key={a.id} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 font-medium text-slate-900">{a.client}</td>
                  <td className="py-2 text-slate-600">{a.descriere}</td>
                  <td className="py-2 text-right tabular-nums text-slate-700">{Number(a.suma_ron).toFixed(2)} lei</td>
                  <td className="py-2 text-slate-600">
                    {a.activ ? a.urmatoarea : <span className="text-slate-400">oprit</span>}
                    {a.ultima_rulare && <span className="block text-xs text-slate-400">rulat {a.ultima_rulare}</span>}
                  </td>
                  <td className="py-2 text-right">
                    <button type="button" disabled={busy === a.id}
                      onClick={() => cere("/api/admin/abonamente-servicii", "PATCH", { id: a.id, activ: !a.activ }, a.id, a.activ ? "Abonament oprit." : "Abonament repornit.")}
                      className="text-xs text-slate-500 underline">{a.activ ? "oprește" : "repornește"}</button>
                  </td>
                </tr>,
                /* Esecul sta LANGA abonamentul lui, cu motivul: intrebarea nu e „ce factura a picat",
                   ci „care abonament nu si-a facut treaba". Rand propriu, ca motivul sa incapa intreg. */
                a.ultima_eroare ? (
                  <tr key={a.id + "-eroare"} className="border-b border-slate-100 last:border-0">
                    <td colSpan={5} className="pb-2 text-xs text-red-700">
                      <span className="font-medium">Ultima rulare a eșuat:</span> {a.ultima_eroare}
                    </td>
                  </tr>
                ) : null,
              ])}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* ── FACTURI EMISE ───────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-800">Facturi de servicii</h3>
        {facturi.length === 0 ? (
          <p className="text-sm text-slate-500">Nicio factură de servicii încă.</p>
        ) : (
          <>
          {/* ── TELEFON: o factura = o cartela. Capul e documentul (ZS0001) si suma; sub el cele
              DOUA stari care nu inseamna acelasi lucru — emisa la SmartBill, si trimisa pe email.
              Erorile se vad intregi (in tabel erau taiate la 40 de caractere). */}
          <div className="divide-y divide-slate-100 border-t border-slate-200 md:hidden">
            {facturi.map(f => {
              const st = ETICHETA[f.status] || ETICHETA.pending;
              const em = f.email_status ? (MAIL[f.email_status] || NETRIMIS) : NETRIMIS;
              return (
                <div key={f.id} className="py-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="min-w-0 text-sm font-semibold text-slate-900">
                      {(f.serie || "") + (f.numar || "") || "Fără număr"}
                      {f.din_abonament && <span className="ml-1.5 text-xs font-normal text-slate-400">abonament</span>}
                    </p>
                    <p className="shrink-0 tabular-nums text-sm text-slate-700">{Number(f.suma_ron).toFixed(2)} lei</p>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-600">{f.client} · {f.descriere}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${st.cls}`}>{st.text}</span>
                    <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${em.cls}`}>email {em.text}</span>
                  </div>
                  {f.email_to && <p className="mt-1 break-all text-xs text-slate-400">{f.email_to}</p>}
                  {f.smartbill_error && <p className="mt-1 text-xs text-red-600">{f.smartbill_error}</p>}
                  {f.email_error && <p className="mt-1 text-xs text-red-600">{f.email_error}</p>}
                  {f.status === "emisa" && f.email_status !== "sent" && (
                    <button type="button" disabled={busy === f.id}
                      onClick={() => cere("/api/admin/facturi-servicii", "PATCH", { id: f.id }, f.id, "Factură trimisă.")}
                      className="mt-2 min-h-[44px] w-full rounded-md bg-slate-900 px-3 text-sm font-medium text-white disabled:opacity-50">
                      {busy === f.id ? "…" : "Trimite factura"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="py-2">Document</th><th className="py-2">Client</th><th className="py-2">Serviciu</th>
                  <th className="py-2 text-right">Sumă</th><th className="py-2">Emitere</th><th className="py-2">Email</th><th /></tr>
            </thead>
            <tbody>
              {facturi.map(f => {
                const st = ETICHETA[f.status] || ETICHETA.pending;
                const em = f.email_status ? (MAIL[f.email_status] || NETRIMIS) : NETRIMIS;
                return (
                  <tr key={f.id} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 font-medium text-slate-900">
                      {(f.serie || "") + (f.numar || "") || "—"}
                      {f.din_abonament && <span className="ml-1 text-xs text-slate-400">abonament</span>}
                    </td>
                    <td className="py-2 text-slate-600">{f.client}</td>
                    <td className="py-2 text-slate-600">{f.descriere}</td>
                    <td className="py-2 text-right tabular-nums text-slate-700">{Number(f.suma_ron).toFixed(2)} lei</td>
                    <td className="py-2">
                      <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${st.cls}`}>{st.text}</span>
                      {f.smartbill_error && <span className="ml-2 text-xs text-red-600" title={f.smartbill_error}>{f.smartbill_error.slice(0, 40)}</span>}
                    </td>
                    <td className="py-2">
                      <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${em.cls}`}>{em.text}</span>
                      {f.email_to && <span className="ml-2 text-xs text-slate-400">{f.email_to}</span>}
                      {f.email_error && <span className="ml-2 text-xs text-red-600" title={f.email_error}>{f.email_error.slice(0, 40)}</span>}
                    </td>
                    <td className="py-2 text-right">
                      {f.status === "emisa" && f.email_status !== "sent" && (
                        <button type="button" disabled={busy === f.id}
                          onClick={() => cere("/api/admin/facturi-servicii", "PATCH", { id: f.id }, f.id, "Factură trimisă.")}
                          className="rounded-md bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50">
                          {busy === f.id ? "…" : "Trimite"}
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
      </div>
    </section>
  );
}
