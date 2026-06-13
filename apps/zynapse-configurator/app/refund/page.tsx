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
const draftBanner: React.CSSProperties = {
  display: "inline-block", padding: "6px 12px", borderRadius: 8, fontSize: 12.5,
  color: "#F0C674", background: "rgba(240,198,116,0.08)",
  border: "1px solid rgba(240,198,116,0.25)", margin: "24px 0 8px",
};
const h1: React.CSSProperties = {
  fontSize: 30, fontWeight: 700, color: "#CDEBFF", letterSpacing: -0.5, margin: "12px 0 6px",
};
const updated: React.CSSProperties = { fontSize: 13.5, color: "#6b7180", margin: "0 0 28px" };
const linkStyle: React.CSSProperties = { color: "#5BB8F5", textDecoration: "none" };

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

export default function RefundPage() {
  return (
    <div style={page}>
      <div style={container}>
        <a href="/" style={wordmark}>ZYNAPSE</a>

        <div style={draftBanner}>
          [CIORNĂ — text-șablon, a se verifica de un specialist înainte de publicare]
        </div>

        <h1 style={h1}>Politica de Retur și Rambursare</h1>
        <p style={updated}>Data ultimei actualizări: [COMPLETEAZĂ: data]</p>

        <Section n={1} title="Natura serviciului">
          Zynapse furnizează conținut digital și servicii prestate prin mijloace electronice (generarea
          documentației tehnice). Achiziția se realizează prin Z-Coins, credite preplătite utilizate în cadrul
          platformei.
        </Section>

        <Section n={2} title="Dreptul de retragere (14 zile) și excepția pentru conținut digital">
          <p style={{ margin: "0 0 10px" }}>
            Conform OUG nr. 34/2014, consumatorul are dreptul de a se retrage din contract în termen de 14 zile
            în cazul achizițiilor online, fără a fi nevoit să justifice decizia.
          </p>
          <p style={{ margin: 0 }}>
            Însă, pentru conținutul digital livrat și pentru serviciile executate integral, dreptul de
            retragere se <strong style={{ color: "#cfd3dd" }}>PIERDE</strong> odată ce utilizatorul a consumat
            Z-Coins pentru generarea documentației, cu acordul prealabil expres al acestuia. La cumpărare,
            utilizatorul confirmă că ia la cunoștință pierderea dreptului de retragere pentru Z-Coins consumați.
          </p>
        </Section>

        <Section n={3} title="Z-Coins neconsumați">
          Z-Coins cumpărați dar neconsumați pot fi rambursați în termen de [COMPLETEAZĂ: nr.] zile de la
          achiziție, la cerere prin{" "}
          <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>, mai puțin eventualele
          comisioane de procesare a plății.
        </Section>

        <Section n={4} title="Z-Coins gratuiți / bonus">
          Z-Coins primiți gratuit (de exemplu bonusul de bun-venit) nu sunt rambursabili și nu au valoare
          monetară.
        </Section>

        <Section n={5} title="Procedura de rambursare">
          Solicitarea de rambursare se transmite la{" "}
          <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>, împreună cu datele
          tranzacției. Rambursarea se efectuează pe aceeași metodă de plată utilizată la achiziție, în termen de
          [COMPLETEAZĂ: nr.] zile de la aprobarea cererii.
        </Section>

        <Section n={6} title="Erori tehnice">
          Dacă o generare eșuează din cauza unei erori a platformei, Z-Coins reținuți pentru acea operațiune se
          returnează automat în contul utilizatorului.
        </Section>

        <Section n={7} title="Contact">
          Pentru orice solicitare privind returul sau rambursarea, ne puteți contacta la{" "}
          <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>.
        </Section>

        <div style={{ marginTop: 40, paddingTop: 24, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
          <Link href="/" style={linkStyle}>← Înapoi la pagina principală</Link>
        </div>
      </div>
    </div>
  );
}
