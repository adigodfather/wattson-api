import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

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
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });

    const { data: proj } = await supa
      .from("projects")
      .select("result_data, faza, phase")
      .eq("id", projectId)
      .eq("user_id", user.id)   // ownership: RLS + filtru explicit (anti-IDOR, ca la regenerate-plan)
      .single();
    if (!proj) return NextResponse.json({ error: "Proiect inexistent sau neautorizat" }, { status: 403 });

    rd = (proj.result_data as Record<string, unknown>) || {};
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
        // (heating-driven, ortogonal de plan); TEG/TES vin din plan.
        body: JSON.stringify({ plan_elements: planElements, form: { power_phase, extra_equipment: [] }, base_circuits: visionCircuits }),
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
    faza,
    phase,
    cartus_firma: firma,
    circuits_source: circuitsSource,   // "plan (enrich)" | "vision (fallback)" — traceabilitate Faza 2
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
      // BOM UNIFICAT: /bom (din enrich + plan_elements, CONSISTENT cu schema/memoriu/tabel). Mapat la
      // formatul citit de UI {category,item,quantity,unit,notes}. Fallback: pastreaza BOM-ul n8n (parsed.bom).
      try {
        const key = process.env.ZYNAPSE_INTERNAL_KEY;
        const ps2 = (rd.power_summary as { connection?: string }) || {};
        const pp2 = /trif|400/.test(String(ps2.connection || "").toLowerCase()) ? "tri" : "mono";
        const br = await fetch(`${FASTAPI}/bom`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
          body: JSON.stringify({ project_id: projectId, form: { power_phase: pp2, extra_equipment: [] } }),
        });
        const bj = await br.json();
        if (bj?.success && Array.isArray(bj.rows) && bj.rows.length > 0) {
          parsed.bom = (bj.rows as Array<Record<string, unknown>>).map((r) => ({
            category: r.categorie, item: r.denumire, quantity: r.cantitate, unit: r.um, notes: r.specificatie,
          }));
          parsed.bom_source = "plan (unified)";
        } else {
          parsed.bom_source = "n8n (fallback)";   // parsed.bom ramane cel de la n8n
        }
      } catch { parsed.bom_source = "n8n (fallback)"; }
    }
    return NextResponse.json(parsed, { status: resp.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
