// ─── SmartBill — emitere factură la plată confirmată ───────────────────────
// Auth Basic (SMARTBILL_USERNAME : SMARTBILL_TOKEN). POST /SBORO/api/invoice.
// Zynapse = NEPLĂTITOR de TVA -> taxPercentage 0 (preț = suma plătită, fără TVA adăugat).
// Mailul: trimis DIRECT de SmartBill (setare auto-send în cont) — punem doar client.email.
// Secretele se citesc EXCLUSIV din process.env (Vercel). Nu se logează niciodată.

const SMARTBILL_API = "https://ws.smartbill.ro/SBORO/api";
const TIMEOUT_MS = 15000;

// ── tipuri minime (subset din profiles/payments) ──
export interface SmartbillProfile {
  email?: string | null;
  full_name?: string | null;
  firma_nume?: string | null;
  firma_cui?: string | null;
  firma_adresa?: string | null;
  firma_email?: string | null;
}

export interface SmartbillPayment {
  amount_ron: number | string;
  credits: number;
  order_id: string;
}

// Alegerea de facturare (gate Home). company_profile = firma din profil; company_custom = date ad-hoc;
// individual = persoană fizică (B2C). adminName -> "Reprezentant: X" în observations.
export type BillingType = "company_profile" | "company_custom" | "individual";
export interface BillingInput {
  type: BillingType;
  name?: string | null;       // company_custom: denumire firmă
  vatCode?: string | null;    // company_custom: CIF
  address?: string | null;    // company_custom: adresă
  email?: string | null;      // company_custom: email facturare
  adminName?: string | null;  // nume administrator/reprezentant -> observations
}

export interface SmartbillClient {
  name: string;
  vatCode?: string;
  isTaxPayer: boolean;
  address?: string;
  email: string;
  country: string;   // SmartBill cere ţara obligatoriu — platformă RO -> "Romania" automat
  saveToDb: boolean;
}

export interface SmartbillInvoicePayload {
  companyVatCode: string;
  client: SmartbillClient;
  issueDate: string;
  seriesName: string;
  isDraft: boolean;
  observations?: string;   // mențiuni pe factură (ex. "Reprezentant: X")
  products: Array<{
    name: string;
    measuringUnitName: string;
    currency: string;
    quantity: number;
    price: number;
    taxName: string;
    taxPercentage: number;
    isTaxIncluded: boolean;
    isService: boolean;
    saveToDb: boolean;
  }>;
}

export interface SmartbillResult {
  success: boolean;
  invoiceNumber?: string;
  series?: string;
  error?: string;
  status?: number;
}

/** Prezența env-urilor (booleeni, fără valori) — pt. un health-check viitor. */
export function smartbillConfigStatus(): Record<string, boolean> {
  return {
    SMARTBILL_USERNAME: !!process.env.SMARTBILL_USERNAME,
    SMARTBILL_TOKEN: !!process.env.SMARTBILL_TOKEN,
    SMARTBILL_VAT_CODE: !!process.env.SMARTBILL_VAT_CODE,
    SMARTBILL_SERIES: !!process.env.SMARTBILL_SERIES,
  };
}

/** issueDate = azi, format YYYY-MM-DD (UTC). */
function todayYmd(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`;
}

/** Mapare client în funcţie de alegerea de facturare (billing). Fără billing -> comportamentul vechi
 *  (firma_cui completat = B2B firmă; altfel B2C) pentru BACKWARD-COMPAT (plăţi vechi). */
export function mapSmartbillClient(p: SmartbillProfile, billing?: BillingInput | null): SmartbillClient {
  const b2c = (): SmartbillClient => ({
    name: (p.full_name || "Client").trim() || "Client",
    isTaxPayer: false,
    country: "Romania",
    email: (p.email || "").trim(),
    saveToDb: false,
  });

  // OPŢIUNEA 3 — persoană fizică (B2C)
  if (billing?.type === "individual") return b2c();

  // OPŢIUNEA 2 — firmă cu date AD-HOC (din billing, NU din profil)
  if (billing?.type === "company_custom") {
    const cui = (billing.vatCode || "").trim();
    return {
      name: (billing.name || p.full_name || "Client").trim() || "Client",
      vatCode: cui || undefined,
      isTaxPayer: /^ro/i.test(cui),
      address: (billing.address || "").trim() || undefined,
      country: "Romania",
      email: (billing.email || p.email || "").trim(),
      saveToDb: false,
    };
  }

  // OPŢIUNEA 1 (company_profile) SAU fără billing (backward-compat): firma din profil dacă firma_cui;
  // altfel B2C (safety — UI/G3 împiedică opt.1 fără firma_cui).
  const cui = (p.firma_cui || "").trim();
  if (cui) {
    return {
      name: (p.firma_nume || p.full_name || "Client").trim() || "Client",
      vatCode: cui,
      isTaxPayer: /^ro/i.test(cui),          // CUI cu prefix "RO" = plătitor TVA; altfel neplătitor
      address: (p.firma_adresa || "").trim() || undefined,
      country: "Romania",                    // toți clienții sunt din România (platformă RO)
      email: (p.firma_email || p.email || "").trim(),
      saveToDb: false,
    };
  }
  return b2c();
}

/** Construiește payload-ul facturii. PUR (fără rețea) -> testabil. */
export function buildInvoicePayload(
  profile: SmartbillProfile,
  payment: SmartbillPayment,
  opts?: { draft?: boolean; billing?: BillingInput | null }
): SmartbillInvoicePayload {
  const price = Math.round(Number(payment.amount_ron) * 100) / 100;
  const adminName = (opts?.billing?.adminName || "").trim();
  return {
    companyVatCode: (process.env.SMARTBILL_VAT_CODE || "").trim(),
    client: mapSmartbillClient(profile, opts?.billing),
    issueDate: todayYmd(),
    seriesName: (process.env.SMARTBILL_SERIES || "").trim(),
    isDraft: opts?.draft === true,
    // nume administrator/reprezentant pe factură (SmartBill n-are câmp dedicat -> observations)
    ...(adminName ? { observations: `Reprezentant: ${adminName}` } : {}),
    products: [
      {
        name: `${payment.credits} Z-Coins — credite Zynapse`,
        measuringUnitName: "buc",
        currency: "RON",
        quantity: 1,
        price,
        // Zynapse NEPLĂTITOR de TVA: 0%. Contul SmartBill (neplătitor) nu adaugă TVA.
        // ⚠️ Dacă draft-ul e respins pe TVA -> de ajustat (omite taxName / "SDD"/scutit).
        taxName: "Normala",
        taxPercentage: 0,
        isTaxIncluded: true,   // preț = suma plătită (50 lei = 50 lei pe factură)
        isService: true,
        saveToDb: false,
      },
    ],
  };
}

/** Emite factura la SmartBill. Defensiv: env lipsă / timeout / non-2xx / errorText -> {success:false}. */
export async function createInvoice(
  profile: SmartbillProfile,
  payment: SmartbillPayment,
  opts?: { draft?: boolean; billing?: BillingInput | null }
): Promise<SmartbillResult> {
  const username = (process.env.SMARTBILL_USERNAME || "").trim();
  const token = (process.env.SMARTBILL_TOKEN || "").trim();
  const vat = (process.env.SMARTBILL_VAT_CODE || "").trim();
  const series = (process.env.SMARTBILL_SERIES || "").trim();
  if (!username || !token || !vat || !series) {
    return { success: false, error: "SmartBill env lipsă (USERNAME/TOKEN/VAT_CODE/SERIES)" };
  }

  const payload = buildInvoicePayload(profile, payment, opts);
  const auth = "Basic " + Buffer.from(`${username}:${token}`).toString("base64");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${SMARTBILL_API}/invoice`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: auth,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const raw = await res.text();
    let data: Record<string, unknown> = {};
    try { data = raw ? (JSON.parse(raw) as Record<string, unknown>) : {}; } catch { /* non-JSON */ }

    if (!res.ok) {
      const msg = (data.errorText as string) || (data.message as string) || raw.slice(0, 200) || `HTTP ${res.status}`;
      return { success: false, error: msg, status: res.status };
    }
    // SmartBill: succes -> errorText gol + number/series; eroare logică -> errorText ne-gol (status 200)
    const errorText = (data.errorText as string) || "";
    if (errorText) return { success: false, error: errorText, status: res.status };

    return {
      success: true,
      invoiceNumber: data.number != null ? String(data.number) : undefined,
      series: data.series != null ? String(data.series) : series,
      status: res.status,
    };
  } catch (e) {
    const msg =
      e instanceof Error && e.name === "AbortError"
        ? "SmartBill timeout"
        : e instanceof Error ? e.message : "eroare necunoscută";
    return { success: false, error: msg };
  } finally {
    clearTimeout(timer);
  }
}
