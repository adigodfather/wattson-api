"use client";

// ─── Cloudflare Turnstile (protecție anti-bot la signup) ─────────────────────
// De ce Turnstile și nu hCaptcha: gratuit FĂRĂ limită de volum, invizibil în majoritatea
// cazurilor (userul real nu rezolvă nimic), fără cookie de tracking. Verificarea token-ului
// o face SUPABASE server-side (Auth → Bot and Abuse Protection), nu noi — noi doar producem
// token-ul și-l trimitem în signUp({ options: { captchaToken } }).
//
// Randare EXPLICITĂ (?render=explicit): în React, varianta cu auto-render pe `.cf-turnstile`
// se dublează la re-render/StrictMode. Aici widget-ul e creat o singură dată și curățat la unmount.

import { useCallback, useEffect, useRef, useState } from "react";

type TurnstileApi = {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  remove: (id: string) => void;
  reset: (id?: string) => void;
};
declare global {
  interface Window { turnstile?: TurnstileApi }
}

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export default function TurnstileWidget({
  siteKey, onToken, onError,
}: {
  siteKey: string;
  onToken: (token: string) => void;
  onError?: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  // callback-urile prin ref -> efectul NU se re-execută când părintele se re-randează
  const onTokenRef = useRef(onToken);
  const onErrorRef = useRef(onError);
  onTokenRef.current = onToken;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!siteKey) return;                       // fără cheie -> widget inexistent (fallback)
    let cancelled = false;

    const render = () => {
      if (cancelled || widgetIdRef.current || !boxRef.current || !window.turnstile) return;
      try {
        widgetIdRef.current = window.turnstile.render(boxRef.current, {
          sitekey: siteKey,
          theme: "dark",                        // tema platformei (#0A0B0E)
          language: "ro",
          // Tokenul Turnstile expira in 300s si e de UNICA folosinta. Daca userul lasa pagina
          // deschisa si se logheaza mai tarziu, tokenul vechi -> "invalid-input-response".
          // refresh-expired:auto => widgetul isi ia singur token nou la expirare (userul nu face nimic).
          "refresh-expired": "auto",
          retry: "auto",                        // eroare de retea -> reincearca singur
          "retry-interval": 2000,
          callback: (t: string) => onTokenRef.current(t),
          "error-callback": () => { onTokenRef.current(""); onErrorRef.current?.(); },
          // expirat -> golim tokenul din state (gate-ul opreste submit-ul pana vine unul nou)
          "expired-callback": () => onTokenRef.current(""),
          // dupa `reset()` widgetul poate cere din nou interactiune -> tokenul vechi nu mai e valid
          "timeout-callback": () => onTokenRef.current(""),
        });
      } catch { onErrorRef.current?.(); }
    };

    if (window.turnstile) {
      render();
    } else {
      let s = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
      if (!s) {
        s = document.createElement("script");
        s.src = SCRIPT_SRC;
        s.async = true;
        s.defer = true;
        document.head.appendChild(s);
      }
      s.addEventListener("load", render);
      s.addEventListener("error", () => onErrorRef.current?.());
    }

    return () => {
      cancelled = true;
      if (widgetIdRef.current && window.turnstile?.remove) {
        try { window.turnstile.remove(widgetIdRef.current); } catch { /* deja curatat */ }
      }
      widgetIdRef.current = null;
    };
  }, [siteKey]);

  if (!siteKey) return null;
  return <div ref={boxRef} style={{ minHeight: 65 }} />;
}

// ─── useTurnstile — CAPTCHA pentru orice flux de auth ────────────────────────
// Setarea din Supabase (Attack Protection) e GLOBALĂ: se aplică la TOATE endpoint-urile
// publice de auth, nu doar la signup. Orice pagină care cheamă signInWithPassword /
// resetPasswordForEmail trebuie să trimită token, altfel Supabase respinge cu
// "captcha protection: request disallowed". Hook-ul ține state-ul + widget-ul într-un
// singur loc, ca să nu se mai uite un flux.
//
// FALLBACK: fără NEXT_PUBLIC_TURNSTILE_SITE_KEY -> `required` false, `widget` null,
// `token` "" -> apelantul nu trimite captchaToken și fluxul merge exact ca înainte.
const SITE_KEY = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();

/** Eroarea bruta de la Supabase cand tokenul e expirat/consumat/respins de Cloudflare
 *  ("captcha protection: request disallowed (invalid-input-response)") -> mesaj pentru om. */
export function captchaErrorMessage(raw: string): string | null {
  const m = (raw || "").toLowerCase();
  if (!m.includes("captcha")) return null;
  return "Verificarea de securitate a expirat. Am reîncărcat-o — mai încearcă o dată.";
}

export function useTurnstile(onFail?: (msg: string) => void) {
  const [token, setToken] = useState("");
  const [nonce, setNonce] = useState(0);       // schimbat -> widget remontat (token NOU)

  // token-ul Turnstile e de UNICĂ folosință: după orice apel eșuat trebuie regenerat
  const reset = useCallback(() => { setToken(""); setNonce(n => n + 1); }, []);

  const widget = SITE_KEY ? (
    <TurnstileWidget
      key={nonce}
      siteKey={SITE_KEY}
      onToken={setToken}
      onError={() => onFail?.("Verificarea de securitate a eșuat. Reîncarcă pagina și încearcă din nou.")}
    />
  ) : null;

  return {
    token,
    reset,
    required: !!SITE_KEY,                       // true -> gate pe token înainte de submit
    widget,
    /** de pus în `options` la apelul de auth: { ...captchaOption } */
    captchaOption: token ? { captchaToken: token } : {},
  };
}
