// Footer comun (landing + home). Layout: brand centrat sus, 3 coloane (Platforma
// / Legal / Contact), linie legala jos. Lista de linkuri pastreaza exact href-urile
// existente. "Contact" (mailto) din lista veche e omis din coloana Platforma fiindca
// email-ul apare deja in coloana Contact (evita redundanta).

import NetopiaLogo from "@/components/NetopiaLogo";

const PLATFORM_LINKS = [
  { label: "Login", href: "/login" },
  { label: "Register", href: "/register" },
  { label: "Calculator", href: "#pachete" },
];

const LEGAL_LINKS = [
  { label: "Termeni și Condiții", href: "/terms" },
  { label: "Confidențialitate", href: "/privacy" },
  { label: "Politică de retur", href: "/refund" },
  { label: "Livrare", href: "/livrare" },
];

export default function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer style={{
      position: "relative", zIndex: 1,
      maxWidth: 1100, margin: "0 auto", padding: "40px 40px 56px",
      borderTop: "1px solid rgba(255,255,255,0.04)",
    }}>
      <style>{`
        .sf-cols { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; margin-top: 20px; }
        .sf-col { display: flex; flex-direction: column; gap: 8px; }
        .sf-label { font-size: 11px; color: #545870; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px; }
        .sf-link { font-size: 13px; color: #8B8FA8; text-decoration: none; transition: color .15s; }
        .sf-link:hover { color: #E2E4E9; }
        .sf-contact:hover { color: #CDEBFF !important; }
        @media (max-width: 720px) {
          .sf-cols { grid-template-columns: 1fr; gap: 22px; text-align: center; }
          .sf-col { align-items: center; }
        }
      `}</style>

      {/* ── ZONA 1 — brand (sus, centrat) ── */}
      <div style={{ textAlign: "center", paddingBottom: 18, borderBottom: "0.5px solid rgba(255,255,255,0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/bgbgbun.png" alt="Zynapse" width={55} height={30} style={{
            objectFit: "contain", height: 30, width: "auto", filter: "drop-shadow(0 0 6px rgba(91,184,245,0.42))",
          }} />
          <span style={{
            fontSize: 18, fontWeight: 700, letterSpacing: 3, lineHeight: 1,
            background: "linear-gradient(90deg, #5BB8F5, #CDEBFF, #378ADD)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            filter: "drop-shadow(0 0 10px rgba(91,184,245,0.4))",
          }}>ZYNAPSE</span>
        </div>
        <p style={{ fontSize: 12, color: "#6B6F85", margin: "6px 0 0" }}>
          {`${year} — Proiectare electrică automată`}
        </p>
      </div>

      {/* ── ZONA 2 — 3 coloane ── */}
      <div className="sf-cols">
        {/* Platformă */}
        <div className="sf-col">
          <span className="sf-label">Platformă</span>
          {PLATFORM_LINKS.map(item => (
            <a key={item.label} href={item.href} className="sf-link">{item.label}</a>
          ))}
        </div>

        {/* Legal */}
        <div className="sf-col">
          <span className="sf-label">Legal</span>
          {LEGAL_LINKS.map(item => (
            <a key={item.label} href={item.href} className="sf-link">{item.label}</a>
          ))}
        </div>

        {/* Contact */}
        <div className="sf-col">
          <span className="sf-label">Contact</span>
          <a href="tel:+40774484053" className="sf-link sf-contact">+40 774 484 053</a>
          <a href="mailto:office@zynapse.org" className="sf-link sf-contact">office@zynapse.org</a>
          <span style={{ fontSize: 13, color: "#8B8FA8" }}>Jud. Bihor, Aleșd</span>
        </div>
      </div>

      {/* ── ZONA 3 — rând conformitate (ANPC · Netopia · SmartBill) + linie legală ── */}
      <div style={{ marginTop: 18, paddingTop: 16, borderTop: "0.5px solid rgba(255,255,255,0.05)", textAlign: "center" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexWrap: "wrap", gap: 20, marginBottom: 14 }}>
          {/* ANPC SAL — stânga */}
          <a href="https://reclamatiisal.anpc.ro/" target="_blank" rel="noopener noreferrer" style={{ display: "inline-flex" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/anpc-sal.png" alt="ANPC - Soluționarea Alternativă a Litigiilor"
              height={44} style={{ height: 44, width: "auto", display: "block" }} />
          </a>
          {/* Netopia — centru (existent) */}
          <NetopiaLogo />
          {/* SmartBill — dreapta */}
          <a href="https://www.smartbill.ro" target="_blank" rel="noopener noreferrer" style={{ display: "inline-flex" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/smartbill-logo.png" alt="Facturare SmartBill"
              height={44} style={{ height: 44, width: "auto", display: "block" }} />
          </a>
        </div>
        <span style={{ fontSize: 12, color: "#545870" }}>
          S.C. ZYNAPSE S.R.L. · Str. Nucului nr. 20, Aleșd, jud. Bihor
        </span>
      </div>
    </footer>
  );
}
