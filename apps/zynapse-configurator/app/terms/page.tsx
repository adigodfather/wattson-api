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

export default function TermsPage() {
  return (
    <div style={page}>
      <div style={container}>
        <a href="/" style={wordmark}>ZYNAPSE</a>

        <div style={draftBanner}>
          [CIORNĂ — text-șablon, a se verifica de un specialist înainte de publicare]
        </div>

        <h1 style={h1}>Termeni și Condiții</h1>
        <p style={updated}>Data ultimei actualizări: [COMPLETEAZĂ: data]</p>

        <Section n={1} title="Identificarea operatorului">
          Serviciul Zynapse este operat de <strong style={{ color: "#cfd3dd" }}>S.C. ZYNAPSE S.R.L.</strong>,
          CUI [COMPLETEAZĂ: CUI], înregistrată la Registrul Comerțului sub nr.
          [COMPLETEAZĂ: Nr. Registrul Comerțului], cu sediul social în
          [COMPLETEAZĂ: Adresă sediu social]. Email de contact:{" "}
          <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>. Site:{" "}
          <a href="https://www.zynapse.org" style={linkStyle}>www.zynapse.org</a>.
        </Section>

        <Section n={2} title="Obiectul serviciului">
          Zynapse este o platformă SaaS care automatizează elaborarea documentației tehnice pentru
          instalații electrice (scheme monofilare, memorii tehnice, liste de cantități) conform
          normativelor românești în vigoare. Serviciul generează documente-suport pe baza datelor
          introduse de utilizator.
        </Section>

        <Section n={3} title="Răspunderea profesională">
          <p style={{ margin: "0 0 10px" }}>
            Toate documentele generate (planșe, scheme, memorii tehnice, liste de cantități) trebuie{" "}
            <strong style={{ color: "#cfd3dd" }}>ASUMATE</strong> de către un inginer proiectant autorizat
            ANRE și, după caz, <strong style={{ color: "#cfd3dd" }}>VERIFICATE</strong> de un verificator de
            proiecte atestat MDLPA.
          </p>
          <p style={{ margin: 0 }}>
            Zynapse furnizează documente-suport generate automat; responsabilitatea tehnică și legală a
            proiectului revine inginerului proiectant și verificatorului. Zynapse nu se substituie
            proiectantului autorizat.
          </p>
        </Section>

        <Section n={4} title="Cont de utilizator">
          Pentru utilizarea serviciului este necesară crearea unui cont. Utilizatorul este responsabil de
          păstrarea în siguranță a credențialelor sale și de toate activitățile desfășurate prin contul său.
          Datele furnizate la înregistrare trebuie să fie reale, complete și actualizate.
        </Section>

        <Section n={5} title="Z-Coins (moneda virtuală a platformei)">
          <p style={{ margin: "0 0 10px" }}>
            1 Z-Coin = 0,50 lei. Z-Coins sunt credite preplătite utilizate pentru generarea documentației
            (DTAC = 1 Z-Coin/mp; DTAC + PT = 3 Z-Coins/mp).
          </p>
          <p style={{ margin: 0 }}>
            Z-Coins nu reprezintă un instrument de plată electronică, nu pot fi transferați între conturi și
            nu pot fi preschimbați înapoi în bani decât în condițiile prevăzute în Politica de retur.
          </p>
        </Section>

        <Section n={6} title="Suprafața declarată (anti-fraudă)">
          Utilizatorul are obligația de a declara corect suprafața proiectului. Declararea unei suprafețe mai
          mici decât cea reală constituie o încălcare a prezentilor termeni și poate atrage suspendarea sau
          închiderea contului.
        </Section>

        <Section n={7} title="Proprietate intelectuală">
          Platforma, codul-sursă, design-ul și marca Zynapse aparțin S.C. ZYNAPSE S.R.L. și sunt protejate de
          legislația privind proprietatea intelectuală. Documentele generate de utilizator pentru propriile
          proiecte îi aparțin utilizatorului.
        </Section>

        <Section n={8} title="Limitarea răspunderii">
          Serviciul este furnizat „ca atare" („as is"). Zynapse nu garantează potrivirea documentelor generate
          pentru un scop specific în absența verificării și asumării de către un specialist autorizat. Zynapse
          nu răspunde pentru daune rezultate din utilizarea documentelor fără verificarea profesională impusă.
        </Section>

        <Section n={9} title="Modificarea termenilor">
          Zynapse poate actualiza periodic prezentii termeni. Versiunea curentă este întotdeauna disponibilă pe
          această pagină, iar continuarea utilizării serviciului după publicarea modificărilor reprezintă
          acceptarea acestora.
        </Section>

        <Section n={10} title="Legea aplicabilă">
          Prezentilor termeni li se aplică legea română. Eventualele litigii se soluționează pe cale amiabilă
          sau, în lipsa unei înțelegeri, de către instanțele competente din România.
        </Section>

        <Section n={11} title="Contact">
          Pentru orice întrebări privind acești termeni, ne puteți contacta la{" "}
          <a href="mailto:office@zynapse.org" style={linkStyle}>office@zynapse.org</a>.
        </Section>

        <div style={{ marginTop: 40, paddingTop: 24, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
          <Link href="/" style={linkStyle}>← Înapoi la pagina principală</Link>
        </div>
      </div>
    </div>
  );
}
