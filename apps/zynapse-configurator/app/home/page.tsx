"use client";
/* eslint-disable @next/next/no-img-element */

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
import { CalculatorPanel } from "@/components/CreditCalculator";

// TODO: Netopia — deblocare secvențială + marcare pachet cumpărat per cont (aici legăm plata)
const HOME_PACKAGES: { coins: number; lei: number; stack: number }[] = [
  { coins: 500, lei: 222, stack: 1 },
  { coins: 1000, lei: 444, stack: 3 },
  { coins: 5000, lei: 2222, stack: 5 },
  { coins: 10000, lei: 4444, stack: 7 },
];

/* Ilustrație Z-Coin: teanc care crește cu numărul de monede (500→1 ... 10.000→multe) */
function CoinStack({ count }: { count: number }) {
  const size = 42, dy = 6, dx = 3;
  return (
    <div style={{ position: "relative", width: size + (count - 1) * dx, height: size + (count - 1) * dy, margin: "0 auto 16px" }}>
      {Array.from({ length: count }).map((_, i) => (
        <img key={i} src="/z-coin.svg" alt="" width={size} height={size}
          style={{ position: "absolute", left: i * dx, bottom: i * dy, filter: "drop-shadow(0 2px 5px rgba(0,0,0,0.45))" }} />
      ))}
    </div>
  );
}

export default function HomePage() {
  const { user, profile, loading } = useAuth();
  const balance = profile?.credits_balance ?? 0;

  // Regula B2B: pachetele apar DOAR pentru conturi cu 30+ zile vechime,
  // calculat din created_at-ul userului logat.
  const createdMs = user?.created_at ? new Date(user.created_at).getTime() : null;
  const showPackages = createdMs != null && (Date.now() - createdMs) >= 30 * 24 * 60 * 60 * 1000;

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E", color: "#E2E4E9", fontFamily: "'DM Sans', system-ui, sans-serif", overflowX: "hidden", maxWidth: "100%" }}>
      {/* ── Header ── */}
      <header style={{
        position: "sticky", top: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 12, padding: "14px 18px", borderBottom: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(10,11,14,0.85)", backdropFilter: "blur(16px)",
      }}>
        <Link href="/home" aria-label="Zynapse — acasă" style={{ display: "flex", alignItems: "center", gap: 9, textDecoration: "none", flexShrink: 0 }}>
          <img src="/logo-icon.png" alt="" width={32} height={32} style={{ objectFit: "contain", filter: "brightness(2.2) drop-shadow(0 0 6px rgba(91,184,245,0.45))" }} />
          <span style={{
            fontSize: 20, fontWeight: 700, letterSpacing: 1.5, lineHeight: 1,
            background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            filter: "drop-shadow(0 0 8px rgba(91,184,245,0.4))",
          }}>ZYNAPSE</span>
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span title="Z-Coins disponibile" style={{
            display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 11px", borderRadius: 9,
            fontSize: 14, fontWeight: 600, color: "#E2E4E9",
            background: "rgba(55,138,221,0.08)", border: "1px solid rgba(55,138,221,0.2)",
          }}>
            <img src="/z-coin.svg" alt="" width={20} height={20} style={{ display: "block" }} />
            {loading || !profile ? "—" : balance.toLocaleString("ro-RO")}
            <span className="zc-bal-word" style={{ color: "#8B8FA8", fontWeight: 500 }}>&nbsp;Z-Coins</span>
          </span>
          <Link href="/configurator" style={{
            fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none",
            padding: "8px 16px", borderRadius: 8, whiteSpace: "nowrap",
            background: "linear-gradient(135deg, #378ADD, #5BB8F5)",
          }}>Configurator</Link>
        </div>
      </header>

      {/* ── Calculator ── */}
      <section style={{ position: "relative", zIndex: 1, maxWidth: 1100, margin: "0 auto", padding: "44px 18px 20px" }}>
        <h1 style={{ fontSize: 30, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 8px", letterSpacing: -0.5 }}>
          Calculează-ți proiectul
        </h1>
        <p style={{ textAlign: "center", color: "#888", fontSize: 15, margin: 0 }}>
          Estimează Z-Coins și costul în câteva secunde
        </p>
        <CalculatorPanel />
      </section>

      {/* ── Pachete B2B (doar conturi 30+ zile) ── */}
      {showPackages && (
        <section style={{ position: "relative", zIndex: 1, maxWidth: 1100, margin: "0 auto", padding: "44px 18px 20px" }}>
          <h2 style={{ fontSize: 28, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 8px", letterSpacing: -0.5 }}>
            Pachete Z-Coins
          </h2>
          <p style={{ textAlign: "center", color: "#888", fontSize: 14.5, margin: "0 0 32px" }}>
            Deblochezi pachetul următor pe măsură ce achiziționezi.
          </p>
          <div className="home-pkg-grid">
            {HOME_PACKAGES.map((p, i) => {
              // VIZUAL: primul pachet activ, restul blocate. Deblocarea reală vine cu Netopia.
              const unlocked = i === 0;
              return (
                <div key={p.coins} style={{
                  position: "relative", padding: "26px 20px 22px", borderRadius: 18, textAlign: "center",
                  background: unlocked ? "rgba(55,138,221,0.06)" : "rgba(255,255,255,0.015)",
                  border: unlocked ? "1px solid rgba(55,138,221,0.3)" : "1px solid rgba(255,255,255,0.06)",
                  boxShadow: unlocked ? "0 0 26px rgba(55,138,221,0.08)" : "none",
                  opacity: unlocked ? 1 : 0.62,
                }}>
                  <CoinStack count={p.stack} />
                  <div style={{ fontSize: 22, fontWeight: 700, color: "#fff", letterSpacing: -0.5 }}>
                    {p.coins.toLocaleString("ro-RO")}<span style={{ fontSize: 14, fontWeight: 500, color: "#5BB8F5", marginLeft: 5 }}>Z-Coins</span>
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#9FD2FA", margin: "4px 0 18px" }}>
                    {p.lei.toLocaleString("ro-RO")} lei
                  </div>
                  <button type="button" disabled style={{
                    width: "100%", padding: "11px 16px", borderRadius: 10, fontSize: 14, fontWeight: 600,
                    fontFamily: "inherit", cursor: "not-allowed", color: "#8B8FA8",
                    background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                  }}>În curând</button>
                  {/* indicator stare (deblocare secvențială — doar vizual) */}
                  <div style={{ marginTop: 12, fontSize: 12, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 7, color: unlocked ? "#5BB8F5" : "#545870" }}>
                    <span style={{ fontSize: 14 }}>{unlocked ? "☐" : "🔒"}</span>
                    {unlocked ? "Disponibil" : "Se deblochează ulterior"}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Mesaj final */}
          <div style={{
            maxWidth: 720, margin: "30px auto 0", padding: "20px 26px", borderRadius: 16, textAlign: "center",
            background: "rgba(55,138,221,0.06)", border: "1px solid rgba(91,184,245,0.28)",
            boxShadow: "0 0 26px rgba(55,138,221,0.1)", color: "#9FD2FA", fontSize: 14.5, lineHeight: 1.7,
          }}>
            După ce ați achiziționat toate pachetele oferite de noi, vă vom contacta pentru a vă face o ofertă specială. Vă mulțumim pentru colaborare.
          </div>
          {/* TODO: la finalizarea celor 4 pachete → trigger email automat (după Netopia) */}
        </section>
      )}

      <div style={{ height: 60 }} />
    </div>
  );
}
