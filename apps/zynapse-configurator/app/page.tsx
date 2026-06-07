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
          ? "linear-gradient(160deg, rgba(55,138,221,0.05), rgba(55,138,221,0.03))"
          : p.pop
          ? "linear-gradient(160deg, rgba(55,138,221,0.07), rgba(55,138,221,0.04))"
          : "rgba(255,255,255,0.015)",
        border: p.custom
          ? "1px solid rgba(55,138,221,0.2)"
          : p.pop
          ? "1px solid rgba(55,138,221,0.25)"
          : p.free
          ? "1px solid rgba(55,138,221,0.2)"
          : "1px solid rgba(255,255,255,0.05)",
        boxShadow: isHovered && p.pop ? "0 16px 60px rgba(55,138,221,.1)" : "none",
        transform: isHovered ? "translateY(-6px)" : "none",
        transition: "transform .3s, border-color .3s, box-shadow .3s",
      }}>
      {p.pop && (
        <div style={{
          position: "absolute", top: -11, left: "50%", transform: "translateX(-50%)",
          padding: "3px 14px", borderRadius: 20, fontSize: 11, fontWeight: 600,
          background: "linear-gradient(135deg, #378ADD, #5BB8F5)", color: "#fff",
        }}>Recomandat</div>
      )}
      {p.free && (
        <div style={{
          position: "absolute", top: -11, left: "50%", transform: "translateX(-50%)",
          padding: "3px 14px", borderRadius: 20, fontSize: 11, fontWeight: 600,
          background: "rgba(55,138,221,0.15)", color: "#5BB8F5", border: "1px solid rgba(55,138,221,0.3)",
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
                stroke={p.custom ? "#5BB8F5" : p.pop ? "#5BB8F5" : p.free ? "#5BB8F5" : "#444"}
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
            ? "linear-gradient(135deg,#378ADD,#5BB8F5)"
            : p.free
            ? "rgba(55,138,221,0.12)"
            : p.custom
            ? "rgba(55,138,221,0.1)"
            : "rgba(255,255,255,0.04)",
          color: p.pop ? "#fff" : p.free ? "#5BB8F5" : p.custom ? "#5BB8F5" : "#888",
          border: p.pop
            ? "none"
            : p.free
            ? "1px solid rgba(55,138,221,0.25)"
            : p.custom
            ? "1px solid rgba(55,138,221,0.25)"
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
        @keyframes logo-pulse {
          0%, 100% { transform: scale(1);    filter: brightness(2.5) contrast(1.1) drop-shadow(0 0 22px rgba(91,184,245,0.32)) drop-shadow(0 0 48px rgba(55,138,221,0.16)); }
          50%      { transform: scale(1.06); filter: brightness(2.6) contrast(1.1) drop-shadow(0 0 40px rgba(91,184,245,0.6))  drop-shadow(0 0 84px rgba(55,138,221,0.30)); }
        }
        @keyframes circ-flow { 0% { stroke-dashoffset: 1.14; opacity: .12 } 45% { opacity: .85 } 100% { stroke-dashoffset: 0; opacity: .12 } }
        .circ-cur { stroke-dasharray: 0.14 1; animation: circ-flow 3s ease-in-out infinite }
        @keyframes wordmark-glow {
          0%,100% { text-shadow: 0 0 14px rgba(91,184,245,0.45), 0 0 36px rgba(55,138,221,0.22) }
          50%     { text-shadow: 0 0 22px rgba(91,184,245,0.75), 0 0 60px rgba(55,138,221,0.40) }
        }
        .zynapse-wordmark { animation: fadeUp .8s ease-out both, wordmark-glow 3s ease-in-out infinite }
        @media (prefers-reduced-motion: reduce) {
          .hero-logo { animation: none !important; transform: none !important }
          .circ-cur { animation: none !important; opacity: .22 !important }
          .zynapse-wordmark { animation: none !important; text-shadow: 0 0 16px rgba(91,184,245,0.5) !important }
        }
        @keyframes pulse-ring { 0%{transform:scale(0.8);opacity:.4} 100%{transform:scale(2.5);opacity:0} }
        @keyframes glow-pulse { 0%,100%{opacity:.3} 50%{opacity:.7} }
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
        @keyframes circuit-flow { 0%{stroke-dashoffset:40} 100%{stroke-dashoffset:0} }
        .fu { animation: fadeUp .8s ease-out both }
        .fu1 { animation-delay:.1s } .fu2 { animation-delay:.2s }
        .fu3 { animation-delay:.35s } .fu4 { animation-delay:.5s }
        .cta-main { transition: all .25s }
        .cta-main:hover { transform:translateY(-2px); box-shadow: 0 8px 40px rgba(55,138,221,.3) }
        .feat { transition: all .25s; position: relative }
        .feat::before {
          content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1.5px;
          background: conic-gradient(from var(--feat-angle), rgba(91,184,245,0) 0deg, rgba(91,184,245,0) 200deg, rgba(55,138,221,0.9) 270deg, #5BB8F5 320deg, #CDEBFF 345deg, #5BB8F5 360deg);
          -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
                  mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
          -webkit-mask-composite: xor; mask-composite: exclude;
          filter: drop-shadow(0 0 3px rgba(91,184,245,0.6));
          opacity: 0; transition: opacity .25s; pointer-events: none;
          animation: feat-rotate 2.6s linear infinite; animation-play-state: paused;
        }
        .feat:hover { border-color: rgba(55,138,221,.2) !important; transform: translateY(-2px) }
        .feat:hover::before { opacity: 1; animation-play-state: running }
        @property --feat-angle { syntax: "<angle>"; initial-value: 0deg; inherits: false }
        @keyframes feat-rotate { to { --feat-angle: 360deg } }
        @media (prefers-reduced-motion: reduce) { .feat:hover::before { animation: none !important; opacity: 1; background: linear-gradient(90deg,#378ADD,#5BB8F5) } }
        .nav-link { transition: color .2s }
        .nav-link:hover { color: #fff !important }
        .sec-btn:hover { border-color: rgba(255,255,255,0.15) !important; color: #fff !important }
        .plans-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px }
        @media (max-width: 820px) { .plans-grid { grid-template-columns: 1fr } }
        .steps-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 16px }
        @media (max-width: 820px) { .steps-grid { grid-template-columns: repeat(2,1fr) } }
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
            background: "linear-gradient(135deg, #378ADD, #5BB8F5)",
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
        <div style={{ position: "relative", marginBottom: 24, display: "flex", flexDirection: "column", alignItems: "center" }}>
          {/* circuite care ies din logo si radiaza sus/jos (SVG, CSS-only) */}
          <svg className="logo-circuits" width="560" height="760" viewBox="0 0 560 760" fill="none" aria-hidden="true"
            style={{ position: "absolute", left: "50%", top: "50%", transform: "translate(-50%,-50%)", zIndex: 0, pointerEvents: "none" }}>
            <defs>
              <filter id="logoCircGlow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2" /></filter>
            </defs>
            {/* trasee de baza (dim) */}
            <g stroke="#378ADD" strokeWidth="1" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.18">
              <path d="M240 250 V160 H170 V40" />
              <path d="M280 245 V20" />
              <path d="M320 250 V160 H390 V40" />
              <path d="M240 510 V600 H170 V720" />
              <path d="M280 515 V740" />
              <path d="M320 510 V600 H390 V720" />
            </g>
            {/* curent care curge ritmic, pompat din logo */}
            <g stroke="#5BB8F5" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" filter="url(#logoCircGlow)">
              <path className="circ-cur" pathLength="1" d="M240 250 V160 H170 V40" />
              <path className="circ-cur" pathLength="1" d="M280 245 V20" />
              <path className="circ-cur" pathLength="1" d="M320 250 V160 H390 V40" />
              <path className="circ-cur" pathLength="1" d="M240 510 V600 H170 V720" />
              <path className="circ-cur" pathLength="1" d="M280 515 V740" />
              <path className="circ-cur" pathLength="1" d="M320 510 V600 H390 V720" />
            </g>
            {/* noduri la capete */}
            <g fill="#5BB8F5" opacity="0.6">
              <circle cx="170" cy="40" r="2.4" /><circle cx="280" cy="20" r="2.4" /><circle cx="390" cy="40" r="2.4" />
              <circle cx="170" cy="720" r="2.4" /><circle cx="280" cy="740" r="2.4" /><circle cx="390" cy="720" r="2.4" />
            </g>
          </svg>
          <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)" }}>
            <PulseRing delay={0} /><PulseRing delay={1.3} /><PulseRing delay={2.6} />
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="Zynapse" width={290} height={290} className="hero-logo" style={{
            position: "relative", zIndex: 1,
            animation: "logo-pulse 3s ease-in-out infinite",
            filter: "brightness(2.5) contrast(1.1) drop-shadow(0 0 22px rgba(91,184,245,0.32)) drop-shadow(0 0 48px rgba(55,138,221,0.16))",
          }} />
        </div>

        <div className="zynapse-wordmark" style={{
          fontSize: "clamp(40px, 9vw, 60px)", fontWeight: 500, letterSpacing: 6,
          color: "#fff", lineHeight: 1, margin: "4px 0 30px",
        }}>ZYNAPSE</div>

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

        <p className="fu fu3" style={{
          margin: "0 0 38px", maxWidth: 560, fontSize: 15, fontStyle: "italic",
          color: "#7E8498", lineHeight: 1.6, textAlign: "center",
        }}>
          „Nu schimbăm normativele, doar le aplicăm pentru tine, scăpându-te de task-urile repetitive.”
        </p>

        <div className="fu fu4" style={{ display: "flex", gap: 16 }}>
          <a href="/register" className="cta-main" style={{
            padding: "15px 36px", borderRadius: 12, fontSize: 16, fontWeight: 600,
            background: "linear-gradient(135deg, #378ADD, #5BB8F5)",
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

      {/* ── Moto (bandă discretă) ── */}
      <section style={{ position: "relative", zIndex: 1, maxWidth: 720, margin: "0 auto", padding: "16px 40px 0", textAlign: "center" }}>
        <p style={{ fontSize: 15.5, lineHeight: 1.7, color: "#6E7488", margin: 0 }}>
          Zynapse este o platformă online care automatizează aplicarea normativelor și generează rapid livrabilele pentru proiecte de instalații electrice.
        </p>
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
        <div className="steps-grid">
          {[
            { n: "01", t: "Upload planșe", d: "PDF, JPG, PNG", icon: (
              <>
                <path d="M12 15.5V5M8 9l4-4 4 4" stroke="#5BB8F5" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M5 19h14" stroke="#378ADD" strokeWidth="1.6" strokeLinecap="round" />
              </>
            ) },
            { n: "02", t: "Formular", d: "Tip clădire, încălzire", icon: (
              <>
                <rect x="4.5" y="4" width="15" height="16" rx="2" stroke="#5BB8F5" strokeWidth="1.5" />
                <path d="M9 4V3.2a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V4" stroke="#378ADD" strokeWidth="1.4" strokeLinejoin="round" />
                <path d="M8 9.5h5M8 13h5" stroke="#378ADD" strokeWidth="1.3" strokeLinecap="round" />
                <path d="M8 16.6l1.4 1.4L12.6 15" stroke="#5BB8F5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </>
            ) },
            { n: "03", t: "AI procesează", d: "Claude Vision + calcul", icon: (
              <>
                <rect x="6" y="6" width="12" height="12" rx="2" stroke="#5BB8F5" strokeWidth="1.5" />
                <path d="M9.5 6V4M14.5 6V4M9.5 20v-2M14.5 20v-2M6 9.5H4M6 14.5H4M20 9.5h-2M20 14.5h-2" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
                <circle cx="12" cy="12" r="2.6" stroke="#5BB8F5" strokeWidth="1.4" />
                <path d="M12 8.7V7.8M12 16.2v-.9M8.7 12h-.9M16.2 12h-.9" stroke="#5BB8F5" strokeWidth="1.2" strokeLinecap="round" />
              </>
            ) },
            { n: "04", t: "Proiect gata", d: "Circuite, memoriu, liste cantități", icon: (
              <>
                <path d="M7 3.5h6.5L18 8v11.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z" stroke="#5BB8F5" strokeWidth="1.5" strokeLinejoin="round" />
                <path d="M13.5 3.5V8H18" stroke="#378ADD" strokeWidth="1.4" strokeLinejoin="round" />
                <path d="M9 15l2 2 4-4.5" stroke="#5BB8F5" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </>
            ) },
          ].map((s, i) => (
            <div key={i} className="feat" style={{
              padding: 24, borderRadius: 16, textAlign: "center",
              background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.04)",
            }}>
              <span style={{
                position: "absolute", top: 12, right: 14, fontSize: 11, fontWeight: 700,
                color: "#5BB8F5", opacity: 0.45, letterSpacing: 0.5,
              }}>{s.n}</span>
              <div style={{
                width: 48, height: 48, borderRadius: 13, margin: "0 auto 14px",
                background: "rgba(55,138,221,0.1)", border: "1px solid rgba(55,138,221,0.25)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">{s.icon}</svg>
              </div>
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
            { dot: "#5BB8F5", title: "Extragere AI din planșe", desc: "Claude Vision citește planșele și identifică încăperile automat" },
            { dot: "#5BB8F5", title: "Calcul conform normativelor", desc: "Dimensionare conform I7-2011, NP 061-2002, NTE 007/08/00 și PE 132-2003" },
            { dot: "#5BB8F5", title: "Memoriu tehnic automat", desc: "Document complet generat, gata de depus la proiect" },
            { dot: "#5BB8F5", title: "Liste de cantități instant", desc: "Liste de cantități automate, exportabile imediat în PDF" },
            { dot: "#5BB8F5", title: "DTAC & PT complet", desc: "Documentații complete pentru autorizare de construire" },
            { dot: "#5BB8F5", title: "Scheme monofilare", desc: "Scheme electrice monofilare generate automat, gata de export PDF" },
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
          background: "linear-gradient(160deg, rgba(55,138,221,0.05), rgba(55,138,221,0.03))",
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
            background: "linear-gradient(135deg, #378ADD, #5BB8F5)", color: "#fff",
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
