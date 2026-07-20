"use client";

// ── Slider before/after (demo FIX, decizia Dan): arhitectura goala vs planul electric generat.
// BEFORE = /demo/before-arhitectura.png (stanga); AFTER = /demo/after-iluminat.png sau
// /demo/after-prize.png (dreapta, toggle). Cele 3 PNG-uri sunt randate din ACEEASI pagina PDF
// (aliniere pixel-perfect prin constructie — bucata 1). Bara verticala se trage stanga<->dreapta
// (pointer events: mouse + touch; touch-action pan-y = scroll-ul vertical al paginii ramane liber).
// Vanilla React, zero librarii; imagini statice din public/ (fara fetch, merge pe landing public).

import { useRef, useState, useCallback } from "react";

const BEFORE = "/demo/before-arhitectura.png";
const AFTERS = {
  iluminat: { src: "/demo/after-iluminat.png", label: "Plan iluminat" },
  prize:    { src: "/demo/after-prize.png",    label: "Plan prize" },
} as const;
type AfterKey = keyof typeof AFTERS;

export default function BeforeAfterSlider() {
  const [pos, setPos] = useState(50);                 // % din latime: stanga=BEFORE, dreapta=AFTER
  const [after, setAfter] = useState<AfterKey>("iluminat");
  const boxRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const moveTo = useCallback((clientX: number) => {
    const el = boxRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const p = ((clientX - r.left) / r.width) * 100;
    setPos(Math.max(2, Math.min(98, p)));             // bara nu iese din cadru
  }, []);

  return (
    <div>
      {/* toggle iluminat / prize — segmented, arata ce e activ */}
      <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 14 }}>
        {(Object.keys(AFTERS) as AfterKey[]).map(k => {
          const active = after === k;
          return (
            <button key={k} type="button" onClick={() => setAfter(k)} style={{
              padding: "8px 18px", borderRadius: 999, fontSize: 13, fontWeight: 700,
              fontFamily: "inherit", cursor: "pointer", letterSpacing: 0.2,
              color: active ? "#fff" : "#8B8FA8",
              background: active ? "linear-gradient(135deg, #378ADD, #5BB8F5)" : "rgba(255,255,255,0.04)",
              border: active ? "1px solid transparent" : "1px solid rgba(255,255,255,0.12)",
              transition: "all .15s ease",
            }}>{AFTERS[k].label}</button>
          );
        })}
      </div>

      {/* cadrul slider-ului: aspect-ratio-ul PNG-urilor (1652x1358) -> imaginile umplu exact */}
      <div
        ref={boxRef}
        onPointerDown={(e) => {
          dragging.current = true;
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          moveTo(e.clientX);
        }}
        onPointerMove={(e) => { if (dragging.current) moveTo(e.clientX); }}
        onPointerUp={() => { dragging.current = false; }}
        onPointerCancel={() => { dragging.current = false; }}
        style={{
          position: "relative", width: "100%", aspectRatio: "1652 / 1358",
          borderRadius: 16, overflow: "hidden", userSelect: "none",
          border: "1px solid rgba(255,255,255,0.1)", background: "#fff",
          boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
          touchAction: "pan-y", cursor: "ew-resize",
        }}
      >
        {/* BEFORE — strat de baza, integral */}
        <img src={BEFORE} alt="Planșa de arhitectură originală" draggable={false}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", pointerEvents: "none" }} />
        {/* AFTER — ambele pre-incarcate (toggle instant); activul se dezvaluie in DREAPTA barei */}
        {(Object.keys(AFTERS) as AfterKey[]).map(k => (
          <img key={k} src={AFTERS[k].src} alt={AFTERS[k].label + " generat de Zynapse"} draggable={false}
            style={{
              position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover",
              pointerEvents: "none", clipPath: `inset(0 0 0 ${pos}%)`,
              visibility: after === k ? "visible" : "hidden",
            }} />
        ))}

        {/* etichete discrete */}
        <span style={{
          position: "absolute", top: 10, left: 12, padding: "3px 10px", borderRadius: 999,
          fontSize: 10, fontWeight: 700, letterSpacing: 1, color: "#C5C8D6",
          background: "rgba(10,11,14,0.6)", pointerEvents: "none",
        }}>ARHITECTURĂ</span>
        <span style={{
          position: "absolute", top: 10, right: 12, padding: "3px 10px", borderRadius: 999,
          fontSize: 10, fontWeight: 700, letterSpacing: 1, color: "#9FD2FA",
          background: "rgba(10,11,14,0.6)", pointerEvents: "none",
        }}>{AFTERS[after].label.toUpperCase()}</span>

        {/* bara verticala + maner */}
        <div style={{
          position: "absolute", top: 0, bottom: 0, left: `${pos}%`, width: 0,
          borderLeft: "2px solid #5BB8F5", boxShadow: "0 0 12px rgba(91,184,245,0.55)",
          pointerEvents: "none",
        }}>
          <div style={{
            position: "absolute", top: "50%", left: 0, transform: "translate(-50%, -50%)",
            width: 36, height: 36, borderRadius: "50%",
            background: "rgba(10,11,14,0.85)", border: "2px solid #5BB8F5",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "#5BB8F5", fontSize: 15, fontWeight: 700,
            boxShadow: "0 2px 10px rgba(0,0,0,0.5)",
          }}>↔</div>
        </div>
      </div>
    </div>
  );
}
