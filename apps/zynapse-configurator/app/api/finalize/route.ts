import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { snapFvPackage } from "@/lib/constants";

// Faza 2b — "Finalizeaza": proxy server-side catre webhook-ul n8n "zynapse-finalize".
// Optiunea (b): n8n NU primeste credentiale Supabase. Aici (autentificat, ownership check)
// citim projects + profiles cu sesiunea userului (RLS -> doar proiectul lui) si trimitem
// DATELE in body-ul webhook-ului. n8n regenereaza schema monofilara + memoriu + BOM din ele.
// Model: app/api/regenerate-plan/route.ts.
export const runtime = "nodejs";
export const maxDuration = 300;   // memoriu + scheme pot dura (FastAPI pe Render free)

const N8N_FINALIZE = "https://www.ai-nord-vest.com/webhook/zynapse-finalize";
const FASTAPI = "https://wattson-api.onrender.com";   // Faza 2: enrich_circuits (circuite din PLAN)

interface CartusFirma {
  firma_nume: string | null; firma_cui: string | null; firma_reg_com: string | null;
  firma_tel: string | null; firma_email: string | null; firma_adresa: string | null;
  firma_logo_url: string | null; proiectant_nume: string | null; desenator_nume: string | null;
}

export async function POST(req: NextRequest) {
  let body: { project_id?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const projectId = String(body.project_id || "");
  if (!projectId) {
    return NextResponse.json({ error: "project_id necesar" }, { status: 400 });
  }

  // ── Auth + ownership + citire (RLS-scoped -> userul isi vede DOAR proiectul/profilul lui) ──
  let rd: Record<string, unknown>;
  let faza: string | null;
  let phase: string | null;
  let firma: CartusFirma;
  let planElements: unknown[] = [];   // Faza 2: planul EDITAT -> circuitele schemei/memoriului
  let inputData: Record<string, unknown> = {};   // formularul salvat (has_tech_room/heating_type/echipamente)
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });

    const { data: proj } = await supa
      .from("projects")
      .select("result_data, faza, phase, input_data")
      .eq("id", projectId)
      .eq("user_id", user.id)   // ownership: RLS + filtru explicit (anti-IDOR, ca la regenerate-plan)
      .single();
    if (!proj) return NextResponse.json({ error: "Proiect inexistent sau neautorizat" }, { status: 403 });

    rd = (proj.result_data as Record<string, unknown>) || {};
    inputData = (proj.input_data as Record<string, unknown>) || {};
    faza = (proj.faza as string | null) ?? null;
    phase = (proj.phase as string | null) ?? null;

    const { data: prof } = await supa
      .from("profiles")
      .select("firma_nume, firma_cui, firma_reg_com, firma_tel, firma_email, firma_adresa, firma_logo_url, proiectant_nume, desenator_nume")
      .eq("id", user.id)
      .single();
    firma = (prof as CartusFirma) || ({} as CartusFirma);

    // Faza 2: planul EDITAT (plan_elements) -> sursa circuitelor pt. schema+memoriu (RLS: doar owner).
    const { data: peData } = await supa
      .from("plan_elements")
      .select("element_type, power_w, phase, room, floor, label, x, y")
      .eq("project_id", projectId);
    planElements = Array.isArray(peData) ? peData : [];
  } catch {
    return NextResponse.json({ error: "Verificare/citire esuata" }, { status: 500 });
  }

  // ── FAZA 2: circuitele schemei+memoriului vin din PLAN (enrich_circuits/FastAPI), ca sa fie
  // CONSISTENTE cu planul editat (nu din Vision inghetat). FALLBACK la result_data.circuits (Vision)
  // daca enrich esueaza / plan gol -> NU blocam finalizarea. ──
  const visionCircuits = Array.isArray(rd.circuits) ? (rd.circuits as unknown[]) : [];
  let circuits: unknown[] = visionCircuits;
  let circuitsSource = "vision (fallback)";
  if (planElements.length > 0) {
    try {
      const ps = (rd.power_summary as { connection?: string }) || {};
      const conn = String(ps.connection || "").toLowerCase();
      const power_phase = (conn.includes("trif") || conn.includes("400")) ? "tri" : "mono";
      const key = process.env.ZYNAPSE_INTERNAL_KEY;
      const er = await fetch(`${FASTAPI}/enrich-circuits`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
        // base_circuits = circuitele vechi (Vision) -> enrich PRESERVA din ele TE-CT + feed-ul coloanei
        // (heating-driven, ortogonal de plan); TEG/TES vin din plan. Faza 2 TE-CT: form-ul include
        // has_tech_room (checkbox; absent -> True in enrich) + heating_type (sinteza setului de GAZ) +
        // extra_equipment (puterile/fazele bifate — regula #2 + boilerul optional la gaz).
        body: JSON.stringify({
          plan_elements: planElements,
          form: {
            power_phase,
            has_tech_room: (inputData.has_tech_room as boolean | undefined) ?? true,
            heating_type: (inputData.heating_type as string | undefined) ?? "",
            extra_equipment: Array.isArray(inputData.extra_equipment) ? inputData.extra_equipment : [],
          },
          base_circuits: visionCircuits,
        }),
      });
      const ej = await er.json();
      if (ej?.success && Array.isArray(ej.circuits) && ej.circuits.length > 0) {
        circuits = ej.circuits as unknown[];
        circuitsSource = "plan (enrich)";
      }
    } catch { /* enrich indisponibil -> ramane fallback Vision */ }
  }
  if (circuits.length === 0) {
    return NextResponse.json(
      { error: "Proiectul nu are circuite (nici din plan, nici Vision) — nu poate fi finalizat." },
      { status: 400 }
    );
  }

  // Trimitem DOAR ce consuma nodurile-doc (circuits/power_summary/panels/rooms/project_info + cartus),
  // NU blob-urile mari (planse/planuri/scheme base64 ~4MB din result_data). annotated_plan_base64 e
  // folosit de memoriu doar ca sa listeze titlurile planselor -> trimitem un placeholder scurt truthy.
  // has_tect din circuitele EFECTIV trimise (nu din rd.has_tect Vision): plan-circuite n-au TE-CT
  // (ramane goala in Faza 2) -> hasTect=false -> Finalize nu genereaza schema TE-CT goala/sparta.
  const hasTect = circuits.some((c) => (c as { panel?: string })?.panel === "TE-CT");

  // ── F1 (2026-07-14): extra_floors pt. numerotarea din clona finalize (nodul "Numerotare Planse").
  // Sursa PREFERATA = tipurile planurilor STAMPILATE (etichete REALE: P+M da 'mansarda', nu 'etaj' ca
  // derivarea din floor — conteaza pt. borderoul memoriului). Fallback: floor-urile INTREGI din circuite.
  // [0] = parter (se sare). Oglinda _PLAN_TYPE_LABEL + derive_extra_floors din plansa_numbering.py.
  const PLAN_TYPE_LABEL: Record<string, string> = {
    plan_etaj: "etaj", plan_etaj1: "etaj", plan_etaj2: "etaj 2",
    plan_mansarda: "mansarda", plan_demisol: "demisol", plan_subsol: "subsol",
  };
  const planuri = Array.isArray(rd.planuri) ? (rd.planuri as Array<{ type?: string }>) : [];
  let extraFloors: string[] = planuri.slice(1).map(
    (p) => PLAN_TYPE_LABEL[String(p?.type || "").toLowerCase()] || "etaj",
  );
  if (extraFloors.length === 0) {
    const FLOOR_LABEL: Record<number, string> = { 1: "etaj", 2: "mansarda" };
    const fset = new Set<number>();
    for (const c of circuits as Array<{ floor?: unknown }>) {
      const fi = parseInt(String(c?.floor), 10);
      if (Number.isFinite(fi) && fi > 0) fset.add(fi);
    }
    extraFloors = [...fset].sort((a, b) => a - b).map((f) => FLOOR_LABEL[f] || `nivel ${f}`);
  }

  // ── F2-v2 + memoriu (2026-07-14): semnalul FV pt. clona finalize -> REGENEREAZA schema FV cu kW-ul
  // EDITORULUI (nodul Compune, gated pe has_fv===true) + CAPITOLUL FV in memoriu (solar). Sursa kW, in
  // ordine: circuitul fotovoltaic din enrich (consistent cu schema/plan) -> invertorul din plan
  // (tablou_inv, power_w=kW*1000) -> solarul din formular (input_data). Normalizat la pachet (snapFvPackage).
  const fvCirc = (circuits as Array<{ description?: string; power_w?: number }>).find(
    (c) => /fotovoltaic/i.test(String(c?.description || "")),
  );
  const invEl = (planElements as Array<{ element_type?: string; power_w?: number | null }>).find(
    (e) => e?.element_type === "tablou_inv",
  );
  const solarEq = (Array.isArray(inputData.extra_equipment) ? inputData.extra_equipment : []).find(
    (e) => !!e && (e as { type?: string }).type === "solar",
  ) as { package_kw?: number; power_kw?: number; soil_type?: string } | undefined;
  const hasFv = !!fvCirc || !!invEl || !!solarEq;
  const fvKwRaw =
    fvCirc && typeof fvCirc.power_w === "number" && fvCirc.power_w > 0 ? fvCirc.power_w / 1000
    : invEl && typeof invEl.power_w === "number" && invEl.power_w > 0 ? invEl.power_w / 1000
    : Number(solarEq?.package_kw ?? solarEq?.power_kw ?? 5);
  const fvKw = snapFvPackage(fvKwRaw);
  const fvSoilType = String(solarEq?.soil_type || "agricol");

  // ── BOM UNIFICAT — chemat INAINTE de n8n (depinde doar de DB: plan_elements exista la finalize).
  // (1) Randurile-CABLU intra in webhookBody.bom_cables -> memoriul enumera cablurile REALE
  // (fraza 2.6 + lista TEG dinamice, decizia Dan 2026-07-24 — doar tipuri, fara metri);
  // (2) ACELASI raspuns devine parsed.bom dupa n8n (sursa unica, UN singur call /bom).
  // Pica -> bomRows=null: memoriul cade pe textul static, parsed.bom pe fallback-ul n8n (ca azi).
  let bomRows: Array<Record<string, unknown>> | null = null;
  try {
    const bomKey = process.env.ZYNAPSE_INTERNAL_KEY;
    const bomPs = (rd.power_summary as { connection?: string }) || {};
    const bomPp = /trif|400/.test(String(bomPs.connection || "").toLowerCase()) ? "tri" : "mono";
    const br = await fetch(`${FASTAPI}/bom`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(bomKey ? { "x-zynapse-key": bomKey } : {}) },
      body: JSON.stringify({ project_id: projectId, form: { power_phase: bomPp, extra_equipment: [] } }),
    });
    const bj = await br.json();
    if (bj?.success && Array.isArray(bj.rows) && bj.rows.length > 0) {
      bomRows = bj.rows as Array<Record<string, unknown>>;
    }
  } catch { /* bomRows ramane null -> fallback-urile de mai sus */ }
  const bomCables = (bomRows || [])
    .filter((r) => String(r.categorie) === "Cabluri" || /cyaby|cablu solar|myf/i.test(String(r.denumire)))
    .map((r) => ({ item: r.denumire, sectiune: r.sectiune }));

  const webhookBody = {
    project_id: projectId,
    circuits,
    power_summary: rd.power_summary || {},
    panel: rd.panel || {},
    panels: rd.panels || [],
    rooms: rd.rooms || [],
    project_info: rd.project_info || {},
    annotated_plan_base64: rd.annotated_plan_base64 ? "1" : null,
    has_tect: hasTect,
    // F1/F2-v2/memoriu: sursa EXPLICITA pt. clona finalize (numerotare corecta + FV regenerat + capitol memoriu).
    // Fara acestea, clona cade pe fallback-urile in-nod (numerotarea merge; FV regen + memoriu FV stau pe has_fv).
    extra_floors: extraFloors,
    has_fv: hasFv,
    fv_kw: fvKw,
    fv_soil_type: fvSoilType,
    faza,
    phase,
    cartus_firma: firma,
    circuits_source: circuitsSource,   // "plan (enrich)" | "vision (fallback)" — traceabilitate Faza 2
    bom_cables: bomCables,             // randurile-cablu /bom -> memoriul (nodul Generate Memoriu le paseaza)
  };

  // ── Circuitele UNIFICATE (enrich) pt. PERSISTARE in result_data -> tabelul UI = documentele.
  // Tabelul UI (CircuitTable) citeste `usage` + `cable`; enrich produce `description` + `cable_type`
  // -> adaugam alias-urile (fallback la campurile Vision daca lipsesc, ptr. fallback-ul Vision).
  // Split pe panel: TE-CT vs restul (TEG/TES/feed) — ca cele 2 tabele din UI. Raw `circuits`
  // (description/cable_type) merge NEATINS la n8n; uiCircuits = DOAR pt. raspuns/persistare.
  const uiCircuits = (circuits as Record<string, unknown>[]).map((c): Record<string, unknown> => ({
    ...c,
    usage: (c.usage ?? c.description ?? "") as string,
    cable: (c.cable ?? c.cable_type ?? "") as string,
  }));
  const circuitsTeCt = uiCircuits.filter((c) => c.panel === "TE-CT");
  const circuitsTeg = uiCircuits.filter((c) => c.panel !== "TE-CT");

  // ── Forward la webhook-ul n8n de finalizare ──
  try {
    const resp = await fetch(N8N_FINALIZE, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // P0-2 (optiunea A): auth webhook finalize — ACELASI pattern ca webhook-urile scumpe
        // (generate:148 -> zynapse-electrical). n8n valideaza cu credential "Zynapse Webhook Secret".
        // Ordinea sigura: codul trimite ACUM secretul (n8n inca accepta fara) -> Dan activeaza Header
        // Auth pe nodul finalize DUPA deploy -> sincron, fara downtime.
        ...(process.env.N8N_WEBHOOK_SECRET ? { "x-webhook-secret": process.env.N8N_WEBHOOK_SECRET } : {}),
        // FIX (03.07): cheia interna FastAPI prin webhook -> Code nodes din finalize o forwardeaza
        // la /generate-schema-b64 + /generate-memoriu ($env nu ajunge in task runner-ul n8n).
        ...(process.env.ZYNAPSE_INTERNAL_KEY ? { "x-zynapse-key": process.env.ZYNAPSE_INTERNAL_KEY } : {}),
      },
      body: JSON.stringify(webhookBody),
    });
    const text = await resp.text();
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(text) as Record<string, unknown>;
    } catch {
      return NextResponse.json(
        { error: "n8n a returnat non-JSON (posibil timeout)", preview: text.slice(0, 200) },
        { status: 502 }
      );
    }
    // Augmentam raspunsul cu circuitele UNIFICATE (enrich) -> frontend-ul le persista in result_data
    // (circuits + circuits_te_ct/teg/all + source) => tabelul UI reflecta PLANUL, nu Vision. DOAR pe succes.
    if (resp.ok && parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      parsed.circuits = uiCircuits;
      parsed.circuits_te_ct = circuitsTeCt;
      parsed.circuits_teg = circuitsTeg;
      parsed.circuits_all = uiCircuits;
      parsed.circuits_source = circuitsSource;
      // BOM UNIFICAT: refoloseste raspunsul /bom chemat INAINTE de n8n (sursa unica cu memoriul —
      // aceleasi randuri). Mapat la formatul UI {category,item,quantity,unit,notes,sectiune}.
      // bomRows null (/bom picat) -> pastreaza BOM-ul n8n (parsed.bom), ca inainte.
      if (bomRows) {
        parsed.bom = bomRows.map((r) => ({
          category: r.categorie, item: r.denumire, quantity: r.cantitate, unit: r.um, notes: r.specificatie,
          sectiune: r.sectiune,   // BOM restructurat: pastreaza sectiunea pt. gruparea vizuala pe cele 8 sectiuni (bucata 3)
        }));
        parsed.bom_source = "plan (unified)";
      } else {
        parsed.bom_source = "n8n (fallback)";   // parsed.bom ramane cel de la n8n
      }
    }
    return NextResponse.json(parsed, { status: resp.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
