import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { cerAdmin } from "@/lib/adminGuard";

// Abonamentele recurente: creare si oprire. Emiterea NU se face de aici — o face fluxul zilnic
// (`/api/abonamente/run`), ca sa existe UN singur loc care decide ce e scadent.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const refuz = await cerAdmin();
  if (refuz) return refuz;
  let b: Record<string, unknown> = {};
  try { b = (await req.json()) as Record<string, unknown>; }
  catch { return NextResponse.json({ error: "Body invalid" }, { status: 400 }); }

  const clientId = String(b.client_id ?? "").trim();
  const descriere = String(b.descriere ?? "").trim();
  const suma = Math.round(Number(b.suma_ron) * 100) / 100;
  const zi = Math.floor(Number(b.zi_emitere));
  const dataStart = String(b.data_start ?? "").trim();

  if (!clientId) return NextResponse.json({ error: "Alege clientul." }, { status: 400 });
  if (!descriere) return NextResponse.json({ error: "Descrierea serviciului e obligatorie." }, { status: 400 });
  if (!(suma > 0)) return NextResponse.json({ error: "Suma trebuie să fie mai mare ca zero." }, { status: 400 });
  // 1..25 (decizia lui Dan). Cu plafonul aici, problema lunilor scurte dispare COMPLET: 25 exista
  // in orice luna, inclusiv februarie, deci nu mai e nevoie de nicio regula speciala nicaieri in
  // cod. Validarea sta pe SERVER, nu doar in formular — un formular se ocoleste cu o cerere.
  // Baza are acelasi plafon (CHECK), deci nici o cerere directa la PostgREST nu-l poate sari.
  if (!(zi >= 1 && zi <= 25)) {
    return NextResponse.json({ error: "Ziua de emitere e între 1 și 25 (ca să existe în orice lună)." }, { status: 400 });
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dataStart)) {
    return NextResponse.json({ error: "Data de start lipsește sau are alt format." }, { status: 400 });
  }

  const admin = createAdminClient();
  const { data: cl } = await admin.from("clienti_servicii").select("id, activ").eq("id", clientId).single();
  if (!cl) return NextResponse.json({ error: "Clientul nu există." }, { status: 404 });
  if ((cl as { activ: boolean }).activ !== true) {
    return NextResponse.json({ error: "Clientul e dezactivat." }, { status: 409 });
  }

  const { data, error } = await admin.from("abonamente_servicii").insert({
    client_id: clientId, descriere, suma_ron: suma, zi_emitere: zi, data_start: dataStart,
  }).select("id").single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, id: (data as { id: string }).id });
}

/** Oprirea (sau repornirea) unui abonament. Randul RAMANE, ca istoricul sa nu dispara. */
export async function PATCH(req: NextRequest) {
  const refuz = await cerAdmin();
  if (refuz) return refuz;
  let b: Record<string, unknown> = {};
  try { b = (await req.json()) as Record<string, unknown>; }
  catch { return NextResponse.json({ error: "Body invalid" }, { status: 400 }); }
  const id = String(b.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "id lipsă" }, { status: 400 });
  const { error } = await createAdminClient()
    .from("abonamente_servicii").update({ activ: b.activ === true }).eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
