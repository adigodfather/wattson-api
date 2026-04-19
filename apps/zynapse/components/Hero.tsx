import Link from "next/link";

export default function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-4 overflow-hidden pt-14">
      {/* Grid background */}
      <div className="absolute inset-0 pointer-events-none" style={{
        backgroundImage: "linear-gradient(var(--border2) 1px, transparent 1px), linear-gradient(90deg, var(--border2) 1px, transparent 1px)",
        backgroundSize: "60px 60px",
        maskImage: "radial-gradient(ellipse 80% 60% at 50% 50%, black 30%, transparent 100%)",
      }} />

      {/* Glow orbs */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, #00C89611 0%, transparent 70%)" }} />
      <div className="absolute top-1/2 left-1/3 w-[300px] h-[300px] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, #6366F108 0%, transparent 70%)" }} />

      <div className="relative z-10 max-w-4xl mx-auto">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono mb-6"
          style={{ border: "1px solid var(--border)", color: "var(--accent)", background: "#00C89611" }}>
          <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "var(--accent)" }} />
          Automatizare proiectare electrică
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-6xl font-extrabold leading-tight tracking-tight mb-6">
          <span style={{ color: "var(--text)" }}>Planșă arhitecturală</span>
          <br />
          <span style={{
            background: "linear-gradient(90deg, #00C896 0%, #6366F1 50%, #EC4899 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>
            → proiect electric complet
          </span>
        </h1>

        <p className="text-base sm:text-lg max-w-xl mx-auto mb-8 leading-relaxed" style={{ color: "var(--muted)" }}>
          Încarcă planul de arhitectură, selectează opțiunile și primești în minute
          circuitele, siguranțele, cablurile și memoriul tehnic — gata de semnat.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link href="/app"
            className="px-6 py-3 rounded-xl font-bold text-sm tracking-wide transition hover:opacity-90"
            style={{ background: "linear-gradient(90deg, #00C896, #6366F1)", color: "#fff" }}>
            ⚡ Generează proiect gratuit
          </Link>
          <a href="#cum-functioneaza"
            className="px-6 py-3 rounded-xl font-semibold text-sm transition hover:opacity-80"
            style={{ border: "1px solid var(--border)", color: "var(--muted)" }}>
            Cum funcționează →
          </a>
        </div>

        {/* Social proof */}
        <p className="mt-8 text-xs" style={{ color: "var(--muted2)" }}>
          Fără cont. Fără card. Rezultat instant.
        </p>
      </div>

      {/* Preview card */}
      <div className="relative z-10 mt-16 w-full max-w-2xl mx-auto rounded-2xl overflow-hidden"
        style={{ border: "1px solid var(--border)", background: "var(--bg2)" }}>
        <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="w-3 h-3 rounded-full" style={{ background: "#EF4444" }} />
          <div className="w-3 h-3 rounded-full" style={{ background: "#F59E0B" }} />
          <div className="w-3 h-3 rounded-full" style={{ background: "#10B981" }} />
          <span className="ml-2 text-xs font-mono" style={{ color: "var(--muted)" }}>zynapse — generator proiect electric</span>
        </div>
        <div className="p-6 font-mono text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
          <div><span style={{ color: "var(--accent)" }}>✓</span> Planșă analizată: <span style={{ color: "var(--text)" }}>Casa Ionescu P+M · 160 m²</span></div>
          <div className="mt-1"><span style={{ color: "var(--accent)" }}>✓</span> Zonă climatică detectată: <span style={{ color: "var(--text)" }}>II · izolație bună</span></div>
          <div className="mt-1"><span style={{ color: "var(--accent)" }}>✓</span> PDC aer-apă 10 kW · <span style={{ color: "var(--text)" }}>5×2,5 mm² · 16A</span></div>
          <div className="mt-1"><span style={{ color: "#6366F1)" }}>→</span> Generând circuite TEG... <span style={{ color: "var(--text)" }}>14 circuite</span></div>
          <div className="mt-1"><span style={{ color: "#6366F1" }}>→</span> Memoriu tehnic... <span style={{ color: "var(--text)" }}>gata</span></div>
          <div className="mt-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: "var(--accent)" }} />
            <span style={{ color: "var(--accent)" }}>Proiect generat în 4.2s</span>
          </div>
        </div>
      </div>
    </section>
  );
}
