"use client";

// ─── Cloudflare Turnstile (protecție anti-bot la signup) ─────────────────────
// De ce Turnstile și nu hCaptcha: gratuit FĂRĂ limită de volum, invizibil în majoritatea
// cazurilor (userul real nu rezolvă nimic), fără cookie de tracking. Verificarea token-ului
// o face SUPABASE server-side (Auth → Bot and Abuse Protection), nu noi — noi doar producem
// token-ul și-l trimitem în signUp({ options: { captchaToken } }).
//
// Randare EXPLICITĂ (?render=explicit): în React, varianta cu auto-render pe `.cf-turnstile`
// se dublează la re-render/StrictMode. Aici widget-ul e creat o singură dată și curățat la unmount.

import { useEffect, useRef } from "react";

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
          callback: (t: string) => onTokenRef.current(t),
          "error-callback": () => { onTokenRef.current(""); onErrorRef.current?.(); },
          "expired-callback": () => onTokenRef.current(""),   // token expirat -> se cere din nou
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
