// ─── Config Netopia ────────────────────────────────────────────────────────
// Citește secretele EXCLUSIV din process.env (Vercel + .env.local local).
// Cheile reale NU sunt în repo (vezi .env.example pentru structură).
// REGULĂ: nu loga niciodată valorile cheilor (signature/cer/key).

export type NetopiaEnv = "sandbox" | "live";

export interface NetopiaConfig {
  env: NetopiaEnv;
  signature: string;   // string POS din contul Netopia
  publicCer: string;   // public.cer (PEM, BEGIN/END) — criptează cererea
  privateKey: string;  // private.key (PEM, BEGIN/END) — decriptează IPN-ul (SECRET)
  baseUrl: string;     // endpoint Netopia (sandbox sau live)
  returnUrl: string;   // unde revine userul după plată (browser redirect)
  confirmUrl: string;  // IPN server-to-server (Netopia -> noi)
}

function required(name: string): string {
  const v = process.env[name];
  if (!v || !v.trim()) {
    throw new Error(
      `[netopia/config] Variabila de mediu ${name} lipsește sau e goală. ` +
      `Seteaz-o în Vercel (Project Settings → Environment Variables) și în .env.local local.`
    );
  }
  return v;
}

function optional(name: string, fallback: string): string {
  const v = process.env[name];
  return v && v.trim() ? v.trim() : fallback;
}

// PEM-urile pot fi stocate cu "\n" literal (Vercel) -> normalizează la newline real.
function normalizePem(raw: string): string {
  return raw.includes("\\n") ? raw.replace(/\\n/g, "\n") : raw;
}

let _cfg: NetopiaConfig | null = null;

/** Config Netopia, citit lazy (la prima cerere de plată, NU la build/import).
 *  Aruncă eroare clară dacă lipsește o variabilă obligatorie. */
export function getNetopiaConfig(): NetopiaConfig {
  if (_cfg) return _cfg;

  const env: NetopiaEnv =
    optional("NETOPIA_ENV", "sandbox").toLowerCase() === "live" ? "live" : "sandbox";

  const baseUrl =
    env === "live"
      ? optional("NETOPIA_LIVE_URL", "https://secure.mobilpay.ro")
      : optional("NETOPIA_SANDBOX_URL", "https://sandboxsecure.mobilpay.ro");

  const site = required("NEXT_PUBLIC_BASE_URL").replace(/\/+$/, "");

  _cfg = {
    env,
    signature: required("NETOPIA_SIGNATURE"),
    publicCer: normalizePem(required("NETOPIA_PUBLIC_CER")),
    privateKey: normalizePem(required("NETOPIA_PRIVATE_KEY")),
    baseUrl,
    returnUrl: `${site}/plata/retur`,
    confirmUrl: `${site}/api/payment/ipn`,
  };
  return _cfg;
}

/** Verifică prezența tuturor variabilelor Netopia fără a expune valorile.
 *  Util pentru un endpoint de health/debug (returnează doar booleeni). */
export function netopiaConfigStatus(): Record<string, boolean> {
  return {
    NETOPIA_ENV: !!process.env.NETOPIA_ENV,
    NETOPIA_SIGNATURE: !!process.env.NETOPIA_SIGNATURE,
    NETOPIA_PUBLIC_CER: !!process.env.NETOPIA_PUBLIC_CER,
    NETOPIA_PRIVATE_KEY: !!process.env.NETOPIA_PRIVATE_KEY,
    NEXT_PUBLIC_BASE_URL: !!process.env.NEXT_PUBLIC_BASE_URL,
  };
}
