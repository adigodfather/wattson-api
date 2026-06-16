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

export default function LivrarePage() {
  return (
    <div style={page}>
      <div style={container}>
        <a href="/" style={wordmark}>ZYNAPSE</a>

        <h1 style={h1}>Livrarea produselor și serviciilor</h1>
        <p style={updated}>Data ultimei actualizări: 16 iunie 2026</p>

        <p style={{ fontSize: 15, color: "#aab0bd", margin: "0 0 28px" }}>
          Zynapse comercializează exclusiv documentație tehnică în format electronic (documente PDF:
          scheme monofilare, memorii tehnice, planuri de instalații electrice). Nu se livrează produse
          fizice și nu se percep costuri de transport.
        </p>

        <Section n={1} title="Modul de livrare">
          Documentația generată este livrată exclusiv în format digital, prin încărcare automată în
          contul utilizatorului, în secțiunea „Proiectele mele". Documentele pot fi vizualizate și
          descărcate direct din cont.
        </Section>

        <Section n={2} title="Termenul de livrare">
          Livrarea se realizează automat, în mod normal în 5-10 minute de la inițierea generării, și în
          maximum 1 oră în cazul unor volume mari de procesare. Nu este necesară nicio acțiune
          suplimentară din partea clientului.
        </Section>

        <Section n={3} title="Disponibilitate">
          Documentația livrată rămâne disponibilă în contul utilizatorului timp de 1 an de la data
          livrării, perioadă în care poate fi descărcată ori de câte ori este necesar.
        </Section>

        <div style={{ marginTop: 40, paddingTop: 24, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
          <Link href="/" style={linkStyle}>← Înapoi la pagina principală</Link>
        </div>
      </div>
    </div>
  );
}
