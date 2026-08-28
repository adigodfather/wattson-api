// F5a — AUTO-REPARTIZARE PRIZE (functii PURE: fara React/Konva/DB/desen).
//
// (1) prizeCountPerRoom(circuits)  -> { numeCamera: N_prize }
//     Refoloseste regulile Dan: nr. prize/camera e DEJA calculat in result_data.circuits
//     (fiecare circuit type='prize' are room + outlets). N_camera = sum(outlets) pe acel room.
//     SKIP room null/gol (circuite generale/exterior — inginerul le pune manual).
//
// (2) placePrizasInRoom(bbox, n, walls, W, H) -> [{x, y, snapped}]  (PUNCTE PDF)
//     Distribuie N pozitii uniform pe PERIMETRUL bbox-ului (offset 1/2 pas -> evita colturile),
//     apoi snap pe cel mai apropiat perete real (aceeasi matematica ca P3 in plan-editor.tsx).
//     Fara perete sub prag -> fallback liber, usor INSPRE centru (nu fix pe linia bbox-ului).
//
// NU face INSERT in DB, NU deseneaza, NU atinge UI-ul (acelea = F5b). Doar count + pozitii.

import { cameraCanonica, CAMERE_COMERCIALE } from "./comercial";

export type Circuit = { room?: string | null; type?: string | null; outlets?: number | null };
export type RoomBBox = { x: number; y: number; w: number; h: number }; // 0-1 normalizat (Vision)
export type WallSeg = { x1: number; y1: number; x2: number; y2: number }; // puncte PDF (/extract-geometry)
export type PrizaPos = { x: number; y: number; snapped: boolean; wall: "h" | "v" | null }; // puncte PDF + orientarea peretelui de snap

// ── (1) Nr. prize per camera din circuits (regulile Dan, deja calculate) ──
export function prizeCountPerRoom(circuits: Circuit[] | null | undefined): Record<string, number> {
  const out: Record<string, number> = {};
  if (!Array.isArray(circuits)) return out; // defensiv: lipsa/gol -> {} (buton inactiv la F5b)
  for (const c of circuits) {
    if (!c || c.type !== "prize") continue; // doar circuite de prize (nu iluminat/dedicat/sub_tablou)
    const room = (c.room ?? "").toString().trim();
    if (!room) continue; // SKIP room null/gol -> general/exterior, manual
    const n = Number(c.outlets);
    if (!Number.isFinite(n) || n <= 0) continue; // defensiv: outlets lipsa/0
    out[room] = (out[room] || 0) + Math.round(n); // sum pe camera (ex. Bucatarie 4+4=8)
  }
  return out;
}

// ── (1b) REGULA Dan pe TIP de camera (mapare pe `name` substring) — count + tip priza + grup circuit. ──
// Sursa = regulile FIXE Dan (NU n8n circuits). Ordine specific->generic (evita coliziuni: camara!=camera,
// terasa acces!=acoperita). null = SKIP (camera tehnica TE-CT, gestionata de T1). circuitGroup: "BAIE"/"HOL"/
// "KITCHEN" (comun/special, pt. R3) sau numele camerei (circuit propriu). PURA, determinista.
export type PrizaType = "priza_simpla" | "priza_dubla" | "priza_16a" | "priza_exterior_ip44";
export type PrizaRule = { count: number; type: PrizaType; circuitGroup: string; heightM: number };

// FIX-P: familiile de camere cu prize IP44 — SINCRON cu enrich_circuits.py (_BATH_RX / _TERRACE_KW):
// acolo dau RCCB 10mA pe circuit, aici tipul + inaltimea prizei. Modifici una -> modifici AMBELE
// (altfel: simbol/cablu normal pe un circuit protejat 10mA). "teras" acopera terasa/terasă din enrich.
// ZONA UMEDA — regex, OGLINDA EXACTĂ a lui _BATH_RX din enrich_circuits.py. Pe planuri reale camera
// se cheamă „GR. SANITAR" (abreviere), care nu se potrivea cu vechile chei → prize simple, fără IP44
// și fără RCCB 10mA (neconform I7-2011). „sanitar" acoperă toate variantele scrise; „g.s" acoperă
// abrevierea pură, dar DELIMITATĂ — vechiul „gs" ca substring liber era un fals-pozitiv în așteptare.
// Dacă se schimbă una, se schimbă AMÂNDOUĂ: altfel prizele primesc IP44 iar circuitul rămâne fără RCCB.
const BATH_RX = /(baie|bath|\bwc\b|sanitar|\bg\s*\.?\s*s\.?\b)/i;
const BALCONY_KW = ["balcon", "loggia", "logie"];

// SPAȚII COMERCIALE — regex pe nume normalizat, oglinda lui _COMERCIAL_RULES din draw_elements.py.
// [count fix, pas_mp] — pasul adaugă +1 priză la fiecare X mp (null = doar fixul).
// Numele vin cu diacritice din Vision, deci le scoatem înainte de test (ca _norm_name_ro în backend).
const COMERCIAL_PRIZE: [RegExp, number, number | null][] = [
  [/\b(sala|spatiu|sp\.?)\s*(de\s+)?vanzare\b|\bshowroom|\bmagazin/, 4, 10],
  [/\b(spatiu|sp\.?)\s*servicii\b|\bdeservire/,                      4, 10],
  [/\bcasa\s*(de\s+)?marcat\b|\breceptie\b/,                         4, null],
  [/\bvestiar|\bgarderob/,                                           2, null],
  [/\bchicinet|\boficiu\b/,                                          4, null],
  [/\bprobe?\b|\bcabina\s*prob/,                                     1, null],
];
const deDiacritice = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "");

export function prizeRuleForRoom(
  name: string | null | undefined,
  areaM2?: number | null,
  subtip?: string | null,          // sub-tipul comercial: da intelesul numelor GENERICE („Sala", „Spatiu")
): PrizaRule | null {
  // Cu sub-tip comercial, numele de pe plan se traduce intai in camera canonica, si REGULILE se
  // aplica pe eticheta ei. Asa „Sala" pe un fitness devine „Sala aparate", iar pe un magazin
  // „Spatiu vanzare" — acelasi cuvant, doua seturi de reguli. Fara sub-tip: nimic nu se schimba.
  const canon = subtip ? cameraCanonica(name, subtip) : null;
  const efectiv = canon ? CAMERE_COMERCIALE[canon].label : (name ?? "");
  const n = efectiv.toLowerCase().trim();
  const na = deDiacritice(n);
  const supl = (pas: number | null) =>
    pas && areaM2 && areaM2 > 0 ? Math.floor(areaM2 / pas) : 0;   // „+1 priză la X mp"
  // COMERCIAL, înaintea regulilor rezidențiale (numele sunt specifice, nu se suprapun).
  // Grupul sanitar rămâne PRIMUL (mai jos e deja tratat) — zona umedă are prioritate absolută.
  if (!BATH_RX.test(n)) {
    for (const [rx, fix, pas] of COMERCIAL_PRIZE) {
      if (rx.test(na)) {
        const own = (name ?? "").trim() || "Camera";
        return { count: fix + supl(pas), type: "priza_simpla", circuitGroup: own, heightM: 0.6 };
      }
    }
  }
  const own = (name ?? "").trim() || "Camera";   // circuit propriu = numele camerei
  const S: PrizaType = "priza_simpla";
  const IP44: PrizaType = "priza_exterior_ip44"; // si pt. IP65 (terasa) — nu exista tip IP65 v1

  // 0. BAIE/G.S./WC (prima, ca in enrich.rccb_zone) -> 1 IP44 la h=1.2, grup comun BAIE
  if (BATH_RX.test(n))
    return { count: 1, type: IP44, circuitGroup: "BAIE", heightM: 1.2 };
  // 1-2. TERASA: "acces" -> 0 (manual) INAINTE de terasa generica (acoperita -> 2 IP65->IP44, h=0.4)
  if (n.includes("teras"))
    return n.includes("acces")
      ? { count: 0, type: S, circuitGroup: own, heightM: 0.4 }
      : { count: 2, type: IP44, circuitGroup: own, heightM: 0.4 };
  // 2b. BALCON/LOGGIA -> 1 IP44 la h=0.4 (decizia Dan: 1, nu 2 ca terasa)
  if (BALCONY_KW.some((k) => n.includes(k)))
    return { count: 1, type: IP44, circuitGroup: own, heightM: 0.4 };
  // 3. SPATIU TEHNIC -> SKIP (camera TE-CT, gestionata de schema/T1, nu auto-repartizata)
  if (n.includes("spatiu tehnic") || n.includes("tehnic")) return null;
  // 4. DEPOZIT/CAMARA/DRESSING -> 2 (ATENTIE: "camara" NU prinde "camera" -> inainte de living)
  if (n.includes("depozit") || n.includes("camara") || n.includes("dressing"))
    return { count: 2 + supl(20), type: S, circuitGroup: own, heightM: 0.6 };   // +1 la 20 mp
  // 5. LIVING / CAMERA DE ZI / "zi" -> 4
  if (n.includes("living") || n.includes("camera de zi") || n.includes(" zi") || n === "zi")
    return { count: 4, type: S, circuitGroup: own, heightM: 0.6 };
  // 6. restul (specific): garaj, bucatarie(KITCHEN), dormitor, birou, spalator, hol(COMUN)
  //    (baie a urcat la punctul 0 — BATH_RX acopera si "baie")
  if (n.includes("garaj")) return { count: 3, type: IP44, circuitGroup: own, heightM: 0.6 };
  if (n.includes("bucatar")) return { count: 6, type: S, circuitGroup: "KITCHEN", heightM: 0.6 };
  if (n.includes("dormitor")) return { count: 3, type: S, circuitGroup: own, heightM: 0.6 };
  if (n.includes("birou")) return { count: 4 + supl(12), type: S, circuitGroup: own, heightM: 0.6 };   // 500 lx -> +1 la 12 mp
  if (n.includes("spalator")) return { count: 2, type: S, circuitGroup: own, heightM: 0.6 };
  if (n.includes("hol")) return { count: 2, type: S, circuitGroup: "HOL", heightM: 0.6 };
  // 7. DEFAULT (nume necunoscut) -> 2 simpla, circuit propriu
  return { count: 2, type: S, circuitGroup: own, heightM: 0.6 };
}

// ── Geometrie pura (proiectie punct-pe-segment CLAMPAT) — IDENTICA cu P3 din plan-editor.tsx ──
function projectOnSegment(px: number, py: number, x1: number, y1: number, x2: number, y2: number) {
  const dx = x2 - x1, dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  let t = len2 <= 1e-9 ? 0 : ((px - x1) * dx + (py - y1) * dy) / len2;
  t = Math.max(0, Math.min(1, t)); // clampat pe segment (nu linie infinita)
  const qx = x1 + t * dx, qy = y1 + t * dy;
  return { x: qx, y: qy, dist: Math.hypot(px - qx, py - qy) };
}
// cel mai apropiat perete; sub prag -> proiectie (snapped) + ORIENTAREA peretelui ("h"/"v",
// pt. rotatia simbolului), altfel pozitia libera. walls gol -> fara snap.
export function snapToWall(px: number, py: number, walls: WallSeg[], threshold = 40) {
  let best: { x: number; y: number; dist: number; wall: "h" | "v" } | null = null;
  for (const w of walls) {
    const p = projectOnSegment(px, py, w.x1, w.y1, w.x2, w.y2);
    if (!best || p.dist < best.dist)
      best = { ...p, wall: Math.abs(w.x2 - w.x1) >= Math.abs(w.y2 - w.y1) ? "h" : "v" };
  }
  if (best && best.dist < threshold) return { x: best.x, y: best.y, snapped: true, wall: best.wall };
  return { x: px, y: py, snapped: false, wall: null as "h" | "v" | null };
}

// distribuie N puncte uniform pe perimetrul dreptunghiului (dupa lungime de arc), offset 1/2 pas.
function distributeOnRectPerimeter(
  l: number, t: number, r: number, b: number, n: number
): { x: number; y: number }[] {
  const w = r - l, h = b - t;
  const perim = 2 * (w + h);
  if (perim <= 1e-6) return Array.from({ length: n }, () => ({ x: (l + r) / 2, y: (t + b) / 2 }));
  const pts: { x: number; y: number }[] = [];
  for (let i = 0; i < n; i++) {
    let d = ((i + 0.5) / n) * perim; // 1/2 pas -> nu cad fix pe colturi
    if (d < w) { pts.push({ x: l + d, y: t }); continue; }          // latura sus  (l->r)
    d -= w;
    if (d < h) { pts.push({ x: r, y: t + d }); continue; }          // latura dr.  (t->b)
    d -= h;
    if (d < w) { pts.push({ x: r - d, y: b }); continue; }          // latura jos  (r->l)
    d -= w;
    pts.push({ x: l, y: b - (Math.min(d, h)) });                    // latura stg. (b->t)
  }
  return pts;
}

// ── (2) N pozitii pe perimetrul camerei, cu snap pe perete ──
export function placePrizasInRoom(
  bbox: RoomBBox,
  n: number,
  walls: WallSeg[],
  W: number,
  H: number,
  opts?: { inset?: number; snapThreshold?: number }
): PrizaPos[] {
  if (!bbox || n <= 0 || !(W > 0) || !(H > 0)) return [];
  const inset = opts?.inset ?? 15;          // fallback liber: cat de mult inspre centru (puncte PDF)
  const threshold = opts?.snapThreshold ?? 40;
  const wallList = Array.isArray(walls) ? walls : [];

  // bbox 0-1 -> dreptunghi in PUNCTE PDF (acelasi spatiu ca peretii si ca plan_elements.x/y)
  const l = bbox.x * W, t = bbox.y * H;
  const r = l + bbox.w * W, b = t + bbox.h * H;
  const cx = (l + r) / 2, cy = (t + b) / 2;

  const perimPts = distributeOnRectPerimeter(l, t, r, b, n);
  return perimPts.map((p) => {
    const s = snapToWall(p.x, p.y, wallList, threshold);
    if (s.snapped) return { x: s.x, y: s.y, snapped: true, wall: s.wall }; // pe perete real (+ orientarea lui)
    // fara perete sub prag -> trage usor inspre centru (sa nu stea fix pe linia bbox-ului)
    const vx = cx - p.x, vy = cy - p.y;
    const d = Math.hypot(vx, vy) || 1;
    const k = Math.min(inset, d);
    return { x: p.x + (vx / d) * k, y: p.y + (vy / d) * k, snapped: false, wall: null };
  });
}
