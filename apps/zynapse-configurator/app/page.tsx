"use client";

import { useState, useEffect, useRef } from "react";

// TODO: ajustează prețurile/creditele — valori PLACEHOLDER (model pe credite)
const PLANS = [
  { name: "Start", price: "125", credits: "250 credite", perCredit: "0,50 lei/credit", desc: "Pentru primele proiecte", features: ["~250 m² DTAC", "Schemă + memoriu + listă cantități", "Creditele nu expiră"], cta: "Cumpără credite", pop: false },
  { name: "Profesional", price: "450", credits: "1.000 credite", perCredit: "0,45 lei/credit", desc: "Pentru proiectanți activi", features: ["~1.000 m² DTAC", "10% reducere/credit", "Suport prioritar"], cta: "Cumpără credite", pop: true },
  { name: "Birou", price: "2.000", credits: "5.000 credite", perCredit: "0,40 lei/credit", desc: "Pentru firme de proiectare", features: ["~5.000 m² DTAC", "20% reducere/credit", "Facturare firmă"], cta: "Cumpără credite", pop: false },
  { name: "Nelimitat", price: "La cerere", credits: "", perCredit: "", desc: "Volum mare / integrare custom", features: ["Credite în volum", "Facturare firmă", "Suport dedicat", "Integrare custom"], cta: "Solicită ofertă", pop: false, custom: true },
];

interface Node {
  x: number; y: number; vx: number; vy: number;
  r: number; pulse: number; speed: number; color: string;
}
interface Spark {
  x: number; y: number; vx: number; vy: number;
  life: number; decay: number; color: string;
}

interface Trace {
  pts: { x: number; y: number }[];
  len: number; seg: number; speed: number; phase: number;
}

function CircuitCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: -1000, y: -1000 });
  const sparks = useRef<Spark[]>([]);
  const nodes = useRef<Node[]>([]);
  const traces = useRef<Trace[]>([]);
  const raf = useRef<number>(0);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d") as CanvasRenderingContext2D;
    if (!ctx) return;
    const canvas = c;
    let W = 0, H = 0;
    const reduced = typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches : false;

    function polyLen(pts: { x: number; y: number }[]) {
      let L = 0;
      for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
      return L;
    }

    function initNodes() {
      nodes.current = [];
      // densitate redusa + plafon -> O(n^2) ramane ieftin si pe mobil/laptop slab
      const count = Math.min(Math.floor((W * H) / 38000), 70);
      for (let i = 0; i < count; i++) {
        nodes.current.push({
          x: Math.random() * W, y: Math.random() * H,
          vx: (Math.random() - 0.5) * 0.14, vy: (Math.random() - 0.5) * 0.14,
          r: Math.random() * 1.6 + 0.5,
          pulse: Math.random() * Math.PI * 2,
          speed: Math.random() * 0.02 + 0.005,
          color: Math.random() > 0.6 ? "55,138,221" : "91,184,245",
        });
      }
    }

    function initTraces() {
      traces.current = [];
      const rows = Math.max(3, Math.min(7, Math.round(H / 150)));
      for (let i = 0; i < rows; i++) {
        const baseY = (H / (rows + 1)) * (i + 1) + (Math.random() - 0.5) * 30;
        const jog = (Math.random() > 0.5 ? 1 : -1) * (28 + Math.random() * 34);
        const x1 = W * (0.18 + Math.random() * 0.12);
        const x2 = W * (0.55 + Math.random() * 0.18);
        const pts = [
          { x: -20, y: baseY },
          { x: x1, y: baseY },
          { x: x1, y: baseY + jog },
          { x: x2, y: baseY + jog },
          { x: x2, y: baseY },
          { x: W + 20, y: baseY },
        ];
        const len = polyLen(pts);
        const dur = 6000 + Math.random() * 4000; // 6-10s per traversare
        traces.current.push({ pts, len, seg: 70 + Math.random() * 40, speed: len / dur, phase: Math.random() * len });
      }
    }

    function resize() {
      // canvas la dimensiunea viewport-ului (fixed) -> ~1/3 din pixelii vechi (era innerHeight*3)
      W = canvas.width = window.innerWidth;
      H = canvas.height = window.innerHeight;
      initNodes();
      initTraces();
    }

    function addSpark(x: number, y: number) {
      for (let i = 0; i < 6; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 3 + 1.5;
        sparks.current.push({
          x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
          life: 1, decay: Math.random() * 0.03 + 0.015,
          color: Math.random() > 0.5 ? "55,138,221" : "91,184,245",
        });
      }
    }

    function drawTraces(t: number) {
      traces.current.forEach(tr => {
        ctx.beginPath();
        ctx.moveTo(tr.pts[0].x, tr.pts[0].y);
        for (let i = 1; i < tr.pts.length; i++) ctx.lineTo(tr.pts[i].x, tr.pts[i].y);
        // traseu PCB de baza (dim)
        ctx.setLineDash([]);
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(55,138,221,0.05)";
        ctx.stroke();
        // curent luminos care curge dintr-o parte in alta (segment cu lineDash mobil)
        const off = (t * tr.speed + tr.phase) % tr.len;
        ctx.setLineDash([tr.seg, tr.len]);
        ctx.lineDashOffset = -off;
        ctx.lineWidth = 1.6;
        ctx.strokeStyle = "rgba(91,184,245,0.8)";
        ctx.shadowColor = "rgba(91,184,245,0.7)";
        ctx.shadowBlur = 6;
        ctx.stroke();
        ctx.shadowBlur = 0;
        ctx.setLineDash([]);
      });
    }

    function drawNodes() {
      const mx = mouse.current.x, my = mouse.current.y;
      const ns = nodes.current;
      ns.forEach(n => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > W) n.vx *= -1;
        if (n.y < 0 || n.y > H) n.vy *= -1;
        n.pulse += n.speed;
        const dx = n.x - mx, dy = n.y - my;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const glow = dist < 200 ? (200 - dist) / 200 : 0;
        const a = 0.14 + Math.sin(n.pulse) * 0.09 + glow * 0.6;
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
      for (let i = 0; i < ns.length; i++) {
        for (let j = i + 1; j < ns.length; j++) {
          const a = ns[i], b = ns[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 120) {
            const midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2;
            const dmx = midX - mx, dmy = midY - my;
            const md = Math.sqrt(dmx * dmx + dmy * dmy);
            const mg = md < 180 ? (180 - md) / 180 : 0;
            const alpha = (1 - d / 120) * 0.05 + mg * 0.2;
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
    }

    function drawSparks() {
      sparks.current = sparks.current.filter(s => {
        s.x += s.vx; s.y += s.vy; s.vy += 0.05; s.life -= s.decay;
        if (s.life <= 0) return false;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.life * 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${s.color},${s.life * 0.8})`;
        ctx.fill();
        return true;
      });
    }

    function draw(t: number) {
      ctx.clearRect(0, 0, W, H);
      drawTraces(t);
      drawNodes();
      drawSparks();
      raf.current = requestAnimationFrame(draw);
    }

    function drawStatic() {
      ctx.clearRect(0, 0, W, H);
      traces.current.forEach(tr => {
        ctx.beginPath();
        ctx.moveTo(tr.pts[0].x, tr.pts[0].y);
        for (let i = 1; i < tr.pts.length; i++) ctx.lineTo(tr.pts[i].x, tr.pts[i].y);
        ctx.strokeStyle = "rgba(55,138,221,0.06)";
        ctx.lineWidth = 1;
        ctx.stroke();
      });
      nodes.current.forEach(n => {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${n.color},0.18)`;
        ctx.fill();
      });
    }

    resize();

    // prefers-reduced-motion: fundal STATIC, fara RAF/listeneri de animatie
    if (reduced) {
      drawStatic();
      const onResizeStatic = () => { resize(); drawStatic(); };
      window.addEventListener("resize", onResizeStatic);
      return () => window.removeEventListener("resize", onResizeStatic);
    }

    const start = () => { if (!raf.current) raf.current = requestAnimationFrame(draw); };
    const stop = () => { if (raf.current) { cancelAnimationFrame(raf.current); raf.current = 0; } };

    start();
    window.addEventListener("resize", resize);
    const onMove = (e: MouseEvent) => { mouse.current = { x: e.clientX, y: e.clientY }; };
    const onClick = (e: MouseEvent) => { addSpark(e.clientX, e.clientY); };
    // pauza cand tab-ul nu e vizibil -> nu consuma degeaba
    const onVis = () => { if (document.hidden) stop(); else start(); };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("click", onClick);
    document.addEventListener("visibilitychange", onVis);

    return () => {
      stop();
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("click", onClick);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  return (
    <canvas ref={ref} style={{
      position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
      pointerEvents: "none", zIndex: 0,
    }} />
  );
}

function PulseRing({ delay = 0 }: { delay?: number }) {
  return (
    <div style={{
      position: "absolute", width: 350, height: 350, borderRadius: "50%",
      border: "1px solid rgba(55,138,221,0.1)",
      animation: `pulse-ring 4s ease-out infinite ${delay}s`,
      pointerEvents: "none",
    }} />
  );
}

interface PlanCard {
  name: string; price: string;
  credits?: string; perCredit?: string;
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
        }}>Recomandat</div>
      )}
      {p.free && (
        <div style={{
          position: "absolute", top: -11, left: "50%", transform: "translateX(-50%)",
          padding: "3px 14px", borderRadius: 20, fontSize: 11, fontWeight: 600,
          background: "rgba(29,158,117,0.15)", color: "#5DCAA5", border: "1px solid rgba(29,158,117,0.3)",
        }}>Gratuit</div>
      )}
      <div style={{ fontSize: 13, fontWeight: 600, color: "#777", marginBottom: 6 }}>{p.name}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginBottom: 2 }}>
        <span style={{ fontSize: 38, fontWeight: 700, color: "#fff", letterSpacing: -1 }}>{p.price}</span>
        {!p.custom && <span style={{ fontSize: 14, color: "#666" }}>lei</span>}
      </div>
      {p.credits && (
        <div style={{ fontSize: 14, fontWeight: 600, color: "#5BB8F5", marginBottom: 2 }}>{p.credits}</div>
      )}
      {p.perCredit && (
        <div style={{ fontSize: 12, color: "#555" }}>{p.perCredit}</div>
      )}
      <p style={{ fontSize: 12, color: "#444", margin: "12px 0 20px" }}>{p.desc}</p>
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
        @keyframes logo-spin { from { transform: rotateY(0deg) } to { transform: rotateY(360deg) } }
        @media (prefers-reduced-motion: reduce) { .hero-logo { animation: none !important; transform: none !important } }
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
        .feat:hover { border-color: rgba(55,138,221,.2) !important; transform: translateY(-2px) }
        .nav-link { transition: color .2s }
        .nav-link:hover { color: #fff !important }
        .sec-btn:hover { border-color: rgba(255,255,255,0.15) !important; color: #fff !important }
        .plans-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px }
        @media (max-width: 820px) { .plans-grid { grid-template-columns: 1fr } }
      `}</style>

      <CircuitCanvas />

      {/* ── Header ── */}
      <header style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        padding: "14px 40px", display: "flex", justifyContent: "space-between", alignItems: "center",
        background: "rgba(5,7,9,0.85)", backdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(255,255,255,0.03)",
      }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="Zynapse" width={68} height={68} style={{
            objectFit: "contain", filter: "brightness(2.2) drop-shadow(0 0 4px rgba(55,138,221,0.3))",
          }} />
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
        <div style={{ position: "relative", marginBottom: 24, perspective: 800, display: "flex", flexDirection: "column", alignItems: "center" }}>
          <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)" }}>
            <PulseRing delay={0} /><PulseRing delay={1.3} /><PulseRing delay={2.6} />
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="Zynapse" width={250} height={250} className="hero-logo" style={{
            position: "relative", transformStyle: "preserve-3d",
            animation: "logo-spin 9s linear infinite",
            filter: "brightness(2.5) contrast(1.1) drop-shadow(0 0 30px rgba(55,138,221,0.5)) drop-shadow(0 0 60px rgba(29,158,117,0.25))",
          }} />
        </div>

        <p className="fu" style={{
          fontSize: 14.5, lineHeight: 1.65, color: "#6E7488",
          maxWidth: 560, margin: "0 0 22px", textAlign: "center",
        }}>
          Zynapse este o platformă online care automatizează aplicarea normativelor și generează rapid livrabilele pentru proiecte de instalații electrice.
        </p>

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
          AUTOMATIZARE PROIECTARE ELECTRICĂ
        </div>

        <h1 className="fu fu2" style={{
          fontSize: 56, fontWeight: 700, lineHeight: 1.06, color: "#fff",
          margin: "0 0 22px", letterSpacing: -2, maxWidth: 700,
        }}>
          Proiectare electrică<br />
          <span style={{
            background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            backgroundSize: "200% 100%", animation: "shimmer 3.2s linear infinite",
            filter: "drop-shadow(0 0 14px rgba(91,184,245,0.35))",
          }}>din viitor</span>
        </h1>

        <p className="fu fu3" style={{
          fontSize: 17, lineHeight: 1.7, color: "#555", margin: "0 0 26px", maxWidth: 520,
        }}>
          Încarcă planșele, AI-ul extrage camerele, motorul calculează circuitele.
          Memoriu tehnic, liste de cantități — totul generat automat, conform I7-2011.
        </p>

        <div className="fu fu3" style={{
          margin: "0 0 34px", padding: "12px 24px", borderRadius: 12, maxWidth: 600,
          background: "rgba(55,138,221,0.05)", border: "1px solid rgba(55,138,221,0.16)",
          fontSize: 15, fontStyle: "italic", color: "#9FD2FA", lineHeight: 1.6, textAlign: "center",
        }}>
          „Nu schimbăm normativele, doar le aplicăm pentru tine, scăpându-te de task-urile repetitive.”
        </div>

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

        <div style={{
          display: "flex", gap: 48, marginTop: 40, padding: "28px 0",
          borderTop: "1px solid rgba(255,255,255,0.04)",
        }}>
          {[
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
        maxWidth: 900, margin: "0 auto", padding: "60px 40px 60px",
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
            { n: "04", t: "Proiect gata", d: "Circuite, memoriu, liste cantități" },
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

      {/* ── Tot ce ai nevoie ── */}
      <section style={{
        position: "relative", zIndex: 1,
        maxWidth: 1100, margin: "0 auto", padding: "60px 40px",
      }}>
        <h2 style={{ fontSize: 34, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 10px", letterSpacing: -.8 }}>
          Tot ce ai nevoie
        </h2>
        <p style={{ textAlign: "center", color: "#555", fontSize: 15, margin: "0 0 48px" }}>
          Un singur tool pentru întregul proiect electric
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }}>
          {[
            { dot: "#378ADD", title: "Extragere AI din planșe", desc: "Claude Vision citește planșele și identifică încăperile automat" },
            { dot: "#1D9E75", title: "Calcul conform normativelor", desc: "Dimensionare conform I7-2011, NP 061-2002, NTE 007/08/00 și PE 132-2003" },
            { dot: "#C4963A", title: "Memoriu tehnic automat", desc: "Document complet generat, gata de depus la proiect" },
            { dot: "#378ADD", title: "Liste de cantități instant", desc: "Liste de cantități automate, exportabile imediat în PDF" },
            { dot: "#1D9E75", title: "DTAC & PT complet", desc: "Documentații complete pentru autorizare de construire" },
            { dot: "#C4963A", title: "30 secunde per proiect", desc: "Fără ore de calcul manual — totul automatizat" },
          ].map((f, i) => (
            <div key={i} className="feat" style={{
              padding: "24px 28px", borderRadius: 16,
              background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.04)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: f.dot, flexShrink: 0 }} />
                <span style={{ fontSize: 15, fontWeight: 700, color: "#ddd" }}>{f.title}</span>
              </div>
              <p style={{ fontSize: 13, color: "#555", lineHeight: 1.6, margin: 0 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pachete & prețuri ── */}
      <section id="pachete" style={{
        position: "relative", zIndex: 1,
        maxWidth: 1200, margin: "0 auto", padding: "60px 40px 100px",
      }}>
        <h2 style={{ fontSize: 34, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 12px", letterSpacing: -.8 }}>
          Plătești cât proiectezi
        </h2>
        <p style={{ textAlign: "center", color: "#888", fontSize: 15, margin: "0 0 22px" }}>
          1 credit = 1 m² de suprafață construită · 1 credit = 0,50 lei
        </p>
        <div style={{
          maxWidth: 640, margin: "0 auto 52px", padding: "16px 24px", borderRadius: 14,
          background: "rgba(55,138,221,0.06)", border: "1px solid rgba(55,138,221,0.2)",
          textAlign: "center", fontSize: 14, color: "#9FD2FA", lineHeight: 1.65,
        }}>
          Un proiect DTAC de 150 m² costă <strong style={{ color: "#5BB8F5" }}>150 credite (75 lei)</strong>. Faza PT consumă dublu (×2). Cumperi credite în avans, nu expiră.
        </div>
        <div className="plans-grid" style={{ marginBottom: 16 }}>
          {PLANS.slice(0, 3).map((p, i) => (
            <PlanCard key={i} p={p} idx={i} hovered={hovered} onHover={setHovered} />
          ))}
        </div>
        {PLANS.slice(3).map((p, i) => (
          <div key={i + 3} style={{ maxWidth: 380, margin: "0 auto" }}>
            <PlanCard p={p} idx={i + 3} hovered={hovered} onHover={setHovered} />
          </div>
        ))}
        <p style={{ textAlign: "center", color: "#888", fontSize: 13.5, margin: "36px auto 0", maxWidth: 560, lineHeight: 1.6 }}>
          Primii 100 de utilizatori primesc <strong style={{ color: "#5BB8F5" }}>500 credite gratuite</strong> la confirmarea contului.
        </p>
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
        maxWidth: 1100, margin: "0 auto", padding: "40px 40px 56px",
        borderTop: "1px solid rgba(255,255,255,0.04)",
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 40, alignItems: "start" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-icon.png" alt="Zynapse" width={18} height={18} style={{
                filter: "brightness(2) drop-shadow(0 0 4px rgba(55,138,221,0.3))",
              }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: "#555" }}>ZYNAPSE</span>
            </div>
            <span style={{ fontSize: 12, color: "#333", lineHeight: 1.7 }}>2025 — Proiectare electrică<br />automată</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "center" }}>
            {[
              { label: "Login", href: "/login" },
              { label: "Register", href: "/register" },
              { label: "Pachete", href: "#pachete" },
              { label: "Contact", href: "mailto:contact@zynapse.org" },
            ].map(item => (
              <a key={item.label} href={item.href} style={{ fontSize: 12, color: "#444", textDecoration: "none" }}>{item.label}</a>
            ))}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
            <a href="mailto:contact@zynapse.org" style={{ fontSize: 12, color: "#444", textDecoration: "none" }}>contact@zynapse.org</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
