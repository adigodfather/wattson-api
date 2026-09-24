// ─── Trimiterea facturii pe email, de la noi ────────────────────────────────
// De ce de la noi şi nu de la SmartBill: SmartBill ARE un endpoint de email (`POST /document/send`)
// şi un buton manual în interfaţă, dar în ambele cazuri textul e al lor. Factura e primul document
// oficial pe care clientul îl primeşte de la firmă, aşa că textul rămâne al nostru.
//
// Resend, acelaşi furnizor ca la emailurile de autentificare. ATENŢIE: aplicaţia NU trimitea niciun
// email până acum — Resend era configurat în Supabase, nu aici. Deci `RESEND_API_KEY` trebuie ADĂUGAT
// în Vercel, iar `office@zynapse.org` trebuie să fie domeniu verificat în Resend. Fără cheie,
// funcţia NU tace: întoarce eroare, care ajunge în `payments.invoice_email_error` şi se vede în
// pagina de admin. Un pas automat care eşuează tăcut e exact ce nu vrem aici.
//
// API: POST https://api.resend.com/emails · Bearer · attachments: [{filename, content(base64)}]
// Limita Resend e 40 MB după codare base64; o factură PDF e de ordinul zecilor de KB.

const RESEND_API = "https://api.resend.com/emails";
const TIMEOUT_MS = 15000;
const FROM_IMPLICIT = "Zynapse <office@zynapse.org>";

export interface InvoiceEmailInput {
  to: string;
  clientName: string;
  series: string;
  number: string;
  amountRon: number | string;
  credits: number;
  pdfBase64: string;
}

export interface EmailResult {
  success: boolean;
  id?: string;
  error?: string;
  status?: number;
}

/** Textul facturii — PUR (fără reţea), ca să poată fi citit şi verificat fără să trimită nimic. */
export function invoiceEmailBody(i: InvoiceEmailInput): { subject: string; text: string; html: string } {
  const doc = `${i.series}${i.number}`;
  const suma = Number(i.amountRon).toFixed(2).replace(".", ",");
  const nume = (i.clientName || "").trim();
  const salut = nume ? `Bună ziua, ${nume},` : "Bună ziua,";
  const subject = `Factura ${doc} · Zynapse`;
  const linii = [
    salut,
    "",
    `Vă mulțumim pentru achiziție. Atașat găsiți factura ${doc}, în valoare de ${suma} lei, pentru ${i.credits} Z-Coins.`,
    "",
    "Pentru orice nelămurire legată de factură ne puteți scrie la office@zynapse.org.",
    "",
    "Zynapse",
    "office@zynapse.org · zynapse.org",
  ];
  const text = linii.join("\n");
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html =
    `<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;line-height:1.6;color:#1b1d23">`
    + linii.map(l => (l ? `<p style="margin:0 0 10px">${esc(l)}</p>` : "")).join("")
    + `</div>`;
  return { subject, text, html };
}

export async function sendInvoiceEmail(i: InvoiceEmailInput, timeoutMs?: number): Promise<EmailResult> {
  const key = (process.env.RESEND_API_KEY || "").trim();
  if (!key) return { success: false, error: "RESEND_API_KEY lipsă (de adăugat în Vercel)" };
  const to = (i.to || "").trim();
  if (!to) return { success: false, error: "adresă de email lipsă" };
  if (!i.pdfBase64) return { success: false, error: "PDF lipsă" };

  const { subject, text, html } = invoiceEmailBody(i);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs || TIMEOUT_MS);
  try {
    const res = await fetch(RESEND_API, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from: (process.env.INVOICE_EMAIL_FROM || "").trim() || FROM_IMPLICIT,
        to: [to],
        subject,
        text,
        html,
        attachments: [{
          filename: `Factura-${i.series}${i.number}.pdf`,
          content: i.pdfBase64,
          content_type: "application/pdf",
        }],
      }),
      signal: controller.signal,
    });
    const raw = await res.text();
    let data: Record<string, unknown> = {};
    try { data = raw ? (JSON.parse(raw) as Record<string, unknown>) : {}; } catch { /* non-JSON */ }
    if (!res.ok) {
      const m = data.message as string | undefined;
      const e = data.error as { message?: string } | undefined;
      return { success: false, status: res.status, error: (m || e?.message || raw.slice(0, 200) || `HTTP ${res.status}`) };
    }
    return { success: true, id: data.id != null ? String(data.id) : undefined, status: res.status };
  } catch (e) {
    const msg = e instanceof Error && e.name === "AbortError" ? "Resend timeout"
              : e instanceof Error ? e.message : "eroare necunoscută";
    return { success: false, error: msg };
  } finally {
    clearTimeout(timer);
  }
}
