"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { createClient } from "@/lib/supabase";
import { CalculatorPanel } from "@/components/CreditCalculator";
import { startCheckout } from "@/lib/payment/startCheckout";
import SiteFooter from "@/components/SiteFooter";

// Pachetele vin DIN DB (credit_packages) — sursa de adevăr pt. id/credite/preț.
interface DbPackage {
  id: string;          // packageId trimis la /api/payment/start (ex. pack_500)
  name: string;
  credits: number;
  price_ron: number | string;
  sort_order: number;
}

// nr. de monede din ilustrație, pe poziție (pur vizual, indexat pe sort_order)
const PILE_COUNTS = [3, 6, 11, 18];

// jitter determinist (x + rotație) pentru aspect natural de grămadă
const PILE_JITTER = [
  { dx: -2, r: -5 }, { dx: 10, r: 7 }, { dx: -9, r: -9 }, { dx: 4, r: 4 },
  { dx: -6, r: 8 }, { dx: 12, r: -6 }, { dx: 1, r: -3 }, { dx: -11, r: 6 },
  { dx: 7, r: -8 }, { dx: -3, r: 3 }, { dx: 9, r: 9 }, { dx: -7, r: -4 },
];

/* Ilustrație Z-Coin: GRĂMADĂ de monede care crește cu cantitatea (500 → puține, 10.000 → morman).
   Monedă mare (S=54, ~1.7×) ca „Z"-ul să iasă clar; zonă fixă -> carduri egale, grămada bottom-aligned. */
function CoinPile({ count }: { count: number }) {
  const S = 54;                                          // dimensiunea monedei (mărită ~1.7×)
  const step = S * 0.085;                                // pas vertical (overlap dens, aspect de morman)
  const jx = S / 32;                                     // scalare jitter orizontal proporțional cu moneda
  const pileH = S + (count - 1) * step;                  // înălțimea reală a grămezii
  const ZONE_H = 148;                                    // zonă fixă (≥ cea mai mare grămadă) -> carduri egale
  const W = Math.round(S + 24 + Math.min(48, count * 2.4)); // baza se lățește cu nr. monede
  return (
    <div style={{ position: "relative", width: W, height: ZONE_H, margin: "0 auto 18px" }}>
      {Array.from({ length: count }).map((_, i) => {
        const j = PILE_JITTER[i % PILE_JITTER.length];
        const t = count > 1 ? i / (count - 1) : 0;        // 0 (jos) .. 1 (sus)
        const bottom = t * (pileH - S);                   // grămada crește din baza zonei în sus
        const spread = 1 - t * 0.5;                        // monedele de jos se împrăștie mai lat
        const left = (W - S) / 2 + j.dx * jx * spread;
        return (
          <img key={i} src="/z-coin.svg" alt="" width={S} height={S}
            style={{ position: "absolute", left, bottom, transform: `rotate(${j.r}deg)`, filter: "drop-shadow(0 2px 5px rgba(0,0,0,0.5))" }} />
        );
      })}
    </div>
  );
}

export default function HomePage() {
  const { user, profile, loading } = useAuth();
  const router = useRouter();
  const balance = profile?.credits_balance ?? 0;

  // Pachetele citite din DB (credit_packages), sortate după sort_order.
  const [packages, setPackages] = useState<DbPackage[] | null>(null);
  const [buying, setBuying] = useState<string | null>(null);   // packageId în curs
  const [buyError, setBuyError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    let active = true;
    supabase
      .from("credit_packages")
      .select("id, name, credits, price_ron, sort_order")
      .eq("is_active", true)
      .order("sort_order", { ascending: true })
      .then(({ data }) => { if (active && data) setPackages(data as DbPackage[]); });
    return () => { active = false; };
  }, []);

  // Click „Cumpără" → cere formularul Netopia de la rută și redirectează la plată.
  // Neautentificat → login (ruta oricum cere auth).
  async function handleBuy(packageId: string) {
    setBuyError(null);
    if (!user) { router.push("/login"); return; }
    setBuying(packageId);
    const r = await startCheckout({ packageId });
    if (r.authRequired) { router.push("/login"); return; }
    if (!r.ok) { setBuyError(r.error || "Nu am putut iniția plata."); setBuying(null); }
    // succes -> pagina navighează spre Netopia; lăsăm butonul în „Se redirecționează…"
  }

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
          {packages === null ? (
            <p style={{ textAlign: "center", color: "#888", fontSize: 14 }}>Se încarcă pachetele…</p>
          ) : (
          <div className="home-pkg-grid">
            {packages.map((p, i) => {
              const emphasized = i === 0;        // primul evidențiat vizual; toate cumpărabile
              const lei = Number(p.price_ron);
              const isThis = buying === p.id;
              return (
                <div key={p.id} style={{
                  position: "relative", padding: "26px 20px 22px", borderRadius: 18, textAlign: "center",
                  background: emphasized ? "rgba(55,138,221,0.06)" : "rgba(255,255,255,0.02)",
                  border: emphasized ? "1px solid rgba(55,138,221,0.3)" : "1px solid rgba(255,255,255,0.08)",
                  boxShadow: emphasized ? "0 0 26px rgba(55,138,221,0.08)" : "none",
                }}>
                  <CoinPile count={PILE_COUNTS[i] ?? 6} />
                  <div style={{ fontSize: 22, fontWeight: 700, color: "#fff", letterSpacing: -0.5 }}>
                    {p.credits.toLocaleString("ro-RO")}<span style={{ fontSize: 14, fontWeight: 500, color: "#5BB8F5", marginLeft: 5 }}>Z-Coins</span>
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#9FD2FA", margin: "4px 0 18px" }}>
                    {lei.toLocaleString("ro-RO")} lei
                  </div>
                  <button type="button" onClick={() => handleBuy(p.id)} disabled={buying !== null} style={{
                    width: "100%", padding: "11px 16px", borderRadius: 10, fontSize: 14, fontWeight: 700,
                    fontFamily: "inherit", cursor: buying !== null ? "wait" : "pointer", color: "#fff",
                    background: "linear-gradient(135deg, #378ADD, #5BB8F5)", border: "none",
                    opacity: buying !== null && !isThis ? 0.55 : 1,
                  }}>{isThis ? "Se redirecționează…" : "Cumpără"}</button>
                </div>
              );
            })}
          </div>
          )}
          {buyError && (
            <p style={{ textAlign: "center", color: "#F09595", fontSize: 13.5, margin: "16px 0 0" }}>{buyError}</p>
          )}

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
      <SiteFooter />
    </div>
  );
}
