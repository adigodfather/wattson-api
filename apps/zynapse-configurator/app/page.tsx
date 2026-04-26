"use client";

import { useState, useEffect, useRef } from "react";

const PLANS = [
  { name: "DTAC Casă", price: "0", unit: "LEI", period: "cont gratuit", desc: "Login & proiectare gratuită", features: ["1 proiect DTAC", "Memoriu tehnic", "BOM automat", "Export JSON"], cta: "Creează cont gratuit", pop: false, free: true },
  { name: "1 DTAC + PT", price: "150", unit: "LEI", period: "per pachet", desc: "Proiect complet unic", features: ["1 DTAC complet", "1 PT complet", "Memoriu + Caiet sarcini", "BOM + Liste cantități", "Export PDF"], cta: "Cumpără pachet", pop: false },
  { name: "5 DTAC-uri", price: "200", unit: "LEI", period: "per pachet", desc: "Pachet rezidențial", features: ["5 proiecte DTAC", "Memoriu tehnic", "BOM automat", "Export PDF", "Suport email"], cta: "Cumpără pachet", pop: true },
  { name: "5 PT-uri", price: "800", unit: "LEI", period: "per pachet", desc: "Proiectare completă", features: ["5 proiecte PT", "Memoriu + Caiet sarcini", "BOM + Liste cantități", "Planșe generate", "Export PDF", "Suport prioritar"], cta: "Cumpără pachet", pop: false },
  { name: "10 DTAC + 10 PT", price: "1300", unit: "LEI", period: "per pachet", desc: "Pachet profesional", features: ["10 proiecte DTAC", "10 proiecte PT", "Documentație completă", "Export PDF", "Suport prioritar", "API access"], cta: "Cumpără pachet", pop: false },
  { name: "Nelimitat", price: "?", unit: "", period: "lunar", desc: "DTAC + PT nelimitat", features: ["Proiecte nelimitate", "DTAC + PT complet", "Toate funcționalitățile", "Suport dedicat", "SLA garantat", "Integrare custom"], cta: "Solicită ofertă", pop: false, custom: true },
];

interface Node {
  x: number; y: number; vx: number; vy: number;
  r: number; pulse: number; speed: number; color: string;
}
interface Spark {
  x: number; y: number; vx: number; vy: number;
  life: number; decay: number; color: string;
}

function CircuitCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: -1000, y: -1000 });
  const sparks = useRef<Spark[]>([]);
  const nodes = useRef<Node[]>([]);
  const raf = useRef<number>(0);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d") as CanvasRenderingContext2D;
    if (!ctx) return;
    const canvas = c;
    let W = 0, H = 0;

    function initNodes() {
      nodes.current = [];
      const count = Math.floor((W * H) / 28000);
      for (let i = 0; i < count; i++) {
        nodes.current.push({
          x: Math.random() * W, y: Math.random() * H,
          vx: (Math.random() - 0.5) * 0.15, vy: (Math.random() - 0.5) * 0.15,
          r: Math.random() * 1.8 + 0.5,
          pulse: Math.random() * Math.PI * 2,
          speed: Math.random() * 0.02 + 0.005,
          color: Math.random() > 0.6 ? "55,138,221" : "29,158,117",
        });
      }
    }

    function resize() {
      W = canvas.width = window.innerWidth;
      H = canvas.height = window.innerHeight * 3;
      initNodes();
    }

    function addSpark(x: number, y: number) {
      for (let i = 0; i < 6; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 3 + 1.5;
        sparks.current.push({
          x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
          life: 1, decay: Math.random() * 0.03 + 0.015,
          color: Math.random() > 0.5 ? "55,138,221" : "29,158,117",
        });
      }
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);
      const mx = mouse.current.x;
      const my = mouse.current.y + window.scrollY;

      nodes.current.forEach(n => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > W) n.vx *= -1;
        if (n.y < 0 || n.y > H) n.vy *= -1;
        n.pulse += n.speed;

        const dx = n.x - mx, dy = n.y - my;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const glow = dist < 200 ? (200 - dist) / 200 : 0;
        const a = 0.15 + Math.sin(n.pulse) * 0.1 + glow * 0.6;

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r + glow * 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${n.color},${a})`;
        ctx.fill();

        if (glow > 0.3) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.r + glow * 6, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${n.color},${glow * 0.08})`;
          ctx.fill();
        }
      });

      for (let i = 0; i < nodes.current.length; i++) {
        for (let j = i + 1; j < nodes.current.length; j++) {
          const a = nodes.current[i], b = nodes.current[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 120) {
            const midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2;
            const dmx = midX - mx, dmy = midY - my;
            const md = Math.sqrt(dmx * dmx + dmy * dmy);
            const mg = md < 180 ? (180 - md) / 180 : 0;
            const alpha = (1 - d / 120) * 0.06 + mg * 0.2;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `rgba(55,138,221,${alpha})`;
            ctx.lineWidth = 0.5 + mg;
            ctx.stroke();
            if (mg > 0.5 && Math.random() < 0.003) addSpark(midX, midY);
          }
        }
      }

      sparks.current = sparks.current.filter(s => {
        s.x += s.vx; s.y += s.vy; s.vy += 0.05; s.life -= s.decay;
        if (s.life <= 0) return false;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.life * 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${s.color},${s.life * 0.8})`;
        ctx.fill();
        return true;
      });

      raf.current = requestAnimationFrame(draw);
    }

    resize();
    draw();
    window.addEventListener("resize", resize);
    const onMove = (e: MouseEvent) => { mouse.current = { x: e.clientX, y: e.clientY }; };
    const onClick = (e: MouseEvent) => { addSpark(e.clientX, e.clientY + window.scrollY); };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("click", onClick);

    return () => {
      cancelAnimationFrame(raf.current);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("click", onClick);
    };
  }, []);

  return (
    <canvas ref={ref} style={{
      position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
      pointerEvents: "none", zIndex: 0,
    }} />
  );
}

function PulseRing({ delay = 0 }: { delay?: number }) {
  return (
    <div style={{
      position: "absolute", width: 400, height: 400, borderRadius: "50%",
      border: "1px solid rgba(55,138,221,0.1)",
      animation: `pulse-ring 4s ease-out infinite ${delay}s`,
      pointerEvents: "none",
    }} />
  );
}

interface PlanCard {
  name: string; price: string; unit: string; period: string;
  desc: string; features: string[]; cta: string;
  pop?: boolean; free?: boolean; custom?: boolean;
}

function PlanCard({ p, idx, hovered, onHover }: {
  p: PlanCard; idx: number; hovered: number | null; onHover: (i: number | null) => void;
}) {
  const isHovered = hovered === idx;
  return (
    <div
      onMouseOver={() => onHover(idx)}
      onMouseOut={() => onHover(null)}
      style={{
        padding: 28, borderRadius: 18, position: "relative", cursor: "default",
        background: p.custom
          ? "linear-gradient(160deg, rgba(196,150,58,0.05), rgba(55,138,221,0.03))"
          : p.pop
          ? "linear-gradient(160deg, rgba(55,138,221,0.07), rgba(29,158,117,0.04))"
          : "rgba(255,255,255,0.015)",
        border: p.custom
          ? "1px solid rgba(196,150,58,0.2)"
          : p.pop
          ? "1px solid rgba(55,138,221,0.25)"
          : p.free
          ? "1px solid rgba(29,158,117,0.2)"
          : "1px solid rgba(255,255,255,0.05)",
        boxShadow: isHovered && p.pop ? "0 16px 60px rgba(55,138,221,.1)" : "none",
        transform: isHovered ? "translateY(-6px)" : "none",
        transition: "transform .3s, border-color .3s, box-shadow .3s",
      }}>
      {p.pop && (
        <div style={{
          position: "absolute", top: -11, left: "50%", transform: "translateX(-50%)",
          padding: "3px 14px", borderRadius: 20, fontSize: 11, fontWeight: 600,
          background: "linear-gradient(135deg, #378ADD, #1D9E75)", color: "#fff",
        }}>Popular</div>
      )}
      {p.free && (
        <div style={{
          position: "absolute", top: -11, left: "50%", transform: "translateX(-50%)",
          padding: "3px 14px", borderRadius: 20, fontSize: 11, fontWeight: 600,
          background: "rgba(29,158,117,0.15)", color: "#5DCAA5", border: "1px solid rgba(29,158,117,0.3)",
        }}>Gratuit</div>
      )}
      <div style={{ fontSize: 13, fontWeight: 600, color: "#777", marginBottom: 6 }}>{p.name}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 4 }}>
        <span style={{ fontSize: 38, fontWeight: 700, color: "#fff", letterSpacing: -1 }}>{p.price}</span>
        <span style={{ fontSize: 13, color: "#555" }}>{p.unit} {p.period}</span>
      </div>
      <p style={{ fontSize: 12, color: "#444", margin: "0 0 20px" }}>{p.desc}</p>
      <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px" }}>
        {p.features.map((f, j) => (
          <li key={j} style={{ fontSize: 13, color: "#888", padding: "5px 0", display: "flex", alignItems: "center", gap: 8 }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M3 6L5 8L9 4"
                stroke={p.custom ? "#C4963A" : p.pop ? "#5BB8F5" : p.free ? "#5DCAA5" : "#444"}
                strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {f}
          </li>
        ))}
      </ul>
      <a
        href={p.custom ? "mailto:contact@zynapse.org" : "/register"}
        style={{
          display: "block", textAlign: "center", padding: "11px 20px", borderRadius: 10,
          fontSize: 13, fontWeight: 600, textDecoration: "none",
          background: p.pop
            ? "linear-gradient(135deg,#378ADD,#1D9E75)"
            : p.free
            ? "rgba(29,158,117,0.12)"
            : p.custom
            ? "rgba(196,150,58,0.1)"
            : "rgba(255,255,255,0.04)",
          color: p.pop ? "#fff" : p.free ? "#5DCAA5" : p.custom ? "#C4963A" : "#888",
          border: p.pop
            ? "none"
            : p.free
            ? "1px solid rgba(29,158,117,0.25)"
            : p.custom
            ? "1px solid rgba(196,150,58,0.25)"
            : "1px solid rgba(255,255,255,0.06)",
          transition: "all .2s",
        }}>
        {p.cta}
      </a>
    </div>
  );
}

export default function Landing() {
  const [hovered, setHovered] = useState<number | null>(null);

  return (
    <div style={{
      minHeight: "100vh", background: "#050709",
      fontFamily: "'Instrument Sans', 'DM Sans', system-ui, sans-serif",
      color: "#c0c0c0", position: "relative",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { margin: 0; background: #050709; }
        @keyframes fadeUp { from{opacity:0;transform:translateY(30px)} to{opacity:1;transform:translateY(0)} }
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
        @keyframes pulse-ring { 0%{transform:scale(0.8);opacity:.4} 100%{transform:scale(2.5);opacity:0} }
        @keyframes glow-pulse { 0%,100%{opacity:.3} 50%{opacity:.7} }
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
        @keyframes circuit-flow { 0%{stroke-dashoffset:40} 100%{stroke-dashoffset:0} }
        .fu { animation: fadeUp .8s ease-out both }
        .fu1 { animation-delay:.1s } .fu2 { animation-delay:.2s }
        .fu3 { animation-delay:.35s } .fu4 { animation-delay:.5s }
        .cta-main { transition: all .25s }
        .cta-main:hover { transform:translateY(-2px); box-shadow: 0 8px 40px rgba(55,138,221,.3) }
        .feat { transition: all .25s }
        .feat:hover { border-color: rgba(55,138,221,.25) !important; transform: translateY(-3px) }
        .nav-link { transition: color .2s }
        .nav-link:hover { color: #fff !important }
        .sec-btn:hover { border-color: rgba(255,255,255,0.15) !important; color: #fff !important }
      `}</style>

      <CircuitCanvas />

      {/* ── Header ── */}
      <header style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        padding: "14px 40px", display: "flex", justifyContent: "space-between", alignItems: "center",
        background: "rgba(5,7,9,0.85)", backdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(255,255,255,0.03)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="Zynapse" width={32} height={32} style={{
            objectFit: "contain", filter: "brightness(2) drop-shadow(0 0 6px rgba(55,138,221,0.4))",
          }} />
          <span style={{ fontSize: 18, fontWeight: 700, color: "#fff", letterSpacing: -.5 }}>ZYNAPSE</span>
          <span style={{ fontSize: 10, color: "#444", fontWeight: 500, letterSpacing: 1.5, marginLeft: 4 }}>ELECTRICAL AI</span>
        </div>
        <nav style={{ display: "flex", gap: 28, alignItems: "center" }}>
          {[
            { label: "Pachete", href: "#pachete" },
            { label: "Cum funcționează", href: "#cum-functioneaza" },
            { label: "Contact", href: "mailto:contact@zynapse.org" },
          ].map(item => (
            <a key={item.label} href={item.href} className="nav-link"
              style={{ color: "#666", fontSize: 13, textDecoration: "none", fontWeight: 500 }}>
              {item.label}
            </a>
          ))}
          <a href="/login" className="cta-main" style={{
            padding: "8px 22px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "linear-gradient(135deg, #378ADD, #1D9E75)",
            color: "#fff", textDecoration: "none",
          }}>Intră în cont</a>
        </nav>
      </header>

      {/* ── Hero ── */}
      <section style={{
        minHeight: "100vh", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        position: "relative", zIndex: 1, padding: "120px 40px 80px", textAlign: "center",
      }}>
        {/* Logo floating */}
        <div style={{ position: "relative", marginBottom: 24, animation: "float 5s ease-in-out infinite", display: "flex", flexDirection: "column", alignItems: "center" }}>
          <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)" }}>
            <PulseRing delay={0} /><PulseRing delay={1.3} /><PulseRing delay={2.6} />
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="Zynapse" width={220} height={220} style={{
            position: "relative",
            filter: "brightness(2.5) contrast(1.2) drop-shadow(0 0 30px rgba(55,138,221,0.5)) drop-shadow(0 0 60px rgba(29,158,117,0.3)) drop-shadow(0 0 100px rgba(55,138,221,0.15))",
          }} />
        </div>

        {/* Badge */}
        <div className="fu fu1" style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "5px 16px", borderRadius: 20,
          background: "rgba(55,138,221,0.06)", border: "1px solid rgba(55,138,221,0.12)",
          fontSize: 12, color: "#5BB8F5", fontWeight: 500, marginBottom: 28, letterSpacing: .5,
        }}>
          <span style={{
            width: 5, height: 5, borderRadius: "50%", background: "#1D9E75",
            animation: "glow-pulse 2s infinite", display: "inline-block",
          }} />
          BUSINESS AI &amp; ELECTRICAL AUTOMATION
        </div>

        {/* Headline */}
        <h1 className="fu fu2" style={{
          fontSize: 56, fontWeight: 700, lineHeight: 1.06, color: "#fff",
          margin: "0 0 22px", letterSpacing: -2, maxWidth: 700,
        }}>
          Proiectare electrică<br />
          <span style={{
            background: "linear-gradient(135deg, #378ADD 0%, #1D9E75 50%, #C4963A 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            backgroundSize: "200% 100%", animation: "shimmer 4s linear infinite",
          }}>din viitor</span>
        </h1>

        <p className="fu fu3" style={{
          fontSize: 17, lineHeight: 1.7, color: "#555", margin: "0 0 40px", maxWidth: 520,
        }}>
          Încarcă planșele, AI-ul extrage camerele, motorul calculează circuitele.
          Memoriu tehnic, BOM, liste cantități — totul în 30 de secunde, conform I7-2011.
        </p>

        {/* CTAs */}
        <div className="fu fu4" style={{ display: "flex", gap: 16 }}>
          <a href="/register" className="cta-main" style={{
            padding: "15px 36px", borderRadius: 12, fontSize: 16, fontWeight: 600,
            background: "linear-gradient(135deg, #378ADD, #1D9E75)",
            color: "#fff", textDecoration: "none",
          }}>Începe gratuit</a>
          <a href="#pachete" className="sec-btn" style={{
            padding: "15px 36px", borderRadius: 12, fontSize: 16, fontWeight: 500,
            background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)",
            color: "#777", textDecoration: "none", transition: "all .2s",
          }}>
            Vezi pachetele
          </a>
        </div>

        {/* Stats */}
        <div style={{
          display: "flex", gap: 48, marginTop: 72, padding: "28px 0",
          borderTop: "1px solid rgba(255,255,255,0.04)",
        }}>
          {[
            { v: "30s", l: "per proiect" },
            { v: "I7-2011", l: "normativ" },
            { v: "17+", l: "circuite" },
            { v: "DTAC+PT", l: "complet" },
          ].map((s, i) => (
            <div key={i} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#fff", letterSpacing: -.5 }}>{s.v}</div>
              <div style={{ fontSize: 11, color: "#444", marginTop: 2, letterSpacing: .5 }}>{s.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Cum funcționează ── */}
      <section id="cum-functioneaza" style={{
        position: "relative", zIndex: 1,
        maxWidth: 900, margin: "0 auto", padding: "60px 40px 100px",
      }}>
        <h2 style={{ fontSize: 34, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 12px", letterSpacing: -.8 }}>
          Cum funcționează
        </h2>
        <p style={{ textAlign: "center", color: "#555", fontSize: 15, margin: "0 0 56px" }}>
          4 pași — planșă la proiect electric
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16 }}>
          {[
            { n: "01", t: "Upload planșe", d: "PDF, JPG, PNG" },
            { n: "02", t: "Formular", d: "Tip clădire, încălzire" },
            { n: "03", t: "AI procesează", d: "Claude Vision + calcul" },
            { n: "04", t: "Proiect gata", d: "Circuite, memoriu, BOM" },
          ].map((s, i) => (
            <div key={i} className="feat" style={{
              padding: 24, borderRadius: 16, textAlign: "center",
              background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.04)",
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12, margin: "0 auto 14px",
                background: i === 2 ? "linear-gradient(135deg,#378ADD,#1D9E75)" : "rgba(255,255,255,0.04)",
                border: i === 2 ? "none" : "1px solid rgba(255,255,255,0.06)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 14, fontWeight: 700, color: i === 2 ? "#fff" : "#444",
              }}>{s.n}</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: "#ddd", marginBottom: 4 }}>{s.t}</div>
              <div style={{ fontSize: 12, color: "#555" }}>{s.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pachete & prețuri ── */}
      <section id="pachete" style={{
        position: "relative", zIndex: 1,
        maxWidth: 1200, margin: "0 auto", padding: "40px 40px 100px",
      }}>
        <h2 style={{ fontSize: 34, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 12px", letterSpacing: -.8 }}>
          Pachete &amp; prețuri
        </h2>
        <p style={{ textAlign: "center", color: "#555", fontSize: 15, margin: "0 0 56px" }}>
          Începe gratuit cu DTAC Casă. Upgrade când ai nevoie.
        </p>

        {/* Row 1 */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginBottom: 16 }}>
          {PLANS.slice(0, 3).map((p, i) => (
            <PlanCard key={i} p={p} idx={i} hovered={hovered} onHover={setHovered} />
          ))}
        </div>
        {/* Row 2 */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }}>
          {PLANS.slice(3).map((p, i) => (
            <PlanCard key={i + 3} p={p} idx={i + 3} hovered={hovered} onHover={setHovered} />
          ))}
        </div>
      </section>

      {/* ── CTA final ── */}
      <section style={{
        position: "relative", zIndex: 1,
        maxWidth: 900, margin: "0 auto", padding: "40px 40px 80px", textAlign: "center",
      }}>
        <div style={{
          padding: "56px 40px", borderRadius: 24,
          background: "linear-gradient(160deg, rgba(55,138,221,0.05), rgba(29,158,117,0.03))",
          border: "1px solid rgba(55,138,221,0.08)",
        }}>
          <h2 style={{ fontSize: 30, fontWeight: 700, color: "#fff", margin: "0 0 10px", letterSpacing: -.5 }}>
            Gata de automatizare?
          </h2>
          <p style={{ fontSize: 15, color: "#555", margin: "0 0 28px" }}>
            Primul proiect DTAC Casă e gratuit. Creează-ți contul și testează.
          </p>
          <a href="/register" className="cta-main" style={{
            display: "inline-block", padding: "14px 40px", borderRadius: 12,
            fontSize: 16, fontWeight: 600, textDecoration: "none",
            background: "linear-gradient(135deg, #378ADD, #1D9E75)", color: "#fff",
          }}>Creează cont gratuit</a>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{
        position: "relative", zIndex: 1,
        maxWidth: 1100, margin: "0 auto", padding: "32px 40px 48px",
        borderTop: "1px solid rgba(255,255,255,0.03)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="Zynapse" width={18} height={18} style={{
            filter: "brightness(2) drop-shadow(0 0 4px rgba(55,138,221,0.3))",
          }} />
          <span style={{ fontSize: 12, color: "#333" }}>ZYNAPSE 2025 — Business AI &amp; Electrical Automation</span>
        </div>
        <div style={{ display: "flex", gap: 20 }}>
          <a href="/login" style={{ fontSize: 12, color: "#444", textDecoration: "none" }}>Login</a>
          <a href="mailto:contact@zynapse.org" style={{ fontSize: 12, color: "#444", textDecoration: "none" }}>Contact</a>
        </div>
      </footer>
    </div>
  );
}
