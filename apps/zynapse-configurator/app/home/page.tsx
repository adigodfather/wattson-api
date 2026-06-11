import Link from "next/link";

/* Home zonei logate — SCHELET placeholder. Conținut (pachete, Z-Coin balance,
   calculator) se adaugă în pasul următor. Login + auth/callback redirectează aici. */
export default function HomePage() {
  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E", color: "#E2E4E9", fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 12, padding: "16px 20px", borderBottom: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(10,11,14,0.85)", backdropFilter: "blur(16px)",
      }}>
        <Link href="/home" aria-label="Zynapse — acasă" style={{ display: "flex", alignItems: "center", gap: 9, textDecoration: "none" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="" width={32} height={32} style={{ objectFit: "contain", filter: "brightness(2.2) drop-shadow(0 0 6px rgba(91,184,245,0.45))" }} />
          <span style={{
            fontSize: 20, fontWeight: 700, letterSpacing: 1.5, lineHeight: 1,
            background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            filter: "drop-shadow(0 0 8px rgba(91,184,245,0.4))",
          }}>ZYNAPSE</span>
        </Link>
        <Link href="/configurator" style={{
          fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none",
          padding: "8px 18px", borderRadius: 8, whiteSpace: "nowrap",
          background: "linear-gradient(135deg, #378ADD, #5BB8F5)",
        }}>Configurator</Link>
      </header>

      <main style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "62vh", textAlign: "center", padding: "48px 24px" }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: "#fff", margin: "0 0 10px" }}>Home — în construcție</h1>
        <p style={{ fontSize: 15, color: "#8B8FA8", maxWidth: 460, lineHeight: 1.6, margin: 0 }}>
          Aici vor apărea pachetele, balanța de Z-Coins și calculatorul. Între timp, deschide{" "}
          <Link href="/configurator" style={{ color: "#5BB8F5", textDecoration: "none", fontWeight: 600 }}>Configuratorul</Link>.
        </p>
      </main>
    </div>
  );
}
