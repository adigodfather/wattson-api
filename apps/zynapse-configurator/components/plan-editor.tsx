"use client";

// Editor vizual plan — PASUL 3.3: panou-listă (stânga) + selectare bidirecțională (listă <-> plan).
// Peste 3.1 (afișare PNG + overlay) și 3.2 (DRAG cu persistare poziție). READ-ONLY pe date.
// Coordonate: afișare px = x_pdf * png_meta.scale (spațiul PNG, în Layer). Stage are scaleX/scaleY =
// displayScale (PNG->ecran), transform SEPARAT. Salvare drag: x_pdf = e.target.x() / scale (invers exact).
// react-konva e client-only (canvas/window) -> importat cu dynamic ssr:false în configurator.
import { useEffect, useMemo, useRef, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Circle, Rect, Text, Group } from "react-konva";
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
};

const BULB = "aplica_tavan";
const SWITCH = "intrerupator_simplu";
const COL_BULB = "#1E63D6";
const COL_SWITCH = "#D62828";
const COL_SEL = "#FFD400";        // contur galben pe plan pt. elementul selectat
const ACCENT = "#378ADD";
const DISPLAY_W_FALLBACK = 880;   // lățime inițială până măsurăm containerul

// numele afișat în listă: label -> room -> fallback pe tip
function elName(el: PlanElement): string {
  return el.label || el.room || (el.element_type === BULB ? "Bec" : el.element_type === SWITCH ? "Întrerupător" : "Element");
}

export default function PlanEditor({
  projectId, pngBase64, pngMeta,
}: { projectId: string; pngBase64?: string | null; pngMeta?: PngMeta }) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [elements, setElements] = useState<PlanElement[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // factor puncte-PDF -> pixeli-PNG (din png_meta; NICIODATĂ hardcodat)
  const scale = pngMeta?.scale ?? 1;
  // client Supabase reutilizat (citire la mount + UPDATE la drag)
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
      .select("id, element_type, room, label, power_w, x, y, rotation, plan_type, floor")
      .eq("project_id", projectId)
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) { setErr(error.message); setElements([]); }
        else setElements((data as PlanElement[]) || []);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [projectId, supabase]);

  // Drag -> salvează noua poziție în PUNCTE PDF. e.target e Group-ul; x/y sunt în coordonate Layer
  // (spațiul PNG), iar Stage-scale (displayScale) e separat și NU intervine. Inversul exact al afișării.
  function handleDragEnd(el: PlanElement, e: KonvaEventObject<DragEvent>) {
    const xPdf = e.target.x() / scale;
    const yPdf = e.target.y() / scale;
    // optimist: mută elementul în state imediat (controlled prop va fi px = xPdf*scale = poziția curentă -> fără salt)
    setElements(prev => prev.map(p => (p.id === el.id ? { ...p, x: xPdf, y: yPdf } : p)));
    // persistă NON-BLOCANT: eroarea doar se loghează, elementul rămâne mutat vizual
    supabase.from("plan_elements").update({ x: xPdf, y: yPdf }).eq("id", el.id)
      .then(({ error }) => { if (error) console.error("[plan_elements] UPDATE esuat", el.id, error.message); });
  }

  // cursor "move" la hover peste element draggable
  function setCursor(e: KonvaEventObject<MouseEvent>, c: string) {
    const stage = e.target.getStage();
    if (stage) stage.container().style.cursor = c;
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

  const bulbs = elements.filter(e => e.element_type === BULB);
  const switches = elements.filter(e => e.element_type === SWITCH);

  // desenează selectatul ULTIMUL -> conturul lui (+ Group) e deasupra vecinilor
  const ordered = selectedId
    ? [...elements.filter(e => e.id !== selectedId), ...elements.filter(e => e.id === selectedId)]
    : elements;

  // un rând din listă (click -> selectează; highlight când e selectat)
  const renderRow = (el: PlanElement) => {
    const isSel = selectedId === el.id;
    const isBulb = el.element_type === BULB;
    return (
      <button
        key={el.id}
        type="button"
        onClick={() => setSelectedId(el.id)}
        className="w-full flex items-center gap-2 px-2 py-[7px] rounded-md text-left transition-colors hover:bg-white/[0.05]"
        style={{
          background: isSel ? "rgba(55,138,221,0.18)" : "transparent",
          border: isSel ? "1px solid rgba(55,138,221,0.45)" : "1px solid transparent",
          cursor: "pointer",
        }}
      >
        <span
          aria-hidden
          style={{
            width: 11, height: 11, flexShrink: 0,
            borderRadius: isBulb ? "50%" : 2,
            border: `2px solid ${isBulb ? COL_BULB : COL_SWITCH}`,
            background: isBulb ? "rgba(30,99,214,0.25)" : "rgba(214,40,40,0.25)",
          }}
        />
        <span style={{ fontSize: 12, color: isSel ? "#DCEBFB" : "#C5C8D6", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {elName(el)}
        </span>
        {el.power_w ? <span style={{ fontSize: 10, color: "#8B8FA8" }}>{el.power_w}W</span> : null}
      </button>
    );
  };

  const sectionTitle = (label: string, n: number) => (
    <div className="flex items-center gap-2 mt-3 mb-1 px-1" style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "#8B8FA8" }}>
      <span>{label}</span>
      <span style={{ color: "#5BB8F5" }}>({n})</span>
    </div>
  );

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
      {/* ── STÂNGA: panou-listă ── */}
      <div
        style={{
          width: 260, flexShrink: 0, boxSizing: "border-box",
          borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)",
          padding: 10, maxHeight: "72vh", overflowY: "auto",
        }}
      >
        <div className="px-1 mb-1" style={{ fontSize: 11, color: "#8B8FA8" }}>
          {loading ? "Se încarcă elementele…" : err ? `Eroare: ${err}` : `${elements.length} elemente · read-only`}
        </div>

        {sectionTitle("Becuri", bulbs.length)}
        {bulbs.length ? bulbs.map(renderRow)
          : <div className="px-2 py-1" style={{ fontSize: 11, color: "#545870" }}>niciun bec</div>}

        {sectionTitle("Întrerupătoare", switches.length)}
        {switches.length ? switches.map(renderRow)
          : <div className="px-2 py-1" style={{ fontSize: 11, color: "#545870" }}>niciun întrerupător</div>}
      </div>

      {/* ── DREAPTA: planul (Stage), umple spațiul rămas ── */}
      <div ref={planWrapRef} style={{ flex: 1, minWidth: 280 }}>
        <div style={{ width: stageW || "100%", maxWidth: "100%", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
          {stageW > 0 && stageH > 0 && (
            <Stage width={stageW} height={stageH} scaleX={displayScale} scaleY={displayScale}>
              <Layer>
                {img && <KonvaImage image={img} width={pngW} height={pngH} listening={false} />}
                {ordered.map((el) => {
                  const px = el.x * scale;
                  const py = el.y * scale;
                  const isBulb = el.element_type === BULB;
                  const isSel = selectedId === el.id;
                  const col = isBulb ? COL_BULB : COL_SWITCH;
                  return (
                    // Group la (px,py); copiii relativi la origine -> e.target.x() = poziția absolută în Layer
                    <Group
                      key={el.id}
                      x={px}
                      y={py}
                      draggable
                      onClick={() => setSelectedId(el.id)}
                      onTap={() => setSelectedId(el.id)}
                      onDragStart={(e) => e.target.moveToTop()}
                      onDragEnd={(e) => handleDragEnd(el, e)}
                      onMouseEnter={(e) => setCursor(e, "move")}
                      onMouseLeave={(e) => setCursor(e, "default")}
                    >
                      {/* contur de selecție (galben), desenat dedesubt */}
                      {isSel && (isBulb
                        ? <Circle x={0} y={0} radius={15} stroke={COL_SEL} strokeWidth={3} listening={false} />
                        : <Rect x={-13} y={-13} width={26} height={26} cornerRadius={2} stroke={COL_SEL} strokeWidth={3} listening={false} />)}
                      {isBulb
                        ? <Circle x={0} y={0} radius={9} stroke={col} strokeWidth={2} fill="rgba(30,99,214,0.22)" />
                        : <Rect x={-7} y={-7} width={14} height={14} stroke={col} strokeWidth={2} fill="rgba(214,40,40,0.22)" />}
                      {el.room && <Text x={11} y={-6} text={el.room} fontSize={11} fill={col} listening={false} />}
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
