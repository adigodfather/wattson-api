"use client";

import { useState } from "react";

// TODO: ajustează prețul/Z-Coins calculatorului
const CREDIT_PRICING = {
  perM2: { dtac: 1, pt: 2 },   // Z-Coins/mp: DTAC = 1, PT = 2 (DTAC+PT = 3)
  pricePerCredit: 0.50,        // lei/Z-Coin — preț fix, fără reducere la volum
};

const DELIVERABLES_BY_PHASE: Record<"dtac" | "dtac_pt", { title: string; sub: string; items: string[] }> = {
  dtac: {
    title: "Ce primești la DTAC",
    sub: "Documentație Tehnică pentru Autorizația de Construire",
    items: ["Scheme monofilare", "Memoriu tehnic"],
  },
  dtac_pt: {
    title: "Ce primești la DTAC + PT",
    sub: "Proiect Tehnic complet, pentru execuție",
    items: [
      "Planuri de iluminat",
      "Planuri de forță (prize)",
      "Scheme monofilare",
      "Scheme de distribuție",
      "Memoriu tehnic amplu (cu program de control și faze determinante)",
      "Caiet de sarcini",
      "Breviar de calcul",
      "Liste de cantități",
    ],
  },
};

/* Card „Ce primești" — dinamic după faza selectată în calculator (doar citire) */
function CeprimestiCard({ phase }: { phase: "dtac" | "dtac_pt" }) {
  const d = DELIVERABLES_BY_PHASE[phase];
  return (
    <div key={phase} className="cefade-card" style={{
      padding: "26px 26px", borderRadius: 18, height: "100%",
      background: "rgba(55,138,221,0.06)", border: "1px solid rgba(55,138,221,0.22)",
      boxShadow: "0 0 30px rgba(55,138,221,0.06)",
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#5BB8F5" }}>{d.title}</div>
      <div style={{ fontSize: 12.5, color: "#777", margin: "4px 0 18px", lineHeight: 1.5 }}>{d.sub}</div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 11 }}>
        {d.items.map(it => (
          <li key={it} style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: 14, color: "#cfd3df", lineHeight: 1.5 }}>
            <span style={{ color: "#5BB8F5", flexShrink: 0 }}>▸</span>{it}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* Calculator de Z-Coins — pur de prezentare (calcul local, fara apel extern) */
function CreditCalculator({ phase, setPhase }: { phase: "dtac" | "dtac_pt"; setPhase: (p: "dtac" | "dtac_pt") => void }) {
  const [area, setArea] = useState<number>(1000);

  const perM2 = phase === "dtac_pt"
    ? CREDIT_PRICING.perM2.dtac + CREDIT_PRICING.perM2.pt
    : CREDIT_PRICING.perM2.dtac;
  const credits = Math.max(0, Math.round(area * perM2));
  const pricePerCredit = CREDIT_PRICING.pricePerCredit;
  const totalLei = credits * pricePerCredit;

  const fmtLei = (n: number) => n.toLocaleString("ro-RO", { maximumFractionDigits: 2 });
  const fmtCredit = (n: number) => n.toFixed(2).replace(".", ",");

  const phaseBtn = (val: "dtac" | "dtac_pt", label: string) => {
    const active = phase === val;
    return (
      <button type="button" onClick={() => setPhase(val)} style={{
        flex: 1, padding: "10px 14px", borderRadius: 10, fontSize: 14, fontWeight: 600,
        cursor: "pointer", fontFamily: "inherit", transition: "all .2s",
        background: active ? "linear-gradient(135deg, #378ADD, #5BB8F5)" : "rgba(255,255,255,0.03)",
        border: active ? "1px solid transparent" : "1px solid rgba(255,255,255,0.08)",
        color: active ? "#fff" : "#888",
      }}>{label}</button>
    );
  };

  return (
    <div style={{
      maxWidth: 560, margin: "0 auto", padding: "28px 28px 24px", borderRadius: 18,
      background: "rgba(55,138,221,0.04)", border: "1px solid rgba(55,138,221,0.16)",
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#5BB8F5", letterSpacing: .5, textAlign: "center" }}>
        CALCULATOR Z-COINS
      </div>
      <div style={{ fontSize: 13, color: "#666", textAlign: "center", margin: "4px 0 20px" }}>
        Estimează Z-Coins și costul proiectului tău
      </div>

      <div style={{ fontSize: 11, fontWeight: 600, color: "#777", letterSpacing: .5, marginBottom: 8 }}>FAZA</div>
      <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
        {phaseBtn("dtac", "DTAC")}
        {phaseBtn("dtac_pt", "DTAC + PT")}
      </div>

      <label htmlFor="cc-area" style={{ display: "block", fontSize: 11, fontWeight: 600, color: "#777", letterSpacing: .5, marginBottom: 8 }}>
        SUPRAFAȚĂ CONSTRUITĂ (mp)
      </label>
      <input id="cc-area" type="number" min={0} step={10} value={area || ""} placeholder="ex: 1000"
        onChange={e => setArea(Math.max(0, parseFloat(e.target.value) || 0))}
        style={{
          width: "100%", padding: "12px 14px", borderRadius: 10, fontSize: 16, fontFamily: "inherit",
          background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff",
          outline: "none", marginBottom: 22, boxSizing: "border-box",
        }} />

      <div style={{
        padding: "18px 20px", borderRadius: 12, textAlign: "center",
        background: "rgba(55,138,221,0.07)", border: "1px solid rgba(55,138,221,0.2)",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 30, fontWeight: 700, color: "#fff", letterSpacing: -.5, display: "inline-flex", alignItems: "center", gap: 7 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/z-coin.svg" alt="" width={26} height={26} style={{ display: "block" }} />
            {credits.toLocaleString("ro-RO")}<span style={{ fontSize: 15, fontWeight: 500, color: "#5BB8F5", marginLeft: 6 }}>Z-Coins</span>
          </span>
          <span style={{ fontSize: 18, color: "#444" }}>·</span>
          <span style={{ fontSize: 30, fontWeight: 700, color: "#fff", letterSpacing: -.5 }}>
            {fmtLei(totalLei)}<span style={{ fontSize: 15, fontWeight: 500, color: "#5BB8F5", marginLeft: 6 }}>lei</span>
          </span>
        </div>
        <div style={{ fontSize: 12.5, color: "#888", marginTop: 8 }}>
          Tarif: <strong style={{ color: "#5BB8F5" }}>{fmtCredit(pricePerCredit)} lei/Z-Coin</strong>
        </div>
      </div>

      <a href="/register" className="cta-main" style={{
        display: "block", textAlign: "center", marginTop: 16, padding: "13px 20px", borderRadius: 11,
        fontSize: 15, fontWeight: 600, textDecoration: "none",
        background: "linear-gradient(135deg, #378ADD, #5BB8F5)", color: "#fff",
      }}>
        {credits > 0 ? `Cumpără ${credits.toLocaleString("ro-RO")} Z-Coins` : "Începe gratuit"}
      </a>

      <div style={{ fontSize: 11.5, color: "#555", textAlign: "center", marginTop: 12, lineHeight: 1.6 }}>
        DTAC = 1 Z-Coin/mp · DTAC + PT = 3 Z-Coins/mp
      </div>
    </div>
  );
}

/* Panou calculator: calculator (stânga) + card „Ce primești" dinamic (dreapta) */
export function CalculatorPanel() {
  const [phase, setPhase] = useState<"dtac" | "dtac_pt">("dtac");
  return (
    <div className="calc-row">
      <div className="calc-mid"><CreditCalculator phase={phase} setPhase={setPhase} /></div>
      <div className="calc-side"><CeprimestiCard phase={phase} /></div>
    </div>
  );
}
