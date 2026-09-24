// ─── Facturi de SERVICII: emitere pe seria proprie + livrare pe email ───────
// Creditele raman neatinse: alt tabel (`payments`), alta serie (ZN), alt drum. Aici se factureaza
// automatizari, softuri, site-uri — pe seria configurata in `SMARTBILL_SERIES_SERVICII`.
//
// Orchestrarea e DUPLICATA fata de `invoiceDelivery.ts`, dinadins: aceea lucreaza pe `payments` si
// e LIVE pe banii din credite. A o generaliza ca sa acopere si tabelul asta ar fi insemnat s-o
// rescriu sub un flux care incaseaza deja. Bucatile care conteaza (PDF, email, tiparul de claim)
// sunt aceleasi functii; se repeta doar ~40 de linii de marcaj pe alt tabel.

import type { SupabaseClient } from "@supabase/supabase-js";
import { createInvoice, fetchInvoicePdf, type BillingInput } from "./smartbill";
import { sendInvoiceEmail } from "./email/invoice";

export interface ClientServiciu {
  id: string;
  denumire: string;
  cui: string;
  adresa: string;
  judet: string;
  localitate: string;
  email: string;
}

export type RezultatFactura =
  | { status: "emisa"; serie: string; numar: string; email: "sent" | "failed"; eroareEmail?: string }
  | { status: "esuata"; error: string }
  | { status: "sarita"; motiv: string };

/** Clientul de servicii -> forma pe care o stie deja `mapSmartbillClient` (ramura de firma ad-hoc).
 *  Asa judetul si localitatea ajung la SmartBill pe acelasi drum ca la credite, cu acelasi fix. */
function billingDinClient(c: ClientServiciu): BillingInput {
  return {
    type: "company_custom",
    name: c.denumire, vatCode: c.cui, address: c.adresa,
    county: c.judet, city: c.localitate, email: c.email,
  };
}

/** Livrarea PDF + email pentru o factura de servicii. Claim ATOMIC, ca la credite. */
export async function livreazaFacturaServiciu(
  admin: SupabaseClient, facturaId: string, opts?: { force?: boolean; timeoutMs?: number },
): Promise<{ status: "sent" | "failed" | "skipped"; to?: string; error?: string }> {
  const reluabile = opts?.force
    ? "invoice_email_status.is.null,invoice_email_status.eq.failed,invoice_email_status.eq.sending"
    : "invoice_email_status.is.null,invoice_email_status.eq.failed";
  const { data: claimed } = await admin
    .from("facturi_servicii")
    .update({ invoice_email_status: "sending" })
    .eq("id", facturaId).eq("status", "emisa").or(reluabile)
    .select("id, client_id, descriere, suma_ron, serie, numar, invoice_email_attempts");
  if (!claimed?.length) return { status: "skipped", error: "deja trimisă sau în curs (sau neemisă)" };
  const f = claimed[0] as Record<string, unknown>;
  const incercari = Number(f.invoice_email_attempts || 0) + 1;
  const marcheaza = async (patch: Record<string, unknown>) =>
    void (await admin.from("facturi_servicii")
      .update({ invoice_email_attempts: incercari, ...patch }).eq("id", facturaId));

  const { data: cl } = await admin.from("clienti_servicii")
    .select("denumire, email").eq("id", f.client_id as string).single();
  const to = String((cl as Record<string, string> | null)?.email || "").trim();
  if (!to) {
    const error = "clientul n-are adresă de email";
    await marcheaza({ invoice_email_status: "failed", invoice_email_error: error });
    return { status: "failed", error };
  }

  const pdf = await fetchInvoicePdf(String(f.serie || ""), String(f.numar || ""), opts?.timeoutMs);
  if (!pdf.success || !pdf.pdfBase64) {
    const error = `PDF: ${pdf.error || "necunoscut"}`;
    await marcheaza({ invoice_email_status: "failed", invoice_email_error: error, invoice_email_to: to });
    return { status: "failed", error, to };
  }
  const mail = await sendInvoiceEmail({
    to, clientName: String((cl as Record<string, string> | null)?.denumire || ""),
    series: String(f.serie || ""), number: String(f.numar || ""),
    amountRon: f.suma_ron as number, credits: 0, pdfBase64: pdf.pdfBase64,
  }, opts?.timeoutMs);
  if (!mail.success) {
    const error = `email: ${mail.error || "necunoscut"}`;
    await marcheaza({ invoice_email_status: "failed", invoice_email_error: error, invoice_email_to: to });
    return { status: "failed", error, to };
  }
  await marcheaza({ invoice_email_status: "sent", invoice_email_to: to,
                    invoice_email_at: new Date().toISOString(), invoice_email_error: null });
  return { status: "sent", to };
}

/** Emite in SmartBill o factura deja INSERATA (status 'pending'), apoi o trimite.
 *  Emiterea si trimiterea sunt UN SINGUR pas, cum a cerut Dan — butonul de reincercare din admin
 *  ramane pentru esecuri. */
export async function emiteSiTrimite(
  admin: SupabaseClient, facturaId: string, opts?: { timeoutMs?: number },
): Promise<RezultatFactura> {
  // CLAIM atomic pe emitere: randul trece din 'pending' in 'emitere' intr-o singura instructiune.
  // Fara asta, doua rulari ale fluxului zilnic peste acelasi rand ar chema SmartBill de doua ori —
  // iar o factura fiscala emisa de doua ori nu se sterge, se storneaza.
  const { data: claimed } = await admin
    .from("facturi_servicii").update({ status: "emitere" })
    .eq("id", facturaId).eq("status", "pending")
    .select("id, client_id, descriere, suma_ron");
  if (!claimed?.length) return { status: "sarita", motiv: "factura nu e în starea 'pending'" };
  const f = claimed[0] as Record<string, unknown>;

  const { data: cl } = await admin.from("clienti_servicii")
    .select("id, denumire, cui, adresa, judet, localitate, email")
    .eq("id", f.client_id as string).single();
  if (!cl) {
    const error = "clientul facturii nu mai există";
    await admin.from("facturi_servicii").update({ status: "esuata", smartbill_error: error }).eq("id", facturaId);
    return { status: "esuata", error };
  }

  const inv = await createInvoice(
    { email: (cl as ClientServiciu).email },
    { amount_ron: f.suma_ron as number, credits: 0, order_id: facturaId },
    { draft: false, billing: billingDinClient(cl as ClientServiciu), seriesKind: "servicii",
      produs: { name: String(f.descriere || "Servicii") } },
  );
  if (!inv.success || !inv.invoiceNumber) {
    const error = inv.error || "SmartBill a răspuns fără număr";
    await admin.from("facturi_servicii")
      .update({ status: "esuata", smartbill_error: error }).eq("id", facturaId);
    return { status: "esuata", error };
  }
  await admin.from("facturi_servicii").update({
    status: "emisa", serie: inv.series ?? null, numar: inv.invoiceNumber,
    emisa_at: new Date().toISOString(), smartbill_error: null,
  }).eq("id", facturaId);

  const liv = await livreazaFacturaServiciu(admin, facturaId, { timeoutMs: opts?.timeoutMs });
  return { status: "emisa", serie: inv.series ?? "", numar: inv.invoiceNumber,
           email: liv.status === "sent" ? "sent" : "failed",
           ...(liv.status === "sent" ? {} : { eroareEmail: liv.error }) };
}

/** Ziua de azi in fusul Romaniei, ca scadenta sa nu sara o zi din cauza UTC. */
export function aziRo(acum?: Date): { zi: number; perioada: string; iso: string } {
  const d = acum || new Date();
  const ro = new Date(d.toLocaleString("en-US", { timeZone: "Europe/Bucharest" }));
  const p = (n: number) => String(n).padStart(2, "0");
  return { zi: ro.getDate(), perioada: `${ro.getFullYear()}-${p(ro.getMonth() + 1)}`,
           iso: `${ro.getFullYear()}-${p(ro.getMonth() + 1)}-${p(ro.getDate())}` };
}

/** Fluxul ZILNIC: emite ce e scadent azi. Idempotent prin indexul unic (abonament, perioada). */
export async function ruleazaAbonamente(
  admin: SupabaseClient, acum?: Date,
): Promise<{ scadente: number; emise: number; sarite: number; esuate: number; detalii: string[] }> {
  const { zi, perioada, iso } = aziRo(acum);
  const detalii: string[] = [];
  const { data: abos } = await admin
    .from("abonamente_servicii")
    .select("id, client_id, descriere, suma_ron")
    .eq("activ", true).eq("zi_emitere", zi).lte("data_start", iso);
  const lista = (abos || []) as Array<Record<string, unknown>>;
  let emise = 0, sarite = 0, esuate = 0;

  // Rezultatul fiecarui abonament se scrie PE ABONAMENT, nu doar pe randul de factura: intrebarea
  // pe care si-o pune Dan nu e „ce factura a picat", ci „care abonament nu si-a facut treaba".
  const marcheazaAbonament = async (id: string, patch: Record<string, unknown>) =>
    void (await admin.from("abonamente_servicii")
      .update({ ultima_rulare_at: new Date().toISOString(), ...patch }).eq("id", id));

  for (const a of lista) {
    // INSERAREA E GARDA: indexul unic (abonament_id, perioada) respinge a doua incercare din
    // aceeasi luna, chiar daca fluxul ruleaza de doua ori in paralel. Se insereaza INAINTE de
    // orice apel la SmartBill, deci o factura nu poate fi emisa de doua ori.
    const { data: f, error } = await admin.from("facturi_servicii").insert({
      client_id: a.client_id, abonament_id: a.id, perioada,
      descriere: `${String(a.descriere)} — ${perioada}`, suma_ron: a.suma_ron,
    }).select("id").single();
    if (error || !f) {
      // Deja facturat luna asta NU e esec — e chiar garda care si-a facut treaba.
      sarite++;
      await marcheazaAbonament(String(a.id), { ultima_eroare: null, ultima_perioada: perioada });
      detalii.push(`abonament ${String(a.id).slice(0, 8)}: deja facturat pe ${perioada}`);
      continue;
    }
    const r = await emiteSiTrimite(admin, (f as { id: string }).id);
    if (r.status === "emisa") {
      emise++;
      // Factura a iesit. Daca EMAILUL n-a plecat, nu e un esec al abonamentului (factura exista si
      // se retrimite din buton), dar se scrie pe abonament ca sa nu ramana nevazut.
      await marcheazaAbonament(String(a.id), {
        ultima_perioada: perioada,
        ultima_eroare: r.email === "sent" ? null : `factura ${r.serie}${r.numar} emisă, dar emailul n-a plecat: ${r.eroareEmail ?? "necunoscut"}`,
      });
      detalii.push(`abonament ${String(a.id).slice(0, 8)}: ${r.serie}${r.numar}, email ${r.email}`);
    } else {
      esuate++;
      const motiv = "error" in r ? r.error : r.motiv;
      await marcheazaAbonament(String(a.id), { ultima_eroare: motiv });
      detalii.push(`abonament ${String(a.id).slice(0, 8)}: EȘUAT — ${motiv}`);
    }
  }
  return { scadente: lista.length, emise, sarite, esuate, detalii };
}
