import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { cerAdmin } from "@/lib/adminGuard";
import { deliverInvoiceEmail } from "@/lib/invoiceDelivery";

// Reîncercarea trimiterii unei facturi pe email (dashboard admin). Acelaşi tipar de autorizare ca
// la award-bug: poarta comuna `cerAdmin` (sesiune pe cookie + `is_admin` verificat server-side).
//
// `force: true` reia şi o livrare rămasă agăţată în 'sending' (proces căzut între claim şi
// finalizare). Fără el, factura aia n-ar mai putea fi trimisă niciodată — o gardă care se blochează
// pe sine e la fel de rea ca una care lipseşte. Dublarea rămâne oprită: claim-ul e tot un UPDATE
// condiţionat, deci două apăsări simultane pe buton nu trimit două emailuri.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  // Poarta COMUNA, nu o copie locala (vezi nota din award-bug).
  const refuz = await cerAdmin();
  if (refuz) return refuz;

  let orderId = "";
  try {
    const body = await req.json();
    orderId = String(body?.order_id ?? "").trim();
  } catch {
    return NextResponse.json({ error: "Body invalid" }, { status: 400 });
  }
  if (!orderId) return NextResponse.json({ error: "order_id lipsă" }, { status: 400 });

  try {
    const r = await deliverInvoiceEmail(createAdminClient(), orderId, { force: true });
    if (r.status === "sent") return NextResponse.json({ ok: true, to: r.to });
    if (r.status === "skipped") return NextResponse.json({ ok: false, error: r.reason }, { status: 409 });
    return NextResponse.json({ ok: false, error: r.error }, { status: 502 });
  } catch (e) {
    return NextResponse.json({ ok: false, error: e instanceof Error ? e.message : "eroare" }, { status: 500 });
  }
}
