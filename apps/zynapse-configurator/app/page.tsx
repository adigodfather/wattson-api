"use client";

import { useState, useEffect, useRef } from "react";
import { CalculatorPanel } from "@/components/CreditCalculator";

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
  // Pe mobil (<768px) NU randam canvas-ul deloc: fara JS/animatie/RAF -> fundal
  // curat (#050709) si zero consum de baterie. Default false = SSR-safe.
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(min-width: 768px)");
    const apply = () => setEnabled(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    if (!enabled) return;       // mobil -> efectul (RAF + listeneri) nici nu porneste
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
  }, [enabled]);

  if (!enabled) return null;    // mobil: niciun canvas in DOM

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
        href={p.custom ? "mailto:office@zynapse.org" : "/register"}
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

/* ─── Schemă de flux „Cum funcționează" (CSS/SVG, fără JS per frame) ─── */
const FLOW_PLANSE_ICON = (
  <>
    <rect x="5" y="3" width="14" height="18" rx="2" stroke="#5BB8F5" strokeWidth="1.5" />
    <path d="M8 8h8M8 11.5h8M8 15h5" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
  </>
);
const FLOW_BRAIN_ICON = (
  <>
    <path d="M9.5 4.2A2.7 2.7 0 0 0 5 6.5 2.4 2.4 0 0 0 4 11a2.4 2.4 0 0 0 1.2 4.3A2.5 2.5 0 0 0 9.5 17.8" stroke="#5BB8F5" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M14.5 4.2A2.7 2.7 0 0 1 19 6.5 2.4 2.4 0 0 1 20 11a2.4 2.4 0 0 1-1.2 4.3A2.5 2.5 0 0 1 14.5 17.8" stroke="#5BB8F5" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M12 4.6v13.6" stroke="#378ADD" strokeWidth="1.1" strokeLinecap="round" />
    <path d="M9.5 8.2c1 .7 2.2 .7 3.2 0M14.5 10.6c-1 .7-2.2 .7-3.2 0" stroke="#378ADD" strokeWidth="1" strokeLinecap="round" />
  </>
);
const FLOW_DELIVERABLES: { label: string; icon: React.ReactNode }[] = [
  {
    label: "Schemă monofilară",
    icon: (
      <>
        <path d="M12 2.5v19" stroke="#5BB8F5" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="12" cy="4.5" r="1.2" fill="#378ADD" />
        <path d="M12 8h4.5" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
        <rect x="16.5" y="6.6" width="4" height="2.8" rx="0.6" stroke="#378ADD" strokeWidth="1.1" />
        <path d="M12 13H7.5" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
        <circle cx="5.6" cy="13" r="1.9" stroke="#378ADD" strokeWidth="1.1" />
        <path d="M12 18h4.5" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
        <path d="M16.8 16.5v3M18.3 16.5v3M19.8 16.5v3" stroke="#378ADD" strokeWidth="1" strokeLinecap="round" />
      </>
    ),
  },
  {
    label: "Memoriu tehnic",
    icon: (
      <>
        <path d="M12 6c-1.7-1.2-4.1-1.5-6.6-1.2v12c2.5-.3 4.9 0 6.6 1.2" stroke="#5BB8F5" strokeWidth="1.4" strokeLinejoin="round" />
        <path d="M12 6c1.7-1.2 4.1-1.5 6.6-1.2v12c-2.5-.3-4.9 0-6.6 1.2" stroke="#5BB8F5" strokeWidth="1.4" strokeLinejoin="round" />
        <path d="M12 6v12" stroke="#378ADD" strokeWidth="1.2" />
      </>
    ),
  },
  {
    label: "Liste de cantități",
    icon: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="2" stroke="#5BB8F5" strokeWidth="1.4" />
        <path d="M9 4v16" stroke="#378ADD" strokeWidth="1.1" />
        <path d="M4 9.3h16M4 14.6h16" stroke="#378ADD" strokeWidth="1.1" />
        <path d="M5.6 6.4l.8 .8 1.3-1.4" stroke="#5BB8F5" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M5.6 11.7l.8 .8 1.3-1.4" stroke="#5BB8F5" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M5.6 17l.8 .8 1.3-1.4" stroke="#5BB8F5" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M11 6.7h6M11 12h6M11 17.3h6" stroke="#378ADD" strokeWidth="1.1" strokeLinecap="round" />
      </>
    ),
  },
  {
    label: "Circuite dimensionate",
    icon: (
      <>
        <path d="M3 8h6v8h12" stroke="#5BB8F5" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M9 8V4h8" stroke="#378ADD" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="3" cy="8" r="1.2" fill="#5BB8F5" /><circle cx="21" cy="16" r="1.2" fill="#5BB8F5" /><circle cx="17" cy="4" r="1.2" fill="#5BB8F5" />
      </>
    ),
  },
];

const FLOW_CURVES = [
  "M460 302 C 360 345, 205 352, 133 384",
  "M460 302 C 432 348, 382 354, 351 384",
  "M460 302 C 488 348, 538 354, 569 384",
  "M460 302 C 560 345, 715 352, 787 384",
];

function FlowDiagram() {
  return (
    <>
      {/* Flux vertical (desktop/tabletă) */}
      <svg className="flow-h" viewBox="0 0 920 548" preserveAspectRatio="xMidYMid meet" fill="none" aria-hidden="true">
        <defs>
          <filter id="flGlow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="3.4" /></filter>
        </defs>

        {/* săgeți curbe creier -> livrabile: bază dim + curent care curge (stagger) */}
        {FLOW_DELIVERABLES.map((d, i) => (
          <path key={`b${i}`} d={FLOW_CURVES[i]} stroke="#378ADD" strokeWidth="1.2" opacity="0.18" fill="none" strokeLinecap="round" />
        ))}
        {FLOW_DELIVERABLES.map((d, i) => (
          <path key={`c${i}`} className="fl-cur" pathLength="1" d={FLOW_CURVES[i]} stroke="#5BB8F5" strokeWidth="1.7" fill="none" strokeLinecap="round" filter="url(#flGlow)" style={{ animationDelay: `${i * 0.5}s` }} />
        ))}

        {/* Input „Planșe" (sus) */}
        <rect x="410" y="22" width="100" height="100" rx="18" fill="rgba(55,138,221,0.06)" stroke="rgba(55,138,221,0.25)" strokeWidth="1.5" />
        <svg x="437" y="49" width="46" height="46" viewBox="0 0 24 24" fill="none">{FLOW_PLANSE_ICON}</svg>
        <text x="460" y="146" textAnchor="middle" fontSize="15" fontWeight="600" fill="#9FD2FA">Planșe</text>

        {/* planșă care „călătorește" în jos spre creier */}
        <g className="fl-travel">
          <svg x="447" y="92" width="26" height="26" viewBox="0 0 24 24" fill="none">{FLOW_PLANSE_ICON}</svg>
        </g>

        {/* săgeată în jos spre creier */}
        <path d="M460 162 V206" stroke="#378ADD" strokeWidth="1.3" opacity="0.3" strokeLinecap="round" />
        <path d="M454 201 L460 210 L466 201" stroke="#5BB8F5" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />

        {/* Analiză AI: creier (fără chenar) cu glow care pulsează */}
        <circle className="fl-aiglow" cx="460" cy="258" r="46" fill="#378ADD" filter="url(#flGlow)" />
        <g className="fl-brain">
          <svg x="421" y="219" width="78" height="78" viewBox="0 0 24 24" fill="none">{FLOW_BRAIN_ICON}</svg>
        </g>
        <text x="460" y="340" textAnchor="middle" fontSize="15" fontWeight="600" fill="#9FD2FA">Analiză AI</text>

        {/* Livrabile (jos, casete mari egale) */}
        {FLOW_DELIVERABLES.map((d, i) => {
          const cx = 133 + i * 218;
          return (
            <g key={`d${i}`}>
              <circle cx={cx} cy="384" r="2.6" fill="#5BB8F5" />
              <rect x={cx - 85} y="384" width="170" height="150" rx="16" fill="rgba(55,138,221,0.05)" stroke="rgba(55,138,221,0.2)" strokeWidth="1.4" />
              <svg x={cx - 21} y="410" width="42" height="42" viewBox="0 0 24 24" fill="none">{d.icon}</svg>
              <text x={cx} y="500" textAnchor="middle" fontSize="13.5" fontWeight="600" fill="#cfd3df">{d.label}</text>
            </g>
          );
        })}
      </svg>

      {/* Vertical compact (mobil) */}
      <div className="flow-v" style={{ flexDirection: "column", alignItems: "center" }}>
        <div style={{ width: 150, padding: "16px 12px", borderRadius: 14, textAlign: "center", background: "rgba(55,138,221,0.06)", border: "1px solid rgba(55,138,221,0.22)" }}>
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" style={{ display: "block", margin: "0 auto 6px" }}>{FLOW_PLANSE_ICON}</svg>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#9FD2FA" }}>Planșe</div>
        </div>
        <svg width="12" height="30" viewBox="0 0 12 30" fill="none" style={{ margin: "8px 0" }}>
          <path d="M6 0V30" stroke="#378ADD" strokeWidth="1.5" opacity="0.25" />
          <path className="fl-down" d="M6 0V30" stroke="#5BB8F5" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <div style={{ textAlign: "center" }}>
          <svg className="fl-brain" width="58" height="58" viewBox="0 0 24 24" fill="none" style={{ display: "block", margin: "0 auto 6px", filter: "drop-shadow(0 0 12px rgba(91,184,245,0.45))" }}>{FLOW_BRAIN_ICON}</svg>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#9FD2FA" }}>Analiză AI</div>
        </div>
        <svg width="12" height="30" viewBox="0 0 12 30" fill="none" style={{ margin: "8px 0" }}>
          <path d="M6 0V30" stroke="#378ADD" strokeWidth="1.5" opacity="0.25" />
          <path className="fl-down" d="M6 0V30" stroke="#5BB8F5" strokeWidth="1.6" strokeLinecap="round" style={{ animationDelay: ".4s" }} />
        </svg>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, width: "100%", maxWidth: 380 }}>
          {FLOW_DELIVERABLES.map((d, i) => (
            <div key={i} className="feat" style={{ padding: "18px 12px", borderRadius: 14, textAlign: "center", background: "rgba(55,138,221,0.05)", border: "1px solid rgba(55,138,221,0.16)" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style={{ display: "block", margin: "0 auto 8px" }}>{d.icon}</svg>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: "#cfd3df", lineHeight: 1.3 }}>{d.label}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default function Landing() {
  const [hovered, setHovered] = useState<number | null>(null);

  return (
    <div style={{
      minHeight: "100vh", background: "#050709",
      fontFamily: "'Instrument Sans', 'DM Sans', system-ui, sans-serif",
      color: "#c0c0c0", position: "relative", overflowX: "hidden", maxWidth: "100%",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { margin: 0; background: #050709; overflow-x: hidden; max-width: 100%; }
        @keyframes fadeUp { from{opacity:0;transform:translateY(30px)} to{opacity:1;transform:translateY(0)} }
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
        @keyframes logo-pulse {
          0%, 100% { transform: scale(1);    filter: brightness(2.5) contrast(1.1) drop-shadow(0 0 22px rgba(91,184,245,0.32)) drop-shadow(0 0 48px rgba(55,138,221,0.16)); }
          50%      { transform: scale(1.06); filter: brightness(2.6) contrast(1.1) drop-shadow(0 0 40px rgba(91,184,245,0.6))  drop-shadow(0 0 84px rgba(55,138,221,0.30)); }
        }
        @keyframes circ-flow { 0% { stroke-dashoffset: 1.14; opacity: .12 } 45% { opacity: .85 } 100% { stroke-dashoffset: 0; opacity: .12 } }
        .circ-cur { stroke-dasharray: 0.14 1; animation: circ-flow 3s ease-in-out infinite }
        @keyframes wordmark-glow {
          0%,100% { filter: drop-shadow(0 0 12px rgba(91,184,245,0.35)) }
          50%     { filter: drop-shadow(0 0 22px rgba(91,184,245,0.70)) }
        }
        .zynapse-wordmark { animation: fadeUp .8s ease-out both, shimmer 3.2s linear infinite, wordmark-glow 3s ease-in-out infinite }
        @media (prefers-reduced-motion: reduce) {
          .hero-logo { animation: none !important; transform: none !important }
          .circ-cur { animation: none !important; opacity: .22 !important }
          .zynapse-wordmark { animation: none !important; filter: drop-shadow(0 0 14px rgba(91,184,245,0.45)) !important }
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
        .rules-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px }
        @media (max-width: 760px) { .rules-grid { grid-template-columns: 1fr } }
        .calc-row { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 20px; align-items: start; max-width: 1000px; margin: 40px auto 0 }
        @media (max-width: 860px) { .calc-row { grid-template-columns: 1fr; max-width: 560px; gap: 16px } }
        .cefade-card { animation: zy-cefade .35s ease }
        @keyframes zy-cefade { from { opacity: 0; transform: translateY(4px) } to { opacity: 1; transform: none } }
        @media (prefers-reduced-motion: reduce) { .cefade-card { animation: none } }
        .norm-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 12px }
        @media (max-width: 820px) { .norm-grid { grid-template-columns: repeat(2,1fr) } }
        @media (max-width: 520px) { .norm-grid { grid-template-columns: 1fr } }
        .flow-h { display: block; width: 100%; max-width: 720px; height: auto; margin: 0 auto }
        .flow-v { display: none; flex-direction: column; align-items: center }
        @media (max-width: 768px) { .flow-h { display: none } .flow-v { display: flex } }
        .nav-links { display: flex; gap: 28px; align-items: center }
        .landing-header { padding: 14px 40px }
        @media (max-width: 768px) { .nav-links { display: none } .landing-header { padding: 12px 18px } }
        .fl-travel { animation: fl-travel 3.6s ease-in-out infinite; transform-box: fill-box; transform-origin: center }
        @keyframes fl-travel { 0% { transform: translate(0,0) scale(1); opacity: 0 } 14% { opacity: 1 } 70% { transform: translate(0,118px) scale(.42); opacity: 1 } 84%,100% { transform: translate(0,118px) scale(.42); opacity: 0 } }
        .fl-cur { stroke-dasharray: 0.16 1; animation: fl-flow 2.8s ease-in-out infinite }
        @keyframes fl-flow { 0% { stroke-dashoffset: 1.16; opacity: .15 } 45% { opacity: .9 } 100% { stroke-dashoffset: 0; opacity: .15 } }
        .fl-aiglow { animation: fl-aiglow 3s ease-in-out infinite; transform-box: fill-box; transform-origin: center }
        @keyframes fl-aiglow { 0%,100% { opacity: .16; transform: scale(1) } 50% { opacity: .5; transform: scale(1.22) } }
        .fl-brain { animation: fl-brain 3s ease-in-out infinite; transform-box: fill-box; transform-origin: center }
        @keyframes fl-brain { 0%,100% { transform: scale(1) } 50% { transform: scale(1.09) } }
        .fl-ai-v { animation: fl-aiglowv 3s ease-in-out infinite }
        @keyframes fl-aiglowv { 0%,100% { box-shadow: 0 0 14px rgba(55,138,221,0.15) } 50% { box-shadow: 0 0 30px rgba(55,138,221,0.4) } }
        .fl-down { stroke-dasharray: 6 8; animation: fl-down 1.3s linear infinite }
        @keyframes fl-down { to { stroke-dashoffset: -14 } }
        @media (prefers-reduced-motion: reduce) {
          .fl-travel { animation: none !important; opacity: 0 !important }
          .fl-cur { animation: none !important; opacity: .3 !important }
          .fl-aiglow { animation: none !important; opacity: .3 !important }
          .fl-brain { animation: none !important }
          .fl-ai-v { animation: none !important }
          .fl-down { animation: none !important }
        }
      `}</style>

      <CircuitCanvas />

      {/* ── Header ── */}
      <header className="landing-header" style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: "rgba(5,7,9,0.85)", backdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(255,255,255,0.03)",
      }}>
        <a href="/" aria-label="Zynapse — pagina principală" style={{ display: "flex", alignItems: "center", gap: 9, textDecoration: "none" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="" width={34} height={34} style={{ objectFit: "contain", filter: "brightness(2.2) drop-shadow(0 0 6px rgba(91,184,245,0.45))" }} />
          <span className="zynapse-wordmark" style={{
            fontSize: 21, fontWeight: 700, letterSpacing: 2, lineHeight: 1,
            background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            backgroundSize: "200% 100%", filter: "drop-shadow(0 0 10px rgba(91,184,245,0.4))",
          }}>ZYNAPSE</span>
        </a>
        <nav style={{ display: "flex", gap: 20, alignItems: "center" }}>
          <div className="nav-links">
            {[
              { label: "Calculator", href: "#pachete" },
              { label: "Cum funcționează", href: "#cum-functioneaza" },
              { label: "Contact", href: "mailto:office@zynapse.org" },
            ].map(item => (
              <a key={item.label} href={item.href} className="nav-link"
                style={{ color: "#666", fontSize: 13, textDecoration: "none", fontWeight: 500 }}>
                {item.label}
              </a>
            ))}
          </div>
          <a href="/login" className="cta-main" style={{
            padding: "8px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "linear-gradient(135deg, #378ADD, #5BB8F5)",
            color: "#fff", textDecoration: "none", whiteSpace: "nowrap",
          }}>Intră în cont</a>
        </nav>
      </header>

      {/* ── Hero ── */}
      <section style={{
        minHeight: "100vh", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        position: "relative", zIndex: 1, padding: "120px 40px 80px", textAlign: "center",
      }}>
        <h1 className="fu fu2" style={{
          fontSize: "clamp(34px, 9vw, 56px)", fontWeight: 700, lineHeight: 1.06, color: "#fff",
          margin: "0 0 22px", letterSpacing: -1.5, maxWidth: 700,
        }}>
          Proiectare electrică<br />
          <span style={{
            background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            backgroundSize: "200% 100%", animation: "shimmer 3.2s linear infinite",
            filter: "drop-shadow(0 0 14px rgba(91,184,245,0.35))",
          }}>din viitor</span>
        </h1>

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
          fontSize: "clamp(40px, 9vw, 60px)", fontWeight: 700, letterSpacing: 6, lineHeight: 1, margin: "4px 0 30px",
          background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
          WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
          backgroundSize: "200% 100%", filter: "drop-shadow(0 0 14px rgba(91,184,245,0.4))",
        }}>ZYNAPSE</div>

        <p className="fu fu3" style={{
          fontSize: 17, lineHeight: 1.7, color: "#555", margin: "0 0 36px", maxWidth: 520,
        }}>
          Nu schimbăm normativele, doar le aplicăm pentru tine, scăpându-te de task-urile repetitive.
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
            Calculează Z-Coins
          </a>
        </div>

        <div style={{
          display: "flex", flexWrap: "wrap", justifyContent: "center",
          gap: 40, marginTop: 40, padding: "28px 0",
          borderTop: "1px solid rgba(255,255,255,0.04)",
        }}>
          {[
            { v: "Asistență AI", l: "analiză automată", hi: true },
            { v: "I7-2011", l: "100% conform", hi: false },
            { v: "DTAC + PT", l: "faze complete", hi: false },
            { v: "1 Z-Coin / m²", l: "preț transparent", hi: false },
          ].map((s, i) => (
            <div key={i} style={{ textAlign: "center" }}>
              <div style={{
                fontSize: s.hi ? 24 : 20, fontWeight: 700, letterSpacing: -.5,
                color: s.hi ? "#5BB8F5" : "#fff",
                textShadow: s.hi ? "0 0 16px rgba(91,184,245,0.5)" : "none",
              }}>{s.v}</div>
              <div style={{ fontSize: s.hi ? 12 : 11, color: s.hi ? "#7FB4E0" : "#444", marginTop: 2, letterSpacing: .5 }}>{s.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Ce facem ── */}
      <section style={{ position: "relative", zIndex: 1, maxWidth: 1000, margin: "0 auto", padding: "40px 40px 20px" }}>
        <h2 style={{ fontSize: 34, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 18px", letterSpacing: -.8 }}>
          Ce facem
        </h2>
        <p style={{ textAlign: "center", color: "#888", fontSize: 16, lineHeight: 1.75, margin: "0 auto", maxWidth: 720 }}>
          Zynapse transformă planșele tale arhitecturale în documentație electrică completă. Sistemul analizează automat încăperile, dimensionează circuitele și generează schema monofilară, memoriul tehnic și listele de cantități — toate conform normativelor românești în vigoare. Tu păstrezi controlul deciziilor de proiectare; noi eliminăm munca repetitivă de calcul și redactare.
        </p>

        <p style={{ textAlign: "center", color: "#5BB8F5", fontSize: 13, fontWeight: 600, letterSpacing: .5, margin: "44px 0 18px" }}>
          NORMATIVELE PE CARE LE APLICĂM
        </p>
        <div className="norm-grid">
          {[
            { code: "I7-2011", desc: "Instalații electrice aferente clădirilor" },
            { code: "NP 061-2002", desc: "Sisteme de iluminat artificial" },
            { code: "NTE 007/08/00", desc: "Rețele de cabluri electrice" },
            { code: "PE 132-2003", desc: "Rețele electrice de distribuție" },
            { code: "NP 099-2004", desc: "Instalații electrice în zone cu pericol de explozie" },
            { code: "I18/1-2002", desc: "Instalații electrice de curenți slabi" },
            { code: "I18/2-2002", desc: "Semnalizare incendii și alarmare" },
            { code: "STAS 12604", desc: "Protecția împotriva electrocutărilor (prize de pământ)" },
            { code: "Legea 10/1995", desc: "Calitatea în construcții" },
          ].map(n => (
            <div key={n.code} className="feat" style={{
              padding: "16px 18px", borderRadius: 14,
              background: "rgba(55,138,221,0.04)", border: "1px solid rgba(55,138,221,0.14)",
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#5BB8F5", marginBottom: 5 }}>{n.code}</div>
              <div style={{ fontSize: 12.5, color: "#888", lineHeight: 1.5 }}>{n.desc}</div>
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
        <FlowDiagram />
      </section>

      {/* ── Arhitectură (plan care se desenează) ── */}
      <section style={{
        position: "relative", zIndex: 1,
        maxWidth: 900, margin: "0 auto", padding: "60px 40px",
      }}>
        <h2 style={{ fontSize: 34, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 10px", letterSpacing: -.8 }}>
          Arhitectura ta, citită automat
        </h2>
        <p style={{ textAlign: "center", color: "#555", fontSize: 15, margin: "0 0 40px" }}>
          AI-ul interpretează planșele și extrage încăperile, ca un proiectant
        </p>
        <div style={{ maxWidth: 620, margin: "0 auto" }}>
          <svg viewBox="0 0 420 290" preserveAspectRatio="xMidYMid meet" fill="none" aria-hidden="true" style={{ display: "block", width: "100%", height: "auto" }}>
            <defs>
              <filter id="bpArch" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.4" /></filter>
            </defs>
            <style dangerouslySetInnerHTML={{ __html: `
              .bp{animation:bp-fade 15s ease-in-out infinite}
              @keyframes bp-fade{0%{opacity:0}2.5%{opacity:1}93%{opacity:1}100%{opacity:0}}
              .bp-line{stroke-dasharray:1}
              .bp-1{animation:bp-d1 15s ease-in-out infinite}
              .bp-2{animation:bp-d2 15s ease-in-out infinite}
              .bp-3{animation:bp-d3 15s ease-in-out infinite}
              .bp-4{animation:bp-d4 15s ease-in-out infinite}
              .bp-5{animation:bp-d5 15s ease-in-out infinite}
              @keyframes bp-d1{0%,2%{stroke-dashoffset:1}25%,100%{stroke-dashoffset:0}}
              @keyframes bp-d2{0%,25%{stroke-dashoffset:1}45%,100%{stroke-dashoffset:0}}
              @keyframes bp-d3{0%,45%{stroke-dashoffset:1}63%,100%{stroke-dashoffset:0}}
              @keyframes bp-d4{0%,63%{stroke-dashoffset:1}74%,100%{stroke-dashoffset:0}}
              @keyframes bp-d5{0%,74%{stroke-dashoffset:1}85%,100%{stroke-dashoffset:0}}
              .bp-glow-el{animation:bp-glow 15s ease-in-out infinite}
              @keyframes bp-glow{0%,86%{opacity:0}90%{opacity:.5}94%,100%{opacity:0}}
              @media (prefers-reduced-motion: reduce){
                .bp{animation:none!important;opacity:1!important}
                .bp-line{animation:none!important;stroke-dashoffset:0!important}
                .bp-glow-el{animation:none!important;opacity:0!important}
              }
            `}} />
            <g className="bp" fill="none" strokeLinecap="round" strokeLinejoin="round">
              {/* halo puls pe contur (după desenarea completă) */}
              <path className="bp-glow-el" d="M30 30 H390 V260 H30 Z" stroke="#5BB8F5" strokeWidth="2.8" filter="url(#bpArch)" />
              {/* contur exterior */}
              <path className="bp-line bp-1" pathLength="1" d="M30 30 H390 V260 H30 Z" stroke="#5BB8F5" strokeWidth="2.4" />
              {/* pereți interiori principali */}
              <path className="bp-line bp-2" pathLength="1" d="M180 30 V180 M30 180 H390 M290 30 V180" stroke="#378ADD" strokeWidth="1.8" />
              {/* pereți interiori secundari (camere) */}
              <path className="bp-line bp-3" pathLength="1" d="M120 180 V260 M230 180 V260 M320 180 V260 M180 110 H290" stroke="#378ADD" strokeWidth="1.7" />
              {/* uși (arce de deschidere) */}
              <path className="bp-line bp-4" pathLength="1" d="M180 130 A22 22 0 0 0 158 152 M250 180 A20 20 0 0 1 270 200 M290 90 A18 18 0 0 0 272 108" stroke="#5BB8F5" strokeWidth="1.6" />
              {/* ferestre */}
              <path className="bp-line bp-5" pathLength="1" d="M80 26 H120 M80 34 H120 M320 26 H360 M320 34 H360 M26 95 V135 M34 95 V135 M160 256 H200 M160 264 H200" stroke="#5BB8F5" strokeWidth="1.6" />
            </g>
          </svg>
        </div>
      </section>

      {/* ── Reguli ── */}
      <section style={{ position: "relative", zIndex: 1, maxWidth: 760, margin: "0 auto", padding: "40px 40px 60px" }}>
        <h2 style={{ fontSize: 30, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 10px", letterSpacing: -.6 }}>
          Reguli pentru o colaborare corectă
        </h2>
        <p style={{ textAlign: "center", color: "#666", fontSize: 14, margin: "0 0 28px" }}>
          Câteva cerințe simple ca proiectul tău să iasă impecabil
        </p>

        {/* Casetă legală evidențiată — glow pulsatoriu (reutilizează .zy-current; static la reduced-motion) */}
        <div className="zy-current" style={{
          borderRadius: 16, padding: "22px 26px", marginBottom: 24,
          background: "rgba(55,138,221,0.08)", border: "1px solid rgba(91,184,245,0.35)",
          boxShadow: "0 0 36px rgba(55,138,221,0.16)",
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#5BB8F5", letterSpacing: .5, marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
            <span aria-hidden="true">⚠</span> CERINȚE LEGALE OBLIGATORII
          </div>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 14 }}>
            {[
              "Toate planșele, schemele, memoriile tehnice și listele de cantități trebuie asumate de către un inginer proiectant autorizat ANRE.",
              "Documentațiile tehnice pentru autorizarea construirii (DTAC) și proiectele tehnice (PT) trebuie verificate de un verificator de proiecte atestat MDLPA.",
            ].map(r => (
              <li key={r} style={{ display: "flex", alignItems: "flex-start", gap: 11, fontSize: 14.5, fontWeight: 500, color: "#cfe6ff", lineHeight: 1.6 }}>
                <span style={{ color: "#5BB8F5", flexShrink: 0, fontWeight: 700 }}>▸</span>{r}
              </li>
            ))}
          </ul>
        </div>

        <div className="rules-grid">
          <div style={{
            padding: "24px 26px", borderRadius: 16,
            background: "rgba(55,138,221,0.04)", border: "1px solid rgba(55,138,221,0.16)",
            boxShadow: "0 0 30px rgba(55,138,221,0.06)",
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#5BB8F5", letterSpacing: .5, marginBottom: 14 }}>PLANȘE</div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                "Planșele să nu fie semnate sau ștampilate",
                "Planșele să nu fie semnate electronic",
                "Planșele să nu fie scanate (preferabil format vectorial / PDF nativ)",
              ].map(r => (
                <li key={r} style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: 14, color: "#9FD2FA", lineHeight: 1.55 }}>
                  <span style={{ color: "#5BB8F5", flexShrink: 0 }}>▸</span>{r}
                </li>
              ))}
            </ul>
          </div>
          <div style={{
            padding: "24px 26px", borderRadius: 16,
            background: "rgba(55,138,221,0.04)", border: "1px solid rgba(55,138,221,0.16)",
            boxShadow: "0 0 30px rgba(55,138,221,0.06)",
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#5BB8F5", letterSpacing: .5, marginBottom: 14 }}>SUPRAFAȚĂ DECLARATĂ</div>
            <p style={{ fontSize: 14, color: "#9FD2FA", lineHeight: 1.7, margin: 0 }}>
              Suprafața declarată trebuie să corespundă planșelor încărcate. Declararea unei suprafețe mai mici decât cea reală, pentru a reduce numărul de Z-Coins, atrage penalizarea contului.
            </p>
          </div>
        </div>
      </section>

      {/* ── Calculator ── */}
      <section id="pachete" style={{
        position: "relative", zIndex: 1,
        maxWidth: 1200, margin: "0 auto", padding: "40px 40px 100px",
      }}>
        <h2 style={{ fontSize: 34, fontWeight: 700, color: "#fff", textAlign: "center", margin: "0 0 12px", letterSpacing: -.8 }}>
          Calculează-ți proiectul
        </h2>
        <p style={{ textAlign: "center", color: "#888", fontSize: 15, margin: 0 }}>
          Estimează Z-Coins și costul în câteva secunde
        </p>
        <CalculatorPanel />

        <p style={{ textAlign: "center", color: "#888", fontSize: 13.5, margin: "44px auto 0", maxWidth: 560, lineHeight: 1.6 }}>
          Primii 100 de utilizatori primesc <strong style={{ color: "#5BB8F5" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/z-coin.svg" alt="" width={15} height={15} style={{ display: "inline-block", verticalAlign: "-2px", marginRight: 4 }} />500 Z-Coins gratuite</strong> la confirmarea contului.
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
              { label: "Calculator", href: "#pachete" },
              { label: "Termeni și Condiții", href: "/terms" },
              { label: "Confidențialitate", href: "/privacy" },
              { label: "Politică de retur", href: "/refund" },
              { label: "Contact", href: "mailto:office@zynapse.org" },
            ].map(item => (
              <a key={item.label} href={item.href} style={{ fontSize: 12, color: "#444", textDecoration: "none" }}>{item.label}</a>
            ))}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
            <span style={{ fontSize: 12, color: "#555", fontWeight: 500 }}>S.C. ZYNAPSE S.R.L.</span>
            <a href="mailto:office@zynapse.org" style={{ fontSize: 12, color: "#888", textDecoration: "none" }}>office@zynapse.org</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
