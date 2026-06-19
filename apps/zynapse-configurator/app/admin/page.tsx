// app/admin/page.tsx — Dashboard ADMIN (vizibilitate business pentru Dan).
// SECURITATE: server component. Verificarea de admin se face pe SERVER (sesiune din cookies +
// profiles.is_admin) INAINTE de orice citire de date. Un non-admin e redirectat -> niciun query de
// date, nicio expunere. Agregatele + top 10 se citesc cu service role (server-only, niciodata in client).
// Emailurile apar DOAR in top 10, randate server-side (NU in URL/query/loguri).
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { createServerClient } from "@/lib/supabase";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { isPhasePT } from "@/lib/constants";

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
  const [profilesRes, paymentsRes, projectsRes] = await Promise.all([
    admin.from("profiles").select("id, email, credits_balance"),
    admin.from("payments").select("user_id, credits, amount_ron, status, credited"),
    admin.from("projects").select("user_id, faza"),
  ]);

  const profiles = profilesRes.data ?? [];
  const payments = paymentsRes.data ?? [];
  const projects = projectsRes.data ?? [];

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
    <main className="min-h-screen bg-slate-50 px-4 py-8 md:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Dashboard Admin</h1>
            <p className="text-sm text-slate-500">Vizibilitate business Zynapse — acces restrictionat.</p>
          </div>
          <Link href="/home" className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
            &larr; Acasa
          </Link>
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
          )}
        </section>
      </div>
    </main>
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
