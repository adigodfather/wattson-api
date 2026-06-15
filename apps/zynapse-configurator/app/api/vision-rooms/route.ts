import { NextRequest, NextResponse } from "next/server";

// Faza B.2 — Vision multi-call paralel (proxy server-side).
// Deține cheia Anthropic ca env var (ANTHROPIC_API_KEY) — NU în n8n, NU în client.
// n8n "Vision Rooms Multi" apelează acest endpoint cu toate planurile; aici rulează
// Promise.all peste planuri și se agregă camerele cu `floor`.

export const runtime = "nodejs";
export const maxDuration = 120;

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_MODEL = "claude-opus-4-7";

// Prompt IDENTIC cu nodul existent "Claude Vision – Analiză Plan" (detectează
// rooms[], building_info, project_info, climate_zone, levels_string, building_category).
const VISION_PROMPT = `Ești expert în analiza planurilor de construcție românești. Returnează UN SINGUR OBIECT JSON valid (fără alt text).

1. LOCALIZARE — caută în cartușul din colțul dreapta-jos: județ, localitate.
   Determină zona climatică C107/2005:
   - Zona I: Constanța, Tulcea, Galați, Brăila, Ialomița, Călărași, Giurgiu, Teleorman, Dolj, Mehedinți, Olt
   - Zona II: Ilfov, București, Iași, Vaslui, Vrancea, Buzău, Prahova, Dâmbovița, Argeș, Vâlcea, Gorj, Hunedoara, Caraș-Severin, Timiș, Arad, Bihor, Satu Mare
   - Zona III: Bacău, Neamț, Suceava, Botoșani, Harghita, Covasna, Brașov, Sibiu, Alba, Cluj, Mureș, Bistrița-Năsăud, Sălaj, Maramureș
   - Zona IV: zone montane înalte
   Dacă nu găsești → climate_zone: "II", climate_source: "necunoscut"

2. REGIM ÎNĂLȚIME — caută titluri (PLAN PARTER, PLAN ETAJ, PLAN MANSARDĂ, PLAN SUBSOL) sau notații P+1, D+P+M.
   Returnează: has_basement (bool), floors_above_ground (int 0-5), has_attic (bool), levels_string (ex: "P+M")
   Dacă nu detectezi → levels_string: "P", has_basement: false, floors_above_ground: 0, has_attic: false

3. TIP CLĂDIRE → building_category:
   - dormitoare, living → "rezidential"
   - săli, amfiteatre, clase → "public"
   - utilaje, poduri rulante → "industrial"
   - apartamente repetitive pe etaje → "bloc"
   - vitrine, casă de marcat → "comercial"

4. CAMERE — pentru fiecare spațiu: name, room_type, area_m2, height_m, function, bbox ({x,y,w,h} NORMALIZAT între 0 și 1 față de lățimea/înălțimea imaginii, NU pixeli — x=0 stânga, x=1 dreapta, y=0 sus, y=1 jos).
   bbox = dreptunghiul care acoperă ÎNTREAGA suprafață a camerei, de la perete la perete (toți cei 4 pereți care o delimitează), NU doar zona textului/etichetei/cotelor.
   Funcții valide: day/night/bathroom/kitchen/circulation/technical/storage/other/hall/office/corridor/sanitary/kitchen_pub/production/warehouse/office_ind

5. DIMENSIUNI IMAGINE — estimează: image_width_px, image_height_px

6. CARTUS (titlu bloc dreapta-jos) — citește cu atenție textul din caseta dreptunghiulară din colțul dreapta-jos al planșei.
   Caută câmpurile: TITLU PROIECT, BENEFICIAR, AMPLASAMENT, ȘEF PROIECT / PROIECTANT, PROIECT NR., DATA, FAZA, PLANSĂ NR.
   Câmpuri lipsă sau invizibile → string gol ""

7. SUPRAFETE (din cartuș / tabel bilanț-indici) — extrage numeric dacă există: suprafața construită (Sc) -> surfaces.construita_mp; suprafața utilă (Su) -> surfaces.utila_mp; suprafața construită desfășurată (Scd) -> surfaces.desfasurata_mp. Caută texte gen "Suprafata construita = NNN mp" sau "Sc = NNN". Extrage DOAR numărul (ex. 245.73); negăsit -> null. NU inventa, NU estima. Dacă sunt MAI MULTE construcții (C1, C2, C3), ia construcția PRINCIPALĂ (C1 / casa de locuit), NU rândul TOTAL/TOTALA; pune în surfaces.note ce construcție ai ales (ex. "C1 CASA").

JSON final:
{
  "climate_zone": "II",
  "climate_source": "jud. Bihor",
  "has_basement": false,
  "floors_above_ground": 1,
  "has_attic": true,
  "levels_string": "P+M",
  "total_area_m2": 120,
  "building_category": "rezidential",
  "building_info": {"image_width_px": 2480, "image_height_px": 3508},
  "project_info": {"titlu_proiect": "", "beneficiar": "", "amplasament": "", "sef_proiect": "", "proiect_nr": "", "data": "", "faza": "", "plansa_nr": "", "surfaces": {"construita_mp": null, "utila_mp": null, "desfasurata_mp": null, "note": ""}},
  "rooms": [{"name": "Living", "room_type": "living", "area_m2": 25, "height_m": 2.7, "function": "day", "bbox": {"x": 0.05, "y": 0.10, "w": 0.20, "h": 0.15}}]
}

Pentru FIECARE cameră din rooms[], include bbox NORMALIZAT între 0 și 1 (fracții din lățime/înălțime, NU pixeli):
- x,y = colțul stânga-sus al camerei (intersecția pereților stânga+sus), w,h = până la pereții dreapta+jos.
- Centrul bbox-ului (x+w/2, y+h/2) trebuie să cadă în mijlocul liber al încăperii (unde ar sta un corp de iluminat pe tavan), nu lângă un perete sau pe etichetă.
- Dacă eticheta «A: NN mp» e într-un colț, ignoră poziția ei — bbox-ul urmează pereții, nu textul.
- Verificare: aria dreptunghiului (w×h × suprafața imaginii) trebuie să fie aproximativ proporțională cu area_m2 declarat — dacă bbox-ul e mult mai mic decât cameră, l-ai desenat prea strâns.

Returnează DOAR JSON-ul, fără explicații.`;

interface PlanInput {
  base64: string;
  plan_type?: string; // mime sau "parter"/"etaj"/"mansarda"
  mime?: string;
}

function floorTag(floor: number): string {
  return floor === 0 ? "(parter)" : floor === 1 ? "(etaj)" : "(mansarda)";
}

function planLabel(floor: number): string {
  return floor === 0 ? "parter" : floor === 1 ? "etaj" : "mansarda";
}

async function analyzePlan(
  apiKey: string,
  plan: PlanInput,
  floor: number,
  hasMultiFloor: boolean
) {
  const mime = plan.mime || (plan.plan_type && plan.plan_type.includes("/") ? plan.plan_type : "application/pdf");
  const isPdf = mime === "application/pdf";

  try {
    const res = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: ANTHROPIC_MODEL,
        max_tokens: 4096,
        temperature: 0,
        messages: [
          {
            role: "user",
            content: [
              { type: isPdf ? "document" : "image", source: { type: "base64", media_type: mime, data: plan.base64 } },
              { type: "text", text: VISION_PROMPT },
            ],
          },
        ],
      }),
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[vision-rooms] floor ${floor} HTTP ${res.status}: ${errorText.slice(0, 300)}`);
      return { error: true, floor, rooms: [], building_info: {}, project_info: {}, total_area_m2: 0 };
    }

    const data = await res.json();
    const text = data?.content?.[0]?.text || "";
    const jsonMatch = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```|(\{[\s\S]*\})/);
    const jsonStr = jsonMatch?.[1] || jsonMatch?.[2] || text.trim();

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonStr);
    } catch (e) {
      console.error(`[vision-rooms] floor ${floor} JSON parse failed:`, (e as Error).message);
      return { error: true, floor, rooms: [], building_info: {}, project_info: {}, total_area_m2: 0 };
    }

    const rawRooms = Array.isArray(parsed.rooms) ? (parsed.rooms as Record<string, unknown>[]) : [];
    const rooms: Record<string, unknown>[] = rawRooms.map((r) => ({
      ...r,
      floor,
      plan_type: planLabel(floor),
      name: hasMultiFloor && r.name ? `${r.name} ${floorTag(floor)}` : r.name,
    }));

    const areaSum = rooms.reduce((s, r) => s + (parseFloat(String(r.area_m2 ?? 0)) || 0), 0);

    return {
      error: false,
      floor,
      rooms,
      building_info: parsed.building_info || {},
      project_info: parsed.project_info || {},
      climate_zone: parsed.climate_zone,
      climate_source: parsed.climate_source,
      levels_string: parsed.levels_string,
      building_category: parsed.building_category,
      has_basement: parsed.has_basement,
      floors_above_ground: parsed.floors_above_ground,
      has_attic: parsed.has_attic,
      total_area_m2: areaSum,
    };
  } catch (e) {
    console.error(`[vision-rooms] floor ${floor} error:`, (e as Error).message);
    return { error: true, floor, rooms: [], building_info: {}, project_info: {}, total_area_m2: 0 };
  }
}

export async function POST(request: NextRequest) {
  // Protecție server-to-server: ruta e exclusă din middleware-ul de auth (n8n n-are cookie),
  // așa că o protejăm cu un secret header. Se aplică DOAR dacă ZYNAPSE_INTERNAL_KEY e setat
  // (altfel ar bloca testarea înainte de configurare). Setează cheia în Vercel + n8n.
  const internalKey = process.env.ZYNAPSE_INTERNAL_KEY;
  if (internalKey) {
    const provided = request.headers.get("x-zynapse-key");
    if (provided !== internalKey) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    // Cheia trebuie setată în Vercel env vars (Project Settings → Environment Variables).
    return NextResponse.json(
      { error: "ANTHROPIC_API_KEY not configured on server" },
      { status: 500 }
    );
  }

  let payload: { plans?: PlanInput[] };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const plans = Array.isArray(payload.plans) ? payload.plans.filter((p) => p && p.base64) : [];
  if (plans.length === 0) {
    return NextResponse.json({ error: "No plans provided" }, { status: 400 });
  }

  const hasMultiFloor = plans.length > 1;

  // Paralelism real peste planuri
  const results = await Promise.all(
    plans.map((plan, idx) => analyzePlan(apiKey, plan, idx, hasMultiFloor))
  );

  const allRooms = results.flatMap((r) => r.rooms);
  const totalArea = results.reduce((s, r) => s + (r.total_area_m2 || 0), 0);
  const parter = results.find((r) => r.floor === 0) || results[0];

  const floorStats = results.map((r) => ({
    floor: r.floor,
    rooms_count: r.rooms.length,
    area_m2: r.total_area_m2,
    error: r.error,
  }));

  return NextResponse.json({
    rooms: allRooms,
    building_info: parter.building_info || {},
    project_info: parter.project_info || {},
    climate_zone: parter.climate_zone ?? null,
    climate_source: parter.climate_source ?? null,
    levels_string: parter.levels_string ?? null,
    building_category: parter.building_category ?? null,
    has_basement: parter.has_basement ?? null,
    floors_above_ground: parter.floors_above_ground ?? null,
    has_attic: parter.has_attic ?? null,
    total_area_m2: totalArea,
    floors_count: plans.length,
    has_etaj: plans.length >= 2,
    has_mansarda: plans.length >= 3,
    floor_stats: floorStats,
  });
}
