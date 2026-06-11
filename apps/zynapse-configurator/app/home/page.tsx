"use client";
/* eslint-disable @next/next/no-img-element */

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
import { CalculatorPanel } from "@/components/CreditCalculator";

// TODO: Netopia — deblocare secvențială + marcare pachet cumpărat per cont (aici legăm plata)
const HOME_PACKAGES: { coins: number; lei: number; count: number }[] = [
  { coins: 500, lei: 222, count: 3 },
  { coins: 1000, lei: 444, count: 6 },
  { coins: 5000, lei: 2222, count: 11 },
  { coins: 10000, lei: 4444, count: 18 },
];

// jitter determinist (x + rotație) pentru aspect natural de grămadă
const PILE_JITTER = [
  { dx: -2, r: -5 }, { dx: 10, r: 7 }, { dx: -9, r: -9 }, { dx: 4, r: 4 },
  { dx: -6, r: 8 }, { dx: 12, r: -6 }, { dx: 1, r: -3 }, { dx: -11, r: 6 },
  { dx: 7, r: -8 }, { dx: -3, r: 3 }, { dx: 9, r: 9 }, { dx: -7, r: -4 },
];

/* Ilustrație Z-Coin: GRĂMADĂ de monede care crește cu cantitatea (500 → puține, 10.000 → morman) */
function CoinPile({ count }: { count: number }) {
  const S = 32;
  const H = S + Math.round((count - 1) * 3.2);          // înălțimea grămezii crește cu nr. monede
  const W = S + 18 + Math.min(28, count * 1.5);          // baza se lățește cu nr. monede
  return (
    <div style={{ position: "relative", width: W, height: H, margin: "0 auto 18px" }}>
      {Array.from({ length: count }).map((_, i) => {
        const j = PILE_JITTER[i % PILE_JITTER.length];
        const t = count > 1 ? i / (count - 1) : 0;        // 0 (jos) .. 1 (sus)
        const bottom = t * (H - S);
        const spread = 1 - t * 0.5;                        // monedele de jos se împrăștie mai lat
        const left = (W - S) / 2 + j.dx * spread;
        return (
          <img key={i} src="/z-coin.svg" alt="" width={S} height={S}
            style={{ position: "absolute", left, bottom, transform: `rotate(${j.r}deg)`, filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))" }} />
        );
      })}
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

          {/* Nav desktop */}
          <nav className="home-nav-desktop">
            <Link href="/projects" style={{ fontSize: 13.5, color: "#8B8FA8", textDecoration: "none", fontWeight: 500, whiteSpace: "nowrap" }}>Proiectele mele</Link>
            <Link href="/settings" style={{ fontSize: 13.5, color: "#8B8FA8", textDecoration: "none", fontWeight: 500, whiteSpace: "nowrap" }}>Setări firmă</Link>
            <Link href="/configurator" style={{
              fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none",
              padding: "8px 16px", borderRadius: 8, whiteSpace: "nowrap",
              background: "linear-gradient(135deg, #378ADD, #5BB8F5)",
            }}>Configurator</Link>
          </nav>

          {/* Nav mobil — hamburger CSS-only (<details>) */}
          <details className="home-nav-mobile" style={{ position: "relative" }}>
            <summary style={{
              listStyle: "none", cursor: "pointer", width: 38, height: 38, display: "flex",
              alignItems: "center", justifyContent: "center", borderRadius: 9, fontSize: 18,
              color: "#8B8FA8", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
            }}>☰</summary>
            <div style={{
              position: "absolute", right: 0, top: "calc(100% + 8px)", zIndex: 60,
              display: "flex", flexDirection: "column", minWidth: 184, padding: 6, borderRadius: 12,
              background: "#14161C", border: "1px solid rgba(255,255,255,0.1)", boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
            }}>
              <Link href="/configurator" style={{ padding: "9px 14px", fontSize: 13.5, fontWeight: 600, color: "#5BB8F5", textDecoration: "none", borderRadius: 7 }}>Configurator</Link>
              <Link href="/projects" style={{ padding: "9px 14px", fontSize: 13.5, color: "#C8CAD6", textDecoration: "none", borderRadius: 7 }}>Proiectele mele</Link>
              <Link href="/settings" style={{ padding: "9px 14px", fontSize: 13.5, color: "#C8CAD6", textDecoration: "none", borderRadius: 7 }}>Setări firmă</Link>
            </div>
          </details>
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
                  <CoinPile count={p.count} />
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
