"use client";

// Editor vizual plan — PASUL 3.6: panou stâng pe CAMERE (accordion) cu Add/Remove per cameră.
// Peste 3.1 (PNG+overlay), 3.2 (DRAG cu persistare), 3.3/3.4a (selecție), 3.4b (editare Tip/Putere).
// Coordonate: afișare px = x_pdf * png_meta.scale (spațiul PNG, în Layer). Stage are scaleX/scaleY =
// displayScale (PNG->ecran), transform SEPARAT. Salvare drag: x_pdf = e.target.x() / scale (invers exact).
// Add = INSERT cu ACELAȘI tipar ca popularea (configurator.tsx); id e gen_random_uuid() în DB.
// Remove = DELETE manual (cu confirm inline), fără paritate automată.
// react-konva e client-only (canvas/window) -> importat cu dynamic ssr:false în configurator.
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Stage, Layer, Image as KonvaImage, Circle, Rect, Line, Arc, Text, Group } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import { createClient } from "@/lib/supabase";
import { prizeRuleForRoom, placePrizasInRoom } from "@/lib/auto-prize";   // R1+F5a: reguli prize + plasare
import { floorCanonic, floorIndex } from "@/lib/floors";   // M2a: un singur sistem de etaje (canonic)
import { HEATING_RECEPTOR_TYPES, visibleHeatingReceptors, visibleEquipmentReceptors } from "@/lib/constants";   // Regula 10 + H5/H6: receptoare gate-uite pe formular
import type { HeatingEquipment } from "@/lib/heating-equipment";   // T3: echipamentele de incalzire auto-plasabile

type PngMeta = {
  dpi?: number; scale?: number;
  pdf_width_pt?: number; pdf_height_pt?: number;
  png_width_px?: number; png_height_px?: number;
} | null;

type PlanElement = {
  id: string;
  element_type: string;
  room: string | null;
  label: string | null;
  power_w: number | null;
  x: number;
  y: number;
  rotation: number | null;
  plan_type: string | null;
  floor: string | null;
  status: string | null;   // doar tablouri: 'nou' | 'existent' (altele null)
  wall_mounted?: boolean | null;   // true pt. aparataj pe perete (intrerupatoare/prize)
  mount_height_m?: number | null;   // doar prize (metri); default 0.6, editabil per priza
  phase?: string | null;            // Regula 10: 'mono' | 'tri' (radiator/VCV per element); null = mono
  circuit_id?: string | null;       // atribuit AUTOMAT la "Obtine plan" (C3); incarcat pt. eticheta (C4)
  cable_path?: number[][] | null;   // doar "traseu" (dunga): [[x0,y0],[x1,y1]] puncte PDF
};

const COL_BULB = "#1E63D6";
const COL_SWITCH = "#D62828";
const COL_SEL = "#FFD400";        // contur galben pe plan pt. elementul selectat
const COL_SENZOR_FILL = "#FAC775"; // umplutură galbenă DOAR pt. aplica_senzor
const DISPLAY_W_FALLBACK = 1200;  // lățime inițială până măsurăm containerul (editor full-width)
const NO_ROOM = "(fără cameră)";  // grupul pentru elemente cu room null
// coloanele citite (read + re-select după insert) — aceeași listă, o singură sursă
const SELECT_COLS = "id, element_type, room, label, power_w, phase, x, y, rotation, plan_type, floor, status, wall_mounted, mount_height_m, circuit_id, cable_path";

// Tipuri permise de CHECK (chk_element_type), grupate pe categorie. VALOAREA = exact valoarea din CHECK.
const BULB_TYPES = [
  { value: "lustra_led",    label: "Lustră LED" },
  { value: "aplica_tavan",  label: "Aplică tavan" },
  { value: "aplica_perete", label: "Aplică perete" },
  { value: "aplica_senzor", label: "Aplică cu senzor" },
  { value: "banda_led",     label: "Bandă LED" },
];
const SWITCH_TYPES = [
  { value: "intrerupator_simplu",    label: "Întrerupător simplu" },
  { value: "intrerupator_dublu",     label: "Întrerupător dublu" },
  { value: "intrerupator_triplu",    label: "Întrerupător triplu" },
  { value: "intrerupator_cap_scara", label: "Întrerupător cap scară" },
];
// Tablouri (panouri) — desenate distinct: dreptunghi împărțit diagonal în 2 culori + conector scurt.
// colA = triunghi sus-dreapta, colB = triunghi jos-stânga. (Plasarea + selectorul nou/existent vin separat.)
const PANEL_TYPES = [
  { value: "tablou_teg",    label: "Tablou TEG",    short: "TEG",   colA: "#F0F0F0", colB: "#22C55E" },
  { value: "tablou_te_ct",  label: "Tablou TE-CT",  short: "TE-CT", colA: "#EF4444", colB: "#3B82F6" },
  { value: "tablou_tes",    label: "Tablou TES",    short: "TES",   colA: "#F0F0F0", colB: "#1565C0" },
  { value: "transformator", label: "Transformator", short: "TR",    colA: "#D1D5DB", colB: "#6B7280" },
  // FV-P1: tablourile sistemului fotovoltaic (gated pe solar.enabled, DOAR parter, montaj în label).
  // INV are simbol propriu (pătrat roșu ~/=) — colA/colB nefolosite acolo.
  { value: "tablou_tcc",    label: "Tablou T.CC (FV)",   short: "T.CC", colA: "#F0F0F0", colB: "#1a1a1a" },
  { value: "tablou_inv",    label: "Invertor solar (FV)", short: "INV",  colA: "#FFFFFF", colB: "#DC2626" },
  { value: "tablou_tca",    label: "Tablou T.CA (FV)",   short: "T.CA", colA: "#F0F0F0", colB: "#1a1a1a" },
];
const FV_PANEL_TYPES = ["tablou_tcc", "tablou_inv", "tablou_tca"];
const isFvPanelType = (t: string) => FV_PANEL_TYPES.includes(t);
const FV_SPACING = 16;   // FV-B2: pasul blocului T.CC|INV|T.CA (pt; simbol 14x14 -> 2pt aer) — buton + drag
// Prize (aparataj pe perete) — simbol semicerc (priza). MULTIPLE per plansa. Tipurile sunt deja in CHECK.
const PRIZA_TYPES = [
  { value: "priza_simpla",        label: "Priză simplă" },
  { value: "priza_dubla",         label: "Priză dublă" },
  { value: "priza_16a",           label: "Alimentare directă" },
  { value: "priza_exterior_ip44", label: "Priză exterior (IP44)" },
];

const BULB_SET = new Set(BULB_TYPES.map(o => o.value));
const SWITCH_SET = new Set(SWITCH_TYPES.map(o => o.value));
const PANEL_SET = new Set(PANEL_TYPES.map(o => o.value));
const PRIZA_SET = new Set(PRIZA_TYPES.map(o => o.value));
const isBulbType = (t: string) => BULB_SET.has(t);
const isSwitchType = (t: string) => SWITCH_SET.has(t);
const isPanelType = (t: string) => PANEL_SET.has(t);
const isPrizaType = (t: string) => PRIZA_SET.has(t);
const isLegendType = (t: string) => t === "legenda";
const isTraseuType = (t: string) => t === "traseu";
const isGroundType = (t: string) => t === "ground_electrode_path";   // Faza 3: priza de pamant (polyline pe fundatie)
const isFvChainType = (t: string) => t === "fv_chain_path";          // lantul FV desenat MANUAL (polilinie deschisa galbena)
const isReceptorType = (t: string) => t === "alimentare_receptor";   // Receptoare bucata A: 1 tip + `label` (boiler/cuptor/...)
const isInternetType = (t: string) => t === "receptor_internet";     // Retea internet (RJ45): simbol propriu (turcoaz + router + WiFi)
// Inaltime de montaj DEFAULT pe tip la receptoare (metri), ca la prize; modificabila in editor.
// boiler/AC/HRV/net = 2.0 ; cuptor = 0.5 ; EV/statie = 1.2 ; necunoscut = 0.6 (default coloana).
// Regula 10: metadata receptorului termic din LABEL exact (radiator/VCV/distribuitor zona) sau null.
function heatingReceptorDef(label: string | null | undefined) {
  return HEATING_RECEPTOR_TYPES.find(t => t.label === (label || "")) || null;
}
function receptorDefaultHeight(et: string, label: string): number {
  const h = heatingReceptorDef(label);
  if (h) return h.default_height;                    // Regula 10: radiator 0.3 / VCV 2.2 / distribuitor 0.5
  if (et === "receptor_internet") return 2.0;
  const l = (label || "").toLowerCase();
  if (l.includes("cuptor")) return 0.5;
  if (l.includes("statie") || l.includes("incarcare") || l.includes("ev")) return 1.2;
  if (l.includes("boiler") || l.includes("aer") || l.includes("condi") || l === "ac" || l.includes("hrv") || l.includes("recuper")) return 2.0;
  return 0.6;
}
const COL_PRIZA = "#1565C0";   // simbol priza in editor (ALBASTRU/forta — coerent cu cablurile, distinct de iluminat)
const COL_GROUND = "#F27308";  // PORTOCALIU — priza de pamant (platbanda), coerent cu backend _GROUND_COLOR
const COL_FV_CHAIN = "#F9A825";  // GALBEN/GOLD — lantul FV desenat manual, coerent cu backend _FV_LINK_COLOR
// caseta-placeholder a legendei in editor, in PUNCTE PDF (afisata x scale, ca elementele).
// Doar placeholder mutabil; continutul real (simboluri + text) se deseneaza pe PDF la "Obtine plan" (L3).
const LEG_W = 90, LEG_H = 60;
// culori + etichetă scurtă pt. simbolul de tablou
const PANEL_INFO: Record<string, { short: string; colA: string; colB: string }> =
  Object.fromEntries(PANEL_TYPES.map(o => [o.value, { short: o.short, colA: o.colA, colB: o.colB }]));

// etichetă prietenoasă pt. tip (ex. aplica_tavan -> "Aplică tavan"); fallback la valoarea brută
const TYPE_LABEL: Record<string, string> = Object.fromEntries(
  [...BULB_TYPES, ...SWITCH_TYPES, ...PANEL_TYPES, ...PRIZA_TYPES].map(o => [o.value, o.label])
);
const typeLabel = (t: string) => TYPE_LABEL[t] || t;

// X (2 diagonale) înscris într-un cerc de rază r — refolosit la tavan / lustră / senzor
function bulbX(r: number) {
  const d = r * 0.7071;
  return (
    <>
      <Line points={[-d, -d, d, d]} stroke={COL_BULB} strokeWidth={2} listening={false} />
      <Line points={[-d, d, d, -d]} stroke={COL_BULB} strokeWidth={2} listening={false} />
    </>
  );
}

// Simbol bec per tip (Konva), contur albastru COL_BULB, relativ la origine (0,0). Senzor = fill galben.
function bulbSymbol(type: string) {
  switch (type) {
    case "aplica_perete":   // semicerc (partea curbă în jos) + punct plin
      return (
        <>
          <Arc x={0} y={0} innerRadius={0} outerRadius={9} angle={180} rotation={0} stroke={COL_BULB} strokeWidth={2} />
          <Circle x={0} y={4} radius={1.8} fill={COL_BULB} listening={false} />
        </>
      );
    case "lustra_led":      // cerc + X, mai mare, cu 2 cercuri concentrice exterioare
      return (
        <>
          <Circle x={0} y={0} radius={24} stroke={COL_BULB} strokeWidth={1.5} listening={false} />
          <Circle x={0} y={0} radius={18} stroke={COL_BULB} strokeWidth={1.5} listening={false} />
          <Circle x={0} y={0} radius={12} stroke={COL_BULB} strokeWidth={2} />
          {bulbX(12)}
        </>
      );
    case "banda_led":       // dreptunghi alungit rotunjit + liniuțe interioare (LED-uri)
      return (
        <>
          <Rect x={-30} y={-7} width={60} height={14} cornerRadius={7} stroke={COL_BULB} strokeWidth={2} />
          {[-18, -6, 6, 18].map(tx => (
            <Line key={tx} points={[tx, -3, tx, 3]} stroke={COL_BULB} strokeWidth={1.5} listening={false} />
          ))}
        </>
      );
    case "aplica_senzor":   // cerc + X, dar cu interior GALBEN
      return (
        <>
          <Circle x={0} y={0} radius={9} stroke={COL_BULB} strokeWidth={2} fill={COL_SENZOR_FILL} />
          {bulbX(9)}
        </>
      );
    default:                // aplica_tavan: cerc (fără fill) + X
      return (
        <>
          <Circle x={0} y={0} radius={9} stroke={COL_BULB} strokeWidth={2} />
          {bulbX(9)}
        </>
      );
  }
}

// Zonă de hit invizibilă -> Group draggable/clickable (simbolurile sunt fără fill -> n-ar avea hit interior)
function bulbHit(type: string) {
  if (type === "banda_led") return <Rect x={-32} y={-9} width={64} height={18} cornerRadius={7} fill="rgba(0,0,0,0.001)" />;
  const r = type === "lustra_led" ? 26 : 11;
  return <Circle x={0} y={0} radius={r} fill="rgba(0,0,0,0.001)" />;
}

// Contur de selecție (galben) adaptat la mărimea/forma fiecărui tip de bec
function bulbSelRing(type: string) {
  if (type === "banda_led") return <Rect x={-35} y={-12} width={70} height={24} cornerRadius={6} stroke={COL_SEL} strokeWidth={3} listening={false} />;
  const r = type === "lustra_led" ? 29 : 15;
  return <Circle x={0} y={0} radius={r} stroke={COL_SEL} strokeWidth={3} listening={false} />;
}

// Simbol PRIZA (Konva): semicerc UMPLUT turcoaz (SPATELE, curbă JOS) + 2 contacte DEASUPRA (deschiderea);
// contur ALBASTRU COL_PRIZA. priza_16a = ALIMENTARE DIRECTĂ (cerc PLIN). IP44 = cutie + semicerc ALB (teal).
// Orientare: rotația (DB) duce CONTACTELE spre cameră; simbol identic cu _draw_priza (PDF). Dim. editor = referință.
const PRIZA_TURQ = "#3fd0c9";   // umplutura prizelor interioare
const PRIZA_TEAL = "#0f766e";   // contur IP44 (teal închis, distinct de interior)
const PRIZA_DARK = "#0d3c7a";   // contur alimentare directă (albastru închis)
const NET_FILL = "#BA68C8";     // retea internet: dreptunghi VIOLET plin (distinct de albastrul prizei)
const NET_EDGE = "#8E24AA";     // retea internet: contur violet inchis
const TRASEU_PRINCIPAL = "#1565C0";   // traseu principal: albastru inchis (= culoarea existenta -> zero regresie)
const TRASEU_SECUNDAR = "#1ab3ab";    // traseu secundar: turcoaz (distinct de principal)
const traseuCol = (label?: string | null) => (label === "secundar" ? TRASEU_SECUNDAR : TRASEU_PRINCIPAL);   // fara label -> principal
function prizaSymbol(type: string) {
  const C = COL_PRIZA;
  const disc = (cx: number, r = 13, fill: string = PRIZA_TURQ, edge: string = C) => (
    <Arc x={cx} y={0} innerRadius={0} outerRadius={r} angle={180} rotation={0} fill={fill} stroke={edge} strokeWidth={2} />
  );
  const contacts = (cx: number, col: string = C) => (
    <>
      <Line points={[cx - 5, -3, cx - 5, -10]} stroke={col} strokeWidth={1.5} listening={false} />
      <Line points={[cx + 5, -3, cx + 5, -10]} stroke={col} strokeWidth={1.5} listening={false} />
    </>
  );
  switch (type) {
    case "priza_dubla":
      return <>{disc(-13, 11)}{contacts(-13)}{disc(13, 11)}{contacts(13)}</>;
    case "priza_16a":   // ALIMENTARE DIRECTĂ = cerc PLIN albastru (consumatori conectați direct, fără priză)
      return <Circle x={0} y={0} radius={13} fill={C} stroke={PRIZA_DARK} strokeWidth={2} />;
    case "priza_exterior_ip44":
      return <><Rect x={-18} y={-16} width={36} height={34} cornerRadius={4} fill={PRIZA_TURQ} stroke={PRIZA_TEAL} strokeWidth={1.5} listening={false} />{disc(0, 13, "#ffffff", PRIZA_TEAL)}{contacts(0, PRIZA_TEAL)}<Text x={-16} y={21} text="IP44" fontSize={9} fontStyle="bold" fill={PRIZA_TEAL} listening={false} /></>;
    default: // priza_simpla
      return <>{disc(0)}{contacts(0)}</>;
  }
}
function prizaHit() {   // zonă de hit invizibilă (acoperă simbolul mărit ×1.6) -> Group draggable
  return <Circle x={0} y={0} radius={21} fill="rgba(0,0,0,0.001)" />;
}
function prizaSelRing(type: string) {
  const w = type === "priza_dubla" ? 60 : 44;
  return <Rect x={-w / 2} y={-23} width={w} height={46} cornerRadius={4} stroke={COL_SEL} strokeWidth={3} listening={false} />;
}

// Simbol RETEA INTERNET (RJ45): dreptunghi turcoaz plin + router alb (contur + 2 LED-uri + liniuta)
// in jos + 3 unde WiFi albe deasupra. IDENTIC cu _draw_internet (PDF): backend = aceleasi numere * 0.6.
function netArc(r: number): number[] {   // unda WiFi = arc alb centrat la (0,5), deschis in SUS (210°..330°)
  const out: number[] = [];
  for (let i = 0; i <= 10; i++) {
    const a = ((210 + 12 * i) * Math.PI) / 180;
    out.push(r * Math.cos(a), 5 + r * Math.sin(a));
  }
  return out;
}
function internetSymbol() {
  const W = "#ffffff";
  return (
    <>
      <Rect x={-15} y={-15} width={30} height={30} cornerRadius={5} fill={NET_FILL} stroke={NET_EDGE} strokeWidth={1.6} />
      <Rect x={-9} y={4} width={18} height={8} cornerRadius={1} stroke={W} strokeWidth={1.6} listening={false} />
      <Circle x={-5.5} y={8} radius={1.3} fill={W} listening={false} />
      <Circle x={-2.5} y={8} radius={1.3} fill={W} listening={false} />
      <Line points={[2, 8, 7, 8]} stroke={W} strokeWidth={1.6} listening={false} lineCap="round" />
      <Line points={netArc(4)} stroke={W} strokeWidth={1.5} listening={false} lineCap="round" lineJoin="round" />
      <Line points={netArc(7.5)} stroke={W} strokeWidth={1.5} listening={false} lineCap="round" lineJoin="round" />
      <Line points={netArc(11)} stroke={W} strokeWidth={1.5} listening={false} lineCap="round" lineJoin="round" />
    </>
  );
}

// ── SNAP PRIZA PE PERETE (P3): proiectie punct-pe-segment CLAMPAT (t in [0,1]) — aceeasi matematica ca B2. ──
type WallSeg = { x1: number; y1: number; x2: number; y2: number };
function projectOnSegment(px: number, py: number, x1: number, y1: number, x2: number, y2: number) {
  const dx = x2 - x1, dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  let t = len2 <= 1e-9 ? 0 : ((px - x1) * dx + (py - y1) * dy) / len2;
  t = Math.max(0, Math.min(1, t));   // CLAMPAT pe segment (nu linie infinita)
  const qx = x1 + t * dx, qy = y1 + t * dy;
  return { x: qx, y: qy, dist: Math.hypot(px - qx, py - qy) };
}
// cel mai apropiat perete; daca sub prag -> proiectie (snapped) + ORIENTAREA peretelui ("h"/"v",
// pt. rotatia simbolului), altfel pozitie libera. walls gol -> fara snap. Sincron cu lib/auto-prize.ts.
function snapToWall(px: number, py: number, walls: WallSeg[], threshold = 40) {
  let best: { x: number; y: number; dist: number; wall: "h" | "v" } | null = null;
  for (const w of walls) {
    const p = projectOnSegment(px, py, w.x1, w.y1, w.x2, w.y2);
    if (!best || p.dist < best.dist)
      best = { ...p, wall: Math.abs(w.x2 - w.x1) >= Math.abs(w.y2 - w.y1) ? "h" : "v" };
  }
  if (best && best.dist < threshold) return { x: best.x, y: best.y, snapped: true, wall: best.wall };
  return { x: px, y: py, snapped: false, wall: null as "h" | "v" | null };
}
// Snap la o POLILINIE (ex. traseul PRINCIPAL): cea mai apropiata proiectie pe segmentele ei; sub prag
// -> punctul lipit, altfel null. Reutilizeaza projectOnSegment (ca snapToWall) — secundar pornit din principal.
function snapToPolyline(px: number, py: number, pts: number[][], threshold = 30): [number, number] | null {
  let best: { x: number; y: number; dist: number } | null = null;
  for (let i = 0; i < pts.length - 1; i++) {
    const p = projectOnSegment(px, py, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]);
    if (!best || p.dist < best.dist) best = p;
  }
  return best && best.dist < threshold ? [best.x, best.y] : null;
}

const fieldLabel: CSSProperties = { display: "block", fontSize: 10, color: "#8B8FA8", marginBottom: 3, textTransform: "uppercase", letterSpacing: 0.3 };
const inputStyle: CSSProperties = {
  width: "100%", boxSizing: "border-box", marginBottom: 10, padding: "8px 10px", fontSize: 12.5,
  color: "#E6E8F0", borderRadius: 7, outline: "none", fontFamily: "inherit",
};

// ── RUBRICĂ: container de grupare pentru sidebar-ul de forța (register PRODUS, impeccable). ──
// „Al doilea strat neutru" (panou distinct: tint subtil + border), heading SENTENCE-CASE 13.5px/600 —
// NU alt titlu uppercase, ca sa NU fie „eyebrow peste eyebrow" fata de sub-titlurile 11px din interior.
// Spacing mai mare INTRE rubrici (marginTop 16) decat intre sub-sectiuni (12). Reutilizabil pt. toate rubricile.
// DOAR aspect: infasoara continutul (functiile render existente), fara sa atinga handler-ele.
function Rubrica({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section style={{
      marginTop: 16, padding: "13px 13px 12px", borderRadius: 10,
      background: "rgba(255,255,255,0.022)", border: "1px solid rgba(255,255,255,0.06)",
    }}>
      <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 600, letterSpacing: "-0.01em", color: "#E6E8F0", lineHeight: 1.3 }}>
        {title}
      </h3>
      {hint ? <p style={{ margin: "4px 0 0", fontSize: 10.5, color: "#6B7086", lineHeight: 1.45 }}>{hint}</p> : null}
      <div style={{ marginTop: 10 }}>{children}</div>
    </section>
  );
}

// Stări de interacțiune injectate o dată (focus/hover/placeholder + accordion + butoane add/remove).
// border+background pe câmpuri trăiesc aici (nu inline) ca focus-ul accent să suprascrie fără !important.
const FIELD_CSS = `
.zy-ed-field { border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.04);
  transition: border-color .15s ease, background-color .15s ease; }
.zy-ed-field:hover:not(:focus):not(:disabled) { border-color: rgba(255,255,255,0.18); }
.zy-ed-field:focus { border-color: #378ADD; background: rgba(55,138,221,0.08); }
.zy-ed-field::placeholder { color: #5B6076; }
.zy-ed-field:disabled { opacity: .85; cursor: default; }
.zy-chev { transition: transform .18s ease; }
.zy-acc-body { animation: zy-acc-in .18s ease-out; }
@keyframes zy-acc-in { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: none; } }
.zy-add-btn { border: 1px dashed rgba(255,255,255,0.14); background: transparent; color: #8B8FA8;
  border-radius: 6px; padding: 4px 9px; font-size: 11px; cursor: pointer; font-family: inherit; transition: all .15s ease; }
.zy-add-btn:hover { border-color: #378ADD; color: #5BB8F5; background: rgba(55,138,221,0.08); }
.zy-del-x { background: none; border: none; color: #3A3D50; cursor: pointer; font-size: 16px; line-height: 1;
  padding: 1px 6px; border-radius: 5px; transition: all .15s ease; }
.zy-del-x:hover { color: #F09595; background: rgba(214,40,40,0.12); }
.zy-del-yes { background: rgba(214,40,40,0.16); border: 1px solid rgba(214,40,40,0.4); color: #F09595;
  border-radius: 5px; padding: 2px 8px; cursor: pointer; font-family: inherit; font-size: 11px; }
.zy-del-no { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.12); color: #C5C8D6;
  border-radius: 5px; padding: 2px 8px; cursor: pointer; font-family: inherit; font-size: 11px; }
.zy-getplan { width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 11px 14px; border-radius: 9px; border: 1px solid #378ADD; background: #378ADD; color: #fff;
  font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: background-color .15s ease; }
.zy-getplan:hover { background: #4A97E6; }
.zy-gen-prize { width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 12px 14px; border-radius: 9px; border: 1px solid #378ADD; background: #378ADD; color: #fff;
  font-family: inherit; font-size: 13.5px; font-weight: 700; letter-spacing: .2px; cursor: pointer;
  box-shadow: 0 0 0 3px rgba(55,138,221,0.14); transition: background-color .15s ease; }
.zy-gen-prize:hover { background: #4A97E6; }
.zy-gen-prize:disabled { opacity: .6; cursor: default; }
.zy-soon-badge { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px;
  padding: 1px 6px; border-radius: 999px; background: rgba(255,255,255,0.22); color: #fff; }
@media (prefers-reduced-motion: reduce) { .zy-chev { transition: none; } .zy-acc-body { animation: none; } .zy-getplan { transition: none; } .zy-gen-prize { transition: none; } }
`;
const panelStyle: CSSProperties = {
  boxSizing: "border-box", borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)",
  background: "rgba(255,255,255,0.02)", padding: 12,
};

export default function PlanEditor({
  projectId, pngBase64, pngMeta, cleanBasePdf, floor, onRegenerated, mode = "iluminat", rooms = [],
  heatingDistribution = null, heatingType = null, enabledEquipment = [], bgLoading = false, isAdmin = false,
  heatingEquipment = [], hasTechRoom = true, hasFv = false, fvKw = 0, finalized = false,
}: { projectId: string; pngBase64?: string | null; pngMeta?: PngMeta; cleanBasePdf?: string | null; floor?: string;
     onRegenerated?: (pdfBase64: string, mode: "iluminat" | "forta", plansaNr?: string) => void; mode?: "iluminat" | "forta";
     rooms?: { name?: string | null; floor?: string | number | null; bbox?: { x: number; y: number; w: number; h: number } | null }[];
     // H5: emisia (heating_distribution) -> butoane termice ; H6: heating_type (boiler) + echipamentele bifate -> restul receptoarelor
     heatingDistribution?: string | null; heatingType?: string | null; enabledEquipment?: string[];
     bgLoading?: boolean;   // forta: fundalul curat se randeaza -> spinner in loc de gol/eroare
     isAdmin?: boolean;     // Dan: unelte de debug (overlay pereti) vizibile doar admin-ului
     // T3: echipamentele de incalzire (din circuitele reale, pre-filtrate in configurator) + checkbox-ul
     // "am camera tehnica" -> tabloul DESTINATIE al auto-plasarii (TE-CT bifat / TEG nebifat)
     heatingEquipment?: HeatingEquipment[]; hasTechRoom?: boolean;
     // FV-P1: tablourile FV (T.CC/INV/T.CA) in sectiunea Tablouri — doar cu sistem FV selectat;
     // fvKw = pachetul (5/10/15/20) -> power_w pe INV la plasare
     hasFv?: boolean; fvKw?: number;
     // FIX 4 (prize automat): gardul "nefinalizat" — pe proiecte finalizate re-deschise (resume)
     // NU se auto-genereaza prize (zero scrieri automate in DB pe proiecte inchise)
     finalized?: boolean }) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [elements, setElements] = useState<PlanElement[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedRooms, setExpandedRooms] = useState<Set<string>>(new Set());
  const [tectNotNeeded, setTectNotNeeded] = useState(false);   // TE-CT: opțiunea "nu este nevoie" (doar UI)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  // "Obține plan" (sub-pas 1a): regenerare PDF din plan_elements editat, pe baza curată
  const [regenLoading, setRegenLoading] = useState(false);
  const [regenPdf, setRegenPdf] = useState<string | null>(null);
  const [regenErr, setRegenErr] = useState<string | null>(null);
  // Traseele cablurilor primite la "Obține plan" (snapshot din compute_cables, puncte PDF).
  // Desenate ca linii Konva SUB simboluri. Se reîmprospătează la fiecare "Obține plan".
  const [overlayCables, setOverlayCables] = useState<{ path: number[][]; kind?: string }[]>([]);
  // DEBUG P1: peretii din /extract-geometry (puncte PDF, ACELASI spatiu ca x,y) + toggle overlay.
  const [walls, setWalls] = useState<{ x1: number; y1: number; x2: number; y2: number }[]>([]);
  const [showWalls, setShowWalls] = useState(false);
  // V4: geom_bbox per camera (sursa: pereti SAU ancora etichetei) din /extract-geometry —
  // perimetru CORECT la plasarea prizelor (bbox-ul Vision e decalat la holuri/terase/open-space).
  // Cheie = nume|bbox.x|bbox.y (dublurile 'Hol acces' au bbox-uri diferite -> chei diferite).
  const [roomGeoms, setRoomGeoms] = useState<Record<string, { x: number; y: number; w: number; h: number }>>({});
  const roomsRef = useRef(rooms);
  roomsRef.current = rooms;   // fetch-ul de geometrie citeste rooms-ul curent fara sa fie dependency (evita re-fetch pe fiecare render)
  const loadedForRef = useRef<string>("");   // FIX 4: "mode|etaj" pentru care s-au incarcat elementele (anti-cursa auto-prize)
  // R2: auto-generare prize (mode forta) — stare buton + feedback inline.
  const [genLoading, setGenLoading] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  // Faza 3 priza de pamant: mod desenare manuala (click succesiv pe conturul fundatiei).
  const [drawingGround, setDrawingGround] = useState(false);
  const [groundPts, setGroundPts] = useState<number[][]>([]);            // colturi fixate (puncte PDF)
  const [groundHover, setGroundHover] = useState<[number, number] | null>(null);   // rubber-band live
  // ref = sursa de adevar SINCRONA a colturilor (nu doar state): un dublu-click emite click+click+dblclick
  // fara re-render intre ele, deci finishDrawGround trebuie sa vada colturile adaugate in acelasi gest.
  const groundPtsRef = useRef<number[][]>([]);
  // Lantul FV (manual): mod desenare polilinie DESCHISA galbena — mecanismul prizei de pamant
  // (click succesiv + rubber-band + dublu-click/Enter), dar min 2 puncte si fara inchidere.
  const [drawingFvChain, setDrawingFvChain] = useState(false);
  const [fvChainPts, setFvChainPts] = useState<number[][]>([]);          // puncte fixate (puncte PDF)
  const [fvChainHover, setFvChainHover] = useState<[number, number] | null>(null);
  const fvChainPtsRef = useRef<number[][]>([]);   // sursa SINCRONA (vezi nota groundPtsRef)
  // Receptoare (bucata A): mod de plasare "1 click" — { et: element_type, label } activ sau null.
  // Primul click pe plan plaseaza si iese din mod (analog drawingGround, dar 1 punct, nu poligon).
  // et generalizat: alimentari = "alimentare_receptor", retea = "receptor_internet" (doar tip+simbol difera).
  const [placingReceptor, setPlacingReceptor] = useState<{ et: string; label: string } | null>(null);
  // Escape anuleaza / Enter finalizeaza cat timp desenam (finishDrawGround citeste ref-ul -> puncte curente).
  useEffect(() => {
    if (!drawingGround) return;
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (ev.key === "Escape") { ev.preventDefault(); cancelDrawGround(); }
      else if (ev.key === "Enter") { ev.preventDefault(); void finishDrawGround(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawingGround]);   // eslint-disable-line react-hooks/exhaustive-deps
  // Escape/Enter pt. lantul FV (identic cu priza de pamant).
  useEffect(() => {
    if (!drawingFvChain) return;
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (ev.key === "Escape") { ev.preventDefault(); cancelDrawFvChain(); }
      else if (ev.key === "Enter") { ev.preventDefault(); void finishDrawFvChain(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawingFvChain]);   // eslint-disable-line react-hooks/exhaustive-deps
  // Escape anuleaza plasarea receptorului.
  useEffect(() => {
    if (!placingReceptor) return;
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (ev.key === "Escape") { ev.preventDefault(); setPlacingReceptor(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [placingReceptor]);

  // factor puncte-PDF -> pixeli-PNG (din png_meta; NICIODATĂ hardcodat)
  const scale = pngMeta?.scale ?? 1;
  // client Supabase reutilizat (citire la mount + UPDATE/INSERT/DELETE din editor)
  const supabase = useMemo(() => createClient(), []);

  // lățimea disponibilă pentru plan (coloana dreapta) -> planul umple spațiul rămas, responsiv
  const planWrapRef = useRef<HTMLDivElement | null>(null);
  const [availW, setAvailW] = useState(DISPLAY_W_FALLBACK);
  useEffect(() => {
    const node = planWrapRef.current;
    if (!node) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setAvailW(w);
    });
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  // încarcă PNG-ul ca HTMLImageElement (fundal Konva)
  useEffect(() => {
    if (!pngBase64) { setImg(null); return; }
    const image = new window.Image();
    image.onload = () => setImg(image);
    image.src = pngBase64.startsWith("data:") ? pngBase64 : `data:image/png;base64,${pngBase64}`;
    return () => { image.onload = null; };
  }, [pngBase64]);

  // citește elementele din plan_elements (RLS: owner-ul vede doar proiectele lui)
  useEffect(() => {
    let cancelled = false;
    if (!projectId) { setLoading(false); return; }
    supabase
      .from("plan_elements")
      .select(SELECT_COLS)
      .eq("project_id", projectId)
      .in("plan_type", [mode, "ambele"])   // iluminat: iluminat+ambele(tablouri); forta: forta+ambele
      .eq("floor", floorCanonic(floor))    // FIX multi-etaj (afisare): DOAR etajul plansei curente —
                                           // altfel becurile parterului apareau peste planul etajului
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) { setErr(error.message); setElements([]); }
        else {
          // FIX 4: marcheaza PENTRU CE (mode|etaj) sunt elementele din state — auto-gen-ul de
          // prize verifica ref-ul, altfel la comutarea pe forta ar vedea elementele VECHI de
          // iluminat (fara prize forta) si ar genera duplicate cat timp fetch-ul e in zbor.
          loadedForRef.current = `${mode}|${floorCanonic(floor)}`;
          setElements((data as PlanElement[]) || []);
        }
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [projectId, supabase, mode, floor]);   // floor in deps: schimbarea plansei reincarca etajul corect

  // FIX 1 (overlay): snapshot-ul cablurilor ("Obtine plan") apartine modului/etajului la care s-a
  // generat — la schimbare se GOLESTE (altfel cablurile de ILUMINAT ramaneau desenate peste FORTA).
  useEffect(() => { setOverlayCables([]); }, [mode, floor]);

  // DEBUG P1: extrage peretii din cleanBasePdf O DATA (statici) -> state `walls`. NON-BLOCANT.
  // V4: trimite si camerele -> primeste room_geoms (geom_bbox per camera, wall/label_anchor).
  useEffect(() => {
    if (!cleanBasePdf) return;
    let cancelled = false;
    const roomsNow = (roomsRef.current || []).filter(r => r?.bbox);
    fetch("/api/extract-geometry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pdf_base64: cleanBasePdf, rooms: roomsNow }),
    })
      .then(r => r.json())
      .then(d => {
        if (cancelled || !d?.success) return;
        if (Array.isArray(d.walls)) setWalls(d.walls);
        if (Array.isArray(d.room_geoms)) {   // paralel cu roomsNow trimise
          const map: Record<string, { x: number; y: number; w: number; h: number }> = {};
          d.room_geoms.forEach((g: { geom_bbox?: { x: number; y: number; w: number; h: number } | null }, i: number) => {
            const r = roomsNow[i];
            if (r?.bbox && g?.geom_bbox) map[`${r.name ?? ""}|${r.bbox.x}|${r.bbox.y}`] = g.geom_bbox;
          });
          setRoomGeoms(map);
        }
      })
      .catch(() => { /* non-blocant: fara pereti -> editorul merge normal */ });
    return () => { cancelled = true; };
  }, [cleanBasePdf]);

  // mută elementul în state imediat (optimist) — lista + planul reflectă schimbarea instant
  function setLocalField(id: string, patch: Partial<PlanElement>) {
    setElements(prev => prev.map(p => (p.id === id ? { ...p, ...patch } : p)));
  }
  // persistă în plan_elements, NON-BLOCANT (eroarea doar se loghează)
  function persist(id: string, patch: Partial<PlanElement>) {
    supabase.from("plan_elements").update(patch).eq("id", id)
      .then(({ error }) => { if (error) console.error("[plan_elements] UPDATE esuat", id, error.message); });
  }

  // selectează un element + AUTO-EXPANDEAZĂ camera lui (ca să-l vezi evidențiat în accordion)
  function selectElement(id: string) {
    setSelectedId(id);
    const el = elements.find(e => e.id === id);
    if (el) {
      const key = el.room || NO_ROOM;
      setExpandedRooms(prev => (prev.has(key) ? prev : new Set(prev).add(key)));
    }
  }

  function toggleRoom(key: string) {
    setExpandedRooms(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  // ADD: element nou ÎN camera dată — refolosește EXACT tiparul de INSERT din populare (configurator.tsx).
  // Poziție: lângă elementul de referință al camerei (offset lateral, puncte PDF). NON-BLOCANT.
  async function addElement(roomKey: string, category: "bulb" | "switch") {
    const list = elements.filter(e => (e.room || NO_ROOM) === roomKey);
    const ref = list[0];   // camera apare în accordion doar dacă are ≥1 element -> ref există
    const floor = floorCanonic(ref?.floor);
    const baseX = ref ? ref.x : (pngW > 0 ? (pngW / scale) / 2 : 100);
    const baseY = ref ? ref.y : (pngH > 0 ? (pngH / scale) / 2 : 100);
    const stagger = list.length;   // evită suprapunerea exactă la adăugări repetate
    const row = {
      project_id: projectId,
      floor,
      element_type: category === "bulb" ? "aplica_tavan" : "intrerupator_simplu",
      plan_type: "iluminat",
      label: null as string | null,
      room: roomKey === NO_ROOM ? null : roomKey,
      x: baseX + 40 + stagger * 6,
      y: baseY + stagger * 6,
      wall_mounted: category !== "bulb",
      rotation: 0,
      power_w: category === "bulb" ? 25 : null,   // bec nou -> 25 REAL (editabil); intrerupator -> null
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT esuat", error?.message); return; }
    const created = data as PlanElement;
    setElements(prev => [...prev, created]);
    setExpandedRooms(prev => (prev.has(roomKey) ? prev : new Set(prev).add(roomKey)));
    setSelectedId(created.id);
  }

  // REMOVE: DELETE manual (fără paritate auto). NON-BLOCANT.
  async function removeElement(id: string) {
    setConfirmDeleteId(null);
    const { error } = await supabase.from("plan_elements").delete().eq("id", id);
    if (error) { console.error("[plan_elements] DELETE esuat", id, error.message); return; }
    setElements(prev => prev.filter(p => p.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  // ADD TABLOU: TEG / TE-CT pe plan (același tipar de INSERT ca addElement) cu status nou/existent.
  // Global (room=null), poziție inițială = centrul planului; max 1 per tip. NON-BLOCANT.
  async function addPanel(panelType: string, status: "nou" | "existent") {
    // TES: un singur tablou de tip PER ETAJ (floor-scoped) -> parter TEG/TE-CT + etaj TES coexistă.
    if (elements.some(e => e.element_type === panelType && floorIndex(e.floor) === floorIndex(floor))) return;
    const floorVal = floorCanonic(floor);   // floor-ul ETAJULUI CURENT (prop), nu al primului element (elements nefiltrat pe etaj)
    const cx = pngW > 0 ? (pngW / scale) / 2 : 200;
    const cy = pngH > 0 ? (pngH / scale) / 2 : 200;
    // separă tablourile plasate simultan în centru (TE-CT sub TEG). Tablourile FV NU mai trec
    // pe aici (FV-B1: butonul "Pozitioneaza T.CC + INV + T.CA" din forta, positionFvPanelsAuto).
    const off = panelType === "tablou_te_ct" ? 44 : 0;
    const row = {
      project_id: projectId,
      floor: floorVal,
      element_type: panelType,
      plan_type: "ambele",            // tablourile apar in AMBELE planuri (iluminat + forta)
      label: null as string | null,
      room: null as string | null,   // tabloul e global, nu per cameră
      x: cx,
      y: cy + off,
      wall_mounted: true,
      rotation: 0,
      status,
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT tablou esuat", error?.message); return; }
    setElements(prev => [...prev, data as PlanElement]);
    setSelectedId((data as PlanElement).id);
  }

  // ADD PRIZA IN CAMERA: priza noua (default simpla; TIPUL se schimba din dropdown-ul "Tip" la click,
  // ca la bec/intrerupator). Plasare langa elementul de referinta al camerei (ROOM-SCOPED, nu centru)
  // -> acelasi tipar ca addElement. plan_type=forta, wall_mounted. Auto-select -> dropdown Tip apare imediat.
  async function addPrizaInRoom(roomKey: string) {
    const list = elements.filter(e => (e.room || NO_ROOM) === roomKey);
    const ref = list[0];   // camera apare in accordion doar cu >=1 element -> ref exista
    const floor = floorCanonic(ref?.floor);
    const baseX = ref ? ref.x : (pngW > 0 ? (pngW / scale) / 2 : 100);
    const baseY = ref ? ref.y : (pngH > 0 ? (pngH / scale) / 2 : 100);
    const stagger = list.filter(e => (e.element_type || "").startsWith("priza")).length;   // evita suprapunerea
    const rule = prizeRuleForRoom(roomKey === NO_ROOM ? null : roomKey);   // FIX-P: h per camera (baie 1.2 / terasa+balcon 0.4)
    const row = {
      project_id: projectId,
      floor,
      element_type: "priza_simpla",   // default; retipabil din dropdown-ul "Tip"
      plan_type: "forta",             // prizele/alimentarile = planul de forta
      label: null as string | null,
      room: roomKey === NO_ROOM ? null : roomKey,
      x: baseX + 40 + stagger * 6,
      y: baseY + stagger * 6,
      wall_mounted: true,
      mount_height_m: rule?.heightM ?? 0.6,   // inaltime precompletata pe regula camerei (editabila in panou)
      rotation: 0,
      status: null as string | null,
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT priza esuat", error?.message); return; }
    const created = data as PlanElement;
    setElements(prev => [...prev, created]);
    setExpandedRooms(prev => (prev.has(roomKey) ? prev : new Set(prev).add(roomKey)));
    setSelectedId(created.id);
  }

  // R2: GENEREAZA PRIZE AUTOMAT (mode forta) — per camera: prizeRuleForRoom (R1) + placePrizasInRoom (F5a)
  // -> batch INSERT (plan_type=forta, h=0.6, tip priza pe regula). IDEMPOTENT: daca exista prize forta ->
  // confirma inlocuirea (sterge + regenereaza). circuit_id ramane null (R3 il atribuie la "Obtine plan forta").
  async function generatePrizasAuto() {
    if (mode !== "forta" || genLoading) return;
    const pdfW = pngW > 0 ? pngW / scale : 0;
    const pdfH = pngH > 0 ? pngH / scale : 0;
    if (!(pdfW > 0 && pdfH > 0)) { setGenMsg("Dimensiunile planului lipsesc."); return; }
    if (!Array.isArray(rooms) || rooms.length === 0) { setGenMsg("Nu exista camere pentru generare."); return; }

    const existing = elements.filter(e => e.plan_type === "forta" && (e.element_type || "").startsWith("priza"));
    setGenLoading(true); setGenMsg(null);
    try {
      // IDEMPOTENTA: prize forta existente -> confirma inlocuirea (nu dubla niciodata)
      if (existing.length > 0) {
        const ok = typeof window !== "undefined" &&
          window.confirm("Exista deja " + existing.length + " prize de forta. Le inlocuiesti (sterge + regenereaza)?");
        if (!ok) return;
        const ids = existing.map(e => e.id);
        const { error: delErr } = await supabase.from("plan_elements").delete().in("id", ids);
        if (delErr) { setGenMsg("Stergerea prizelor existente a esuat: " + delErr.message); return; }
        setElements(prev => prev.filter(e => !ids.includes(e.id)));
      }

      // GARDĂ M1: `rooms` vin deja scopate pe etajul curent (din configurator). Ne reasigurăm aici
      // (defense-in-depth) + scriem floor-ul CANONIC al etajului din INDEX (robust la cele 3 codificări
      // de etaj), nu hardcodat "parter". fidx = indexul etajului (0=parter/1=etaj/2=mansarda) din rooms[].floor.
      const fidx = floorIndex(rooms[0]?.floor);
      const roomsForFloor = rooms.filter((r) => floorIndex(r.floor) === fidx);
      const fl = floorCanonic(fidx);
      const rows: Record<string, unknown>[] = [];
      let nRooms = 0;
      for (const room of roomsForFloor) {
        const rule = prizeRuleForRoom(room?.name);
        if (!rule || rule.count <= 0) continue;          // SKIP spatiu tehnic (null) + terasa acces (count 0)
        if (!room?.bbox) continue;
        // V4: perimetrul = geom_bbox (pereti reali SAU ancora etichetei) cand exista; fallback
        // bbox Vision — ACELASI tipar ca becurile (centroid geometric cu fallback Vision).
        const gbb = roomGeoms[`${room.name ?? ""}|${room.bbox.x}|${room.bbox.y}`];
        const bb = gbb ?? room.bbox;
        const pos = placePrizasInRoom(bb, rule.count, walls, pdfW, pdfH, { snapThreshold: 70 });
        if (!pos.length) continue;
        nRooms++;
        // Rotatie: baza PE perete, semicercul deschis spre INTERIORUL camerei (centrul perimetrului folosit).
        const rcx = (bb.x + bb.w / 2) * pdfW, rcy = (bb.y + bb.h / 2) * pdfH;
        for (const p of pos) {
          const rot = p.wall === "h" ? (rcy < p.y ? 0 : Math.PI)
                    : p.wall === "v" ? (rcx > p.x ? Math.PI / 2 : -Math.PI / 2)
                    : 0;
          rows.push({
            project_id: projectId, floor: fl, element_type: rule.type, plan_type: "forta",
            label: null, room: room.name ?? null, x: p.x, y: p.y,
            wall_mounted: true, mount_height_m: rule.heightM ?? 0.6, rotation: rot, status: null,   // circuit_id null -> R3; h per regula (FIX-P: baie 1.2 / terasa+balcon 0.4)
          });
        }
      }
      if (rows.length === 0) { setGenMsg("Nicio prize de generat (camere fara regula sau count 0)."); return; }
      const { data, error } = await supabase.from("plan_elements").insert(rows).select(SELECT_COLS);
      if (error || !data) { setGenMsg("INSERT prize esuat: " + (error?.message || "necunoscut")); return; }
      setElements(prev => [...prev, ...(data as PlanElement[])]);
      setGenMsg("S-au generat " + data.length + " prize in " + nRooms + " camere.");
    } finally {
      setGenLoading(false);
    }
  }

  // FIX 4: PRIZELE DE FORTA apar AUTOMAT la prima intrare pe forta (fara buton), per ETAJ.
  // 3 garduri anti-surpriza: (a) exista deja prize forta pe etaj -> nu regenereaza (stergerea
  // PARTIALA e respectata; flag-ul se marcheaza ca sa nu mai verifice); (b) flag localStorage
  // per proiect+etaj -> stergerea TOTALA nu regenereaza (alt browser = cel mult o regenerare,
  // limitare acceptata v1); (c) doar proiecte NEFINALIZATE (resume pe finalizat nu scrie in DB).
  // Butonul manual "Genereaza prize" ramane pentru regenerare intentionata (cu confirm).
  useEffect(() => {
    if (mode !== "forta" || loading || genLoading || finalized || !projectId) return;
    if (loadedForRef.current !== `${mode}|${floorCanonic(floor)}`) return;   // elements = alt mode/etaj (fetch in zbor)
    if (bgLoading || !img) return;                     // fundalul fortei inca se incarca -> re-ruleaza la img
    if (typeof window === "undefined") return;
    const flagKey = `zy_auto_prize_${projectId}_${floorIndex(floor)}`;
    let seen: string | null = null;
    try { seen = window.localStorage.getItem(flagKey); } catch { seen = "1"; }   // storage blocat -> nu auto-genera
    if (seen) return;
    const hasForta = elements.some(e => e.plan_type === "forta" && (e.element_type || "").startsWith("priza"));
    if (hasForta) {
      try { window.localStorage.setItem(flagKey, "1"); } catch { /* best effort */ }
      return;
    }
    if (!Array.isArray(rooms) || rooms.length === 0) return;   // camerele inca nu-s -> efectul re-ruleaza
    try { window.localStorage.setItem(flagKey, "1"); } catch { /* best effort */ }
    void generatePrizasAuto();
  }, [mode, loading, genLoading, finalized, projectId, floor, elements, rooms, bgLoading, img]);

  // ── T3: GENEREAZA ECHIPAMENTE INCALZIRE (mode forta) — echipamentele din CIRCUITELE reale
  // (heatingEquipment, pre-filtrat) plasate GRID compact langa tabloul DESTINATIE (TE-CT daca
  // hasTechRoom + plasat; TEG daca nebifat). Tabloul e FIX (plasat la iluminat) — zero urmarire.
  // IDEMPOTENT: match element_type+label -> plaseaza DOAR lipsurile (fara confirm-sterge-tot).
  // circuit_id=null: dedup-ul Faza A (enrich) leaga elementul de circuitul base la finalize;
  // desenul B1 ruteaza dupa label (clasa 1 -> TE-CT daca tabloul exista, altfel TEG). ──
  const [heqLoading, setHeqLoading] = useState(false);
  const [heqMsg, setHeqMsg] = useState<string | null>(null);
  // Bucata 3: "+ Adauga alimentare proprie" (custom) — receptor cu nume+putere+faza LIBERE, auto-plasat
  // langa TE-CT (ca echipamentele) -> room=camera tehnica (geometric) -> TE-CT; power_w onorat de enrich
  // (_enrich_receptor). Stergerea = removeElement (existent); apare in lista receptoarelor (renderReceptorSection).
  const [customOpen, setCustomOpen] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customW, setCustomW] = useState("");
  const [customPhase, setCustomPhase] = useState<"mono" | "tri">("mono");
  const [customLoading, setCustomLoading] = useState(false);
  const [customMsg, setCustomMsg] = useState<string | null>(null);

  // ── FV-B1: "Pozitioneaza T.CC + INV + T.CA" — cele 3 tablouri FV ca BLOC ADIACENT la FORTA
  // (plan_type="forta" -> NU apar pe iluminat), parter, langa TEG (fallback centru), pas 20pt
  // (etichetele raman curate). Idempotent: plaseaza doar lipsurile. Gruparea + snap-ul de perete
  // exista deja (drag pe oricare -> toate 3 cu delta + lipire pe perete, 461aae2). ──
  const [fvpLoading, setFvpLoading] = useState(false);
  const [fvpMsg, setFvpMsg] = useState<string | null>(null);
  async function positionFvPanelsAuto() {
    if (mode !== "forta" || fvpLoading || !hasFv) return;
    setFvpMsg(null);
    const present = new Set(elements.filter(e => isFvPanelType(e.element_type)).map(e => e.element_type));
    const missing = FV_PANEL_TYPES.filter(t => !present.has(t));
    if (!missing.length) { setFvpMsg("Tablourile FV sunt deja poziționate."); return; }
    setFvpLoading(true);
    try {
      const teg = elements.find(e => e.element_type === "tablou_teg");
      const bx = teg ? teg.x - 20 : (pngW > 0 ? (pngW / scale) / 2 - 20 : 200);
      const by = teg ? teg.y + 40 : (pngH > 0 ? (pngH / scale) / 2 : 200);
      const rows = missing.map(t => ({
        project_id: projectId,
        floor: "parter",
        element_type: t,
        plan_type: "forta",
        label: "fatada" as string | null,   // montajul default (editabil in inspector)
        room: null as string | null,
        x: bx + FV_PANEL_TYPES.indexOf(t) * FV_SPACING,
        y: by,
        wall_mounted: true,
        rotation: 0,
        status: "nou",
        power_w: (t === "tablou_inv" && fvKw ? Math.round(fvKw * 1000) : null) as number | null,
      }));
      const { data, error } = await supabase.from("plan_elements").insert(rows).select(SELECT_COLS);
      if (error || !data) { setFvpMsg("Eroare la poziționare: " + (error?.message || "necunoscută")); return; }
      setElements(prev => [...prev, ...(data as PlanElement[])]);
      setFvpMsg(missing.length === 3
        ? (teg ? "Bloc poziționat lângă TEG — trage-l pe perete (se mută toate 3 împreună)."
               : "Bloc poziționat în centru — trage-l pe perete (se mută toate 3 împreună).")
        : `Adăugate ${missing.length} tablouri lipsă (restul erau plasate).`);
    } finally {
      setFvpLoading(false);
    }
  }
  async function generateHeatingEquipAuto() {
    if (mode !== "forta" || heqLoading || heatingEquipment.length === 0) return;
    const destType = hasTechRoom ? "tablou_te_ct" : "tablou_teg";
    const tab = elements.find(e => e.element_type === destType);
    if (!tab) {
      // decizia Dan: AVERTISMENT, nu fallback silentios (destinatia gresita ar fi tacuta)
      setHeqMsg(`Plasează întâi tabloul ${hasTechRoom ? "TE-CT (camera tehnică)" : "TEG"} pe plan.`);
      return;
    }
    const placed = new Set(elements.filter(e => e.element_type === "alimentare_receptor")
                                   .map(e => (e.label || "").trim()));
    const missing = heatingEquipment.filter(h => !placed.has(h.label));
    if (missing.length === 0) { setHeqMsg("Toate echipamentele de încălzire sunt deja plasate."); return; }
    setHeqLoading(true); setHeqMsg(null);
    try {
      // GRID compact langa tablou: dx=+35pt, dy=28pt, a doua coloana dupa 4 elemente
      const rows = missing.map((h, i) => ({
        project_id: projectId, floor: floorCanonic(floor), element_type: "alimentare_receptor",
        plan_type: "forta", label: h.label, room: null as string | null,
        x: tab.x + 35 + Math.floor(i / 4) * 30, y: tab.y + (i % 4) * 28 - 42,
        wall_mounted: false, rotation: 0, mount_height_m: h.mountHeight, status: null as string | null,
      }));
      const { data, error } = await supabase.from("plan_elements").insert(rows).select(SELECT_COLS);
      if (error || !data) { setHeqMsg("INSERT echipamente eșuat: " + (error?.message || "necunoscut")); return; }
      setElements(prev => [...prev, ...(data as PlanElement[])]);
      setHeqMsg(`S-au plasat ${data.length} echipamente lângă ${hasTechRoom ? "TE-CT" : "TEG"}.`);
    } finally {
      setHeqLoading(false);
    }
  }

  // Bucata 3: ADAUGA ALIMENTARE PROPRIE (custom) — INSERT alimentare_receptor cu label/power_w/phase din
  // form, auto-plasat langa tabloul TE-CT (poziționarea din generateHeatingEquipAuto). room=null -> se pune
  // geometric la regenerare (camera tehnica) -> TE-CT. power_w onorat de _enrich_receptor (dimensionare corecta).
  async function addCustomSupply() {
    if (mode !== "forta" || customLoading) return;
    const name = customName.trim();
    const w = parseInt(customW, 10);
    if (!name) { setCustomMsg("Completează un nume."); return; }
    if (!(Number.isFinite(w) && w > 0)) { setCustomMsg("Completează puterea (W, mai mare ca 0)."); return; }
    const destType = hasTechRoom ? "tablou_te_ct" : "tablou_teg";
    const tab = elements.find(e => e.element_type === destType);
    if (!tab) { setCustomMsg(`Plasează întâi tabloul ${hasTechRoom ? "TE-CT (camera tehnică)" : "TEG"} pe plan.`); return; }
    setCustomLoading(true); setCustomMsg(null);
    try {
      const n = elements.filter(e => e.element_type === "alimentare_receptor").length;   // offset grid, ca la echipamente
      const row = {
        project_id: projectId, floor: floorCanonic(floor), element_type: "alimentare_receptor",
        plan_type: "forta", label: name, room: null as string | null,
        x: tab.x + 35 + Math.floor(n / 4) * 30, y: tab.y + (n % 4) * 28 - 42,
        wall_mounted: false, rotation: 0, phase: customPhase, power_w: w, mount_height_m: 0.5,
        status: null as string | null,
      };
      const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
      if (error || !data) { setCustomMsg("Adăugarea a eșuat: " + (error?.message || "necunoscut")); return; }
      setElements(prev => [...prev, data as PlanElement]);
      setCustomName(""); setCustomW(""); setCustomPhase("mono"); setCustomOpen(false);
      setSelectedId((data as PlanElement).id);
    } finally {
      setCustomLoading(false);
    }
  }

  // ADD LEGENDA: caseta legenda (element draggable global, room=null), max 1 per plansa.
  // Acelasi tipar de INSERT ca addPanel; pozitie initiala = colt stanga-jos (in PUNCTE PDF).
  // L1: DOAR caseta-placeholder in editor; desenul continutului pe PDF vine la L3.
  async function addLegend() {
    if (elements.some(e => e.element_type === "legenda")) return;   // max 1 legenda / plansa
    const floor = floorCanonic(elements[0]?.floor);
    const pdfW = pngW > 0 ? pngW / scale : 400;
    const pdfH = pngH > 0 ? pngH / scale : 400;
    const x = pdfW * 0.55;                          // mai in DREAPTA (legenda lata cu text descriptiv); draggable oricum
    const y = pdfH * 0.30;                           // zona dreapta-sus relativ libera (anchor = colt stanga-sus)
    const row = {
      project_id: projectId,
      floor,
      element_type: "legenda",
      plan_type: mode,                // legenda apartine modului curent (iluminat sau forta)
      label: null as string | null,
      room: null as string | null,      // legenda e globala, nu per camera
      x,
      y,
      wall_mounted: false,
      rotation: 0,
      status: null as string | null,    // legenda nu are nou/existent
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT legenda esuat", error?.message); return; }
    setElements(prev => [...prev, data as PlanElement]);
    setSelectedId((data as PlanElement).id);
  }

  // ADD TRASEU (dunga hol): linie dreapta cu 2 capete, punctele in cable_path (puncte PDF). NELIMITAT/plansa.
  // Faza A: trasee multiple (principal + secundare); label distinge tipul + culoarea in editor. Routing = faza B.
  async function addTraseu(label: string) {
    const floor = floorCanonic(elements[0]?.floor);
    const pdfW = pngW > 0 ? pngW / scale : 400;
    const pdfH = pngH > 0 ? pngH / scale : 400;
    const x0 = pdfW * 0.35, y0 = pdfH * 0.5;        // dunga orizontala default peste centru (mutabila)
    const x1 = pdfW * 0.65, y1 = pdfH * 0.5;
    const row = {
      project_id: projectId,
      floor,
      element_type: "traseu",
      plan_type: mode,                // dunga apartine modului curent (iluminat sau forta)
      label,                          // "principal" | "secundar" -> culoare in editor (+ faza B routing)
      room: null as string | null,
      x: x0,
      y: y0,                              // ancora = capatul 0 (sincron cu NOT NULL x,y)
      wall_mounted: false,
      rotation: 0,
      status: null as string | null,
      cable_path: [[x0, y0], [x1, y1]] as number[][],
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT traseu esuat", error?.message); return; }
    setElements(prev => [...prev, data as PlanElement]);
    setSelectedId((data as PlanElement).id);
  }

  // Drag pe un CAPAT al dungii: updateaza cable_path[i] (+ x,y daca i=0 = ancora) si persista.
  function handleTraseuVertexDragEnd(el: PlanElement, i: number, e: KonvaEventObject<DragEvent>) {
    let xPdf = e.target.x() / scale;
    let yPdf = e.target.y() / scale;
    // SNAP faza A: un varf de traseu SECUNDAR se lipeste de traseul PRINCIPAL (secundar pornit din
    // principal — vizual, fara legatura in date). Sub prag -> punctul de pe principal.
    if (el.label === "secundar") {
      const principal = elements.find(t => t.element_type === "traseu" && t.label !== "secundar");
      const pp = principal?.cable_path;
      if (pp && pp.length >= 2) {
        const s = snapToPolyline(xPdf, yPdf, pp, 30);
        if (s) { xPdf = s[0]; yPdf = s[1]; e.target.position({ x: xPdf * scale, y: yPdf * scale }); }
      }
    }
    const base = (el.cable_path && el.cable_path.length >= 2)
      ? el.cable_path.map(p => [p[0], p[1]])
      : [[el.x, el.y], [el.x + 120, el.y]];
    base[i] = [xPdf, yPdf];
    const patch: Partial<PlanElement> = { cable_path: base };
    if (i === 0) { patch.x = xPdf; patch.y = yPdf; }   // capatul 0 = ancora -> tine x,y in sync
    setLocalField(el.id, patch);
    persist(el.id, patch);
  }

  // Click pe LINIE (cand dunga e selectata): insereaza un varf nou pe cel mai apropiat segment (il sparge).
  function addTraseuVertex(el: PlanElement, e: KonvaEventObject<MouseEvent | TouchEvent>) {
    const pos = e.target.getRelativePointerPosition();   // coordonate Layer (px PNG)
    if (!pos) return;
    const cx = pos.x / scale, cy = pos.y / scale;        // -> puncte PDF
    const pts = (el.cable_path && el.cable_path.length >= 2)
      ? el.cable_path.map(p => [p[0], p[1]])
      : [[el.x, el.y], [el.x + 120, el.y]];
    // cel mai apropiat segment + proiectia clickului pe el (varful nou cade PE linie, apoi se trage)
    let bestI = 0, bestD = Infinity, bestPt: number[] = [cx, cy];
    for (let i = 0; i < pts.length - 1; i++) {
      const ax = pts[i][0], ay = pts[i][1], bx = pts[i + 1][0], by = pts[i + 1][1];
      const dx = bx - ax, dy = by - ay;
      const len2 = dx * dx + dy * dy || 1;
      let t = ((cx - ax) * dx + (cy - ay) * dy) / len2;
      t = Math.max(0, Math.min(1, t));
      const px2 = ax + t * dx, py2 = ay + t * dy;
      const d = Math.hypot(cx - px2, cy - py2);
      if (d < bestD) { bestD = d; bestI = i; bestPt = [px2, py2]; }
    }
    const next = [...pts.slice(0, bestI + 1), bestPt, ...pts.slice(bestI + 1)];   // intre capetele segmentului
    setLocalField(el.id, { cable_path: next });   // varful 0 neschimbat -> x,y raman in sync
    persist(el.id, { cable_path: next });
  }

  // Dublu-click pe un VARF: il sterge (pastreaza minim 2 puncte). Re-sincronizeaza x,y daca se sterge capatul 0.
  function removeTraseuVertex(el: PlanElement, i: number) {
    const pts = (el.cable_path && el.cable_path.length >= 2) ? el.cable_path.map(p => [p[0], p[1]]) : [];
    if (pts.length <= 2) return;   // minim o linie (2 puncte)
    pts.splice(i, 1);
    const patch: Partial<PlanElement> = { cable_path: pts };
    if (i === 0) { patch.x = pts[0][0]; patch.y = pts[0][1]; }
    setLocalField(el.id, patch);
    persist(el.id, patch);
  }

  // ── Faza 3: priza de pamant — desenare manuala prin click succesiv pe colturile fundatiei. ──
  function startDrawGround() {
    setSelectedId(null);            // fara selectie activa cat desenam
    cancelDrawFvChain();            // un singur mod de desenare activ (straturile de captura nu se suprapun)
    groundPtsRef.current = [];
    setGroundPts([]);
    setGroundHover(null);
    setDrawingGround(true);
  }
  function cancelDrawGround() {
    setDrawingGround(false);
    groundPtsRef.current = [];
    setGroundPts([]);
    setGroundHover(null);
  }
  // click pe canvas (mod desenare) -> adauga un colt (puncte PDF). Ref-ul se actualizeaza SINCRON (vezi nota la
  // groundPtsRef) ca dublu-click-ul de finalizare sa vada si colturile plasate in acelasi gest.
  function addGroundPoint(e: KonvaEventObject<MouseEvent | TouchEvent>) {
    const pos = e.target.getRelativePointerPosition();
    if (!pos) return;
    const next = [...groundPtsRef.current, [pos.x / scale, pos.y / scale]];
    groundPtsRef.current = next;
    setGroundPts(next);
  }
  // mousemove -> rubber-band de la ultimul colt fixat la cursor
  function moveGroundHover(e: KonvaEventObject<MouseEvent>) {
    const pos = e.target.getRelativePointerPosition();
    if (!pos) return;
    setGroundHover([pos.x / scale, pos.y / scale]);
  }
  // finalizeaza: INSERT ground_electrode_path (min 3 colturi). floor din PROP (nu elements[0] -> evita bug latent).
  async function finishDrawGround() {
    const raw = groundPtsRef.current || [];
    // dedup colturi consecutive ~identice (ex. cele 2 click-uri ale unui dublu-click pe acelasi punct)
    const pts: number[][] = [];
    for (const p of raw) {
      const last = pts[pts.length - 1];
      if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) > 0.5) pts.push([p[0], p[1]]);
    }
    if (pts.length < 3) return;     // un contur are nevoie de minim 3 colturi
    const row = {
      project_id: projectId,
      floor: floorCanonic(floor),   // PROP curent (parter), NU elements[0]?.floor
      element_type: "ground_electrode_path",
      plan_type: "forta",
      label: null as string | null,
      room: null as string | null,
      x: pts[0][0],
      y: pts[0][1],                 // ancora = coltul 0 (sincron cu NOT NULL x,y)
      wall_mounted: false,
      rotation: 0,
      status: null as string | null,
      cable_path: pts,
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT priza de pamant esuat", error?.message); return; }
    setElements(prev => [...prev, data as PlanElement]);
    setSelectedId((data as PlanElement).id);
    setDrawingGround(false);
    groundPtsRef.current = [];
    setGroundPts([]);
    setGroundHover(null);
  }

  // ── Lantul FV (manual): acelasi mecanism ca priza de pamant, dar polilinie DESCHISA (min 2
  // puncte, fara inchidere) si GALBENA. Inginerul decide traseul (fatada exterior / prin TE-CT). ──
  function startDrawFvChain() {
    setSelectedId(null);
    cancelDrawGround();             // un singur mod de desenare activ
    fvChainPtsRef.current = [];
    setFvChainPts([]);
    setFvChainHover(null);
    setDrawingFvChain(true);
  }
  function cancelDrawFvChain() {
    setDrawingFvChain(false);
    fvChainPtsRef.current = [];
    setFvChainPts([]);
    setFvChainHover(null);
  }
  function addFvChainPoint(e: KonvaEventObject<MouseEvent | TouchEvent>) {
    const pos = e.target.getRelativePointerPosition();
    if (!pos) return;
    const next = [...fvChainPtsRef.current, [pos.x / scale, pos.y / scale]];
    fvChainPtsRef.current = next;
    setFvChainPts(next);
  }
  function moveFvChainHover(e: KonvaEventObject<MouseEvent>) {
    const pos = e.target.getRelativePointerPosition();
    if (!pos) return;
    setFvChainHover([pos.x / scale, pos.y / scale]);
  }
  // finalizeaza: INSERT fv_chain_path (min 2 puncte — polilinie deschisa, nu contur).
  async function finishDrawFvChain() {
    const raw = fvChainPtsRef.current || [];
    const pts: number[][] = [];
    for (const p of raw) {
      const last = pts[pts.length - 1];
      if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) > 0.5) pts.push([p[0], p[1]]);
    }
    if (pts.length < 2) return;     // un traseu are nevoie de minim 2 puncte
    const row = {
      project_id: projectId,
      floor: floorCanonic(floor),   // PROP curent (etajul plansei pe care desenezi)
      element_type: "fv_chain_path",
      plan_type: "forta",
      label: null as string | null,
      room: null as string | null,
      x: pts[0][0],
      y: pts[0][1],                 // ancora = punctul 0 (sincron cu NOT NULL x,y)
      wall_mounted: false,
      rotation: 0,
      status: null as string | null,
      cable_path: pts,
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT lant FV esuat", error?.message); return; }
    setElements(prev => [...prev, data as PlanElement]);
    setSelectedId((data as PlanElement).id);
    setDrawingFvChain(false);
    fvChainPtsRef.current = [];
    setFvChainPts([]);
    setFvChainHover(null);
  }

  // ── Receptoare (bucata A): plasare "1 click" a unei alimentari (boiler/cuptor/...). ──
  // Buton -> intra in mod (label = tipul); primul click pe plan -> INSERT alimentare_receptor
  // la punctul respectiv (puncte PDF = pos/scale) + iese din mod. Simbol = "alimentare directa" (PDF).
  function startPlaceReceptor(et: string, label: string) {
    setSelectedId(null);
    setPlacingReceptor({ et, label });
  }
  async function placeReceptorAt(e: KonvaEventObject<MouseEvent | TouchEvent>) {
    const p = placingReceptor;
    if (!p) return;
    const pos = e.target.getRelativePointerPosition();
    if (!pos) return;
    const heat = heatingReceptorDef(p.label);          // Regula 10: radiator/VCV/distribuitor -> putere+faza DEFAULT
    const row = {
      project_id: projectId,
      floor: floorCanonic(floor),        // PROP curent (nu elements[0]) — coerent cu priza de pamant
      element_type: p.et,                // "alimentare_receptor" | "receptor_internet"
      plan_type: "forta",
      label: p.label,                    // alimentari: boiler/cuptor/...; retea: "internet"; termice: Radiator/VCV/Distribuitor zona
      room: null as string | null,
      x: pos.x / scale,
      y: pos.y / scale,
      wall_mounted: false,
      rotation: 0,
      mount_height_m: receptorDefaultHeight(p.et, p.label),   // inaltime DEFAULT pe tip (editabila)
      // Regula 10: termicele primesc power_w + phase la plasare (editabile in inspector; fallback in backend daca null)
      ...(heat ? { power_w: heat.default_w, phase: heat.default_phase } : {}),
      status: null as string | null,
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT alimentare receptor esuat", error?.message); return; }
    setElements(prev => [...prev, data as PlanElement]);
    setSelectedId((data as PlanElement).id);
    setPlacingReceptor(null);            // 1 click = 1 plasare -> iese din mod
  }

  // Drag -> salvează noua poziție în PUNCTE PDF. e.target e Group-ul; x/y sunt în coordonate Layer
  // (spațiul PNG), iar Stage-scale (displayScale) e separat și NU intervine. Inversul exact al afișării.
  function handleDragEnd(el: PlanElement, e: KonvaEventObject<DragEvent>) {
    let xPdf = e.target.x() / scale;
    let yPdf = e.target.y() / scale;
    // FV: tablourile FV se muta ca BLOC (mut unul -> toate 3) + SNAP la perete. FV-B2: la snap,
    // blocul se REORIENTEAZA PARALEL cu peretele (perete orizontal -> cele 3 in linie pe x cu
    // y=perete; vertical -> stiva pe y cu x=perete), ordinea T.CC|INV|T.CA pastrata (pas
    // FV_SPACING), taratul ramane pe pozitia LUI din ordine. Fara perete sub prag / walls gol
    // (iluminat) -> mutare libera ca bloc (delta rigid, ca inainte).
    if (isFvPanelType(el.element_type)) {
      if (walls.length) {
        const s = snapToWall(xPdf, yPdf, walls);
        if (s.snapped && s.wall) {
          const di = FV_PANEL_TYPES.indexOf(el.element_type);
          for (const other of elements) {
            if (!isFvPanelType(other.element_type) || floorIndex(other.floor) !== floorIndex(el.floor)) continue;
            const off = (FV_PANEL_TYPES.indexOf(other.element_type) - di) * FV_SPACING;
            const nx = s.wall === "h" ? s.x + off : s.x;
            const ny = s.wall === "h" ? s.y : s.y + off;
            if (other.id === el.id) e.target.position({ x: nx * scale, y: ny * scale });
            setLocalField(other.id, { x: nx, y: ny });
            persist(other.id, { x: nx, y: ny });
          }
          return;
        }
      }
      const dx = xPdf - el.x, dy = yPdf - el.y;
      setLocalField(el.id, { x: xPdf, y: yPdf });
      persist(el.id, { x: xPdf, y: yPdf });
      for (const other of elements) {
        if (other.id !== el.id && isFvPanelType(other.element_type)
            && floorIndex(other.floor) === floorIndex(el.floor)) {
          setLocalField(other.id, { x: other.x + dx, y: other.y + dy });
          persist(other.id, { x: other.x + dx, y: other.y + dy });
        }
      }
      return;
    }
    // SNAP P3: DOAR prize, DOAR daca avem pereti -> lipeste pe cel mai apropiat perete sub prag (~40pt).
    // Peste prag SAU walls gol -> ramane unde a fost pus (plasare libera, ex. hol fara pereti).
    if (isPrizaType(el.element_type) && walls.length) {
      const s = snapToWall(xPdf, yPdf, walls);
      if (s.snapped) {
        // Rotatie: baza (diametrul) PE perete, semicercul deschis spre partea din care a venit drag-ul
        // (= interiorul camerei). Radiani, conventia intrerupatoarelor: 0=sus, π=jos, ±π/2=lateral.
        const rot = s.wall === "h" ? (yPdf < s.y ? 0 : Math.PI)
                  : s.wall === "v" ? (xPdf > s.x ? Math.PI / 2 : -Math.PI / 2)
                  : (el.rotation ?? 0);
        xPdf = s.x; yPdf = s.y;
        e.target.position({ x: xPdf * scale, y: yPdf * scale });   // muta Group-ul vizual pe perete imediat
        setLocalField(el.id, { x: xPdf, y: yPdf, rotation: rot });
        persist(el.id, { x: xPdf, y: yPdf, rotation: rot });
        return;
      }
    }
    setLocalField(el.id, { x: xPdf, y: yPdf });
    persist(el.id, { x: xPdf, y: yPdf });
  }

  // cursor "move" la hover peste element draggable
  function setCursor(e: KonvaEventObject<MouseEvent>, c: string) {
    const stage = e.target.getStage();
    if (stage) stage.container().style.cursor = c;
  }

  // base64 PDF -> URL de blob (pt. descărcare / deschidere)
  function pdfBlobUrl(b64: string): string {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  }

  // "Obține plan" (1a): trimite baza curată + project_id/floor -> backend citește plan_elements EDITAT
  // și redesenează -> primim PDF nou. Baza curată lipsă -> mesaj clar; erori -> mesaj, fără crash.
  async function handleRegenerate() {
    if (!cleanBasePdf) { setRegenErr("Baza curată (planul fără becuri) lipsește pentru acest proiect."); return; }
    setRegenLoading(true); setRegenErr(null); setRegenPdf(null);
    try {
      const res = await fetch("/api/regenerate-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, floor: floorCanonic(floor), base_pdf_base64: cleanBasePdf, plan_type: mode }),
      });
      const data = await res.json();
      if (!res.ok || !data?.success || !data?.pdf_base64) {
        setRegenErr(data?.error || "Regenerare eșuată.");
      } else {
        setRegenPdf(pdfBlobUrl(data.pdf_base64));     // URL de blob pt. download/open (ambele moduri)
        // M2b: semnalează finalizarea la părinte pentru AMBELE faze. Iluminat -> persistă IE.1 (regenerated);
        // forța -> marchează etajul ca finalizat (tracking în sesiune; persistarea ca planșă = M3).
        // PAS 2: plansa_nr = numarul FINAL IE.N stampat de backend (autoritate) -> parintele il persista
        onRegenerated?.(data.pdf_base64, mode, typeof data.plansa_nr === "string" && data.plansa_nr ? data.plansa_nr : undefined);
        setOverlayCables(Array.isArray(data.cables) ? data.cables : []);  // snapshot cabluri -> overlay Konva
      }
    } catch (e) {
      setRegenErr(e instanceof Error ? e.message : "Eroare de rețea.");
    } finally {
      setRegenLoading(false);
    }
  }

  // Ordinea CONTEAZA (fix resume): (1) fundalul SE INCARCA (fetch /render-base-png in curs pe forta;
  // la resume aterizezi direct pe forta -> fereastra de 2-3s e in fata userului) -> SPINNER zy-spin,
  // NU mesajul sec — early-return-ul de mai jos scurtcircuita spinner-ul din caseta Stage.
  // (2) PNG absent si NIMIC nu-l incarca -> LIPSA DEFINITIVA (plansa negenerata) -> mesaj clar, fara
  // spinner infinit. Iluminatul nu are fetch (png-ul e deja in result_data) -> doar prezent/absent.
  if (bgLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, minHeight: 360 }}>
        <span aria-hidden style={{ width: 44, height: 44, borderRadius: "50%", border: "4px solid rgba(55,138,221,0.22)",
          borderTopColor: "#378ADD", animation: "zy-spin 0.7s linear infinite" }} />
        <span style={{ fontSize: 12.5, color: "#8B8FA8" }}>Se pregătește planul de {mode === "forta" ? "forță" : "iluminat"}…</span>
      </div>
    );
  }
  if (!pngBase64) {
    return (
      <p className="text-sm text-center py-8" style={{ color: "#545870" }}>
        Această planșă nu a fost generată încă — generează planul de {mode === "forta" ? "forță" : "iluminat"} mai întâi.
      </p>
    );
  }

  // dimensiuni PNG (px) + scalare uniformă la ecran (imagine + overlay împreună -> rămân aliniate)
  const pngW = pngMeta?.png_width_px ?? img?.width ?? 0;
  const pngH = pngMeta?.png_height_px ?? img?.height ?? 0;
  const displayScale = pngW > 0 ? Math.min(1, availW / pngW) : 1;
  const stageW = Math.round(pngW * displayScale);
  const stageH = Math.round(pngH * displayScale);

  const selected = selectedId ? (elements.find(e => e.id === selectedId) ?? null) : null;

  // desenează selectatul ULTIMUL -> conturul lui (+ Group) e deasupra vecinilor
  const ordered = selectedId
    ? [...elements.filter(e => e.id !== selectedId), ...elements.filter(e => e.id === selectedId)]
    : elements;

  // grupare pe cameră (numele) — fiecare cameră o secțiune de accordion
  const byRoom = new Map<string, PlanElement[]>();
  for (const el of elements) {
    const key = el.room || NO_ROOM;
    const arr = byRoom.get(key);
    if (arr) arr.push(el); else byRoom.set(key, [el]);
  }
  const roomKeys = [...byRoom.keys()].sort((a, b) => a.localeCompare(b, "ro"));

  // ── panou de editare pentru elementul selectat ──
  const renderEditPanel = () => {
    if (!selected) {
      return (
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#545870", fontSize: 12, padding: "1px 0" }}>
          <span aria-hidden style={{ width: 7, height: 7, borderRadius: "50%", background: "rgba(255,255,255,0.12)", flexShrink: 0 }} />
          Selectează un element pentru a-l edita
        </div>
      );
    }
    const isBulbSel = isBulbType(selected.element_type);
    const isSwitchSel = isSwitchType(selected.element_type);
    const isPrizaSel = isPrizaType(selected.element_type);   // pt. prize: dropdown Tip ca la bec/intrerupator
    const typeOptions = isBulbSel ? BULB_TYPES : isSwitchSel ? SWITCH_TYPES : isPrizaSel ? PRIZA_TYPES : [];
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <span aria-hidden style={{ width: 7, height: 7, borderRadius: "50%", background: "#378ADD", flexShrink: 0, boxShadow: "0 0 6px rgba(55,138,221,0.85)" }} />
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.4, color: "#5BB8F5" }}>Editare</span>
          <span style={{ fontSize: 12, color: "#C5C8D6", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>· {typeLabel(selected.element_type)}</span>
        </div>

        {/* Tip (element_type) — DOAR opțiuni din aceeași categorie; valoarea = exact valoarea din CHECK */}
        <label style={fieldLabel}>Tip</label>
        {typeOptions.length ? (
          <select
            className="zy-ed-field"
            value={selected.element_type}
            onChange={(e) => {
              const v = e.target.value;
              setLocalField(selected.id, { element_type: v });
              persist(selected.id, { element_type: v });   // schimbare deliberată -> salvează imediat
            }}
            style={inputStyle}
          >
            {typeOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ) : (
          // tip din afara categoriilor bec/întrerupător (ex. tablou) -> read-only (etichetă prietenoasă)
          <input type="text" className="zy-ed-field" value={typeLabel(selected.element_type)} disabled style={{ ...inputStyle, color: "#8B8FA8" }} />
        )}

        {/* Putere (power_w) — DOAR la becuri; gol -> null (coloană integer). Placeholder 25 = doar hint. */}
        {isBulbSel && (
          <>
            <label style={fieldLabel}>Putere (W)</label>
            <input
              type="number"
              className="zy-ed-field"
              min={0}
              placeholder="25"
              value={selected.power_w ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                const n = parseInt(raw, 10);
                setLocalField(selected.id, { power_w: raw === "" || !Number.isFinite(n) ? null : n });
              }}
              onBlur={(e) => {
                const raw = e.target.value;
                const n = parseInt(raw, 10);
                persist(selected.id, { power_w: raw === "" || !Number.isFinite(n) ? null : n });
              }}
              style={inputStyle}
            />
          </>
        )}

        {/* Regula 10: Putere (W) + Fază (mono/tri) — receptoare termice. Radiator/VCV: ambele editabile;
            Distribuitor zona: doar putere (fază fixă mono). Persistă imediat pe plan_elements. */}
        {isReceptorType(selected.element_type) && heatingReceptorDef(selected.label) && (
          <>
            <label style={fieldLabel}>Putere (W)</label>
            <input
              type="number"
              className="zy-ed-field"
              min={0}
              placeholder={String(heatingReceptorDef(selected.label)!.default_w)}
              value={selected.power_w ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                const n = parseInt(raw, 10);
                setLocalField(selected.id, { power_w: raw === "" || !Number.isFinite(n) ? null : n });
              }}
              onBlur={(e) => {
                const raw = e.target.value;
                const n = parseInt(raw, 10);
                persist(selected.id, { power_w: raw === "" || !Number.isFinite(n) ? null : n });
              }}
              style={inputStyle}
            />
            {heatingReceptorDef(selected.label)!.editablePhase && (
              <>
                <label style={fieldLabel}>Fază</label>
                <select
                  className="zy-ed-field"
                  value={selected.phase ?? "mono"}
                  onChange={(e) => {
                    const v = e.target.value;
                    setLocalField(selected.id, { phase: v });
                    persist(selected.id, { phase: v });   // schimbare deliberată -> salvează imediat
                  }}
                  style={inputStyle}
                >
                  <option value="mono">Monofazat (3 fire)</option>
                  <option value="tri">Trifazat (5 fire)</option>
                </select>
              </>
            )}
          </>
        )}

        {/* Înălțime (mount_height_m) — prize + receptoare (alimentări/rețea); default pe tip, editabil (metri).
            Becurile NU au (pe tavan). */}
        {(isPrizaType(selected.element_type) || isReceptorType(selected.element_type) || isInternetType(selected.element_type)) && (
          <>
            <label style={fieldLabel}>Înălțime (m)</label>
            <input
              type="number"
              className="zy-ed-field"
              min={0}
              step={0.1}
              placeholder="0.6"
              value={selected.mount_height_m ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                const n = parseFloat(raw);
                setLocalField(selected.id, { mount_height_m: raw === "" || !Number.isFinite(n) ? null : n });
              }}
              onBlur={(e) => {
                const raw = e.target.value;
                const n = parseFloat(raw);
                persist(selected.id, { mount_height_m: raw === "" || !Number.isFinite(n) ? null : n });
              }}
              style={inputStyle}
            />
          </>
        )}

        {/* Stare (status) — DOAR la tablouri, read-only deocamdată (selectorul nou/existent vine separat) */}
        {isPanelType(selected.element_type) && (
          <>
            <label style={fieldLabel}>Stare</label>
            <input
              type="text"
              className="zy-ed-field"
              disabled
              value={selected.status === "nou" ? "Nou propus" : selected.status === "existent" ? "Existent" : "—"}
              style={{ ...inputStyle, color: "#8B8FA8", marginBottom: 6 }}
            />
          </>
        )}

        {/* FV-P1: MONTAJUL tablourilor FV (fatada default / spatiu tehnic), persistat in label —
            legenda planului il va citi de acolo (FV-P2). Doar pe T.CC/INV/T.CA. */}
        {isFvPanelType(selected.element_type) && (
          <>
            <label style={fieldLabel}>Montaj</label>
            <select
              className="zy-ed-field"
              value={selected.label === "spatiu tehnic" ? "spatiu tehnic" : "fatada"}
              onChange={e => {
                setLocalField(selected.id, { label: e.target.value });
                persist(selected.id, { label: e.target.value });
              }}
              style={{ ...inputStyle, marginBottom: 6 }}
            >
              <option value="fatada">Pe fațadă (h=1.5m)</option>
              <option value="spatiu tehnic">În spațiul tehnic (h=1.5m)</option>
            </select>
          </>
        )}

        {selected.room && (
          <div style={{ fontSize: 11, color: "#8B8FA8", marginTop: 2 }}>Cameră: <span style={{ color: "#C5C8D6" }}>{selected.room}</span></div>
        )}
      </div>
    );
  };

  // un rând de element în accordion: icon + tip prietenos (+ index) + power_w + buton ștergere (× / confirm)
  const renderElementRow = (el: PlanElement, indexSuffix: string) => {
    const isSel = selectedId === el.id;
    const isBulb = isBulbType(el.element_type);
    const isPanel = isPanelType(el.element_type);
    const pInfo = isPanel ? (PANEL_INFO[el.element_type] || { short: "", colA: "#D1D5DB", colB: "#6B7280" }) : null;
    const confirming = confirmDeleteId === el.id;
    return (
      <div
        key={el.id}
        className="flex items-center gap-2 pl-3 pr-1 py-[5px] rounded-md transition-colors"
        style={{
          background: isSel ? "rgba(55,138,221,0.18)" : "transparent",
          border: isSel ? "1px solid rgba(55,138,221,0.45)" : "1px solid transparent",
        }}
      >
        <button
          type="button"
          onClick={() => selectElement(el.id)}
          className="flex items-center gap-2 flex-1 min-w-0 text-left hover:opacity-90"
          style={{ background: "none", border: "none", padding: 0, cursor: "pointer" }}
        >
          {pInfo ? (
            <span aria-hidden style={{
              width: 11, height: 11, flexShrink: 0, borderRadius: 2, border: "1px solid #1F2433",
              background: `linear-gradient(135deg, ${pInfo.colA} 0 50%, ${pInfo.colB} 50% 100%)`,
            }} />
          ) : (
            <span aria-hidden style={{
              width: 10, height: 10, flexShrink: 0,
              borderRadius: isBulb ? "50%" : 2,
              border: `2px solid ${isBulb ? COL_BULB : COL_SWITCH}`,
              background: isBulb ? "rgba(30,99,214,0.25)" : "rgba(214,40,40,0.25)",
            }} />
          )}
          <span style={{ fontSize: 12, color: isSel ? "#DCEBFB" : "#C5C8D6", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {typeLabel(el.element_type)}{indexSuffix}
          </span>
          {el.power_w ? <span style={{ fontSize: 10, color: "#8B8FA8" }}>{el.power_w}W</span> : null}
        </button>
        {confirming ? (
          <span className="flex items-center gap-1" style={{ flexShrink: 0 }}>
            <span style={{ fontSize: 11, color: "#8B8FA8" }}>Ștergi?</span>
            <button type="button" className="zy-del-yes" onClick={() => removeElement(el.id)}>Da</button>
            <button type="button" className="zy-del-no" onClick={() => setConfirmDeleteId(null)}>Nu</button>
          </span>
        ) : (
          <button type="button" className="zy-del-x" title="Șterge elementul" aria-label="Șterge elementul"
            onClick={() => setConfirmDeleteId(el.id)} style={{ flexShrink: 0 }}>×</button>
        )}
      </div>
    );
  };

  // o cameră = un header de accordion + (când e expandată) elementele ei + butoanele Add
  const renderRoom = (key: string) => {
    const list = byRoom.get(key) || [];
    const rbulbs = list.filter(e => isBulbType(e.element_type));
    const rsw = list.filter(e => isSwitchType(e.element_type));
    const rpanels = list.filter(e => isPanelType(e.element_type));
    const rother = list.filter(e => !isBulbType(e.element_type) && !isSwitchType(e.element_type) && !isPanelType(e.element_type));
    const open = expandedRooms.has(key);
    const count = `${rbulbs.length} bec${rbulbs.length === 1 ? "" : "uri"} · ${rsw.length} întrer.${rpanels.length ? ` · ${rpanels.length} tablou${rpanels.length === 1 ? "" : "ri"}` : ""}`;
    return (
      <div key={key} style={{ marginBottom: 5 }}>
        <button
          type="button"
          onClick={() => toggleRoom(key)}
          className="w-full flex items-center gap-2 px-2 py-2 rounded-md text-left transition-colors hover:bg-white/[0.04]"
          style={{ background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.06)", cursor: "pointer" }}
        >
          <span className="zy-chev" style={{ display: "inline-block", width: 11, flexShrink: 0, fontSize: 9, color: "#8B8FA8", transform: open ? "rotate(90deg)" : "none" }}>▶</span>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: "#E2E4E9", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{key}</span>
          <span style={{ fontSize: 10.5, color: "#545870", flexShrink: 0 }}>{count}</span>
        </button>

        {open && (
          <div className="zy-acc-body" style={{ padding: "5px 2px 7px" }}>
            {rbulbs.map((el, i) => renderElementRow(el, rbulbs.length > 1 ? ` #${i + 1}` : ""))}
            {rsw.map((el, i) => renderElementRow(el, rsw.length > 1 ? ` #${i + 1}` : ""))}
            {rpanels.map((el, i) => renderElementRow(el, rpanels.length > 1 ? ` #${i + 1}` : ""))}
            {rother.map((el) => renderElementRow(el, ""))}
            {mode === "iluminat" && (
              <div className="flex gap-1.5 mt-2 pl-1">
                <button type="button" className="zy-add-btn" onClick={() => addElement(key, "bulb")}>+ Bec</button>
                <button type="button" className="zy-add-btn" onClick={() => addElement(key, "switch")}>+ Întrerupător</button>
              </div>
            )}
            {mode === "forta" && (
              <div className="flex gap-1.5 mt-2 pl-1">
                <button type="button" className="zy-add-btn" onClick={() => addPrizaInRoom(key)}>+ Priză</button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // un bloc de tablou (TEG / TE-CT): dacă există deja -> rândul lui (select + ștergere), altfel selectorul.
  const renderPanelBlock = (title: string, panelType: string, allowNotNeeded: boolean) => {
    const existing = elements.find(e => e.element_type === panelType && floorIndex(e.floor) === floorIndex(floor)) || null;
    const badge = (st: string | null) => (
      <span style={{
        fontSize: 10, padding: "1px 7px", borderRadius: 4, marginLeft: 8,
        background: st === "nou" ? "rgba(34,197,94,0.14)" : "rgba(139,143,168,0.14)",
        color: st === "nou" ? "#4ADE80" : "#A8ACC2",
        border: `1px solid ${st === "nou" ? "rgba(34,197,94,0.35)" : "rgba(139,143,168,0.3)"}`,
      }}>{st === "nou" ? "Nou propus" : st === "existent" ? "Existent" : "—"}</span>
    );
    return (
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#C5C8D6", marginBottom: 5, display: "flex", alignItems: "center" }}>
          {title}{existing && badge(existing.status)}
        </div>
        {existing ? (
          renderElementRow(existing, "")
        ) : allowNotNeeded && tectNotNeeded ? (
          <div style={{ fontSize: 11, color: "#545870", display: "flex", alignItems: "center", gap: 8, paddingLeft: 2 }}>
            Nu este nevoie.
            <button type="button" className="zy-add-btn" onClick={() => setTectNotNeeded(false)}>Modifică</button>
          </div>
        ) : (
          <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2 }}>
            <button type="button" className="zy-add-btn" onClick={() => addPanel(panelType, "nou")}>+ Nou propus</button>
            <button type="button" className="zy-add-btn" onClick={() => addPanel(panelType, "existent")}>+ Existent</button>
            {allowNotNeeded && (
              <button type="button" className="zy-add-btn" onClick={() => setTectNotNeeded(true)}>Nu este nevoie</button>
            )}
          </div>
        )}
      </div>
    );
  };

  // secțiunea Tablouri (sub camere): TEG (nou/existent) + TE-CT (nou/existent/nu e nevoie)
  // PARTER -> tabloul GENERAL (TEG) + tehnic (TE-CT). ETAJ/MANSARDĂ -> tabloul SECUNDAR (TES),
  // care se alimentează de la TEG. TE-CT rămâne pe parter în v1 (camera tehnică e de obicei la parter).
  const renderPanelsSection = () => {
    const fc = floorCanonic(floor);
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          {fc === "parter" ? "Tablouri generale" : "Tablou secundar etaj"}
        </div>
        {fc === "parter" ? (
          <>
            {renderPanelBlock("Tablou general (TEG)", "tablou_teg", false)}
            {/* T4 (Faza 2 TE-CT): tabloul camerei tehnice apare DOAR daca "am camera tehnica" e bifat
                (hasTechRoom; absent -> true = non-regresie proiecte existente). Nebifat -> ASCUNS complet
                (coerent cu T2: echipamentele merg pe TEG) — un TE-CT deja plasat ramane pe plan (neatins). */}
            {hasTechRoom && renderPanelBlock("Tablou cameră tehnică (TE-CT)", "tablou_te_ct", true)}
            {/* FV-B1: tablourile FV NU mai stau aici (iluminat) — se pozitioneaza cu butonul
                "Pozitioneaza T.CC + INV + T.CA" din editorul de FORTA (bloc adiacent, plan_type=forta). */}
          </>
        ) : (
          renderPanelBlock("Tablou secundar (TES)", "tablou_tes", false)
        )}
      </div>
    );
  };

  // secțiunea Prize (aparataj pe perete): 4 tipuri, MULTIPLE. Plasare liberă; snap pe perete = P3.
  const renderPrizaSection = () => (
    <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
        Prize
      </div>
      {/* Adaugarea pe TIP a disparut (redundanta): prizele se adauga per camera ("+ Priza" in fiecare
          camera, mai sus) si tipul (simpla/dubla/alimentare/IP44) se schimba cu click pe priza -> dropdown
          "Tip", exact ca la iluminat. */}
      <div style={{ fontSize: 11, color: "#545870", lineHeight: 1.5, paddingLeft: 2, marginBottom: 2 }}>
        Prizele se generează <b style={{ color: "#8B8FA8", fontWeight: 600 }}>automat</b> la intrarea pe forță.
        Adaugă manual cu <span style={{ color: "#8B8FA8" }}>„+ Priză"</span> în fiecare cameră (mai sus),
        apoi schimbă-le tipul cu click pe priză.
      </div>
      {/* R2: auto-repartizare prize pe regulile Dan (per tip camera) — idempotent, rulează AUTOMAT la
          intrarea pe forța (useEffect de mai sus, generatePrizasAuto). Butonul manual a fost SCOS (prizele
          fiind automate); genMsg rămâne = feedback-ul auto-generării. */}
      {genMsg && <div style={{ fontSize: 11.5, color: "#5BB8F5", marginTop: 8, paddingLeft: 2 }}>{genMsg}</div>}
    </div>
  );

  // secțiunea Legendă plan (sub Tablouri): un singur element "legenda" draggable, mutabil în editor.
  // Caseta-placeholder aici; conținutul (simboluri + text) se desenează pe PDF la "Obține plan" (L3).
  const renderLegendSection = () => {
    const existing = elements.find(e => e.element_type === "legenda") || null;
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          Legendă plan
        </div>
        {existing ? (
          <div style={{ fontSize: 11, color: "#545870", display: "flex", alignItems: "center", gap: 8, paddingLeft: 2 }}>
            Casetă adăugată — trage-o pe plan unde vrei.
            <button type="button" className="zy-add-btn" onClick={() => removeElement(existing.id)}>Șterge</button>
          </div>
        ) : (
          <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2 }}>
            <button type="button" className="zy-add-btn" onClick={addLegend}>+ Adaugă legendă</button>
          </div>
        )}
      </div>
    );
  };

  // secțiunea Traseu cabluri (hol): o dungă (linie 2 capete) draggable pe care, la B2, vor merge cablurile.
  // B1: doar dunga vizibilă/mutabilă; fără routing încă.
  const renderTraseuSection = () => {
    const traseuri = elements.filter(e => e.element_type === "traseu");
    const hasPrincipal = traseuri.some(t => t.label !== "secundar");   // fara label = principal
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          Trasee cabluri (hol)
        </div>
        <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2 }}>
          <button type="button" className="zy-add-btn" onClick={() => addTraseu("principal")} disabled={hasPrincipal}>+ Traseu principal</button>
          <button type="button" className="zy-add-btn" onClick={() => addTraseu("secundar")}>+ Traseu secundar</button>
        </div>
        {traseuri.length > 0 && (
          <div style={{ marginTop: 8, paddingLeft: 2 }}>
            {traseuri.map((t) => (
              <div key={t.id} style={{ fontSize: 11, color: "#545870", display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: traseuCol(t.label), flexShrink: 0 }} />
                {t.label === "secundar" ? "Secundar" : "Principal"}
                <button type="button" className="zy-add-btn" onClick={() => removeElement(t.id)}>Șterge</button>
              </div>
            ))}
            <div style={{ fontSize: 11, color: "#545870", marginTop: 2, lineHeight: 1.5 }}>
              Trage vârfurile · click pe linie = adaugă vârf · dublu-click pe vârf = șterge{hasPrincipal ? " · secundarul se lipește de principal" : ""}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Faza 3: sectiunea priza de pamant (fundatie) — buton de desenare, DOAR plan forta + parter.
  const renderGroundingSection = () => {
    if (mode !== "forta" || floorCanonic(floor) !== "parter") return null;
    const existing = elements.find(e => isGroundType(e.element_type)) || null;
    return (
      <Rubrica title="Priza de pământ" hint="Priza de pământ de fundație este obligatorie (I7-2011).">
        {existing ? (
          <div style={{ fontSize: 11, color: "#545870", display: "flex", alignItems: "center", gap: 8, paddingLeft: 2 }}>
            Priză adăugată — șterge-o ca s-o redesenezi.
            <button type="button" className="zy-add-btn" onClick={() => removeElement(existing.id)}>Șterge</button>
          </div>
        ) : drawingGround ? (
          <div style={{ paddingLeft: 2 }}>
            <div style={{ fontSize: 11, color: "#C5C8D6", marginBottom: 6, lineHeight: 1.5 }}>
              Click pe fiecare colț al fundației · <b>{groundPts.length}</b> punct{groundPts.length === 1 ? "" : "e"} · dublu-click / Enter finalizează · Esc anulează
            </div>
            <div className="flex gap-1.5" style={{ flexWrap: "wrap" }}>
              <button type="button" className="zy-add-btn" onClick={() => void finishDrawGround()} disabled={groundPts.length < 3}>Finalizează</button>
              <button type="button" className="zy-add-btn" onClick={cancelDrawGround}>Anulează</button>
            </div>
          </div>
        ) : (
          <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2 }}>
            <button type="button" className="zy-add-btn" onClick={startDrawGround}>+ Desenează priza de pământ</button>
          </div>
        )}
      </Rubrica>
    );
  };

  // Receptoare (bucata A, PILOT): butoane de "alimentare" — 1 click pe plan plaseaza simbolul de
  // alimentare. Pilot = doar boilerul; restul receptoarelor se adauga identic (bucata C = gating pe bifate).
  const renderReceptorSection = () => {
    if (mode !== "forta") return null;
    // H5/H6: butoanele apar STRICT dupa formular. Termice -> heating_distribution ; boiler -> heating_type
    // (PDC/centrala cu boiler) ; AC/cuptor/HRV/EV/internet -> echipamentele bifate. Ascunse complet cand nu-s.
    const eqButtons = visibleEquipmentReceptors({ heatingType, enabledEquipment });
    const heatButtons = visibleHeatingReceptors(heatingDistribution);
    const placedRecs = elements.filter(e => e.element_type === "alimentare_receptor" || e.element_type === "receptor_internet");
    const hasButtons = eqButtons.length > 0 || heatButtons.length > 0;
    // H6: niciun buton vizibil SI niciun receptor plasat -> sectiunea nu apare deloc (fara titlu gol). Daca
    // exista receptoare plasate (de tip acum ascuns), sectiunea RAMANE ca sa le poti edita/sterge (nu se sterg auto).
    if (!hasButtons && placedRecs.length === 0) return null;
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          Alimentări receptoare
        </div>
        {placingReceptor ? (
          <div style={{ paddingLeft: 2 }}>
            <div style={{ fontSize: 11, color: "#C5C8D6", marginBottom: 6, lineHeight: 1.5 }}>
              Click pe plan unde plasezi <b>{placingReceptor.label}</b> · Esc anulează
            </div>
            <button type="button" className="zy-add-btn" onClick={() => setPlacingReceptor(null)}>Anulează</button>
          </div>
        ) : hasButtons ? (
          <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2 }}>
            {/* H6: receptoare NON-termice — boiler din heating_type (PDC/centrala cu boiler); AC/cuptor/HRV/EV/
                internet din echipamentele BIFATE. Label EXACT persistat (declanseaza logica backend). Fotovoltaice
                excluse. Gating pe TIP: plasezi cate unitati vrei. Ascunse complet cand nu-s in formular. */}
            {eqButtons.map(b => (
              <button key={b.label} type="button" className="zy-add-btn" onClick={() => startPlaceReceptor(b.et, b.label)}>
                {b.et === "receptor_internet" ? "+ Rețea internet" : ("+ Alimentare " + b.btnText)}
              </button>
            ))}
            {/* Regula 10 + H5: receptoare termice — dupa emisia (heating_distribution). Radiator/VCV se GRUPEAZA. */}
            {heatButtons.map(h => (
              <button key={h.label} type="button" className="zy-add-btn" onClick={() => startPlaceReceptor("alimentare_receptor", h.label)}>+ {h.label}</button>
            ))}
          </div>
        ) : null}
        {/* LISTA receptoarelor plasate + Sterge. RAMANE vizibila chiar daca butonul tipului e ascuns
            (H6: elementul plasat NU se sterge automat — editabil in inspector, stergibil manual de aici). */}
        {placedRecs.length > 0 && (
          <div style={{ marginTop: 8, paddingLeft: 2 }}>
            {placedRecs.map((r) => (
              <div key={r.id} style={{ fontSize: 11, color: "#545870", display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: r.element_type === "receptor_internet" ? NET_EDGE : COL_PRIZA, flexShrink: 0 }} />
                {r.element_type === "receptor_internet" ? "Rețea internet" : ("Alimentare " + (r.label || "receptor"))}
                <button type="button" className="zy-add-btn" onClick={() => removeElement(r.id)}>Șterge</button>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // T3: sectiunea "Echipamente incalzire" — buton de auto-plasare + LISTA STATUS (informativa v1):
  // ✓ plasat / ○ neplasat per echipament (match element_type+label cu elementele planului).
  // Ascunsa cand proiectul n-are echipamente de incalzire dedicate (fara PDC/centrala).
  // FV-B1: sectiunea tablourilor FV la FORTA — butonul de pozitionare ca bloc + statusul.
  const renderFvPanelsSection = () => {
    // FV DOAR PARTER: sistemul FV se conecteaza la TEG (radacina, parter) -> tablourile (hardcodate
    // floor:"parter" in positionFvPanelsAuto) + lantul galben se pun la parter. Acelasi gate ca priza
    // de pamant (renderGroundingSection) -> ascuns pe etaj/mansarda (unde n-are ce cauta).
    if (mode !== "forta" || !hasFv || floorCanonic(floor) !== "parter") return null;
    const placedCount = FV_PANEL_TYPES.filter(t => elements.some(e => e.element_type === t)).length;
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          Tablouri fotovoltaice
        </div>
        <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2, marginBottom: 8 }}>
          <button type="button" className="zy-add-btn" onClick={positionFvPanelsAuto} disabled={fvpLoading}>
            {fvpLoading ? "Se poziționează…" : "⚡ Poziționează T.CC + INV + T.CA"}
          </button>
        </div>
        {fvpMsg && (
          <div style={{ fontSize: 11, color: "#C5C8D6", paddingLeft: 2, marginBottom: 6, lineHeight: 1.5 }}>{fvpMsg}</div>
        )}
        <div style={{ fontSize: 11, color: placedCount === 3 ? "#3ECFA0" : "#545870", paddingLeft: 2, lineHeight: 1.5 }}>
          {placedCount === 3 ? "✓ Bloc plasat — trage oricare tablou: se mută toate 3 și se lipesc de perete."
            : placedCount > 0 ? `○ ${placedCount}/3 plasate — apasă butonul pentru restul.`
            : "○ Neplasate — butonul pune blocul lângă TEG."}
        </div>
        {/* Lantul FV (manual): polilinie DESCHISA galbena, desenata de inginer (traseul real —
            fatada exterior / prin TE-CT). Mecanismul prizei de pamant; fara lant automat. */}
        {(() => {
          const chain = elements.find(e => isFvChainType(e.element_type)) || null;
          return (
            <div style={{ marginTop: 10, paddingLeft: 2 }}>
              {chain ? (
                <div style={{ fontSize: 11, color: "#545870", display: "flex", alignItems: "center", gap: 8 }}>
                  Traseu FV desenat — șterge-l ca să-l redesenezi.
                  <button type="button" className="zy-add-btn" onClick={() => removeElement(chain.id)}>Șterge</button>
                </div>
              ) : drawingFvChain ? (
                <div>
                  <div style={{ fontSize: 11, color: "#C5C8D6", marginBottom: 6, lineHeight: 1.5 }}>
                    Click pe punctele traseului (T.CC → INV → T.CA → TEG) · <b>{fvChainPts.length}</b> punct{fvChainPts.length === 1 ? "" : "e"} · dublu-click / Enter finalizează · Esc anulează
                  </div>
                  <div className="flex gap-1.5" style={{ flexWrap: "wrap" }}>
                    <button type="button" className="zy-add-btn" onClick={() => void finishDrawFvChain()} disabled={fvChainPts.length < 2}>Finalizează</button>
                    <button type="button" className="zy-add-btn" onClick={cancelDrawFvChain}>Anulează</button>
                  </div>
                </div>
              ) : (
                <button type="button" className="zy-add-btn" onClick={startDrawFvChain}>+ Desenează traseul FV (galben)</button>
              )}
            </div>
          );
        })()}
      </div>
    );
  };

  const renderHeatingEquipSection = () => {
    if (mode !== "forta" || heatingEquipment.length === 0) return null;
    const placed = new Set(elements.filter(e => e.element_type === "alimentare_receptor")
                                   .map(e => (e.label || "").trim()));
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          Echipamente încălzire
        </div>
        <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2, marginBottom: 8 }}>
          <button type="button" className="zy-add-btn" onClick={generateHeatingEquipAuto} disabled={heqLoading}>
            {heqLoading ? "Se plasează…" : "⚡ Generează echipamente încălzire"}
          </button>
        </div>
        {heqMsg && (
          <div style={{ fontSize: 11, color: "#C5C8D6", paddingLeft: 2, marginBottom: 6, lineHeight: 1.5 }}>{heqMsg}</div>
        )}
        <div style={{ paddingLeft: 2 }}>
          {heatingEquipment.map(h => {
            const ok = placed.has(h.label);
            return (
              <div key={h.label} style={{ fontSize: 11, color: ok ? "#3ECFA0" : "#545870",
                display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ width: 12, textAlign: "center", flexShrink: 0 }}>{ok ? "✓" : "○"}</span>
                {h.label}
                <span style={{ color: "#3A3D50" }}>· h={h.mountHeight}m</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // Bucata 3: form "+ Adauga alimentare proprie" — receptor custom (nume+putere+mono/tri) auto-plasat langa TE-CT.
  const renderCustomSupplySection = () => {
    if (mode !== "forta") return null;
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          Alimentare proprie
        </div>
        {!customOpen ? (
          <div style={{ paddingLeft: 2 }}>
            <button type="button" className="zy-add-btn" onClick={() => { setCustomMsg(null); setCustomOpen(true); }}>
              + Adaugă alimentare proprie
            </button>
          </div>
        ) : (
          <div style={{ paddingLeft: 2 }}>
            <label style={fieldLabel}>Denumire</label>
            <input type="text" className="zy-ed-field" style={inputStyle} placeholder="ex. Pompă piscină"
              value={customName} onChange={e => setCustomName(e.target.value)} />
            <label style={fieldLabel}>Putere (W)</label>
            <input type="number" min={1} className="zy-ed-field" style={inputStyle} placeholder="4000"
              value={customW} onChange={e => setCustomW(e.target.value)} />
            <label style={fieldLabel}>Fază</label>
            <select className="zy-ed-field" style={inputStyle} value={customPhase}
              onChange={e => setCustomPhase(e.target.value === "tri" ? "tri" : "mono")}>
              <option value="mono">Monofazat (3 fire)</option>
              <option value="tri">Trifazat (5 fire)</option>
            </select>
            <div className="flex gap-1.5" style={{ flexWrap: "wrap" }}>
              <button type="button" className="zy-add-btn" onClick={() => void addCustomSupply()} disabled={customLoading}>
                {customLoading ? "Se adaugă…" : `Adaugă lângă ${hasTechRoom ? "TE-CT" : "TEG"}`}
              </button>
              <button type="button" className="zy-add-btn" onClick={() => { setCustomOpen(false); setCustomMsg(null); }}>Anulează</button>
            </div>
          </div>
        )}
        {customMsg && <div style={{ fontSize: 11, color: "#F0A868", marginTop: 8, paddingLeft: 2, lineHeight: 1.5 }}>{customMsg}</div>}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
      <style>{FIELD_CSS}</style>

      {/* antet editor — afordanță (ce poți face aici), pe toată lățimea, deasupra coloanelor */}
      <div style={{ flexBasis: "100%", display: "flex", alignItems: "baseline", gap: 10, marginBottom: 2 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "#E2E4E9", letterSpacing: "-0.2px" }}>Editor plan</h3>
        <span style={{ fontSize: 12, color: "#545870" }}>Trage pentru repoziționare · click pentru editare · adaugă/șterge per cameră</span>
      </div>

      {/* ── STÂNGA: panou editare (sticky) + accordion camere + Obține plan ── */}
      <div style={{ width: 300, flexShrink: 0, alignSelf: "flex-start", position: "sticky", top: 70, display: "flex", flexDirection: "column", gap: 12 }}>
        {/* panou editare — iese în evidență la selecție (border accent + tint + ring), discret altfel */}
        <div style={{
          ...panelStyle,
          border: selected ? "1px solid #378ADD" : "1px dashed rgba(255,255,255,0.10)",
          background: selected ? "rgba(55,138,221,0.07)" : "rgba(255,255,255,0.015)",
          boxShadow: selected ? "0 0 0 1px rgba(55,138,221,0.30)" : "none",
          transition: "border-color .18s ease, background-color .18s ease, box-shadow .18s ease",
        }}>
          {renderEditPanel()}
        </div>

        <div style={{ ...panelStyle, padding: 10, maxHeight: "calc(100vh - 330px)", overflowY: "auto" }}>
          <div className="px-1 mb-2" style={{ fontSize: 11, color: "#8B8FA8" }}>
            {loading ? "Se încarcă elementele…" : err ? `Eroare: ${err}` : `${roomKeys.length} camere · ${elements.length} elemente`}
          </div>
          {!loading && !err && roomKeys.length === 0 && (
            <div className="px-2 py-1" style={{ fontSize: 11, color: "#545870" }}>Niciun element pe acest plan.</div>
          )}
          {roomKeys.map(renderRoom)}
          {mode === "iluminat" && renderPanelsSection()}
          {mode === "forta" && renderPrizaSection()}
          {renderLegendSection()}
          {renderTraseuSection()}
          {renderGroundingSection()}
          {renderReceptorSection()}
          {renderHeatingEquipSection()}
          {renderCustomSupplySection()}
          {renderFvPanelsSection()}
        </div>

        {/* Obține plan (1a): regenerează PDF din plan_elements EDITAT, pe baza curată */}
        <div>
          <button type="button" className="zy-getplan" onClick={handleRegenerate} disabled={regenLoading}>
            {regenLoading ? "Se regenerează…" : (mode === "forta" ? "Obține plan forță" : "Obține plan iluminat")}
          </button>
          {regenErr && (
            <div style={{ marginTop: 8, padding: "8px 10px", borderRadius: 8, fontSize: 11.5, lineHeight: 1.45,
              color: "#F0A9A9", background: "rgba(214,40,40,0.08)", border: "1px solid rgba(214,40,40,0.22)" }}>
              {regenErr}
            </div>
          )}
          {regenPdf && (
            <div style={{ marginTop: 8, padding: "8px 10px", borderRadius: 8, fontSize: 12, lineHeight: 1.5,
              background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.22)" }}>
              <div style={{ marginBottom: 6, color: "#C5C8D6" }}>Plan regenerat din modificările tale ✓</div>
              <div className="flex gap-1.5">
                <a className="zy-add-btn" href={regenPdf} download="Plan_iluminat_editat.pdf">Descarcă</a>
                <a className="zy-add-btn" href={regenPdf} target="_blank" rel="noopener noreferrer">Deschide</a>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── DREAPTA: planul (Stage), umple spațiul rămas ── */}
      <div ref={planWrapRef} style={{ flex: 1, minWidth: 280 }}>
        {/* DEBUG P1: toggle overlay pereti (verde) — DOAR admin (Dan). Ascuns inginerului-client in productie;
            codul de randare ramane (jos), showWalls ramane false fara toggle -> conturul nu se deseneaza. */}
        {isAdmin && (
          <div style={{ marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ fontSize: 11, color: "#8B8FA8", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
              <input type="checkbox" checked={showWalls} onChange={(e) => setShowWalls(e.target.checked)} />
              Arată pereți (debug)
            </label>
            {showWalls && <span style={{ fontSize: 11, color: "#16A34A" }}>{walls.length} segmente</span>}
          </div>
        )}
        <div style={{ width: stageW || "100%", maxWidth: "100%", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
          {/* bgLoading face early-return (spinner) INAINTE de acest render — aici fundalul e mereu prezent. */}
          {stageW > 0 && stageH > 0 && (
            <Stage width={stageW} height={stageH} scaleX={displayScale} scaleY={displayScale}>
              <Layer>
                {img && <KonvaImage image={img} width={pngW} height={pngH} listening={false} />}
                {/* DEBUG P1: pereti din /extract-geometry (verde) -> confirma alinierea coord. cu planul.
                    points = (x1,y1)-(x2,y2) puncte PDF × scale (ACELASI scale ca x,y ale elementelor). */}
                {showWalls && walls.map((w, i) => (
                  <Line key={`wall-${i}`} points={[w.x1 * scale, w.y1 * scale, w.x2 * scale, w.y2 * scale]}
                        stroke="#16A34A" strokeWidth={2} opacity={0.7} listening={false} />
                ))}
                {/* CABLURI (snapshot "Obține plan") SUB simboluri: rosu (ca becurile), ne-interactiv.
                    points = path (puncte PDF) × scale, ACELAȘI scale ca x,y ale elementelor. */}
                {overlayCables.map((cab, i) => (
                  <Line
                    key={`cable-${i}`}
                    points={(cab.path || []).flatMap((pt) => [pt[0] * scale, pt[1] * scale])}
                    stroke="#DB2929"
                    strokeWidth={2}
                    dash={[7, 4]}
                    lineCap="round"
                    lineJoin="round"
                    opacity={0.95}
                    listening={false}
                  />
                ))}
                {ordered.map((el) => {
                  if (isTraseuType(el.element_type) || isGroundType(el.element_type) || isFvChainType(el.element_type)) return null;   // traseu + priza de pamant + lantul FV randate separat
                  const px = el.x * scale;
                  const py = el.y * scale;
                  const isBulb = isBulbType(el.element_type);
                  const isPanel = isPanelType(el.element_type);
                  const isSel = selectedId === el.id;
                  const isPriza = isPrizaType(el.element_type);
                  const isReceptor = isReceptorType(el.element_type);   // alimentare receptor (bucata A)
                  const isInternet = isInternetType(el.element_type);   // retea internet (simbol propriu)
                  const col = isBulb ? COL_BULB : isInternet ? NET_EDGE : (isPriza || isReceptor) ? COL_PRIZA : COL_SWITCH;
                  const panel = isPanel ? (PANEL_INFO[el.element_type] || { short: "", colA: "#D1D5DB", colB: "#6B7280" }) : null;
                  const isLegend = isLegendType(el.element_type);
                  const legW = LEG_W * scale, legH = LEG_H * scale;   // caseta legenda (puncte PDF x scale)
                  return (
                    // Group la (px,py); copiii relativi la origine -> e.target.x() = poziția absolută în Layer
                    <Group
                      key={el.id}
                      x={px}
                      y={py}
                      draggable={!(isPanel && mode === "forta" && !isFvPanelType(el.element_type))}   // F2: tablouri READ-ONLY in forta — EXCEPTIE FV (aranjate la forta, unde-s peretii + lantul)
                      onClick={() => selectElement(el.id)}
                      onTap={() => selectElement(el.id)}
                      onDragStart={(e) => e.target.moveToTop()}
                      onDragEnd={(e) => handleDragEnd(el, e)}
                      onMouseEnter={(e) => setCursor(e, isPanel && mode === "forta" ? "default" : "move")}
                      onMouseLeave={(e) => setCursor(e, "default")}
                    >
                      {/* contur de selecție (galben), nu fură evenimente */}
                      {isSel && (isBulb
                        ? bulbSelRing(el.element_type)
                        : isPanel
                          ? <Rect x={-16} y={-20} width={32} height={32} cornerRadius={2} stroke={COL_SEL} strokeWidth={3} listening={false} />
                          : isLegend
                            ? <Rect x={-3} y={-3} width={legW + 6} height={legH + 6} cornerRadius={4} stroke={COL_SEL} strokeWidth={3} listening={false} />
                            : isPriza
                              ? prizaSelRing(el.element_type)
                              : isInternet
                                ? <Rect x={-17} y={-17} width={34} height={34} cornerRadius={4} stroke={COL_SEL} strokeWidth={3} listening={false} />
                                : <Rect x={-13} y={-13} width={26} height={26} cornerRadius={2} stroke={COL_SEL} strokeWidth={3} listening={false} />)}
                      {panel ? (
                        <>
                          {isFvPanelType(el.element_type) ? (
                            <>
                              {/* FV (corectura Dan): patrate MICI (14x14) SIMPLE, FARA conector —
                                  T.CC "=", T.CA "~", INV rosu cu diagonala + ~/=. Rect PLIN = hit. */}
                              {el.element_type === "tablou_inv" ? (
                                <>
                                  <Rect x={-7} y={-7} width={14} height={14} fill="#FFFFFF" stroke="#DC2626" strokeWidth={1.4} />
                                  <Line points={[-7, 7, 7, -7]} stroke="#DC2626" strokeWidth={1.1} listening={false} />
                                  <Text x={-6.5} y={-7} text="~" fontSize={8} fontStyle="bold" fill="#1F2433" listening={false} />
                                  <Text x={1} y={-0.5} text="=" fontSize={7.5} fontStyle="bold" fill="#1F2433" listening={false} />
                                </>
                              ) : (
                                <>
                                  <Rect x={-7} y={-7} width={14} height={14} fill="#FFFFFF" stroke="#1F2433" strokeWidth={1.2} />
                                  <Text x={-7} y={-7} width={14} height={14} align="center" verticalAlign="middle"
                                    text={el.element_type === "tablou_tcc" ? "=" : "~"} fontSize={10} fontStyle="bold" fill="#1F2433" listening={false} />
                                </>
                              )}
                              {panel.short ? <Text x={-11} y={9} text={panel.short} fontSize={9} fontStyle="bold" fill="#1F2433" listening={false} /> : null}
                            </>
                          ) : (
                            <>
                              {/* dreptunghi 24x16 împărțit diagonal: triunghi sus-dreapta (colA) + jos-stânga (colB).
                                  Triunghiurile PLINE rămân "listening" (default) -> zona de hit a Group-ului
                                  draggable (analog cercului becului). Restul (contur/conector/etichetă) listening=false. */}
                              <Line points={[-12, -8, 12, -8, 12, 8]} closed fill={panel.colA} />
                              <Line points={[-12, -8, -12, 8, 12, 8]} closed fill={panel.colB} />
                              <Rect x={-12} y={-8} width={24} height={16} stroke="#1F2433" strokeWidth={1.2} listening={false} />
                              {/* conector vertical scurt deasupra */}
                              <Line points={[0, -8, 0, -16]} stroke="#1F2433" strokeWidth={1.6} listening={false} />
                              {panel.short ? <Text x={-12} y={10} text={panel.short} fontSize={10} fontStyle="bold" fill="#1F2433" listening={false} /> : null}
                            </>
                          )}
                        </>
                      ) : isBulb ? (
                        <>
                          {bulbHit(el.element_type)}
                          {bulbSymbol(el.element_type)}
                        </>
                      ) : isLegend ? (
                        <>
                          {/* caseta-placeholder: chenar + "LEGENDĂ". Rect PLIN = zona de hit a Group-ului
                              draggable. Conținutul real (simboluri + text) se desenează pe PDF la L3.
                              Anchor = colț stânga-sus la (x,y); caseta se extinde dreapta+jos. */}
                          <Rect x={0} y={0} width={legW} height={legH} cornerRadius={3} stroke="#1F2433" strokeWidth={1.4} fill="rgba(255,255,255,0.9)" />
                          <Text x={0} y={0} width={legW} height={legH} align="center" verticalAlign="middle" text="LEGENDĂ" fontSize={Math.max(10, legH * 0.18)} fontStyle="bold" fill="#1F2433" listening={false} />
                        </>
                      ) : isPriza ? (
                        <>
                          {prizaHit()}
                          {/* rotatia DOAR pe simbol (hit-ul e cerc, nu-i pasa) — radiani DB -> grade Konva */}
                          <Group rotation={((el.rotation || 0) * 180) / Math.PI} listening={false}>
                            {prizaSymbol(el.element_type)}
                          </Group>
                        </>
                      ) : isReceptor ? (
                        <>
                          {prizaHit()}
                          {/* receptor = simbolul "alimentare directa" existent (cerc plin), refolosit din prizaSymbol */}
                          {prizaSymbol("priza_16a")}
                        </>
                      ) : isInternet ? (
                        /* retea internet = simbol propriu (caseta turcoaz plina = zona de hit a Group-ului) */
                        internetSymbol()
                      ) : (
                        <Rect x={-7} y={-7} width={14} height={14} stroke={col} strokeWidth={2} fill="rgba(214,40,40,0.22)" />
                      )}
                      {el.room && !isPanel && <Text x={12} y={-7} text={el.room} fontSize={13} fill={col} listening={false} />}
                      {isReceptor && el.label && <Text x={16} y={-7} text={el.label} fontSize={13} fill={col} listening={false} />}
                    </Group>
                  );
                })}
                {/* TRASEU (dunga hol): polilinie N puncte (cable_path) = <Line> + un <Circle draggable> per varf.
                    Click pe linie (cand selectata) = adauga varf; dublu-click pe varf = sterge. B1/B3: vizibil/editabil, FARA routing (B2). */}
                {elements.filter(e => isTraseuType(e.element_type)).map((el) => {
                  const pts = (el.cable_path && el.cable_path.length >= 2) ? el.cable_path : [[el.x, el.y], [el.x + 120, el.y]];
                  const isSel = selectedId === el.id;
                  const tcol = traseuCol(el.label);   // principal albastru inchis / secundar turcoaz (fara label -> principal)
                  const flat = pts.flatMap(p => [p[0] * scale, p[1] * scale]);
                  return (
                    <Group key={el.id}>
                      <Line points={flat} stroke={tcol} strokeWidth={isSel ? 3.5 : 2.5} dash={[9, 5]}
                            lineCap="round" lineJoin="round" hitStrokeWidth={14}
                            onClick={(e) => { if (selectedId === el.id) addTraseuVertex(el, e); else selectElement(el.id); }}
                            onTap={(e) => { if (selectedId === el.id) addTraseuVertex(el, e); else selectElement(el.id); }}
                            onMouseEnter={(e) => setCursor(e, isSel ? "copy" : "pointer")} onMouseLeave={(e) => setCursor(e, "default")} />
                      {pts.map((p, i) => (
                        <Circle key={i} x={p[0] * scale} y={p[1] * scale} radius={isSel ? 7 : 5}
                                fill="#fff" stroke={tcol} strokeWidth={2} draggable
                                onClick={() => selectElement(el.id)}
                                onDblClick={() => removeTraseuVertex(el, i)}
                                onDblTap={() => removeTraseuVertex(el, i)}
                                onDragStart={(e) => { selectElement(el.id); e.target.moveToTop(); }}
                                onDragEnd={(e) => handleTraseuVertexDragEnd(el, i, e)}
                                onMouseEnter={(e) => setCursor(e, "move")} onMouseLeave={(e) => setCursor(e, "default")} />
                      ))}
                    </Group>
                  );
                })}
                {/* Faza 3: priza de pamant EXISTENTA — poligon inchis portocaliu, read-only (editare = follow-up). */}
                {elements.filter(e => isGroundType(e.element_type)).map((el) => {
                  const pts = (el.cable_path && el.cable_path.length >= 2) ? el.cable_path : [[el.x, el.y]];
                  const flat = pts.flatMap(p => [p[0] * scale, p[1] * scale]);
                  return (
                    <Line key={el.id} points={flat} closed stroke={COL_GROUND} strokeWidth={2.5}
                          lineCap="round" lineJoin="round" listening={false} opacity={0.95} />
                  );
                })}
                {/* Lantul FV EXISTENT — polilinie DESCHISA galbena, read-only (redesenare = sterge + deseneaza). */}
                {elements.filter(e => isFvChainType(e.element_type)).map((el) => {
                  const pts = (el.cable_path && el.cable_path.length >= 2) ? el.cable_path : [[el.x, el.y]];
                  const flat = pts.flatMap(p => [p[0] * scale, p[1] * scale]);
                  return (
                    <Line key={el.id} points={flat} stroke={COL_FV_CHAIN} strokeWidth={2.5}
                          lineCap="round" lineJoin="round" listening={false} opacity={0.95} />
                  );
                })}
                {/* Lantul FV: MOD DESENARE — strat de captura + rubber-band (ca priza de pamant, deschis). */}
                {drawingFvChain && (() => {
                  const previewPts = fvChainHover ? [...fvChainPts, fvChainHover] : fvChainPts;
                  const flat = previewPts.flatMap(p => [p[0] * scale, p[1] * scale]);
                  return (
                    <>
                      <Rect x={0} y={0} width={pngW} height={pngH} fill="transparent" listening
                            onClick={addFvChainPoint} onTap={addFvChainPoint}
                            onMouseMove={moveFvChainHover}
                            onDblClick={() => void finishDrawFvChain()} onDblTap={() => void finishDrawFvChain()}
                            onMouseEnter={(e) => setCursor(e, "crosshair")} onMouseLeave={(e) => setCursor(e, "default")} />
                      {previewPts.length >= 2 && (
                        <Line points={flat} stroke={COL_FV_CHAIN} strokeWidth={2} dash={[6, 4]}
                              lineCap="round" lineJoin="round" opacity={0.9} listening={false} />
                      )}
                      {fvChainPts.map((p, i) => (
                        <Circle key={i} x={p[0] * scale} y={p[1] * scale} radius={4}
                                fill="#fff" stroke={COL_FV_CHAIN} strokeWidth={2} listening={false} />
                      ))}
                    </>
                  );
                })()}
                {/* Faza 3: MOD DESENARE — strat de captura (blocheaza elementele existente) + preview rubber-band. */}
                {drawingGround && (() => {
                  const previewPts = groundHover ? [...groundPts, groundHover] : groundPts;
                  const flat = previewPts.flatMap(p => [p[0] * scale, p[1] * scale]);
                  const first = groundPts[0], lastFixed = groundPts[groundPts.length - 1];
                  return (
                    <>
                      <Rect x={0} y={0} width={pngW} height={pngH} fill="transparent" listening
                            onClick={addGroundPoint} onTap={addGroundPoint}
                            onMouseMove={moveGroundHover}
                            onDblClick={() => void finishDrawGround()} onDblTap={() => void finishDrawGround()}
                            onMouseEnter={(e) => setCursor(e, "crosshair")} onMouseLeave={(e) => setCursor(e, "default")} />
                      {previewPts.length >= 2 && (
                        <Line points={flat} stroke={COL_GROUND} strokeWidth={2} dash={[6, 4]}
                              lineCap="round" lineJoin="round" opacity={0.9} listening={false} />
                      )}
                      {groundPts.length >= 3 && first && lastFixed && (
                        <Line points={[lastFixed[0] * scale, lastFixed[1] * scale, first[0] * scale, first[1] * scale]}
                              stroke={COL_GROUND} strokeWidth={1.2} dash={[3, 4]} opacity={0.5} listening={false} />
                      )}
                      {groundPts.map((p, i) => (
                        <Circle key={i} x={p[0] * scale} y={p[1] * scale} radius={4}
                                fill="#fff" stroke={COL_GROUND} strokeWidth={2} listening={false} />
                      ))}
                    </>
                  );
                })()}
                {/* Receptoare (bucata A): overlay transparent care prinde 1 click -> plaseaza alimentarea. */}
                {placingReceptor && (
                  <Rect x={0} y={0} width={pngW} height={pngH} fill="transparent" listening
                        onClick={placeReceptorAt} onTap={placeReceptorAt}
                        onMouseEnter={(e) => setCursor(e, "crosshair")} onMouseLeave={(e) => setCursor(e, "default")} />
                )}
              </Layer>
            </Stage>
          )}
        </div>
      </div>
    </div>
  );
}
