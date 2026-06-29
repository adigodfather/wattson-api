// ─── Netopia: health-check config (FĂRĂ secrete) ────────────────────────────
// GET /api/payment/health — confirmă că env-urile Netopia sunt setate corect
// (env=live + cele 3 chei prezente + format PEM valid) ÎNAINTE de plata-test.
// Întoarce DOAR booleeni + env + URL public. NICIODATĂ valorile secrete (signature/cer/key).
export const runtime = "nodejs";
export const dynamic = "force-dynamic";   // citește process.env la fiecare request (status proaspăt)

import { NextResponse } from "next/server";

// prezență (set + ne-gol), fără a întoarce valoarea
function present(name: string): string {
  const v = process.env[name];
  return v && v.trim() ? v.trim() : "";
}

// PEM-urile pot fi stocate cu "\n" literal (Vercel) -> normalizează ca în lib/netopia/config.ts
function normalizePem(raw: string): string {
  return raw.includes("\\n") ? raw.replace(/\\n/g, "\n") : raw;
}

export function GET() {
  // env NU e secret — Dan vrea să vadă "live". Default "sandbox" (ca în config.ts).
  const env = present("NETOPIA_ENV").toLowerCase() === "live" ? "live" : "sandbox";

  // URL-ul gateway (public) — aceeași derivare ca getNetopiaConfig()
  const payment_url =
    env === "live"
      ? (present("NETOPIA_LIVE_URL") || "https://secure.mobilpay.ro")
      : (present("NETOPIA_SANDBOX_URL") || "https://sandboxsecure.mobilpay.ro");

  const signature = present("NETOPIA_SIGNATURE");
  const cer = normalizePem(present("NETOPIA_PUBLIC_CER"));
  const key = normalizePem(present("NETOPIA_PRIVATE_KEY"));
  const baseSite = present("NEXT_PUBLIC_BASE_URL");

  const signature_set = signature.length > 0;
  const public_cer_set = cer.length > 0;
  // format PEM: începe cu antetul corect (prinde lipirea parțială/greșită a certificatului)
  const public_cer_format_ok = cer.startsWith("-----BEGIN CERTIFICATE-----");
  const private_key_set = key.length > 0;
  // cheia privată: PEM cu BEGIN ... PRIVATE KEY ("-----BEGIN PRIVATE KEY-----" sau "RSA PRIVATE KEY")
  const private_key_format_ok = key.startsWith("-----BEGIN") && key.includes("PRIVATE KEY");
  const base_url_set = baseSite.length > 0;

  // ✅ semnalul verde pt. Dan: env=live + toate cele 3 chei setate cu format valid + base url
  const all_ready =
    env === "live" &&
    signature_set &&
    public_cer_set && public_cer_format_ok &&
    private_key_set && private_key_format_ok &&
    base_url_set;

  return NextResponse.json({
    env,                       // "sandbox" | "live"
    payment_url,               // gateway Netopia (public) — confirmă vizual secure.mobilpay.ro
    base_url_set,              // NEXT_PUBLIC_BASE_URL (return/confirm URLs)
    signature_set,             // DOAR prezență — niciodată valoarea
    public_cer_set,
    public_cer_format_ok,
    private_key_set,
    private_key_format_ok,
    all_ready,
    checked_at: new Date().toISOString(),
  });
}
