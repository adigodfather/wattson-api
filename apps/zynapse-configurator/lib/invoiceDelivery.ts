// ─── Livrarea facturii: PDF de la SmartBill -> email de la noi -> urmă în bază ───────────────
// Rulează DUPĂ ce factura e deja emisă şi transmisă. Un eşec aici nu strică nimic — plata e
// încasată, factura există, creditele sunt date — dar TREBUIE să se vadă, altfel e exact tiparul
// „pas automat care eşuează tăcut".
//
// GARDA ANTI-DUBLARE e în bază, nu într-un `if`: un singur UPDATE condiţionat trece starea în
// 'sending' doar dacă era NULL sau 'failed', şi întoarce rândul. Din două cereri simultane (IPN
// repetat de Netopia), exact una primeşte rândul înapoi; cealaltă pleacă fără să trimită nimic.
// Un `if (!sent)` citit înainte de scris NU face asta.
//
// Se cheamă din DOUĂ locuri, de aceea stă aici şi nu în rută: IPN-ul (automat, după emitere) şi
// butonul de reîncercare din pagina de admin.

import type { SupabaseClient } from "@supabase/supabase-js";
import { fetchInvoicePdf, mapSmartbillClient, type BillingInput, type BillingType } from "./smartbill";
import { sendInvoiceEmail } from "./email/invoice";

export type DeliveryOutcome =
  | { status: "sent"; to: string }
  | { status: "failed"; error: string; to?: string }
  | { status: "skipped"; reason: string };

/** Adresa la care pleacă factura = EXACT cea pe care a primit-o SmartBill (`mapSmartbillClient`).
 *  Aşa clientul o primeşte unde scrie pe document, nu pe altă adresă.
 *  Pe `company_custom` emailul de facturare e OPŢIONAL: regula existentă cade pe emailul contului,
 *  şi o păstrăm — contul are mereu email (autentificarea îl cere), deci nu există caz „fără adresă".
 *  Nu inventăm niciodată o adresă. */
export function adresaFacturii(
  prof: Record<string, unknown> | null,
  billingType: string | null,
  billingData: Record<string, string> | null,
): { to: string; name: string } {
  const p = (prof || {}) as Parameters<typeof mapSmartbillClient>[0];
  const bd = billingData || {};
  const billing: BillingInput | undefined = billingType
    ? {
        type: billingType as BillingType,
        name: bd.name, vatCode: bd.vatCode, address: bd.address, email: bd.email,
        adminName: bd.admin_name, county: bd.county, city: bd.city, cnp: bd.cnp,
      }
    : undefined;
  const c = mapSmartbillClient(p, billing);
  return { to: (c.email || "").trim(), name: (c.name || "").trim() };
}

export async function deliverInvoiceEmail(
  admin: SupabaseClient,
  orderId: string,
  opts?: { force?: boolean; timeoutMs?: number },
): Promise<DeliveryOutcome> {
  // 1. CLAIM atomic. `force` (doar din admin) reia şi un 'sending' rămas agăţat după un proces
  //    căzut la mijloc — altfel factura aia n-ar mai putea fi trimisă niciodată.
  const stariReluabile = opts?.force
    ? "invoice_email_status.is.null,invoice_email_status.eq.failed,invoice_email_status.eq.sending"
    : "invoice_email_status.is.null,invoice_email_status.eq.failed";
  const { data: claimed, error: claimErr } = await admin
    .from("payments")
    .update({ invoice_email_status: "sending" })
    .eq("order_id", orderId)
    .eq("invoiced", true)
    .or(stariReluabile)
    .select("order_id, user_id, amount_ron, credits, billing_type, billing_data, invoice_series, invoice_number, invoice_email_attempts");
  if (claimErr) return { status: "failed", error: `claim: ${claimErr.message}` };
  if (!claimed?.length) return { status: "skipped", reason: "deja trimisă sau în curs (sau nefacturată)" };
  const pay = claimed[0] as Record<string, unknown>;
  const incercari = Number(pay.invoice_email_attempts || 0) + 1;

  const marcheaza = async (patch: Record<string, unknown>) => {
    await admin.from("payments")
      .update({ invoice_email_attempts: incercari, ...patch })
      .eq("order_id", orderId);
  };

  const serie = String(pay.invoice_series || "").trim();
  const numar = String(pay.invoice_number || "").trim();
  if (!serie || !numar) {
    const error = "seria/numărul facturii lipsesc din plată";
    await marcheaza({ invoice_email_status: "failed", invoice_email_error: error });
    return { status: "failed", error };
  }

  // 2. Destinatarul
  const { data: prof } = await admin
    .from("profiles")
    .select("email, full_name, firma_nume, firma_cui, firma_adresa, firma_email")
    .eq("id", pay.user_id as string)
    .single();
  const { to, name } = adresaFacturii(prof, (pay.billing_type as string) || null,
                                      (pay.billing_data as Record<string, string>) || null);
  if (!to) {
    const error = "clientul n-are nicio adresă de email";
    await marcheaza({ invoice_email_status: "failed", invoice_email_error: error });
    return { status: "failed", error };
  }

  // 3. PDF-ul
  const pdf = await fetchInvoicePdf(serie, numar, opts?.timeoutMs);
  if (!pdf.success || !pdf.pdfBase64) {
    const error = `PDF: ${pdf.error || "necunoscut"}`;
    await marcheaza({ invoice_email_status: "failed", invoice_email_error: error, invoice_email_to: to });
    return { status: "failed", error, to };
  }

  // 4. Emailul
  const mail = await sendInvoiceEmail({
    to, clientName: name, series: serie, number: numar,
    amountRon: pay.amount_ron as number, credits: Number(pay.credits || 0),
    pdfBase64: pdf.pdfBase64,
  }, opts?.timeoutMs);
  if (!mail.success) {
    const error = `email: ${mail.error || "necunoscut"}`;
    await marcheaza({ invoice_email_status: "failed", invoice_email_error: error, invoice_email_to: to });
    return { status: "failed", error, to };
  }

  await marcheaza({
    invoice_email_status: "sent",
    invoice_email_to: to,
    invoice_email_at: new Date().toISOString(),
    invoice_email_error: null,
  });
  return { status: "sent", to };
}
