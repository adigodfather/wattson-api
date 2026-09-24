import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { cerAdmin } from "@/lib/adminGuard";
import { eroareCui, normalizeCui } from "@/lib/cui";

// Clientii de servicii: creare si activare/dezactivare. Admin-only.
// Datele fiscale se valideaza AICI, pe server — o validare care traieste doar in formular se
// ocoleste cu o singura cerere.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const CERUTE: Array<[string, string]> = [
  ["denumire", "Denumirea firmei"],
  ["adresa", "Adresa"],
  ["judet", "Județul"],
  ["localitate", "Localitatea"],
  ["email", "Emailul"],
];

export async function POST(req: NextRequest) {
  const refuz = await cerAdmin();
  if (refuz) return refuz;

  let b: Record<string, string> = {};
  try { b = (await req.json()) as Record<string, string>; }
  catch { return NextResponse.json({ error: "Body invalid" }, { status: 400 }); }

  for (const [camp, eticheta] of CERUTE) {
    if (!String(b[camp] ?? "").trim()) {
      return NextResponse.json({ error: `${eticheta} e obligatorie.` }, { status: 400 });
    }
  }
  // Judetul si localitatea sunt in lista de mai sus, nu optionale: fara ele SPV refuza transmiterea.
  const eCui = eroareCui(b.cui);
  if (eCui) return NextResponse.json({ error: eCui }, { status: 400 });
  const email = String(b.email).trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return NextResponse.json({ error: "Emailul nu pare valid." }, { status: 400 });
  }

  const admin = createAdminClient();
  const { data, error } = await admin.from("clienti_servicii").insert({
    denumire: String(b.denumire).trim(),
    cui: normalizeCui(b.cui),                 // stocat normalizat: un CUI = un rand, fara „RO" si spatii
    reg_com: String(b.reg_com ?? "").trim() || null,
    adresa: String(b.adresa).trim(),
    judet: String(b.judet).trim(),
    localitate: String(b.localitate).trim(),
    email,
    persoana_contact: String(b.persoana_contact ?? "").trim() || null,
  }).select("id, denumire, cui").single();

  if (error) {
    const dubla = error.code === "23505";
    return NextResponse.json(
      { error: dubla ? "Există deja un client cu acest CUI." : error.message },
      { status: dubla ? 409 : 500 });
  }
  return NextResponse.json({ ok: true, client: data });
}

export async function PATCH(req: NextRequest) {
  const refuz = await cerAdmin();
  if (refuz) return refuz;
  let b: Record<string, unknown> = {};
  try { b = (await req.json()) as Record<string, unknown>; }
  catch { return NextResponse.json({ error: "Body invalid" }, { status: 400 }); }
  const id = String(b.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "id lipsă" }, { status: 400 });

  // Clientii se DEZACTIVEAZA, nu se sterg: un client sters ar lasa abonamente active care
  // incearca sa factureze in gol. Baza oricum refuza stergerea (ON DELETE RESTRICT).
  const { error } = await createAdminClient()
    .from("clienti_servicii").update({ activ: b.activ === true }).eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
