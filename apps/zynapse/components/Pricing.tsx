import Link from "next/link";

const plans = [
  {
    name: "Free",
    price: "0",
    desc: "Pentru a testa platforma",
    color: "var(--muted)",
    features: ["3 proiecte / lună", "Export PDF memoriu", "Calcul PDC + TEG", "Suport email"],
    cta: "Începe gratuit",
    href: "/app",
    highlight: false,
  },
  {
    name: "Pro",
    price: "49",
    desc: "Pentru proiectanți activi",
    color: "#6366F1",
    features: ["Proiecte nelimitate", "Export DWG + PDF", "Analiză planșe DWG", "Prioritate procesare", "Facturare SmartBill", "Suport prioritar"],
    cta: "Coming soon",
    href: "#",
    highlight: true,
  },
  {
    name: "Studio",
    price: "149",
    desc: "Pentru birouri de proiectare",
    color: "#EC4899",
    features: ["Tot din Pro", "5 utilizatori", "Branding personalizat", "API access", "Onboarding dedicat", "SLA 99.9%"],
    cta: "Coming soon",
    href: "#",
    highlight: false,
  },
];

export default function Pricing() {
  return (
    <section id="pricing" className="py-24 px-4" style={{ borderTop: "1px solid var(--border)" }}>
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <p className="text-xs font-mono uppercase tracking-widest mb-3" style={{ color: "var(--accent)" }}>
            Prețuri
          </p>
          <h2 className="text-3xl sm:text-4xl font-extrabold mb-3" style={{ color: "var(--text)" }}>
            Simplu și transparent.
          </h2>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Plătești cu card prin Stripe. Factură automată prin SmartBill.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {plans.map((p) => (
            <div key={p.name} className="rounded-2xl p-6 flex flex-col relative"
              style={{
                background: p.highlight ? "linear-gradient(135deg, #6366F111, #6366F108)" : "var(--bg2)",
                border: `1px solid ${p.highlight ? "#6366F144" : "var(--border)"}`,
              }}>
              {p.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-bold"
                  style={{ background: "#6366F1", color: "#fff" }}>
                  Popular
                </div>
              )}

              <div className="mb-5">
                <p className="text-xs font-mono uppercase tracking-widest mb-1" style={{ color: p.color }}>
                  {p.name}
                </p>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold" style={{ color: "var(--text)" }}>{p.price}</span>
                  <span className="text-sm" style={{ color: "var(--muted)" }}>€ / lună</span>
                </div>
                <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{p.desc}</p>
              </div>

              <ul className="space-y-2 flex-1 mb-6">
                {p.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
                    <span style={{ color: p.color }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>

              <Link href={p.href}
                className="text-center py-2.5 rounded-xl text-sm font-bold transition hover:opacity-80"
                style={p.highlight
                  ? { background: "#6366F1", color: "#fff" }
                  : { border: "1px solid var(--border)", color: "var(--muted)" }}>
                {p.cta}
              </Link>
            </div>
          ))}
        </div>

        {/* Payment badges */}
        <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
          {["Stripe", "SmartBill", "Factură automată", "Anulare oricând"].map((b) => (
            <span key={b} className="text-xs px-3 py-1 rounded-full font-mono"
              style={{ border: "1px solid var(--border)", color: "var(--muted2)" }}>
              {b}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
