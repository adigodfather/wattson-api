const steps = [
  {
    num: "01",
    icon: "📐",
    title: "Încarci planșa",
    desc: "PDF sau imagine cu planul de arhitectură — parter, etaj, mansardă. Poți adăuga și opțiunile de instalație (PDC, centrală, izolație).",
    color: "#00C896",
  },
  {
    num: "02",
    icon: "🤖",
    title: "AI procesează automat",
    desc: "Sistemul identifică camerele, calculează suprafețele și volumele, selectează circuitele, siguranțele și secțiunile de cablu conform normativului I7.",
    color: "#6366F1",
  },
  {
    num: "03",
    icon: "📄",
    title: "Primești proiectul complet",
    desc: "Schema monofilară, lista circuite TEG și TE-CT, prize și iluminat pe cameră, memoriu tehnic complet — gata de semnat și depus.",
    color: "#EC4899",
  },
];

export default function HowItWorks() {
  return (
    <section id="cum-functioneaza" className="py-24 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <p className="text-xs font-mono uppercase tracking-widest mb-3" style={{ color: "var(--accent)" }}>
            Flux de lucru
          </p>
          <h2 className="text-3xl sm:text-4xl font-extrabold" style={{ color: "var(--text)" }}>
            3 pași. Minute, nu zile.
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
          {/* connector line */}
          <div className="hidden md:block absolute top-10 left-1/3 right-1/3 h-px"
            style={{ background: "linear-gradient(90deg, transparent, var(--border), transparent)" }} />

          {steps.map((s) => (
            <div key={s.num} className="rounded-2xl p-6 relative group transition hover:border-opacity-60"
              style={{ background: "var(--bg2)", border: "1px solid var(--border)" }}>
              <div className="flex items-start gap-4 mb-4">
                <span className="text-2xl">{s.icon}</span>
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded"
                  style={{ background: s.color + "22", color: s.color }}>
                  {s.num}
                </span>
              </div>
              <h3 className="font-bold text-base mb-2" style={{ color: "var(--text)" }}>{s.title}</h3>
              <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>{s.desc}</p>
              <div className="absolute bottom-0 left-0 right-0 h-0.5 rounded-b-2xl opacity-0 group-hover:opacity-100 transition"
                style={{ background: `linear-gradient(90deg, transparent, ${s.color}, transparent)` }} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
