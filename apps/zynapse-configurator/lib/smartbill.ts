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
  address?: string | null;    // company_custom: adresă ; individual: stradă+nr (opţional)
  email?: string | null;      // company_custom: email facturare
  adminName?: string | null;  // nume administrator/reprezentant -> observations
  county?: string | null;     // individual: judeţul (e-Factura B2C — obligatoriu la ANAF)
  city?: string | null;       // individual: localitatea (idem)
  cnp?: string | null;        // individual: CNP (opţional -> vatCode; gol = cod generic de PF)
}

export interface SmartbillClient {
  name: string;
  vatCode?: string;
  isTaxPayer: boolean;
  address?: string;
  city?: string;     // e-Factura: localitatea cumpărătorului
  county?: string;   // e-Factura: judeţul (cbc:CountrySubentity) — ANAF îl cere şi la persoane fizice
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
  // b2c(bi): persoană fizică. Judeţ + localitate (din billing) sunt CERUTE de validarea e-Facturii
  // B2C la ANAF — fără ele SPV respinge trimiterea ("Județ client incorect"), deşi factura se emite.
  // CNP-ul e OPŢIONAL: dat -> vatCode; lipsă -> SmartBill foloseşte codul generic de persoană fizică.
  // Plăţi vechi (billing_data gol / fără billing): câmpurile lipsesc -> comportamentul de dinainte.
  const b2c = (bi?: BillingInput | null): SmartbillClient => {
    const cnp = (bi?.cnp || "").trim();
    return {
      name: (p.full_name || "Client").trim() || "Client",
      ...(cnp ? { vatCode: cnp } : {}),
      isTaxPayer: false,
      ...((bi?.address || "").trim() ? { address: (bi!.address || "").trim() } : {}),
      ...((bi?.city || "").trim() ? { city: (bi!.city || "").trim() } : {}),
      ...((bi?.county || "").trim() ? { county: (bi!.county || "").trim() } : {}),
      country: "Romania",
      email: (p.email || "").trim(),
      saveToDb: false,
    };
  };

  // OPŢIUNEA 3 — persoană fizică (B2C)
  if (billing?.type === "individual") return b2c(billing);

  // OPŢIUNEA 2 — firmă cu date AD-HOC (din billing, NU din profil)
  if (billing?.type === "company_custom") {
    const cui = (billing.vatCode || "").trim();
    return {
      name: (billing.name || p.full_name || "Client").trim() || "Client",
      vatCode: cui || undefined,
      // ⚠️ `isTaxPayer` descrie CLIENTUL, nu pe noi, şi se deduce din prefixul „RO" al CUI-ului.
      // Un CUI scris fără prefix (ex. „46403400") marchează un plătitor de TVA drept NEplătitor.
      // Azi nu schimbă sumele, fiindcă Zynapse e neplătitoare şi emite cu taxPercentage 0 — dar în
      // ziua în care Zynapse devine plătitoare, câmpul ăsta decide taxarea, iar un CUI tastat fără
      // „RO" devine o factură greşită. De verificat la ANAF, nu de ghicit din text.
      isTaxPayer: /^ro/i.test(cui),
      address: (billing.address || "").trim() || undefined,
      // e-Factura cere localitatea (BT-52) şi judeţul (BT-54) pentru ORICE cumpărător, firmă sau
      // persoană. Până acum se trimiteau doar pe ramura B2C: pe firme se COLECTAU (sau nici atât)
      // şi se pierdeau aici, adică transmiterea în SPV pica fără ca nimeni să vadă.
      ...((billing.city || "").trim() ? { city: (billing.city || "").trim() } : {}),
      ...((billing.county || "").trim() ? { county: (billing.county || "").trim() } : {}),
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
                                             // (vezi nota de la `company_custom`: descrie CLIENTUL)
      address: (p.firma_adresa || "").trim() || undefined,
      // Judeţ + localitate vin din `billing`, nu din profil: `profiles` n-are coloane pentru ele,
      // aşa că se cer la checkout (şi se pre-completează din ultima plată). Vezi nota de mai sus.
      ...((billing?.city || "").trim() ? { city: (billing!.city || "").trim() } : {}),
      ...((billing?.county || "").trim() ? { county: (billing!.county || "").trim() } : {}),
      country: "Romania",                    // toți clienții sunt din România (platformă RO)
      email: (p.firma_email || p.email || "").trim(),
      saveToDb: false,
    };
  }
  return b2c();
}

/** Construiește payload-ul facturii. PUR (fără rețea) -> testabil. */
// ── SERIILE ─────────────────────────────────────────────────────────────────
// Contorul numerelor NU e la noi: îl ține SmartBill, per serie, iar `seriesName` se trimite în
// FIECARE cerere. Două serii au deci contoare independente prin construcție — n-avem ce sincroniza
// și n-avem cum să sărim sau să dublăm un număr din codul nostru.
// Structura de aici doar ALEGE seria. `credite` e singura folosită azi și citește exact aceeași
// variabilă ca înainte, deci factura de credite iese byte-identică.
export type SeriesKind = "credite" | "servicii";
const SERIES_ENV: Record<SeriesKind, string> = {
  credite: "SMARTBILL_SERIES",
  servicii: "SMARTBILL_SERIES_SERVICII",
};

/** Numele seriei pentru un tip de document, din env. Gol = neconfigurat (apelantul oprește). */
export function seriesFor(kind: SeriesKind = "credite"): string {
  return (process.env[SERIES_ENV[kind]] || "").trim();
}

export function buildInvoicePayload(
  profile: SmartbillProfile,
  payment: SmartbillPayment,
  opts?: { draft?: boolean; billing?: BillingInput | null; seriesKind?: SeriesKind;
           // `produs` inlocuieste DOAR linia de pe factura, pentru facturile de SERVICII (unde
           // descrierea o scrie Dan). Absent -> linia de credite, byte-identica cu ce era.
           produs?: { name: string; unit?: string } }
): SmartbillInvoicePayload {
  const price = Math.round(Number(payment.amount_ron) * 100) / 100;
  const adminName = (opts?.billing?.adminName || "").trim();
  return {
    companyVatCode: (process.env.SMARTBILL_VAT_CODE || "").trim(),
    client: mapSmartbillClient(profile, opts?.billing),
    issueDate: todayYmd(),
    seriesName: seriesFor(opts?.seriesKind),
    isDraft: opts?.draft === true,
    // nume administrator/reprezentant pe factură (SmartBill n-are câmp dedicat -> observations)
    ...(adminName ? { observations: `Reprezentant: ${adminName}` } : {}),
    products: [
      {
        name: opts?.produs?.name || `${payment.credits} Z-Coins — credite Zynapse`,
        measuringUnitName: opts?.produs?.unit || "buc",
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
  opts?: { draft?: boolean; billing?: BillingInput | null; seriesKind?: SeriesKind;
           produs?: { name: string; unit?: string } }
): Promise<SmartbillResult> {
  const username = (process.env.SMARTBILL_USERNAME || "").trim();
  const token = (process.env.SMARTBILL_TOKEN || "").trim();
  const vat = (process.env.SMARTBILL_VAT_CODE || "").trim();
  const kind: SeriesKind = opts?.seriesKind ?? "credite";
  const series = seriesFor(kind);
  // Seria cerută TREBUIE să fie configurată. Fără verificarea asta, o factură de servicii cu
  // `SMARTBILL_SERIES_SERVICII` nesetat ar cădea pe seria de credite și ar consuma un număr din ZN —
  // un document fiscal pe seria greșită, imposibil de retras altfel decât prin stornare.
  if (!username || !token || !vat || !series) {
    return { success: false, error: `SmartBill env lipsă (USERNAME/TOKEN/VAT_CODE/${SERIES_ENV[kind]})` };
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

// ── PDF-ul facturii ─────────────────────────────────────────────────────────
// Raspunsul la emitere NU contine PDF-ul: intoarce doar `series` + `number` (si `errorText` la
// eroare). Deci e nevoie de o A DOUA cerere, pe acelasi cont si cu aceleasi credentiale.
// Calea e confirmata din SDK-urile client publice (ag84ark/smartbill, `src/Endpoints/`):
//   GET /invoice/pdf?cif=%s&seriesname=%s&number=%s   cu `Accept: application/octet-stream`
// si intoarce PDF-ul BINAR, nu base64 si nu JSON.
// Documentatia web a SmartBill nu se poate citi programatic (pagina randeaza doar meniul), asa ca
// daca raspunsul nu e un PDF, se raporteaza inceputul lui ca text: e singurul fel in care se vede
// un „Unauthorized" sau un mesaj de eroare returnat cu 200.
export interface SmartbillPdfResult {
  success: boolean;
  pdfBase64?: string;
  error?: string;
  status?: number;
}

export async function fetchInvoicePdf(
  series: string,
  number: string,
  timeoutMs?: number,
): Promise<SmartbillPdfResult> {
  const username = (process.env.SMARTBILL_USERNAME || "").trim();
  const token = (process.env.SMARTBILL_TOKEN || "").trim();
  const vat = (process.env.SMARTBILL_VAT_CODE || "").trim();
  if (!username || !token || !vat) {
    return { success: false, error: "SmartBill env lipsă (USERNAME/TOKEN/VAT_CODE)" };
  }
  const s = (series || "").trim(), n = (number || "").trim();
  if (!s || !n) return { success: false, error: "serie sau număr lipsă" };

  const url = `${SMARTBILL_API}/invoice/pdf?cif=${encodeURIComponent(vat)}`
    + `&seriesname=${encodeURIComponent(s)}&number=${encodeURIComponent(n)}`;
  const auth = "Basic " + Buffer.from(`${username}:${token}`).toString("base64");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs || TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Authorization: auth, Accept: "application/octet-stream" },
      signal: controller.signal,
    });
    const buf = Buffer.from(await res.arrayBuffer());
    if (!res.ok) {
      return { success: false, status: res.status, error: buf.toString("utf-8").slice(0, 200) || `HTTP ${res.status}` };
    }
    // Un PDF incepe MEREU cu „%PDF". Fara verificarea asta, un mesaj de eroare returnat cu 200 ar
    // ajunge atasat la mail ca „factura" — clientul primeste un fisier care nu se deschide.
    if (buf.length < 5 || buf.subarray(0, 4).toString("ascii") !== "%PDF") {
      return { success: false, status: res.status,
               error: `răspuns care nu e PDF: ${buf.toString("utf-8").slice(0, 160)}` };
    }
    return { success: true, pdfBase64: buf.toString("base64"), status: res.status };
  } catch (e) {
    const msg = e instanceof Error && e.name === "AbortError" ? "SmartBill timeout"
              : e instanceof Error ? e.message : "eroare necunoscută";
    return { success: false, error: msg };
  } finally {
    clearTimeout(timer);
  }
}
