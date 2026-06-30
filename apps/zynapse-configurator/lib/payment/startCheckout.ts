// ─── Checkout Netopia (client) ───────────────────────────────────────────────
// Mecanism UNIC de pornire a plății, folosit de carduri (home) și de calculator.
// POST /api/payment/start -> primește HTML-ul cu formular auto-submit -> îl
// reconstruiește și-l submite (navigare top-level spre Netopia).
"use client";

/** Reconstruiește formularul auto-submit returnat de rută și-l trimite spre Netopia. */
function submitNetopiaForm(html: string) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const srcForm = doc.querySelector("form");
  if (!srcForm) { document.open(); document.write(html); document.close(); return; }
  const form = document.createElement("form");
  form.method = "post";
  form.action = srcForm.getAttribute("action") || "";
  srcForm.querySelectorAll("input").forEach((inp) => {
    const el = document.createElement("input");
    el.type = "hidden";
    el.name = inp.getAttribute("name") || "";
    el.value = inp.getAttribute("value") || "";
    form.appendChild(el);
  });
  document.body.appendChild(form);
  form.submit();
}

// Alegerea de facturare (gate Home) — trimisă la /api/payment/start (validată server-side).
export interface BillingChoice {
  type: "company_profile" | "company_custom" | "individual";
  name?: string;       // company_custom: denumire firmă
  vatCode?: string;    // company_custom: CIF
  address?: string;    // company_custom: adresă
  email?: string;      // company_custom: email facturare
  adminName?: string;  // nume administrator/reprezentant -> "Reprezentant: X" pe factură
}

// Mod pachet fix SAU sumă liberă (doar numărul de credite; prețul se calculează server-side) + facturare.
// billing OPŢIONAL în tip (gate-ul real e SERVER-SIDE în /api/payment/start); G5 îl trimite mereu din modal.
export type CheckoutBody = ({ packageId: string } | { credits: number }) & { billing?: BillingChoice };

export interface CheckoutResult {
  ok: boolean;           // true -> a pornit navigarea spre Netopia (pagina se schimbă)
  authRequired?: boolean; // 401 -> trimite userul la /login
  error?: string;        // mesaj de afișat dacă pornirea a eșuat
}

/** Pornește plata: trimite body-ul la rută și redirectează spre Netopia.
 *  La succes pagina navighează (nu mai revine). */
export async function startCheckout(body: CheckoutBody): Promise<CheckoutResult> {
  try {
    const res = await fetch("/api/payment/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.status === 401) return { ok: false, authRequired: true };
    if (!res.ok) {
      let error = "Nu am putut iniția plata. Încearcă din nou.";
      try { const j = await res.json(); if (j?.error) error = String(j.error); } catch { /* gol */ }
      return { ok: false, error };
    }
    const html = await res.text();
    submitNetopiaForm(html);
    return { ok: true };
  } catch {
    return { ok: false, error: "Eroare de rețea. Încearcă din nou." };
  }
}
