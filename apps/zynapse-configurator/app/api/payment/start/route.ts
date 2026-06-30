// ─── Netopia: start plată ───────────────────────────────────────────────────
// Autentifică userul, citește pachetul (preț+credite DIN DB), creează payment
// pending, construiește + criptează XML-ul și întoarce un formular auto-submit
// care POSTează spre pagina Netopia.
export const runtime = "nodejs";

import crypto from "crypto";
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { getNetopiaConfig } from "@/lib/netopia/config";
import { encryptRequest } from "@/lib/netopia/crypto";
import { buildPaymentXml, netopiaTimestamp } from "@/lib/netopia/xml";

function escAttr(s: string): string {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Sumă liberă (calculator): preț CANONIC, calculat EXCLUSIV server-side.
const PRICE_PER_CREDIT = 0.5;   // lei/credit (= CREDIT_PRICING.pricePerCredit)
const MAX_CREDITS = 100000;     // plafon de siguranță anti-abuz

export async function POST(req: NextRequest) {
  try {
    // 1. autentificare (metoda din proiect)
    const cookieStore = await cookies();
    const supa = createServerClient({
      get: (n) => cookieStore.get(n),
      set: () => {},
    });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) {
      return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
    }

    // 2. input — DOUĂ moduri: pachet fix {packageId} SAU sumă liberă {credits}
    let body: { packageId?: string; credits?: number; billing?: Record<string, unknown> } = {};
    try { body = await req.json(); } catch { /* gol */ }
    const packageId = body.packageId ? String(body.packageId) : "";

    const admin = createAdminClient();

    // ── GATE FACTURARE (G3): alegerea de facturare e OBLIGATORIE + validată SERVER-SIDE ──
    // (UI-ul o impune, dar o re-validăm aici ca un apel direct la API să NU sară gate-ul.)
    const billing = (body.billing || {}) as {
      type?: string; name?: string; vatCode?: string; address?: string; email?: string; adminName?: string;
    };
    const bType = String(billing.type || "");
    if (!["company_profile", "company_custom", "individual"].includes(bType)) {
      return NextResponse.json({ error: "Alege o opțiune de facturare înainte de plată." }, { status: 400 });
    }
    const { data: bProf } = await admin
      .from("profiles").select("firma_cui, full_name").eq("id", user.id).single();
    let billingData: Record<string, string> = {};
    if (bType === "company_profile") {
      if (!String(bProf?.firma_cui || "").trim()) {
        return NextResponse.json({ error: "Completează datele firmei în Setări înainte de a factura pe firmă." }, { status: 400 });
      }
      const adminName = String(billing.adminName || "").trim();
      if (!adminName) return NextResponse.json({ error: "Numele administratorului e obligatoriu." }, { status: 400 });
      billingData = { admin_name: adminName };
    } else if (bType === "company_custom") {
      const name = String(billing.name || "").trim();
      const vatCode = String(billing.vatCode || "").trim();
      const address = String(billing.address || "").trim();
      if (!name || !vatCode || !address) {
        return NextResponse.json({ error: "Completează denumirea firmei, CIF-ul și adresa." }, { status: 400 });
      }
      billingData = { name, vatCode, address, email: String(billing.email || "").trim(), admin_name: String(billing.adminName || "").trim() };
    } else {
      if (!String(bProf?.full_name || "").trim()) {
        return NextResponse.json({ error: "Numele lipsește din cont." }, { status: 400 });
      }
    }

    // valorile finale (credite + sumă) provin EXCLUSIV de pe server, niciodată din client
    let creditsToBuy: number;
    let amountRon: number;
    let dbPackageId: string | null;
    let label: string;

    if (packageId) {
      // 3a. mod pachet ACTIV din DB — pretul + creditele vin DIN DB
      const { data: pack, error: pErr } = await admin
        .from("credit_packages")
        .select("id, name, credits, price_ron, is_active")
        .eq("id", packageId)
        .eq("is_active", true)
        .single();
      if (pErr || !pack) {
        return NextResponse.json({ error: "Pachet inexistent sau inactiv" }, { status: 404 });
      }
      creditsToBuy = pack.credits;
      amountRon = Number(pack.price_ron);
      dbPackageId = pack.id;
      label = pack.name;
    } else {
      // 3b. mod sumă liberă — clientul trimite DOAR numărul de credite;
      //     prețul = credits * PRICE_PER_CREDIT, calculat AICI (anti-fraudă).
      const n = Number(body.credits);
      if (!Number.isInteger(n) || n < 1 || n > MAX_CREDITS) {
        return NextResponse.json(
          { error: `Număr de credite invalid (între 1 și ${MAX_CREDITS})` },
          { status: 400 }
        );
      }
      creditsToBuy = n;
      amountRon = Math.round(n * PRICE_PER_CREDIT * 100) / 100; // 2 zecimale, server-side
      dbPackageId = null;            // sumă liberă -> fără pachet (package_id e nullable)
      label = `${n} Z-Coins`;
    }

    // 4. order_id unic
    const orderId = `ZYN-${Date.now()}-${crypto.randomBytes(4).toString("hex")}`;
    const amount = amountRon.toFixed(2);

    // 5. INSERT payment pending — credits + amount ÎNGHEȚATE (calculate server-side)
    const { error: insErr } = await admin.from("payments").insert({
      order_id: orderId,
      user_id: user.id,            // profiles.id = auth.uid()
      package_id: dbPackageId,
      credits: creditsToBuy,
      amount_ron: amountRon,
      status: "pending",
      billing_type: bType,         // G3: alegerea de facturare -> citită de IPN pt. createInvoice
      billing_data: billingData,
    });
    if (insErr) {
      return NextResponse.json({ error: "Nu am putut crea comanda" }, { status: 500 });
    }

    // persistă alegerea (default editabil la următoarea cumpărare). NON-BLOCANT.
    try {
      const upd: Record<string, string> = { last_billing_type: bType };
      if (bType === "company_profile" && billingData.admin_name) upd.admin_name = billingData.admin_name;
      await admin.from("profiles").update(upd).eq("id", user.id);
    } catch { /* non-blocant */ }

    // 6. billing din profil
    const { data: prof } = await admin
      .from("profiles")
      .select("full_name, email, phone")
      .eq("id", user.id)
      .single();
    const fullName = String(prof?.full_name || "").trim();
    const parts = fullName ? fullName.split(/\s+/) : [];
    const firstName = parts[0] || "Client";
    const lastName = parts.slice(1).join(" ") || firstName;

    // 7. XML + criptare
    const cfg = getNetopiaConfig();
    const xml = buildPaymentXml({
      orderId,
      amount,
      currency: "RON",
      details: `${label} - Zynapse`,
      signature: cfg.signature,
      confirmUrl: cfg.confirmUrl,
      returnUrl: `${cfg.siteUrl}/payment/return?order=${encodeURIComponent(orderId)}`,
      timestamp: netopiaTimestamp(new Date()),
      billing: {
        firstName,
        lastName,
        email: String(prof?.email || user.email || ""),
        phone: String(prof?.phone || ""),
      },
    });
    const sealed = encryptRequest(xml);

    // 8. formular auto-submit -> pagina Netopia
    const html =
      `<!doctype html><html lang="ro"><head><meta charset="utf-8">` +
      `<title>Redirecționare spre plată...</title></head>` +
      `<body onload="document.forms[0].submit()" style="font-family:sans-serif;background:#0A0B0E;color:#8B8FA8;text-align:center;padding:60px">` +
      `<form method="post" action="${escAttr(cfg.paymentUrl)}">` +
      `<input type="hidden" name="env_key" value="${escAttr(sealed.env_key)}">` +
      `<input type="hidden" name="data" value="${escAttr(sealed.data)}">` +
      `<input type="hidden" name="cipher" value="${escAttr(sealed.cipher)}">` +
      `<input type="hidden" name="iv" value="${escAttr(sealed.iv)}">` +
      `<noscript><button type="submit">Continuă spre plată</button></noscript>` +
      `</form>` +
      `<p>Te redirecționăm spre pagina de plată securizată Netopia...</p>` +
      `</body></html>`;

    return new NextResponse(html, {
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Eroare necunoscută" },
      { status: 500 }
    );
  }
}
