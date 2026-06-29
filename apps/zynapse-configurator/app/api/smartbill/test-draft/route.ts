// ─── SmartBill — emitere CIORNĂ de test (admin) ─────────────────────────────
// GET/POST /api/smartbill/test-draft?order_id=ZYN-... -> createInvoice cu isDraft:TRUE.
// CIORNĂ = NU consumă seria ZN, NU e document fiscal. Dan o vede în SmartBill (Ciorne) ca să
// valideze datele (client, sumă, TVA 0) + mailul (auto-send) ÎNAINTE de ZN0001 real din IPN.
// ADMIN-ONLY. Întoarce payload-ul trimis + răspunsul SmartBill.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { createInvoice, buildInvoicePayload } from "@/lib/smartbill";

async function isAdmin(): Promise<boolean> {
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return false;
    const { data: prof } = await supa.from("profiles").select("is_admin").eq("id", user.id).single();
    return prof?.is_admin === true;
  } catch {
    return false;
  }
}

async function handle(orderId: string) {
  if (!orderId) return NextResponse.json({ error: "order_id lipsă" }, { status: 400 });

  const admin = createAdminClient();
  const { data: pay } = await admin
    .from("payments")
    .select("order_id, amount_ron, credits, user_id")
    .eq("order_id", orderId)
    .single();
  if (!pay) return NextResponse.json({ error: "Plată inexistentă" }, { status: 404 });

  const { data: prof } = await admin
    .from("profiles")
    .select("email, full_name, firma_nume, firma_cui, firma_adresa, firma_email")
    .eq("id", pay.user_id)
    .single();

  const payment = { amount_ron: pay.amount_ron, credits: pay.credits, order_id: pay.order_id };
  // payload-ul (transparență pt. Dan — fără secrete) + apelul real cu draft:true (ciornă)
  const payload = buildInvoicePayload(prof || {}, payment, { draft: true });
  const result = await createInvoice(prof || {}, payment, { draft: true });

  return NextResponse.json({ draft: true, order_id: orderId, payload, result });
}

export async function POST(req: NextRequest) {
  if (!(await isAdmin())) return NextResponse.json({ error: "Doar admin" }, { status: 403 });
  let body: { order_id?: string } = {};
  try { body = await req.json(); } catch { /* gol */ }
  return handle(String(body.order_id || ""));
}

export async function GET(req: NextRequest) {
  if (!(await isAdmin())) return NextResponse.json({ error: "Doar admin" }, { status: 403 });
  return handle(req.nextUrl.searchParams.get("order_id") || "");
}
