"use client";

// Editor vizual plan — PASUL 3.1: READ-ONLY (doar afișare PNG + overlay elemente din plan_elements,
// la coordonatele corecte). Validează maparea puncte-PDF -> pixeli-PNG. Fără drag/click/editare.
// react-konva e client-only (canvas/window) -> componenta e importată cu dynamic ssr:false în configurator.
import { useEffect, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Circle, Rect, Text, Group } from "react-konva";
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
  x: number;
  y: number;
  rotation: number | null;
  plan_type: string | null;
  floor: string | null;
};

const DISPLAY_W = 880; // lățimea maximă pe ecran (px); Stage-ul se scalează uniform sub această valoare

export default function PlanEditor({
  projectId, pngBase64, pngMeta,
}: { projectId: string; pngBase64?: string | null; pngMeta?: PngMeta }) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [elements, setElements] = useState<PlanElement[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // factor puncte-PDF -> pixeli-PNG (din png_meta; NICIODATĂ hardcodat)
  const scale = pngMeta?.scale ?? 1;

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
    const supabase = createClient();
    supabase
      .from("plan_elements")
      .select("id, element_type, room, x, y, rotation, plan_type, floor")
      .eq("project_id", projectId)
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) { setErr(error.message); setElements([]); }
        else setElements((data as PlanElement[]) || []);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [projectId]);

  if (!pngBase64) {
    return <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Nu există imagine PNG a planului pentru editare.</p>;
  }

  // dimensiuni PNG (px) + scalare uniformă la ecran (imagine + overlay împreună -> rămân aliniate)
  const pngW = pngMeta?.png_width_px ?? img?.width ?? 0;
  const pngH = pngMeta?.png_height_px ?? img?.height ?? 0;
  const displayScale = pngW > 0 ? Math.min(1, DISPLAY_W / pngW) : 1;
  const stageW = Math.round(pngW * displayScale);
  const stageH = Math.round(pngH * displayScale);

  const nBulbs = elements.filter(e => e.element_type === "aplica_tavan").length;
  const nSwitches = elements.filter(e => e.element_type === "intrerupator_simplu").length;

  return (
    <div>
      <div className="mb-3 text-[12px]" style={{ color: "#8B8FA8" }}>
        {loading
          ? "Se încarcă elementele…"
          : err
            ? `Eroare la citirea elementelor: ${err}`
            : `${elements.length} elemente · ${nBulbs} becuri (●) + ${nSwitches} întrerupătoare (■) · vizualizare read-only`}
      </div>
      <div style={{ width: stageW || "100%", maxWidth: "100%", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
        {stageW > 0 && stageH > 0 && (
          <Stage width={stageW} height={stageH} scaleX={displayScale} scaleY={displayScale}>
            <Layer>
              {img && <KonvaImage image={img} width={pngW} height={pngH} listening={false} />}
              {elements.map((el) => {
                const px = el.x * scale;
                const py = el.y * scale;
                const isBulb = el.element_type === "aplica_tavan";
                const col = isBulb ? "#1E63D6" : "#D62828";
                return (
                  <Group key={el.id} listening={false}>
                    {isBulb
                      ? <Circle x={px} y={py} radius={9} stroke={col} strokeWidth={2} fill="rgba(30,99,214,0.22)" />
                      : <Rect x={px - 7} y={py - 7} width={14} height={14} stroke={col} strokeWidth={2} fill="rgba(214,40,40,0.22)" />}
                    {el.room && <Text x={px + 11} y={py - 6} text={el.room} fontSize={11} fill={col} />}
                  </Group>
                );
              })}
            </Layer>
          </Stage>
        )}
      </div>
    </div>
  );
}
