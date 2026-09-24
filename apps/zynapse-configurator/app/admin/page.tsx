// app/admin/page.tsx — Dashboard ADMIN (vizibilitate business pentru Dan).
// SECURITATE: server component. Verificarea de admin se face pe SERVER (sesiune din cookies +
// profiles.is_admin) INAINTE de orice citire de date. Un non-admin e redirectat -> niciun query de
// date, nicio expunere. Agregatele + top 10 se citesc cu service role (server-only, niciodata in client).
// Emailurile apar DOAR in top 10, randate server-side (NU in URL/query/loguri).
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createServerClient } from "@/lib/supabase";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { isPhasePT } from "@/lib/constants";
import AppHeader from "@/components/AppHeader";
import BugsSection, { type BugRow } from "./BugsSection";
import FacturiSection, { type FacturaRow } from "./FacturiSection";
import ServiciiSection, { type ClientRow, type AbonamentRow, type FacturaServiciuRow } from "./ServiciiSection";
import { seriesFor } from "@/lib/smartbill";

// Urmatoarea scadenta a unui abonament: ziua Z din luna curenta daca n-a trecut, altfel din luna
// urmatoare — dar niciodata inainte de data de start. Z e mereu <= 28, deci ziua exista in orice luna.
function urmatoareaScadenta(zi: number, dataStart: string): string {
  const azi = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  let an = azi.getFullYear(), luna = azi.getMonth();
  if (azi.getDate() > zi) { luna += 1; if (luna > 11) { luna = 0; an += 1; } }
  let iso = `${an}-${p(luna + 1)}-${p(zi)}`;
  if (dataStart && iso < dataStart) {
    const d = new Date(dataStart);
    let a2 = d.getFullYear(), l2 = d.getMonth();
    if (d.getDate() > zi) { l2 += 1; if (l2 > 11) { l2 = 0; a2 += 1; } }
    iso = `${a2}-${p(l2 + 1)}-${p(zi)}`;
  }
  return iso;
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";   // mereu proaspat, niciodata cache static

const fmtInt = (n: number) => new Intl.NumberFormat("ro-RO").format(Math.round(n));
const fmtRon = (n: number) =>
  new Intl.NumberFormat("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + " RON";

type TopRow = { email: string; creditsConfirmed: number; ronConfirmed: number; projects: number };

export default async function AdminPage() {
  // ── POARTA ADMIN (server-side) ──────────────────────────────────────────────
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
  const { data: { user } } = await supa.auth.getUser();
  if (!user) redirect("/login");
  const { data: prof } = await supa
    .from("profiles").select("is_admin").eq("id", user.id).single();
  if (prof?.is_admin !== true) redirect("/home");   // non-admin BLOCAT inainte de orice date

  // ── DATE (service role, server-only; doar adminul a ajuns aici) ──────────────
  const admin = createAdminClient();
  const [profilesRes, paymentsRes, projectsRes, bugsRes, facturiRes, clientiRes, abonamenteRes, facturiServRes] = await Promise.all([
    admin.from("profiles").select("id, email, credits_balance"),
    admin.from("payments").select("user_id, credits, amount_ron, status, credited"),
    admin.from("projects").select("user_id, faza"),
    // Faza 1.5: rapoartele de bug din chat (cele mai noi primele; 100 = suficient pt. V1)
    admin.from("bug_reports").select("id, user_id, content, status, z_coins_awarded, created_at")
      .order("created_at", { ascending: false }).limit(100),
    // Facturile emise + starea livrării pe email. Interogare SEPARATĂ de `payments` de mai sus:
    // aceea agregă sume pe utilizator şi n-are nevoie de câmpurile de factură.
    // NB: şirul de `select` stă pe UN rând, nu concatenat: supabase-js deduce tipul rândului din
    // literalul de şir, iar o concatenare îl face `GenericStringError` şi pică la compilare.
    admin.from("payments")
      .select("order_id, user_id, amount_ron, created_at, invoice_series, invoice_number, invoice_email_status, invoice_email_to, invoice_email_at, invoice_email_error, invoice_email_attempts")
      .eq("invoiced", true).order("created_at", { ascending: false }).limit(200),
    // Facturarea de SERVICII: clienti, abonamente, facturi. Tabele separate de `payments`.
    admin.from("clienti_servicii").select("id, denumire, cui, reg_com, adresa, judet, localitate, email, persoana_contact, activ").order("denumire"),
    admin.from("abonamente_servicii").select("id, client_id, descriere, suma_ron, zi_emitere, data_start, activ, ultima_rulare_at, ultima_eroare, ultima_perioada").order("created_at", { ascending: false }),
    admin.from("facturi_servicii").select("id, client_id, abonament_id, descriere, suma_ron, status, serie, numar, smartbill_error, created_at, invoice_email_status, invoice_email_to, invoice_email_error").order("created_at", { ascending: false }).limit(200),
  ]);

  const profiles = profilesRes.data ?? [];
  const payments = paymentsRes.data ?? [];
  const projects = projectsRes.data ?? [];
  const bugsRaw = bugsRes.data ?? [];
  const facturiRaw = facturiRes.data ?? [];
  const clientiRaw = clientiRes.data ?? [];
  const abonamenteRaw = abonamenteRes.data ?? [];
  const facturiServRaw = facturiServRes.data ?? [];

  // ZONA 1 — agregate globale (zero date personale)
  const totalUsers = profiles.length;
  const creditsRemaining = profiles.reduce((s, p) => s + (p.credits_balance ?? 0), 0);

  const totalProjects = projects.length;
  const projectsPT = projects.filter((p) => isPhasePT(p.faza ?? "")).length;
  const projectsDTAC = totalProjects - projectsPT;
  const projCountByUser = new Map<string, number>();
  for (const p of projects) if (p.user_id) projCountByUser.set(p.user_id, (projCountByUser.get(p.user_id) ?? 0) + 1);

  const credited = payments.filter((p) => p.credited === true);
  const pending = payments.filter((p) => p.status === "pending");
  const creditsSold = credited.reduce((s, p) => s + (p.credits ?? 0), 0);
  const revenue = credited.reduce((s, p) => s + Number(p.amount_ron ?? 0), 0);
  const pendingCredits = pending.reduce((s, p) => s + (p.credits ?? 0), 0);
  const pendingRon = pending.reduce((s, p) => s + Number(p.amount_ron ?? 0), 0);

  // ZONA 2 — top 10 dupa credite cumparate (CONFIRMATE). Limit 10 hard.
  const byUser = new Map<string, { credits: number; ron: number }>();
  for (const p of credited) {
    if (!p.user_id) continue;
    const cur = byUser.get(p.user_id) ?? { credits: 0, ron: 0 };
    cur.credits += p.credits ?? 0;
    cur.ron += Number(p.amount_ron ?? 0);
    byUser.set(p.user_id, cur);
  }
  const emailById = new Map(profiles.map((p) => [p.id, p.email as string]));
  // Faza 1.5: bug-urile cu emailul userului (randat server-side, doar pe pagina de admin)
  const bugs: BugRow[] = bugsRaw.map((b) => ({
    id: b.id as string,
    email: emailById.get(b.user_id as string) ?? "(necunoscut)",
    content: (b.content as string) ?? "",
    status: (b.status as string) ?? "nou",
    z_coins_awarded: (b.z_coins_awarded as number) ?? 0,
    created_at: (b.created_at as string) ?? "",
  }));
  const facturi: FacturaRow[] = facturiRaw.map((f) => ({
    order_id: f.order_id as string,
    email: emailById.get(f.user_id as string) ?? "(necunoscut)",
    series: (f.invoice_series as string) ?? null,
    number: (f.invoice_number as string) ?? null,
    amount_ron: (f.amount_ron as number) ?? null,
    created_at: (f.created_at as string) ?? "",
    email_status: (f.invoice_email_status as string) ?? null,
    email_to: (f.invoice_email_to as string) ?? null,
    email_at: (f.invoice_email_at as string) ?? null,
    email_error: (f.invoice_email_error as string) ?? null,
    email_attempts: (f.invoice_email_attempts as number) ?? 0,
  }));
  // ── FACTURARE SERVICII ──
  const clienti: ClientRow[] = clientiRaw.map((c) => ({
    id: c.id as string, denumire: c.denumire as string, cui: c.cui as string,
    reg_com: (c.reg_com as string) ?? null, adresa: c.adresa as string,
    judet: c.judet as string, localitate: c.localitate as string, email: c.email as string,
    persoana_contact: (c.persoana_contact as string) ?? null, activ: c.activ === true,
  }));
  const numeClient = new Map(clienti.map((c) => [c.id, c.denumire]));
  const abonamente: AbonamentRow[] = abonamenteRaw.map((a) => ({
    id: a.id as string, client_id: a.client_id as string,
    client: numeClient.get(a.client_id as string) ?? "(client șters)",
    descriere: a.descriere as string, suma_ron: Number(a.suma_ron ?? 0),
    zi_emitere: Number(a.zi_emitere ?? 1), data_start: (a.data_start as string) ?? "",
    activ: a.activ === true,
    urmatoarea: urmatoareaScadenta(Number(a.zi_emitere ?? 1), (a.data_start as string) ?? ""),
    ultima_rulare: a.ultima_rulare_at
      ? new Date(a.ultima_rulare_at as string).toLocaleDateString("ro-RO", { day: "2-digit", month: "short" })
      : null,
    ultima_eroare: (a.ultima_eroare as string) ?? null,
  }));
  const facturiServicii: FacturaServiciuRow[] = facturiServRaw.map((f) => ({
    id: f.id as string, client: numeClient.get(f.client_id as string) ?? "(client șters)",
    descriere: f.descriere as string, suma_ron: Number(f.suma_ron ?? 0),
    status: (f.status as string) ?? "pending", serie: (f.serie as string) ?? null,
    numar: (f.numar as string) ?? null, smartbill_error: (f.smartbill_error as string) ?? null,
    created_at: (f.created_at as string) ?? "",
    email_status: (f.invoice_email_status as string) ?? null,
    email_to: (f.invoice_email_to as string) ?? null,
    email_error: (f.invoice_email_error as string) ?? null,
    din_abonament: !!f.abonament_id,
  }));
  const serieConfigurata = !!seriesFor("servicii");

  const top10: TopRow[] = [...byUser.entries()]
    .sort((a, b) => b[1].credits - a[1].credits || b[1].ron - a[1].ron)
    .slice(0, 10)
    .map(([uid, v]) => ({
      email: emailById.get(uid) ?? "(necunoscut)",
      creditsConfirmed: v.credits,
      ronConfirmed: v.ron,
      projects: projCountByUser.get(uid) ?? 0,
    }));

  return (
    <>
      <AppHeader />
      <main className="min-h-screen bg-slate-50 px-4 py-8 md:px-8">
        <div className="mx-auto max-w-6xl">
          <header className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900">Dashboard Admin</h1>
            <p className="text-sm text-slate-500">Vizibilitate business Zynapse — acces restrictionat.</p>
          </header>

        {/* ZONA 1 — cifre globale */}
        <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card label="Useri inregistrati" value={fmtInt(totalUsers)} />
          <Card label="Proiecte generate" value={fmtInt(totalProjects)}
            sub={`DTAC ${fmtInt(projectsDTAC)} · DTAC+PT ${fmtInt(projectsPT)}`} />
          <Card label="Credite ramase pe conturi" value={fmtInt(creditsRemaining)} sub="suma soldurilor" />
          <Card label="Venit confirmat" value={fmtRon(revenue)} accent="emerald"
            sub={`${fmtInt(creditsSold)} credite vandute (creditate)`} />
          <Card label="In asteptare (pending)" value={fmtRon(pendingRon)} accent="amber"
            sub={`${fmtInt(pending.length)} plati · ${fmtInt(pendingCredits)} credite neconfirmate`} />
          <Card label="Plati totale" value={fmtInt(payments.length)}
            sub={`${fmtInt(credited.length)} creditate · ${fmtInt(pending.length)} pending`} />
        </section>

        {/* ZONA 2 — top 10 clienti dupa credite cumparate (confirmate) */}
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-lg font-semibold text-slate-900">Top 10 clienti dupa credite cumparate</h2>
            <p className="text-xs text-slate-500">Doar achizitii confirmate (creditate). Maxim 10.</p>
          </div>
          {top10.length === 0 ? (
            <p className="px-5 py-10 text-center text-sm text-slate-400">
              Nicio achizitie confirmata inca. Clientii apar aici cand o plata e creditata.
            </p>
          ) : (
            <>
            {/* ── TELEFON (sub 768px): un client = o cartela ──────────────────────────────────
                Capul e locul si emailul; la dreapta VENITUL, fiindca pentru cifra aia se deschide
                clasamentul. Creditele si proiectele vin dedesubt. */}
            <div className="divide-y divide-slate-100 md:hidden">
              {top10.map((r, i) => (
                <div key={r.email} className="px-5 py-4">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="min-w-0 break-all text-sm font-medium text-slate-800">
                      <span className="mr-1.5 text-slate-400">{i + 1}.</span>{r.email}
                    </p>
                    <p className="shrink-0 font-semibold tabular-nums text-slate-900">{fmtRon(r.ronConfirmed)}</p>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {fmtInt(r.creditsConfirmed)} credite · {fmtInt(r.projects)} proiecte
                  </p>
                </div>
              ))}
            </div>

            <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">#</th>
                  <th className="px-5 py-3 font-medium">Email</th>
                  <th className="px-5 py-3 text-right font-medium">Credite cumparate</th>
                  <th className="px-5 py-3 text-right font-medium">Venit (RON)</th>
                  <th className="px-5 py-3 text-right font-medium">Proiecte</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {top10.map((r, i) => (
                  <tr key={r.email} className="hover:bg-slate-50">
                    <td className="px-5 py-3 text-slate-400">{i + 1}</td>
                    <td className="px-5 py-3 font-medium text-slate-800">{r.email}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-slate-700">{fmtInt(r.creditsConfirmed)}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-slate-700">{fmtRon(r.ronConfirmed)}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-slate-700">{fmtInt(r.projects)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            </>
          )}
        </section>

        {/* ZONA 3 — facturile emise si starea livrarii pe email */}
        <FacturiSection facturi={facturi} />

        {/* ZONA 3b — facturarea de SERVICII: clienti, abonamente, facturi */}
        <ServiciiSection clienti={clienti} abonamente={abonamente} facturi={facturiServicii}
                        serieConfigurata={serieConfigurata} />

        {/* ZONA 4 — rapoartele de bug din chat + acordarea Z-coins (Faza 1.5) */}
        <BugsSection bugs={bugs} />
        </div>
      </main>
    </>
  );
}

function Card({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: "emerald" | "amber" }) {
  const ring = accent === "emerald" ? "border-emerald-200" : accent === "amber" ? "border-amber-200" : "border-slate-200";
  const val = accent === "emerald" ? "text-emerald-700" : accent === "amber" ? "text-amber-700" : "text-slate-900";
  return (
    <div className={`rounded-xl border ${ring} bg-white p-5 shadow-sm`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${val}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}
