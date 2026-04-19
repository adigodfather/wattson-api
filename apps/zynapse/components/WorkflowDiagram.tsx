"use client";
import { useState } from "react";

const PHASES: Record<string, { label: string; color: string; desc: string; outputs: string[] }> = {
  DTAC: {
    label: "DTAC",
    color: "#F59E0B",
    desc: "Documentație Tehnică pentru Autorizația de Construire",
    outputs: ["Schema monofilară generală", "Tablou electric (structură)", "Consumatori principali", "Memoriu tehnic DTAC", "Breviar de calcul sarcină instalată"],
  },
  PT: {
    label: "PT",
    color: "#6366F1",
    desc: "Proiect Tehnic de Execuție",
    outputs: ["Plan prize + locații exacte", "Plan iluminat (becuri, spoturi, LED)", "Plan prize internet / TV / date", "Schema monofilară detaliată", "Calcul cablu (ml per circuit)", "BOM complet (materiale)", "Memoriu tehnic PT complet"],
  },
};

interface WorkflowNode {
  id: string;
  col: number;
  row: number;
  color: string;
  icon: string;
  tag: string;
  title: string;
  subtitle: string;
  details: string[];
  phase: string;
}

const allNodes: WorkflowNode[] = [
  { id: "upload", col: 0, row: 1, color: "#00C896", icon: "🌐", tag: "TRIGGER", title: "Site Upload", subtitle: "DWG / PDF / IFC", details: ["Form web: drag & drop fișier", "Selectare fază proiect: DTAC sau PT", "Date proiect: adresă, beneficiar, proiectant", "Webhook n8n primește fișierul + metadata"], phase: "both" },
  { id: "phase_router", col: 1, row: 0, color: "#F59E0B", icon: "🔀", tag: "ROUTER", title: "IF – Fază Proiect", subtitle: "DTAC sau PT?", details: ["Branch DTAC → flux simplificat", "Branch PT → flux complet cu planuri", "Setează flag-uri pentru nodurile aval"], phase: "both" },
  { id: "file_detect", col: 1, row: 2, color: "#F59E0B", icon: "📁", tag: "ROUTER", title: "IF – Tip Fișier", subtitle: "DWG / PDF", details: ["DWG → ODA File Converter API", "PDF → Claude Vision", "IFC → Parser 3D (viitor)"], phase: "both" },
  { id: "dwg_api", col: 2, row: 1, color: "#6366F1", icon: "📐", tag: "HTTP", title: "ODA / AutoCAD API", subtitle: "DWG → SVG + JSON", details: ["Conversie DWG → SVG vectorial", "Extrage layere (pereți, uși, ferestre)", "Coordonate exacte elemente arhitecturale", "Returnează dimensiuni reale (mm/m)"], phase: "both" },
  { id: "pdf_vision", col: 2, row: 3, color: "#6366F1", icon: "🔍", tag: "VISION", title: "Claude Vision", subtitle: "Analiză planșă PDF", details: ["Detectează camere + denumiri", "OCR: cotele dimensionale", "Identifică scara planului (1:50, 1:100)", "Returnează JSON camere + dimensiuni m²"], phase: "both" },
  { id: "room_ai", col: 3, row: 2, color: "#8B5CF6", icon: "🏠", tag: "AI", title: "Claude AI", subtitle: "Detectare & Clasificare Camere", details: ["Identifică: living, dormitor, baie, bucătărie, hol...", "Calculează suprafața fiecărei camere (m²)", "Detectează înălțimea de montaj din normativ", "Returnează: { camera, tip, suprafata, perimetru }"], phase: "both" },
  { id: "normative", col: 4, row: 0, color: "#EF4444", icon: "📚", tag: "DB", title: "Normative DB", subtitle: "Supabase / Airtable", details: ["Normativ I7-2011: prize, iluminat, circuite", "Baie: prize IP44, min 60cm față de cadă/duș", "Max 5 prize / circuit 16A", "Iluminat: min 100 lux living, 300 lux bucătărie", "Circuit dedicat: cuptor, mașină spălat, AC", "Înălțimi montaj: prize 30cm, întrerupătoare 90cm", "Cablu: NYM 3×2.5mm² prize, 3×1.5mm² iluminat"], phase: "both" },
  { id: "questions", col: 4, row: 2, color: "#10B981", icon: "💬", tag: "CHAT", title: "Chat Interactiv", subtitle: "Întrebări per cameră", details: ["„Câte prize în Living?" (normativ: min 4)", "„Iluminat: spot / plafoniera / bandă LED?"", "„Prize internet/TV în ce camere?"", "„AC în dormitor / living?"", "„Mașină spălat, uscător, dishwasher?"", "„Locație tablou electric?"", "Răspunsuri stocate în session JSON"], phase: "both" },
  { id: "consumers", col: 4, row: 4, color: "#10B981", icon: "⚡", tag: "INPUT", title: "Consumatori Speciali", subtitle: "Puteri declarate", details: ["Cuptor: 3500W / circuit 20A dedicat", "Mașină spălat: 2200W / 16A", "AC: 1500–3500W / circuit dedicat", "Boiler: 2000W / circuit dedicat", "Pompe, centrală termică, EV charger"], phase: "both" },
  { id: "circuit_calc", col: 5, row: 1, color: "#F59E0B", icon: "🔢", tag: "CALC", title: "Circuit Calculator", subtitle: "Distribuire circuite", details: ["Grupare prize: max 5/circuit 16A", "Grupare iluminat: max 8 puncte/circuit", "Circuite dedicate: identificare automată", "Numărare: C1-prize living, C2-iluminat, C3-AC...", "Validare vs normativ I7 → alertă dacă depășit"], phase: "both" },
  { id: "cable_calc", col: 5, row: 3, color: "#F59E0B", icon: "📏", tag: "CALC", title: "Cable Calculator", subtitle: "Lungimi cablu (ml)", details: ["Rută cablu: tablou → cameră (din plan)", "+ înălțime montaj tablou (ex: 1.6m)", "+ coborâre la priză (0.3m) sau întrerupător (0.9m)", "+ factor curbe: ×1.15 (15% extra)", "+ rezervă: +10% per circuit", "Tipuri: NYM 3×2.5mm² / 3×1.5mm² / 5×2.5mm²", "Output: { circuit, tip_cablu, lungime_ml }"], phase: "both" },
  { id: "power_calc", col: 6, row: 0, color: "#EC4899", icon: "⚡", tag: "CALC", title: "Power Calculator", subtitle: "Sarcină instalată & absorbită", details: ["Σ putere instalată: Ptotală (W)", "Factor de simultaneitate: ks=0.6–0.8", "Putere absorbită: Pabs = Pi × ks", "Curent absorbit: I = P / (√3 × U × cosφ)", "Selectare branșament: mono/trifazat", "Siguranță generală: 25A / 32A / 40A / 63A"], phase: "both" },
  { id: "breaker_calc", col: 6, row: 2, color: "#EC4899", icon: "🔌", tag: "CALC", title: "Breaker Selector", subtitle: "Siguranțe per circuit", details: ["Prize 16A → MCB 16A tip C, 3kA", "Iluminat 10A → MCB 10A tip B", "Cuptor/mașină → MCB 16A/20A dedicat", "AC → MCB 16A + protecție supratensiune", "RCCB general: 40A / 30mA (diferențial)", "RCCB baie: 25A / 10mA", "SPD (paratrăsnet): dacă în normativ"], phase: "both" },
  { id: "monofil_dtac", col: 7, row: 0, color: "#F59E0B", icon: "📊", tag: "DTAC", title: "Schema Monofilară", subtitle: "DTAC – structură tablou", details: ["Template SVG furnizat de tine", "Completare: nr. circuite, siguranțe, RCCB", "Consumatori principali cu puteri", "Branșament + contor electric", "Fără locații exacte prize (DTAC)"], phase: "DTAC" },
  { id: "plan_prize", col: 7, row: 2, color: "#6366F1", icon: "🗺️", tag: "PT", title: "Plan Prize + Internet", subtitle: "SVG overlay pe planșă", details: ["Poziții exacte prize 230V pe plan", "Prize internet/TV/date (RJ45, coaxial)", "Simboluri CEI 60617", "Numerotare prize per circuit (P1.1, P1.2...)", "Traseul cablurilor pe plan"], phase: "PT" },
  { id: "plan_iluminat", col: 7, row: 4, color: "#06B6D4", icon: "💡", tag: "PT", title: "Plan Iluminat", subtitle: "Becuri, spoturi, LED", details: ["Poziții corpuri de iluminat pe plan", "Tip: plafoniera, spot încastrat, bandă LED", "Întrerupătoare + dimmer poziții", "Calcul flux luminos (lm) per cameră", "Traseul circuitelor iluminat"], phase: "PT" },
  { id: "monofil_pt", col: 7, row: 6, color: "#6366F1", icon: "📋", tag: "PT", title: "Schema Monofilară", subtitle: "PT – detaliată complet", details: ["Template SVG al tău → completat automat", "Toate circuitele cu: nr. prize, nr. becuri, W", "Lungimi cablu per circuit (ml)", "Siguranțe individuale selectate", "RCCB, SPD, comutator de rețea"], phase: "PT" },
  { id: "bom", col: 8, row: 1, color: "#00C896", icon: "📦", tag: "BOM", title: "BOM Generator", subtitle: "Listă completă materiale", details: ["Cablu NYM 3×2.5mm²: X ml", "Cablu NYM 3×1.5mm²: X ml", "Cablu UTP Cat6: X ml", "Prize 230V schuko: X buc", "Prize IP44 baie: X buc", "Corpuri iluminat: X buc per tip", "MCB 16A/10A/20A: X buc", "RCCB 40A/30mA: X buc", "Tablou electric: 1 buc, X module", "Tuburi protecție, doze, bride: cantități"], phase: "both" },
  { id: "memoriu", col: 8, row: 3, color: "#00C896", icon: "📄", tag: "MEMO", title: "Memoriu Tehnic", subtitle: "Template tău + date auto", details: ["Template Word/PDF furnizat de tine", "Replace automat: {PUTERE_INSTALATA}, {NR_CIRCUITE}", "Replace: {TABLOU_LOCATIE}, {BRANSAMENT_TIP}", "Replace: {LISTA_CONSUMATORI}, {NORMATIVE_APLICATE}", "DTAC: memoriu scurt ~3 pagini", "PT: memoriu complet + breviar calcul + anexe", "Output: .docx / .pdf gata semnat"], phase: "both" },
  { id: "export", col: 9, row: 2, color: "#00C896", icon: "📤", tag: "DONE", title: "Export Final", subtitle: "Dosar complet proiect", details: ["📁 /DTAC: schema monofilară + memoriu", "📁 /PT: planuri + scheme + memoriu + BOM", "Format: PDF + DWG/SVG + XLSX (BOM)", "Arhivă .zip cu tot dosarul", "Email automat client + link download", "Stocare Google Drive / S3"], phase: "both" },
];

const edgeDefs = [
  { from: "upload", to: "phase_router" }, { from: "upload", to: "file_detect" },
  { from: "phase_router", to: "monofil_dtac", label: "DTAC", dash: true },
  { from: "file_detect", to: "dwg_api", label: "DWG" }, { from: "file_detect", to: "pdf_vision", label: "PDF" },
  { from: "dwg_api", to: "room_ai" }, { from: "pdf_vision", to: "room_ai" },
  { from: "room_ai", to: "normative" }, { from: "room_ai", to: "questions" }, { from: "room_ai", to: "consumers" },
  { from: "normative", to: "circuit_calc" }, { from: "questions", to: "circuit_calc" },
  { from: "questions", to: "cable_calc" }, { from: "consumers", to: "cable_calc" },
  { from: "consumers", to: "power_calc" }, { from: "circuit_calc", to: "power_calc" },
  { from: "circuit_calc", to: "breaker_calc" }, { from: "cable_calc", to: "breaker_calc" },
  { from: "power_calc", to: "monofil_dtac" }, { from: "breaker_calc", to: "monofil_dtac" },
  { from: "breaker_calc", to: "plan_prize" }, { from: "breaker_calc", to: "plan_iluminat" },
  { from: "breaker_calc", to: "monofil_pt" },
  { from: "monofil_dtac", to: "bom" }, { from: "plan_prize", to: "bom" },
  { from: "plan_iluminat", to: "bom" }, { from: "monofil_pt", to: "bom" },
  { from: "bom", to: "memoriu" }, { from: "bom", to: "export" }, { from: "memoriu", to: "export" },
];

const COLS = ["INPUT", "FAZĂ / TIP", "PARSE", "AI CAMERE", "DATE INPUT", "CALCULE", "PROTECȚII", "DESENE", "BOM + MEMO", "EXPORT"];

const COL_W = 190;
const ROW_H = 115;
const NODE_W = 168;
const NODE_H = 72;
const PAD_X = 20;
const PAD_Y = 20;

function nodePos(node: WorkflowNode) {
  return { x: PAD_X + node.col * COL_W, y: PAD_Y + node.row * ROW_H };
}
function nodeCenter(node: WorkflowNode) {
  const p = nodePos(node);
  return { x: p.x + NODE_W / 2, y: p.y + NODE_H / 2 };
}

const SVG_W = PAD_X * 2 + COLS.length * COL_W;
const SVG_H = 900;

export default function WorkflowDiagram() {
  const [selected, setSelected] = useState<string | null>(null);
  const [activePhase, setActivePhase] = useState("both");

  const selNode = allNodes.find((n) => n.id === selected);
  const visibleNodes = allNodes.filter(
    (n) => activePhase === "both" || n.phase === "both" || n.phase === activePhase
  );
  const visibleIds = new Set(visibleNodes.map((n) => n.id));

  return (
    <section id="arhitectura" className="py-24 px-4" style={{ borderTop: "1px solid var(--border)" }}>
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-10">
          <p className="text-xs font-mono uppercase tracking-widest mb-3" style={{ color: "var(--accent)" }}>
            Arhitectura sistemului
          </p>
          <h2 className="text-3xl sm:text-4xl font-extrabold mb-3" style={{ color: "var(--text)" }}>
            Schema n8n — Flux complet DTAC / PT
          </h2>
          <p className="text-sm mb-6" style={{ color: "var(--muted)" }}>
            Click pe orice nod pentru detalii de implementare.
          </p>

          {/* Phase toggle */}
          <div className="flex gap-3 justify-center mb-2">
            {[
              { key: "both", label: "Ambele faze", color: "#64748B" },
              { key: "DTAC", label: "DTAC", color: "#F59E0B" },
              { key: "PT", label: "PT – Proiect Tehnic", color: "#6366F1" },
            ].map((p) => (
              <button key={p.key} onClick={() => setActivePhase(p.key)} style={{
                padding: "6px 18px", borderRadius: 8,
                border: `1.5px solid ${activePhase === p.key ? p.color : "var(--border)"}`,
                background: activePhase === p.key ? p.color + "22" : "transparent",
                color: activePhase === p.key ? p.color : "var(--muted)",
                fontSize: 11, fontFamily: "monospace", fontWeight: 700,
                cursor: "pointer", letterSpacing: 1, transition: "all .2s",
              }}>{p.label}</button>
            ))}
          </div>
          <p className="text-xs" style={{ color: "var(--muted2)" }}>
            {activePhase === "DTAC" && "DTAC → Schema monofilară + Memoriu (fără planuri detaliate)"}
            {activePhase === "PT" && "PT → Planuri prize + iluminat + internet + scheme + BOM + Memoriu complet"}
            {activePhase === "both" && "Vizualizezi fluxul complet de automatizare"}
          </p>
        </div>

        {/* Phase cards */}
        <div className="flex gap-3 mb-8 justify-center flex-wrap">
          {Object.entries(PHASES).map(([key, ph]) => (
            <div key={key} className="rounded-xl p-4" style={{
              background: "var(--bg2)", border: `1px solid ${ph.color}44`,
              minWidth: 260, maxWidth: 320,
            }}>
              <div className="font-extrabold text-sm tracking-widest mb-1" style={{ color: ph.color }}>{ph.label}</div>
              <div className="text-xs mb-3" style={{ color: "var(--muted)" }}>{ph.desc}</div>
              {ph.outputs.map((o) => (
                <div key={o} className="flex items-center gap-2 text-xs mb-1" style={{ color: "var(--muted)" }}>
                  <span style={{ color: ph.color }}>✓</span>{o}
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* SVG Canvas */}
        <div className="rounded-xl overflow-auto" style={{
          background: "#0A0E1A", border: "1px solid var(--border)", padding: "12px 0",
        }}>
          <div style={{ display: "flex", paddingLeft: PAD_X, marginBottom: 8 }}>
            {COLS.map((c, i) => (
              <div key={i} style={{
                minWidth: COL_W, fontSize: 8, color: "#1E3A5F",
                textAlign: "center", letterSpacing: 1.5, textTransform: "uppercase",
                borderLeft: i > 0 ? "1px solid #0F172A" : "none",
              }}>{c}</div>
            ))}
          </div>

          <svg width={SVG_W} height={SVG_H} style={{ display: "block" }}>
            <defs>
              <pattern id="dots" width="30" height="30" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="0.8" fill="#1A2035" />
              </pattern>
              <marker id="arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6 Z" fill="#1E3A5F" />
              </marker>
              <marker id="arr-active" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6 Z" fill="#00C896" />
              </marker>
            </defs>
            <rect width={SVG_W} height={SVG_H} fill="url(#dots)" />

            {edgeDefs.map((e, i) => {
              const fn = allNodes.find((n) => n.id === e.from);
              const tn = allNodes.find((n) => n.id === e.to);
              if (!fn || !tn || !visibleIds.has(fn.id) || !visibleIds.has(tn.id)) return null;
              const fc = nodeCenter(fn);
              const tc = nodeCenter(tn);
              const mx = (fc.x + tc.x) / 2;
              const isActive = selected === e.from || selected === e.to;
              const col = isActive ? "#00C896" : "#1E3A5F";
              return (
                <g key={i}>
                  <path
                    d={`M${fc.x},${fc.y} C${mx},${fc.y} ${mx},${tc.y} ${tc.x},${tc.y}`}
                    stroke={col} strokeWidth={isActive ? 1.8 : 1} fill="none"
                    strokeDasharray={(e as { dash?: boolean }).dash ? "5 4" : isActive ? "none" : "3 3"}
                    markerEnd={isActive ? "url(#arr-active)" : "url(#arr)"}
                    opacity={isActive ? 1 : 0.5}
                  />
                  {(e as { label?: string }).label && (
                    <text x={mx} y={(fc.y + tc.y) / 2 - 5}
                      textAnchor="middle" fill="#F59E0B"
                      fontSize="8" fontWeight="bold" fontFamily="monospace">
                      {(e as { label?: string }).label}
                    </text>
                  )}
                </g>
              );
            })}

            {visibleNodes.map((node) => {
              const { x, y } = nodePos(node);
              const isSel = selected === node.id;
              const dimmed = selected !== null && !isSel &&
                !edgeDefs.some((e) => (e.from === selected && e.to === node.id) || (e.to === selected && e.from === node.id));
              return (
                <g key={node.id} transform={`translate(${x},${y})`}
                  onClick={() => setSelected(isSel ? null : node.id)}
                  style={{ cursor: "pointer" }}>
                  {isSel && <rect x={-5} y={-5} width={NODE_W + 10} height={NODE_H + 10}
                    rx={14} fill={node.color} opacity={0.12} />}
                  <rect width={NODE_W} height={NODE_H} rx={10}
                    fill={isSel ? "#141C2E" : "#0F1520"}
                    stroke={node.color} strokeWidth={isSel ? 2 : 0.8}
                    opacity={dimmed ? 0.25 : 1} />
                  <rect width={NODE_W} height={3} rx={10} fill={node.color} opacity={dimmed ? 0.1 : 0.9} />
                  <rect x={NODE_W - 48} y={7} width={40} height={13} rx={4} fill={node.color} opacity={0.15} />
                  <text x={NODE_W - 28} y={17.5} textAnchor="middle" fill={node.color}
                    fontSize="7" fontWeight="bold" fontFamily="monospace" opacity={dimmed ? 0.3 : 1}>
                    {node.tag}
                  </text>
                  <text x={8} y={28} fontSize="13" opacity={dimmed ? 0.2 : 1}>{node.icon}</text>
                  <text x={26} y={28} fill="#F1F5F9" fontSize="9.5" fontWeight="700"
                    fontFamily="monospace" opacity={dimmed ? 0.2 : 1}>{node.title}</text>
                  <text x={8} y={54} fill="#475569" fontSize="8.5"
                    fontFamily="monospace" opacity={dimmed ? 0.1 : 1}>{node.subtitle}</text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Detail panel */}
        <div className="mt-4 rounded-xl p-5 transition-all" style={{
          background: "var(--bg2)", border: "1px solid var(--border)", minHeight: 100,
        }}>
          {selNode ? (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <span className="text-2xl">{selNode.icon}</span>
                <div>
                  <div className="font-extrabold text-sm tracking-wide" style={{ color: selNode.color }}>{selNode.title}</div>
                  <div className="text-xs" style={{ color: "var(--muted)" }}>{selNode.subtitle}</div>
                </div>
                <div className="ml-auto px-3 py-1 rounded text-xs font-bold tracking-widest" style={{
                  background: selNode.color + "22", color: selNode.color, border: `1px solid ${selNode.color}44`,
                }}>{selNode.tag}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                {selNode.details.map((d) => (
                  <div key={d} className="flex items-center gap-2 text-xs rounded-lg px-3 py-1.5" style={{
                    background: "#141C2E", border: `1px solid ${selNode.color}2A`, color: "var(--text)",
                  }}>
                    <span style={{ color: selNode.color }}>▸</span>{d}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-center text-xs tracking-widest mt-6" style={{ color: "var(--muted2)" }}>
              ↑ Click pe orice nod pentru detalii tehnice de implementare
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
