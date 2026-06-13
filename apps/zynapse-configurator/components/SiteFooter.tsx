// Footer comun (landing + home). Grid 3 coloane -> 1 coloana pe mobil.
// Lista de linkuri din mijloc pastreaza exact itemii din landing (incl. legale).

const LINKS = [
  { label: "Login", href: "/login" },
  { label: "Register", href: "/register" },
  { label: "Calculator", href: "#pachete" },
  { label: "Termeni și Condiții", href: "/terms" },
  { label: "Confidențialitate", href: "/privacy" },
  { label: "Politică de retur", href: "/refund" },
  { label: "Contact", href: "mailto:office@zynapse.org" },
];

export default function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer style={{
      position: "relative", zIndex: 1,
      maxWidth: 1100, margin: "0 auto", padding: "40px 40px 56px",
      borderTop: "1px solid rgba(255,255,255,0.06)",
    }}>
      <style>{`
        .site-footer-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 40px; align-items: start; }
        .site-footer-mid { align-items: center; }
        .site-footer-right { align-items: flex-end; text-align: right; }
        .site-footer-link { transition: color .15s; }
        .site-footer-link:hover { color: #E2E4E9 !important; }
        .site-footer-contact { transition: color .15s; }
        .site-footer-contact:hover { color: #CDEBFF !important; }
        @media (max-width: 720px) {
          .site-footer-grid { grid-template-columns: 1fr; gap: 28px; }
          .site-footer-mid { align-items: flex-start !important; }
          .site-footer-right { align-items: flex-start !important; text-align: left !important; }
        }
      `}</style>

      <div className="site-footer-grid">
        {/* STÂNGA — brand */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo-icon.png" alt="Zynapse" width={22} height={22} style={{
              filter: "brightness(2) drop-shadow(0 0 4px rgba(55,138,221,0.3))",
            }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "#6B6F85", letterSpacing: 1 }}>ZYNAPSE</span>
          </div>
          <span style={{ fontSize: 13, color: "#6B6F85", lineHeight: 1.7 }}>
            {year} — Proiectare electrică automată
          </span>
        </div>

        {/* MIJLOC — linkuri */}
        <div className="site-footer-mid" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {LINKS.map(item => (
            <a key={item.label} href={item.href} className="site-footer-link"
              style={{ fontSize: 13, color: "#8B8FA8", textDecoration: "none" }}>
              {item.label}
            </a>
          ))}
        </div>

        {/* DREAPTA — contact firmă */}
        <div className="site-footer-right" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span style={{ fontSize: 14, color: "#B8BCC8", fontWeight: 600 }}>S.C. ZYNAPSE S.R.L.</span>
          <span style={{ fontSize: 13, color: "#8B8FA8", lineHeight: 1.6 }}>
            Jud. Bihor, Loc. Aleșd, Str. Nucului nr. 20
          </span>
          <a href="tel:+40774484053" className="site-footer-contact"
            style={{ fontSize: 13, color: "#8B8FA8", textDecoration: "none" }}>
            Telefon: +40 774 484 053
          </a>
          <a href="mailto:office@zynapse.org" className="site-footer-contact"
            style={{ fontSize: 13, color: "#8B8FA8", textDecoration: "none" }}>
            Email: office@zynapse.org
          </a>
        </div>
      </div>
    </footer>
  );
}
