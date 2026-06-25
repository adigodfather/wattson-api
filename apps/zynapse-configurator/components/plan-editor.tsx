"use client";

// Editor vizual plan — PASUL 3.6: panou stâng pe CAMERE (accordion) cu Add/Remove per cameră.
// Peste 3.1 (PNG+overlay), 3.2 (DRAG cu persistare), 3.3/3.4a (selecție), 3.4b (editare Tip/Putere).
// Coordonate: afișare px = x_pdf * png_meta.scale (spațiul PNG, în Layer). Stage are scaleX/scaleY =
// displayScale (PNG->ecran), transform SEPARAT. Salvare drag: x_pdf = e.target.x() / scale (invers exact).
// Add = INSERT cu ACELAȘI tipar ca popularea (configurator.tsx); id e gen_random_uuid() în DB.
// Remove = DELETE manual (cu confirm inline), fără paritate automată.
// react-konva e client-only (canvas/window) -> importat cu dynamic ssr:false în configurator.
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Stage, Layer, Image as KonvaImage, Circle, Rect, Line, Arc, Text, Group } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import { createClient } from "@/lib/supabase";

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
const SELECT_COLS = "id, element_type, room, label, power_w, x, y, rotation, plan_type, floor, status, wall_mounted, mount_height_m, circuit_id, cable_path";

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
  { value: "tablou_tes",    label: "Tablou TES",    short: "TES",   colA: "#D1D5DB", colB: "#6B7280" },
  { value: "transformator", label: "Transformator", short: "TR",    colA: "#D1D5DB", colB: "#6B7280" },
];
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
const COL_PRIZA = "#1565C0";   // simbol priza in editor (ALBASTRU/forta — coerent cu cablurile, distinct de iluminat)
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

// Simbol PRIZA (Konva): semicerc (half-disc, partea curbă SUS) + 2 contacte sub el; ALBASTRU COL_PRIZA (forța).
// priza_16a = ALIMENTARE DIRECTĂ (cerc gol). Distinct de bec (cerc+X) și aplica_perete (semicerc curbat în JOS).
function prizaSymbol(type: string) {
  const C = COL_PRIZA;
  const disc = (cx: number, r = 8) => (
    <Arc x={cx} y={0} innerRadius={0} outerRadius={r} angle={180} rotation={180} stroke={C} strokeWidth={2} />
  );
  const contacts = (cx: number) => (
    <>
      <Line points={[cx - 3, 2, cx - 3, 6]} stroke={C} strokeWidth={1.5} listening={false} />
      <Line points={[cx + 3, 2, cx + 3, 6]} stroke={C} strokeWidth={1.5} listening={false} />
    </>
  );
  switch (type) {
    case "priza_dubla":
      return <>{disc(-8, 7)}{contacts(-8)}{disc(8, 7)}{contacts(8)}</>;
    case "priza_16a":   // ALIMENTARE DIRECTĂ = cerc gol (consumatori conectați direct, fără priză)
      return <Circle x={0} y={0} radius={8} stroke={C} strokeWidth={2} />;
    case "priza_exterior_ip44":
      return <><Rect x={-11} y={-11} width={22} height={21} cornerRadius={3} stroke={C} strokeWidth={1.3} listening={false} />{disc(0)}{contacts(0)}<Text x={-10} y={11} text="IP44" fontSize={6.5} fill={C} listening={false} /></>;
    default: // priza_simpla
      return <>{disc(0)}{contacts(0)}</>;
  }
}
function prizaHit() {   // zonă de hit invizibilă (simbolul e fără fill) -> Group draggable
  return <Circle x={0} y={0} radius={13} fill="rgba(0,0,0,0.001)" />;
}
function prizaSelRing(type: string) {
  const w = type === "priza_dubla" ? 40 : 28;
  return <Rect x={-w / 2} y={-15} width={w} height={28} cornerRadius={3} stroke={COL_SEL} strokeWidth={3} listening={false} />;
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
// cel mai apropiat perete; daca sub prag -> proiectie (snapped), altfel pozitie libera. walls gol -> fara snap.
function snapToWall(px: number, py: number, walls: WallSeg[], threshold = 40) {
  let best: { x: number; y: number; dist: number } | null = null;
  for (const w of walls) {
    const p = projectOnSegment(px, py, w.x1, w.y1, w.x2, w.y2);
    if (!best || p.dist < best.dist) best = p;
  }
  if (best && best.dist < threshold) return { x: best.x, y: best.y, snapped: true };
  return { x: px, y: py, snapped: false };
}

const fieldLabel: CSSProperties = { display: "block", fontSize: 10, color: "#8B8FA8", marginBottom: 3, textTransform: "uppercase", letterSpacing: 0.3 };
const inputStyle: CSSProperties = {
  width: "100%", boxSizing: "border-box", marginBottom: 10, padding: "8px 10px", fontSize: 12.5,
  color: "#E6E8F0", borderRadius: 7, outline: "none", fontFamily: "inherit",
};

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
.zy-soon-badge { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px;
  padding: 1px 6px; border-radius: 999px; background: rgba(255,255,255,0.22); color: #fff; }
@media (prefers-reduced-motion: reduce) { .zy-chev { transition: none; } .zy-acc-body { animation: none; } .zy-getplan { transition: none; } }
`;
const panelStyle: CSSProperties = {
  boxSizing: "border-box", borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)",
  background: "rgba(255,255,255,0.02)", padding: 12,
};

export default function PlanEditor({
  projectId, pngBase64, pngMeta, cleanBasePdf, floor, onRegenerated,
}: { projectId: string; pngBase64?: string | null; pngMeta?: PngMeta; cleanBasePdf?: string | null; floor?: string;
     onRegenerated?: (pdfBase64: string) => void }) {
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
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) { setErr(error.message); setElements([]); }
        else setElements((data as PlanElement[]) || []);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [projectId, supabase]);

  // DEBUG P1: extrage peretii din cleanBasePdf O DATA (statici) -> state `walls`. NON-BLOCANT.
  useEffect(() => {
    if (!cleanBasePdf) return;
    let cancelled = false;
    fetch("/api/extract-geometry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pdf_base64: cleanBasePdf }),
    })
      .then(r => r.json())
      .then(d => { if (!cancelled && d?.success && Array.isArray(d.walls)) setWalls(d.walls); })
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
    const floor = ref?.floor || "parter";
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
    if (elements.some(e => e.element_type === panelType)) return;   // un singur TEG / TE-CT
    const floor = elements[0]?.floor || "parter";
    const cx = pngW > 0 ? (pngW / scale) / 2 : 200;
    const cy = pngH > 0 ? (pngH / scale) / 2 : 200;
    const off = panelType === "tablou_te_ct" ? 44 : 0;   // separă TEG vs TE-CT dacă ambele sunt în centru
    const row = {
      project_id: projectId,
      floor,
      element_type: panelType,
      plan_type: "iluminat",
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

  // ADD PRIZA: aparataj pe perete, MULTIPLE per plansa (fara guard). Plasare LIBERA in centru;
  // inginerul o trage (snap pe perete = P3). wall_mounted=true. Acelasi tipar de INSERT ca addPanel.
  async function addPriza(prizaType: string) {
    const floor = elements[0]?.floor || "parter";
    const cx = pngW > 0 ? (pngW / scale) / 2 : 200;
    const cy = pngH > 0 ? (pngH / scale) / 2 : 200;
    const row = {
      project_id: projectId,
      floor,
      element_type: prizaType,
      plan_type: "iluminat",
      label: null as string | null,
      room: null as string | null,
      x: cx,
      y: cy,
      wall_mounted: true,
      mount_height_m: 0.6,            // inaltime precompletata (editabila in panou)
      rotation: 0,
      status: null as string | null,
    };
    const { data, error } = await supabase.from("plan_elements").insert(row).select(SELECT_COLS).single();
    if (error || !data) { console.error("[plan_elements] INSERT priza esuat", error?.message); return; }
    setElements(prev => [...prev, data as PlanElement]);
    setSelectedId((data as PlanElement).id);
  }

  // ADD LEGENDA: caseta legenda (element draggable global, room=null), max 1 per plansa.
  // Acelasi tipar de INSERT ca addPanel; pozitie initiala = colt stanga-jos (in PUNCTE PDF).
  // L1: DOAR caseta-placeholder in editor; desenul continutului pe PDF vine la L3.
  async function addLegend() {
    if (elements.some(e => e.element_type === "legenda")) return;   // max 1 legenda / plansa
    const floor = elements[0]?.floor || "parter";
    const pdfW = pngW > 0 ? pngW / scale : 400;
    const pdfH = pngH > 0 ? pngH / scale : 400;
    const x = pdfW * 0.55;                          // mai in DREAPTA (legenda lata cu text descriptiv); draggable oricum
    const y = pdfH * 0.30;                           // zona dreapta-sus relativ libera (anchor = colt stanga-sus)
    const row = {
      project_id: projectId,
      floor,
      element_type: "legenda",
      plan_type: "iluminat",
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

  // ADD TRASEU (dunga hol): linie dreapta cu 2 capete, punctele in cable_path (puncte PDF). Max 1/plansa.
  // B1: doar dunga vizibila/mutabila in editor; routing-ul (switch->dunga->tablou) vine la B2. ancora x,y = points[0].
  async function addTraseu() {
    if (elements.some(e => e.element_type === "traseu")) return;   // max 1 traseu / plansa
    const floor = elements[0]?.floor || "parter";
    const pdfW = pngW > 0 ? pngW / scale : 400;
    const pdfH = pngH > 0 ? pngH / scale : 400;
    const x0 = pdfW * 0.35, y0 = pdfH * 0.5;        // dunga orizontala default peste centru (mutabila)
    const x1 = pdfW * 0.65, y1 = pdfH * 0.5;
    const row = {
      project_id: projectId,
      floor,
      element_type: "traseu",
      plan_type: "iluminat",
      label: null as string | null,
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
    const xPdf = e.target.x() / scale;
    const yPdf = e.target.y() / scale;
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

  // Drag -> salvează noua poziție în PUNCTE PDF. e.target e Group-ul; x/y sunt în coordonate Layer
  // (spațiul PNG), iar Stage-scale (displayScale) e separat și NU intervine. Inversul exact al afișării.
  function handleDragEnd(el: PlanElement, e: KonvaEventObject<DragEvent>) {
    let xPdf = e.target.x() / scale;
    let yPdf = e.target.y() / scale;
    // SNAP P3: DOAR prize, DOAR daca avem pereti -> lipeste pe cel mai apropiat perete sub prag (~40pt).
    // Peste prag SAU walls gol -> ramane unde a fost pus (plasare libera, ex. hol fara pereti).
    if (isPrizaType(el.element_type) && walls.length) {
      const s = snapToWall(xPdf, yPdf, walls);
      if (s.snapped) {
        xPdf = s.x; yPdf = s.y;
        e.target.position({ x: xPdf * scale, y: yPdf * scale });   // muta Group-ul vizual pe perete imediat
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
        body: JSON.stringify({ project_id: projectId, floor: floor || "parter", base_pdf_base64: cleanBasePdf }),
      });
      const data = await res.json();
      if (!res.ok || !data?.success || !data?.pdf_base64) {
        setRegenErr(data?.error || "Regenerare eșuată.");
      } else {
        setRegenPdf(pdfBlobUrl(data.pdf_base64));     // URL de blob pt. download/open
        onRegenerated?.(data.pdf_base64);             // trimite PDF-ul sus -> configurator salveaza + afiseaza
        setOverlayCables(Array.isArray(data.cables) ? data.cables : []);  // snapshot cabluri -> overlay Konva
      }
    } catch (e) {
      setRegenErr(e instanceof Error ? e.message : "Eroare de rețea.");
    } finally {
      setRegenLoading(false);
    }
  }

  if (!pngBase64) {
    return <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Nu există imagine PNG a planului pentru editare.</p>;
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
    const typeOptions = isBulbSel ? BULB_TYPES : isSwitchSel ? SWITCH_TYPES : [];
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

        {/* Înălțime (mount_height_m) — DOAR la prize; precompletat 0.6, editabil (metri). Becurile NU au (pe tavan). */}
        {isPrizaType(selected.element_type) && (
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
            <div className="flex gap-1.5 mt-2 pl-1">
              <button type="button" className="zy-add-btn" onClick={() => addElement(key, "bulb")}>+ Bec</button>
              <button type="button" className="zy-add-btn" onClick={() => addElement(key, "switch")}>+ Întrerupător</button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // un bloc de tablou (TEG / TE-CT): dacă există deja -> rândul lui (select + ștergere), altfel selectorul.
  const renderPanelBlock = (title: string, panelType: string, allowNotNeeded: boolean) => {
    const existing = elements.find(e => e.element_type === panelType) || null;
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
  const renderPanelsSection = () => (
    <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
        Tablouri generale
      </div>
      {renderPanelBlock("Tablou general (TEG)", "tablou_teg", false)}
      {renderPanelBlock("Tablou cameră tehnică (TE-CT)", "tablou_te_ct", true)}
    </div>
  );

  // secțiunea Prize (aparataj pe perete): 4 tipuri, MULTIPLE. Plasare liberă; snap pe perete = P3.
  const renderPrizaSection = () => (
    <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
        Prize
      </div>
      <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2 }}>
        {PRIZA_TYPES.map(p => (
          <button key={p.value} type="button" className="zy-add-btn" onClick={() => addPriza(p.value)}>+ {p.label}</button>
        ))}
      </div>
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
    const existing = elements.find(e => e.element_type === "traseu") || null;
    return (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8", marginBottom: 8, paddingLeft: 2 }}>
          Traseu cabluri (hol)
        </div>
        {existing ? (
          <div style={{ fontSize: 11, color: "#545870", display: "flex", alignItems: "center", gap: 8, paddingLeft: 2 }}>
            Dungă adăugată — trage vârfurile; click pe linie = adaugă vârf, dublu-click pe vârf = șterge.
            <button type="button" className="zy-add-btn" onClick={() => removeElement(existing.id)}>Șterge</button>
          </div>
        ) : (
          <div className="flex gap-1.5" style={{ flexWrap: "wrap", paddingLeft: 2 }}>
            <button type="button" className="zy-add-btn" onClick={addTraseu}>+ Adaugă traseu</button>
          </div>
        )}
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
          {renderPanelsSection()}
          {renderPrizaSection()}
          {renderLegendSection()}
          {renderTraseuSection()}
        </div>

        {/* Obține plan (1a): regenerează PDF din plan_elements EDITAT, pe baza curată */}
        <div>
          <button type="button" className="zy-getplan" onClick={handleRegenerate} disabled={regenLoading}>
            {regenLoading ? "Se regenerează…" : "Obține plan iluminat"}
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
        {/* DEBUG P1: toggle overlay pereti (verde) — confirma alinierea coordonatelor */}
        <div style={{ marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ fontSize: 11, color: "#8B8FA8", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
            <input type="checkbox" checked={showWalls} onChange={(e) => setShowWalls(e.target.checked)} />
            Arată pereți (debug)
          </label>
          {showWalls && <span style={{ fontSize: 11, color: "#16A34A" }}>{walls.length} segmente</span>}
        </div>
        <div style={{ width: stageW || "100%", maxWidth: "100%", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
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
                {/* CABLURI (snapshot "Obține plan") SUB simboluri: albastru, ne-interactiv.
                    points = path (puncte PDF) × scale, ACELAȘI scale ca x,y ale elementelor. */}
                {overlayCables.map((cab, i) => (
                  <Line
                    key={`cable-${i}`}
                    points={(cab.path || []).flatMap((pt) => [pt[0] * scale, pt[1] * scale])}
                    stroke="#1565C0"
                    strokeWidth={2}
                    dash={[7, 4]}
                    lineCap="round"
                    lineJoin="round"
                    opacity={0.95}
                    listening={false}
                  />
                ))}
                {ordered.map((el) => {
                  if (isTraseuType(el.element_type)) return null;   // traseu (dunga) randat separat (Line + capete)
                  const px = el.x * scale;
                  const py = el.y * scale;
                  const isBulb = isBulbType(el.element_type);
                  const isPanel = isPanelType(el.element_type);
                  const isSel = selectedId === el.id;
                  const isPriza = isPrizaType(el.element_type);
                  const col = isBulb ? COL_BULB : isPriza ? COL_PRIZA : COL_SWITCH;
                  const panel = isPanel ? (PANEL_INFO[el.element_type] || { short: "", colA: "#D1D5DB", colB: "#6B7280" }) : null;
                  const isLegend = isLegendType(el.element_type);
                  const legW = LEG_W * scale, legH = LEG_H * scale;   // caseta legenda (puncte PDF x scale)
                  return (
                    // Group la (px,py); copiii relativi la origine -> e.target.x() = poziția absolută în Layer
                    <Group
                      key={el.id}
                      x={px}
                      y={py}
                      draggable
                      onClick={() => selectElement(el.id)}
                      onTap={() => selectElement(el.id)}
                      onDragStart={(e) => e.target.moveToTop()}
                      onDragEnd={(e) => handleDragEnd(el, e)}
                      onMouseEnter={(e) => setCursor(e, "move")}
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
                              : <Rect x={-13} y={-13} width={26} height={26} cornerRadius={2} stroke={COL_SEL} strokeWidth={3} listening={false} />)}
                      {panel ? (
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
                          {prizaSymbol(el.element_type)}
                        </>
                      ) : (
                        <Rect x={-7} y={-7} width={14} height={14} stroke={col} strokeWidth={2} fill="rgba(214,40,40,0.22)" />
                      )}
                      {el.room && !isPanel && <Text x={12} y={-7} text={el.room} fontSize={13} fill={col} listening={false} />}
                    </Group>
                  );
                })}
                {/* TRASEU (dunga hol): polilinie N puncte (cable_path) = <Line> + un <Circle draggable> per varf.
                    Click pe linie (cand selectata) = adauga varf; dublu-click pe varf = sterge. B1/B3: vizibil/editabil, FARA routing (B2). */}
                {elements.filter(e => isTraseuType(e.element_type)).map((el) => {
                  const pts = (el.cable_path && el.cable_path.length >= 2) ? el.cable_path : [[el.x, el.y], [el.x + 120, el.y]];
                  const isSel = selectedId === el.id;
                  const flat = pts.flatMap(p => [p[0] * scale, p[1] * scale]);
                  return (
                    <Group key={el.id}>
                      <Line points={flat} stroke="#1565C0" strokeWidth={isSel ? 3.5 : 2.5} dash={[9, 5]}
                            lineCap="round" lineJoin="round" hitStrokeWidth={14}
                            onClick={(e) => { if (selectedId === el.id) addTraseuVertex(el, e); else selectElement(el.id); }}
                            onTap={(e) => { if (selectedId === el.id) addTraseuVertex(el, e); else selectElement(el.id); }}
                            onMouseEnter={(e) => setCursor(e, isSel ? "copy" : "pointer")} onMouseLeave={(e) => setCursor(e, "default")} />
                      {pts.map((p, i) => (
                        <Circle key={i} x={p[0] * scale} y={p[1] * scale} radius={isSel ? 7 : 5}
                                fill="#fff" stroke="#1565C0" strokeWidth={2} draggable
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
              </Layer>
            </Stage>
          )}
        </div>
      </div>
    </div>
  );
}
