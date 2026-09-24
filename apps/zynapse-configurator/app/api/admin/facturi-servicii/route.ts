import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { cerAdmin } from "@/lib/adminGuard";
import { emiteSiTrimite, livreazaFacturaServiciu } from "@/lib/facturiServicii";

// Factura SINGULARA de servicii: se insereaza, se emite in SmartBill si se trimite pe email —
// intr-un singur pas, cum a cerut Dan. Butonul de reincercare (PATCH) ramane pentru esecuri.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;   // emitere + PDF + email, pe rand; 60s e cu marja

export async function POST(req: NextRequest) {
  const refuz = await cerAdmin();
  if (refuz) return refuz;
  let b: Record<string, unknown> = {};
  try { b = (await req.json()) as Record<string, unknown>; }
  catch { return NextResponse.json({ error: "Body invalid" }, { status: 400 }); }

  const clientId = String(b.client_id ?? "").trim();
  const descriere = String(b.descriere ?? "").trim();
  const suma = Math.round(Number(b.suma_ron) * 100) / 100;
  if (!clientId) return NextResponse.json({ error: "Alege clientul." }, { status: 400 });
  if (!descriere) return NextResponse.json({ error: "Descrierea serviciului e obligatorie." }, { status: 400 });
  if (!(suma > 0)) return NextResponse.json({ error: "Suma trebuie să fie mai mare ca zero." }, { status: 400 });

  const admin = createAdminClient();
  // Clientul trebuie sa existe SI sa fie activ: pe un client dezactivat nu se mai factureaza.
  const { data: cl } = await admin.from("clienti_servicii")
    .select("id, activ").eq("id", clientId).single();
  if (!cl) return NextResponse.json({ error: "Clientul nu există." }, { status: 404 });
  if ((cl as { activ: boolean }).activ !== true) {
    return NextResponse.json({ error: "Clientul e dezactivat." }, { status: 409 });
  }

  // Randul se insereaza INAINTE de orice apel la SmartBill: daca emiterea pica, ramane o urma cu
  // motivul, vizibila in admin. Un esec fara urma e exact ce vanam.
  const { data: f, error } = await admin.from("facturi_servicii")
    .insert({ client_id: clientId, descriere, suma_ron: suma })
    .select("id").single();
  if (error || !f) return NextResponse.json({ error: error?.message || "nu s-a putut crea factura" }, { status: 500 });

  const r = await emiteSiTrimite(admin, (f as { id: string }).id, { timeoutMs: 12000 });
  if (r.status !== "emisa") {
    return NextResponse.json({ ok: false, id: (f as { id: string }).id,
      error: "error" in r ? r.error : r.motiv }, { status: 502 });
  }
  return NextResponse.json({ ok: true, serie: r.serie, numar: r.numar, email: r.email,
                             eroareEmail: r.eroareEmail ?? null });
}

/** Reincercarea trimiterii pe email (factura e deja emisa). Oglinda butonului de la credite. */
export async function PATCH(req: NextRequest) {
  const refuz = await cerAdmin();
  if (refuz) return refuz;
  let b: Record<string, unknown> = {};
  try { b = (await req.json()) as Record<string, unknown>; }
  catch { return NextResponse.json({ error: "Body invalid" }, { status: 400 }); }
  const id = String(b.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "id lipsă" }, { status: 400 });

  const r = await livreazaFacturaServiciu(createAdminClient(), id, { force: true });
  if (r.status === "sent") return NextResponse.json({ ok: true, to: r.to });
  return NextResponse.json({ ok: false, error: r.error }, { status: r.status === "skipped" ? 409 : 502 });
}
