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

    // 2. input
    let body: { packageId?: string } = {};
    try { body = await req.json(); } catch { /* gol */ }
    const packageId = String(body.packageId || "");
    if (!packageId) {
      return NextResponse.json({ error: "packageId lipsește" }, { status: 400 });
    }

    const admin = createAdminClient();

    // 3. pachet ACTIV din DB — pretul + creditele vin DIN DB, niciodată din client
    const { data: pack, error: pErr } = await admin
      .from("credit_packages")
      .select("id, name, credits, price_ron, is_active")
      .eq("id", packageId)
      .eq("is_active", true)
      .single();
    if (pErr || !pack) {
      return NextResponse.json({ error: "Pachet inexistent sau inactiv" }, { status: 404 });
    }

    // 4. order_id unic
    const orderId = `ZYN-${Date.now()}-${crypto.randomBytes(4).toString("hex")}`;
    const amount = Number(pack.price_ron).toFixed(2);

    // 5. INSERT payment pending — credits + amount ÎNGHEȚATE din pachet
    const { error: insErr } = await admin.from("payments").insert({
      order_id: orderId,
      user_id: user.id,            // profiles.id = auth.uid()
      package_id: pack.id,
      credits: pack.credits,
      amount_ron: pack.price_ron,
      status: "pending",
    });
    if (insErr) {
      return NextResponse.json({ error: "Nu am putut crea comanda" }, { status: 500 });
    }

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
      details: `Pachet ${pack.name} - Zynapse`,
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
