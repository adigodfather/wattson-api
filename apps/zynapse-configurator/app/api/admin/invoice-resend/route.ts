import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { deliverInvoiceEmail } from "@/lib/invoiceDelivery";

// Reîncercarea trimiterii unei facturi pe email (dashboard admin). Acelaşi tipar de autorizare ca
// la award-bug: sesiunea pe cookie + `is_admin` re-verificat aici.
//
// `force: true` reia şi o livrare rămasă agăţată în 'sending' (proces căzut între claim şi
// finalizare). Fără el, factura aia n-ar mai putea fi trimisă niciodată — o gardă care se blochează
// pe sine e la fel de rea ca una care lipseşte. Dublarea rămâne oprită: claim-ul e tot un UPDATE
// condiţionat, deci două apăsări simultane pe buton nu trimit două emailuri.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
  const { data: { user } } = await supa.auth.getUser();
  if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
  const { data: prof } = await supa.from("profiles").select("is_admin").eq("id", user.id).single();
  if (prof?.is_admin !== true) return NextResponse.json({ error: "Doar admin" }, { status: 403 });

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
