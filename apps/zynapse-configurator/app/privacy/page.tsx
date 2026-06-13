import Link from "next/link";

const page: React.CSSProperties = {
  minHeight: "100vh", background: "#050709", color: "#aab0bd",
  fontFamily: "'DM Sans', system-ui, sans-serif", lineHeight: 1.75,
  padding: "40px 20px 72px", overflowX: "hidden",
};
const container: React.CSSProperties = { maxWidth: 800, margin: "0 auto" };
const wordmark: React.CSSProperties = {
  display: "inline-block", fontSize: 22, fontWeight: 700, letterSpacing: "0.14em",
  lineHeight: 1, textDecoration: "none", fontFamily: "'DM Sans', sans-serif",
  background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
  WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
  filter: "drop-shadow(0 0 10px rgba(91,184,245,0.4))",
};
const h1: React.CSSProperties = {
  fontSize: 30, fontWeight: 700, color: "#CDEBFF", letterSpacing: -0.5, margin: "12px 0 6px",
};
const updated: React.CSSProperties = { fontSize: 13.5, color: "#6b7180", margin: "0 0 28px" };
const linkStyle: React.CSSProperties = { color: "#5BB8F5", textDecoration: "none" };
const li: React.CSSProperties = { marginBottom: 6 };

function Section({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 26 }}>
      <h2 style={{ fontSize: 17, fontWeight: 700, color: "#378ADD", margin: "0 0 8px" }}>
        {n}. {title}
      </h2>
      <div style={{ fontSize: 15, color: "#aab0bd" }}>{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <div style={page}>
      <div style={container}>
        <a href="/" style={wordmark}>ZYNAPSE</a>

        <h1 style={h1}>Politica de Confidențialitate</h1>
        <p style={updated}>Data ultimei actualizări: 13 iunie 2026</p>

        <Section n={1} title="Operatorul de date">
          Operatorul datelor cu caracter personal este{" "}
          <strong style={{ color: "#cfd3dd" }}>S.C. ZYNAPSE S.R.L.</strong>, CUI 54417482,
          înregistrată la Registrul Comerțului sub nr. J2026/0224/13006, cu sediul
          social în Jud. Bihor, Loc. Aleșd, Str. Nucului nr. 20. Responsabil cu protecția datelor:
          ing. Dan Adrian Nicolas — email{" "}
          <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>.
        </Section>

        <Section n={2} title="Ce date colectăm">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li style={li}>Date de cont: email, opțional numele firmei;</li>
            <li style={li}>Date tehnice ale proiectelor încărcate: planșe, suprafețe, parametri tehnici;</li>
            <li style={li}>Date de utilizare și loguri tehnice (jurnale de acces și activitate);</li>
            <li style={li}>Date de facturare necesare emiterii facturii.</li>
          </ul>
        </Section>

        <Section n={3} title="Scopul prelucrării">
          Prelucrăm datele pentru: furnizarea serviciului, generarea documentației tehnice, facturare,
          acordarea de suport, precum și pentru îndeplinirea obligațiilor legale.
        </Section>

        <Section n={4} title="Temeiul legal (GDPR art. 6)">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li style={li}>Executarea contractului — furnizarea serviciului către utilizator;</li>
            <li style={li}>Obligație legală — emiterea și păstrarea documentelor de facturare;</li>
            <li style={li}>Interes legitim — securitatea platformei și prevenirea fraudei;</li>
            <li style={li}>Consimțământ — acolo unde este cazul (ex. comunicări opționale).</li>
          </ul>
        </Section>

        <Section n={5} title="Procesatori terți">
          <p style={{ margin: "0 0 10px" }}>
            Pentru funcționarea serviciului colaborăm cu următorii procesatori, în calitate de persoane
            împuternicite:
          </p>
          <ul style={{ margin: "0 0 10px", paddingLeft: 20 }}>
            <li style={li}>Găzduire aplicație: Vercel;</li>
            <li style={li}>Bază de date și autentificare: Supabase;</li>
            <li style={li}>Procesare plăți: Netopia;</li>
            <li style={li}>Facturare: SmartBill.</li>
          </ul>
          <p style={{ margin: 0 }}>
            Datele de plată (datele cardului) sunt procesate exclusiv de Netopia; Zynapse{" "}
            <strong style={{ color: "#cfd3dd" }}>NU stochează</strong> datele cardului.
          </p>
        </Section>

        <Section n={6} title="Stocarea datelor">
          Păstrăm datele cât timp este necesar pentru furnizarea serviciului și pe perioadele impuse de lege.
          Datele de facturare se păstrează conform legislației fiscale aplicabile.
        </Section>

        <Section n={7} title="Drepturile persoanei vizate (GDPR)">
          <p style={{ margin: "0 0 10px" }}>Conform GDPR, aveți următoarele drepturi:</p>
          <ul style={{ margin: "0 0 10px", paddingLeft: 20 }}>
            <li style={li}>dreptul de acces la date;</li>
            <li style={li}>dreptul la rectificare;</li>
            <li style={li}>dreptul la ștergere („dreptul de a fi uitat");</li>
            <li style={li}>dreptul la restricționarea prelucrării;</li>
            <li style={li}>dreptul la portabilitatea datelor;</li>
            <li style={li}>dreptul de opoziție;</li>
            <li style={li}>dreptul de a retrage consimțământul;</li>
            <li style={li}>dreptul de a depune plângere la ANSPDCP.</li>
          </ul>
          <p style={{ margin: 0 }}>
            Aceste drepturi pot fi exercitate prin email la{" "}
            <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>.
          </p>
        </Section>

        <Section n={8} title="Cookies">
          Utilizăm cookie-uri strict necesare pentru funcționarea platformei (sesiune și autentificare).
          Acestea nu necesită consimțământ. În cazul în care vor fi adăugate cookie-uri de analytics, acestea
          vor fi utilizate doar pe baza consimțământului.
        </Section>

        <Section n={9} title="Securitate">
          Aplicăm măsuri tehnice și organizatorice pentru protejarea datelor: criptarea comunicațiilor în
          tranzit (HTTPS), securitate la nivel de rânduri (RLS) pe baza de date și acces restricționat la
          datele cu caracter personal.
        </Section>

        <Section n={10} title="Contact">
          Pentru orice solicitare privind protecția datelor, ne puteți contacta la{" "}
          <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>.
        </Section>

        <div style={{ marginTop: 40, paddingTop: 24, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
          <Link href="/" style={linkStyle}>← Înapoi la pagina principală</Link>
        </div>
      </div>
    </div>
  );
}
