// ─── Netopia mobilPay v1 — XML cerere + parse IPN + răspuns CRC ──────────────
import { XMLParser } from "fast-xml-parser";

function esc(s: string): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Timestamp Netopia: YYYYMMDDhhmmss (UTC). */
export function netopiaTimestamp(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    d.getUTCFullYear().toString() +
    p(d.getUTCMonth() + 1) +
    p(d.getUTCDate()) +
    p(d.getUTCHours()) +
    p(d.getUTCMinutes()) +
    p(d.getUTCSeconds())
  );
}

export interface PaymentXmlParams {
  orderId: string;
  amount: string;        // 2 zecimale, ex "222.00"
  currency: string;      // "RON"
  details: string;       // descriere
  signature: string;     // POS signature
  confirmUrl: string;    // IPN
  returnUrl: string;     // redirect user
  timestamp: string;     // YYYYMMDDhhmmss
  billing: {
    firstName: string;
    lastName: string;
    email: string;
    phone: string;
    address?: string;
  };
}

/** Construiește XML-ul de cerere mobilPay v1 (tip card), cu ipn_cipher aes-256-cbc. */
export function buildPaymentXml(p: PaymentXmlParams): string {
  const b = p.billing;
  return (
    `<?xml version="1.0" encoding="utf-8"?>` +
    `<order type="card" id="${esc(p.orderId)}" timestamp="${esc(p.timestamp)}">` +
    `<signature>${esc(p.signature)}</signature>` +
    `<invoice currency="${esc(p.currency)}" amount="${esc(p.amount)}">` +
    `<details>${esc(p.details)}</details>` +
    `<contact_info>` +
    `<billing type="person">` +
    `<first_name>${esc(b.firstName)}</first_name>` +
    `<last_name>${esc(b.lastName)}</last_name>` +
    `<email>${esc(b.email)}</email>` +
    `<mobile_phone>${esc(b.phone)}</mobile_phone>` +
    `<address>${esc(b.address || "")}</address>` +
    `</billing>` +
    `</contact_info>` +
    `</invoice>` +
    `<ipn_cipher>aes-256-cbc</ipn_cipher>` +
    `<url>` +
    `<confirm>${esc(p.confirmUrl)}</confirm>` +
    `<return>${esc(p.returnUrl)}</return>` +
    `</url>` +
    `</order>`
  );
}

export interface ParsedIpn {
  orderId: string | null;
  action: string | null;          // confirmed | paid | canceled | credit | ...
  errorCode: string | null;       // "0" = ok
  errorMessage: string | null;
  processedAmount: number | null; // suma procesată (anti-tampering)
  originalAmount: number | null;
  crc: string | null;
  raw: unknown;                    // obiectul parsat (pt. audit)
}

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: "@_",
  textNodeName: "#text",
  parseAttributeValue: false,
  trimValues: true,
});

function num(v: unknown): number | null {
  if (v === undefined || v === null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Parsează XML-ul IPN decriptat și extrage câmpurile relevante. */
export function parseIpnXml(xml: string): ParsedIpn {
  const obj = parser.parse(xml);
  const order = obj?.order ?? {};
  const mob = order?.mobilpay ?? {};
  const err = mob?.error;
  let errorCode: string | null = null;
  let errorMessage: string | null = null;
  if (err && typeof err === "object") {
    errorCode = err["@_code"] != null ? String(err["@_code"]) : null;
    errorMessage = err["#text"] != null ? String(err["#text"]) : null;
  } else if (typeof err === "string") {
    errorMessage = err;
  }
  return {
    orderId: order["@_id"] != null ? String(order["@_id"]) : null,
    action: mob.action != null ? String(mob.action) : null,
    errorCode,
    errorMessage,
    processedAmount: num(mob.processed_amount),
    originalAmount: num(mob.original_amount),
    crc: mob["@_crc"] != null ? String(mob["@_crc"]) : null,
    raw: obj,
  };
}

/** Răspuns CRC cerut de Netopia după IPN.
 *  succes -> <crc>val</crc>; eroare temporară (retry) -> error_type=1;
 *  eroare permanentă -> error_type=2. */
export function buildIpnResponse(opts?: {
  crc?: string | null;
  errorType?: 1 | 2;
  errorCode?: string;
  message?: string;
}): string {
  const head = `<?xml version="1.0" encoding="utf-8"?>`;
  if (opts?.errorType) {
    return (
      head +
      `<crc error_type="${opts.errorType}" error_code="${esc(opts.errorCode || "0x01")}">` +
      `${esc(opts.message || "error")}</crc>`
    );
  }
  return head + `<crc>${esc(opts?.crc || "")}</crc>`;
}
