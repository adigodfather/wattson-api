// ─── Netopia: IPN (confirmare server-to-server) ─────────────────────────────
// Netopia POSTează aici (form-urlencoded: env_key/data/cipher/iv). Decriptăm,
// validăm suma (anti-tampering), marcăm comanda și credit<m idempotent prin RPC.
// Creditarea NU se face niciodată din client — doar aici, cu service role.
export const runtime = "nodejs";

import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { decryptIpn } from "@/lib/netopia/crypto";
import { parseIpnXml, buildIpnResponse } from "@/lib/netopia/xml";
import { createInvoice } from "@/lib/smartbill";

function xml(body: string): NextResponse {
  return new NextResponse(body, {
    status: 200,
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
}

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const env_key = String(form.get("env_key") || "");
    const data = String(form.get("data") || "");
    const cipher = String(form.get("cipher") || "");
    const iv = String(form.get("iv") || "");
    if (!env_key || !data) {
      return xml(buildIpnResponse({ errorType: 2, errorCode: "0x10", message: "missing env_key/data" }));
    }

    // decriptare + parsare (eșec -> eroare PERMANENTĂ: e problemă de chei/format, nu de retrimis)
    let parsed;
    try {
      parsed = parseIpnXml(decryptIpn(env_key, data, cipher, iv));
    } catch {
      return xml(buildIpnResponse({ errorType: 2, errorCode: "0x11", message: "decrypt/parse failed" }));
    }

    const orderId = parsed.orderId;
    if (!orderId) {
      return xml(buildIpnResponse({ errorType: 2, errorCode: "0x12", message: "no order id" }));
    }

    const admin = createAdminClient();
    const { data: pay, error: findErr } = await admin
      .from("payments")
      .select("order_id, amount_ron, credits, status, credited, user_id, invoiced")
      .eq("order_id", orderId)
      .single();
    if (findErr || !pay) {
      return xml(buildIpnResponse({ errorType: 2, errorCode: "0x13", message: "order not found" }));
    }

    // audit: salvăm payload-ul IPN brut + statusul Netopia
    await admin.from("payments")
      .update({ raw_ipn: parsed.raw as object, netopia_status: parsed.action || null })
      .eq("order_id", orderId);

    // ANTI-TAMPERING: suma procesată trebuie să fie cea înghețată la creare
    if (parsed.processedAmount != null && Number(pay.amount_ron) !== Number(parsed.processedAmount)) {
      await admin.from("payments").update({ status: "failed" }).eq("order_id", orderId);
      return xml(buildIpnResponse({ errorType: 2, errorCode: "0x14", message: "amount mismatch" }));
    }

    const action = (parsed.action || "").toLowerCase();
    const codeOk = parsed.errorCode === "0" || parsed.errorCode === null; // 0 = approved

    if ((action === "confirmed" || action === "paid") && codeOk) {
      await admin.from("payments")
        .update({ status: "paid", netopia_status: parsed.action })
        .eq("order_id", orderId);

      // creditare ATOMICĂ + IDEMPOTENTĂ (IPN repetat NU dublează)
      const { error: rpcErr } = await admin.rpc("add_credits_from_purchase", { p_order_id: orderId });
      if (rpcErr) {
        // eroare temporară -> Netopia reîncearcă (funcția e idempotentă, deci safe)
        return xml(buildIpnResponse({ errorType: 1, errorCode: "0x20", message: "credit retry" }));
      }

      // ── FACTURĂ SmartBill — BEST-EFFORT, idempotent (pe `invoiced`). DUPĂ credite (CRITICE). ──
      // ⚠️ Eșecul SmartBill NU blochează creditarea/IPN: clientul are deja creditele. Try/catch izolat;
      // răspundem OK la Netopia oricum; `invoiced` rămâne false -> retry manual ulterior.
      if (!pay.invoiced) {
        try {
          const { data: prof } = await admin
            .from("profiles")
            .select("email, full_name, firma_nume, firma_cui, firma_adresa, firma_email")
            .eq("id", pay.user_id)
            .single();
          const inv = await createInvoice(
            prof || {},
            { amount_ron: pay.amount_ron, credits: pay.credits, order_id: orderId },
            { draft: false }
          );
          if (inv.success) {
            await admin.from("payments")
              .update({ invoiced: true, invoice_number: inv.invoiceNumber ?? null, invoice_series: inv.series ?? null })
              .eq("order_id", orderId);
          } else {
            console.error(`[ipn] SmartBill invoice esuat (order ${orderId}): ${inv.error}`);
          }
        } catch (e) {
          console.error(`[ipn] SmartBill exceptie (order ${orderId}):`, e instanceof Error ? e.message : e);
        }
      }

      return xml(buildIpnResponse({ crc: parsed.crc }));
    }

    if (action === "canceled") {
      await admin.from("payments").update({ status: "canceled" }).eq("order_id", orderId);
      return xml(buildIpnResponse({ crc: parsed.crc }));
    }

    // cod de eroare != 0 (respins/eșuat) -> failed; altfel lăsăm pending
    if (!codeOk) {
      await admin.from("payments").update({ status: "failed" }).eq("order_id", orderId);
    }
    return xml(buildIpnResponse({ crc: parsed.crc }));
  } catch {
    // eroare internă -> temporară (Netopia reîncearcă)
    return xml(buildIpnResponse({ errorType: 1, errorCode: "0x30", message: "internal" }));
  }
}
