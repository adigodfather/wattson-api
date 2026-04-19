const features = [
  { icon: "⚡", title: "Calcul PDC automat", desc: "Putere termică, curent, siguranță și cablu selectate după zonă climatică și izolație.", color: "#00C896" },
  { icon: "🏠", title: "Analiză cameră cu cameră", desc: "Prize, iluminat, înălțimi de montaj — generate per cameră conform normativului I7-2011.", color: "#6366F1" },
  { icon: "📋", title: "Memoriu tehnic complet", desc: "Document gata de semnat cu toate calculele, circuitele și justificările tehnice.", color: "#EC4899" },
  { icon: "🔌", title: "TEG + TE-CT automat", desc: "Tabloul general și tabloul camerei tehnice generate cu siguranțe individuale selectate.", color: "#F59E0B" },
  { icon: "📐", title: "Suport DWG & PDF", desc: "Acceptă planșe AutoCAD (DWG), PDF și imagini. AI extrage camerele direct din plan.", color: "#00C896" },
  { icon: "🔄", title: "n8n orchestrare", desc: "Workflow vizual modificabil — adaptezi procesul fără cod. AI, calcule, output în același flux.", color: "#6366F1" },
];

export default function Features() {
  return (
    <section id="features" className="py-24 px-4" style={{ borderTop: "1px solid var(--border)" }}>
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <p className="text-xs font-mono uppercase tracking-widest mb-3" style={{ color: "var(--accent)" }}>
            Capabilități
          </p>
          <h2 className="text-3xl sm:text-4xl font-extrabold" style={{ color: "var(--text)" }}>
            Tot ce are nevoie un proiect electric.
          </h2>
          <p className="mt-3 text-sm max-w-md mx-auto" style={{ color: "var(--muted)" }}>
            De la planșa brută la dosarul complet — automat, conform normativelor în vigoare.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f) => (
            <div key={f.title} className="rounded-xl p-5 group transition-all hover:scale-[1.01]"
              style={{ background: "var(--bg2)", border: "1px solid var(--border)" }}>
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-bold text-sm mb-1.5" style={{ color: "var(--text)" }}>{f.title}</h3>
              <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
