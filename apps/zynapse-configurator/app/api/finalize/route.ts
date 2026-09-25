import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { snapFvPackage } from "@/lib/constants";
import { culegeDocumente, inregistreaza } from "@/lib/registru-finalizari";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { floorCanonic, sortFloors } from "@/lib/floors";   // axa DESCHISĂ de niveluri (oglinda floors.py)

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
  // `motiv` / `refinalizare_a` / `declansat_de` / `ca_user` sunt campuri de RE-FINALIZARE.
  // NU exista o ruta `/api/admin/refinalizare` care sa le filtreze inainte (a fost planificata, nu
  // construita), deci poarta trebuie sa fie AICI, la locul folosirii — si este: vezi verificarea de
  // `is_admin` de mai jos, care refuza `ca_user` oricui nu e admin. La o finalizare obisnuita
  // campurile lipsesc, iar randul din registru le are null.
  let body: { project_id?: string; motiv?: string; refinalizare_a?: string; declansat_de?: string;
              ca_user?: string };
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
  let userId = "";        // proprietarul proiectului (poate fi altul decat cel logat, la re-finalizare)
  let declansatDe = "";   // adminul care a cerut re-finalizarea
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
    userId = user.id;

    // ── RE-FINALIZARE CERUTA DE ADMIN ───────────────────────────────────────────────────────
    // `ca_user` inseamna „ruleaza finalizarea pentru proiectul ACESTUI proprietar". Se accepta
    // DOAR daca cel autentificat e admin, verificat aici, server-side, pe `profiles.is_admin` —
    // acelasi mecanism ca /admin si admin_award_bug. Fara campul asta nimic nu se schimba, deci
    // calea obisnuita de livrare ramane exact cum era.
    let citire: typeof supa | ReturnType<typeof createAdminClient> = supa;
    if (body.ca_user && body.ca_user !== user.id) {
      const { data: eu } = await supa.from("profiles").select("is_admin").eq("id", user.id).single();
      if (eu?.is_admin !== true) {
        return NextResponse.json({ error: "Doar admin poate re-finaliza in numele altui user" },
                                 { status: 403 });
      }
      if (!String(body.motiv || "").trim()) {
        return NextResponse.json({ error: "Re-finalizarea cere un motiv" }, { status: 400 });
      }
      userId = body.ca_user;                       // proprietarul, pentru ownership si registru
      declansatDe = user.id;                       // adminul, pentru registru
      citire = createAdminClient();                // RLS nu i-ar da adminului proiectul altuia
    }

    const { data: proj } = await citire
      .from("projects")
      .select("result_data, faza, phase, input_data")
      .eq("id", projectId)
      .eq("user_id", userId)   // ownership: RLS + filtru explicit (anti-IDOR, ca la regenerate-plan)
      .single();
    if (!proj) return NextResponse.json({ error: "Proiect inexistent sau neautorizat" }, { status: 403 });

    rd = (proj.result_data as Record<string, unknown>) || {};
    inputData = (proj.input_data as Record<string, unknown>) || {};
    faza = (proj.faza as string | null) ?? null;
    phase = (proj.phase as string | null) ?? null;

    const { data: prof } = await citire
      .from("profiles")
      .select("firma_nume, firma_cui, firma_reg_com, firma_tel, firma_email, firma_adresa, firma_logo_url, proiectant_nume, desenator_nume")
      .eq("id", userId)
      .single();
    firma = (prof as CartusFirma) || ({} as CartusFirma);

    // Faza 2: planul EDITAT (plan_elements) -> sursa circuitelor pt. schema+memoriu (RLS: doar owner).
    const { data: peData } = await citire
      .from("plan_elements")
      // `kit_panica` intra in select ODATA cu poarta detaliului de iluminat de siguranta: fara el,
      // ramura „bec cu kit" din poarta ar fi fost moarta si s-ar fi aprins doar pe corp_evacuare.
      .select("element_type, power_w, phase, room, floor, label, x, y, kit_panica")
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
            // sub-tipul comercial -> zonele umede proprii comerțului (dușuri 10mA, spălător 30mA)
            comercial_subtip: (inputData.comercial_subtip as string | undefined) ?? "",
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
  // Oglinda _PLAN_TYPE_LABEL + extra_floors_din_planuri din plansa_numbering.py.
  const PLAN_TYPE_LABEL: Record<string, string> = {
    plan_etaj: "etaj", plan_etaj1: "etaj", plan_etaj2: "etaj 2",
    plan_mansarda: "mansarda", plan_demisol: "demisol", plan_subsol: "subsol",
  };
  const planuri = Array.isArray(rd.planuri) ? (rd.planuri as Array<{ type?: string }>) : [];
  // ETICHETA decide, nu poziția. `slice(1)` sărea planșa [0] pe contractul „slotul 0 e parterul":
  // adevărat pe o casă, fals pe o clădire cu subsol, unde mânca subsolul și inventa un etaj în
  // locul lui. Măsurat în bază: poziția 0 e `plan_generic` (10) sau `plan_parter` (9) — amândouă
  // dau „parter" prin axă, deci se sar la fel și numerotarea lor rămâne neschimbată. Poziția
  // rămâne departajarea doar pentru planurile care nu spun nimic: primul mut = parterul.
  let vazutParter = false;
  let extraFloors: string[] = planuri.flatMap((p) => {
    const t = String(p?.type || "").toLowerCase();
    const lab = PLAN_TYPE_LABEL[t] || floorCanonic(t);
    if (lab !== "parter") return [lab];
    if (!vazutParter) { vazutParter = true; return []; }
    return ["etaj"];
  });
  if (extraFloors.length === 0) {
    // Sursa PREFERATĂ: `floor_label` de pe circuite (pus de enrich de la P0). Pe axa deschisă
    // întregul nu mai e reversibil — 2 a însemnat dintotdeauna „mansardă", dar poate fi și „etaj 2".
    // Fără etichete (circuitele de până acum) cade pe exact harta veche: 1→etaj, 2→mansardă.
    const labels = (circuits as Array<{ floor_label?: unknown }>)
      .map((c) => String(c?.floor_label || "").trim()).filter(Boolean);
    if (labels.length) {
      extraFloors = sortFloors(labels).filter((f) => f !== "parter");
    } else {
      const FLOOR_LABEL: Record<number, string> = { 1: "etaj", 2: "mansarda" };
      const fset = new Set<number>();
      for (const c of circuits as Array<{ floor?: unknown }>) {
        const fi = parseInt(String(c?.floor), 10);
        if (Number.isFinite(fi) && fi > 0) fset.add(fi);
      }
      extraFloors = [...fset].sort((a, b) => a - b).map((f) => FLOOR_LABEL[f] || floorCanonic(f));
    }
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

  // ── NIVELURILE FĂRĂ TABLOU SECUNDAR, calculate O DATĂ și folosite în DOUĂ locuri ──────────────
  // Punctele de coborâre CHIAR plasate pe plan. Sursa e aceeași cu `_panel_for_floor` din backend,
  // deci numerotarea și circuitele nu pot diverge.
  const coborareFloors = [...new Set(
    (planElements as Array<{ element_type?: string; floor?: string }>)
      .filter((e) => (e?.element_type || "") === "coborare_cabluri")
      .map((e) => String(e?.floor || "").trim().toLowerCase())
      .filter(Boolean),
  )];

  // TABLOURILE FANTOMĂ (P9, defectul înregistrat la P8). `panels` vine ÎNGHEȚAT din `result_data`,
  // scris la GENERARE; punctul de coborâre se plasează DUPĂ, în editor. Deci lista putea conține un
  // TES pentru un nivel care între timp nu mai are tablou secundar — iar nodul de scheme, care
  // citește `panels`, îi genera schemă și îi dădea un număr de rezervă, care cădea peste al unui
  // PLAN (IE.2). Numerotarea știa deja adevărul; lista de tablouri nu.
  // Se repară AICI, la sursă, cu exact semnalul de mai sus — nu în nodul de scheme, unde ar fi fost
  // a doua noțiune de „ce tablouri există".
  // ── PORȚILE DE BLOC (P9) ─────────────────────────────────────────────────────────────────────
  // Același tipar ca `has_cs` / `has_det`: semnalul e ce EXISTĂ CU ADEVĂRAT, nu o bifă din formular.
  // Și, mai important, se derivă din CIRCUITE, nu din elemente — un tablou are schemă doar dacă are
  // circuite, deci poarta se aprinde exact când există conținut de desenat. Fără derivare optimistă:
  // o planșă anunțată și nelivrată e mai rea decât una lipsă, fiindcă borderoul o promite.
  //
  // Se aprind DOAR porțile ale căror tipuri au acum producător (schemele de tablou, prin
  // /schema-payloads). `has_teg`, `has_situatie`, distribuția și detaliile rămân stinse — tipurile
  // lor n-au încă cine să le deseneze, iar aprinderea lor ar reface exact golul 44-vs-23.
  const panelsDinCircuite = new Set(
    (circuits as Array<{ panel?: string }>).map((c) => String(c?.panel || "").trim()).filter(Boolean),
  );
  const areTablou = (pred: (n: string) => boolean) => [...panelsDinCircuite].some(pred);
  // Tipurile de apartament: o schemă per TIP, nu per apartament (25 de apartamente, 2 scheme la
  // Dan). Regula e a autorității — rădăcina lanțului `copiat_din` — deci se cere de la ea.
  let tipuriAp: Array<{ nume?: string }> = [];
  // FIRIDELE IDENTICE ÎMPART O SINGURĂ PLANȘĂ DE SCHEMĂ (decizia lui Dan). La el FDCP ETAJ 1 și
  // FDCP ETAJ 2 sunt două firide fizice, amândouă desenate pe IE.20 cu etichetele lor, dar o
  // singură schemă: IE.22, „FDCP ETAJ 1-2". Gruparea NU se calculează aici — se cere de la
  // aceeași funcție pe care o folosește și /schema-payloads când desenează schema. Două
  // implementări ar fi însemnat că numerotarea anunță un grup pe care generatorul nu-l recunoaște.
  let fdcpNume: string[] = [];
  try {
    const tKey = process.env.ZYNAPSE_INTERNAL_KEY;
    const tr = await fetch(`${FASTAPI}/tipuri-apartament`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(tKey ? { "x-zynapse-key": tKey } : {}) },
      body: JSON.stringify({ plan_elements: planElements, circuits }),
    });
    const tj = await tr.json();
    if (tj?.success && Array.isArray(tj.tipuri)) tipuriAp = tj.tipuri;
    if (tj?.success && Array.isArray(tj.fdcp)) {
      fdcpNume = (tj.fdcp as Array<{ eticheta?: string }>)
        .map((g) => String(g?.eticheta || "").trim()).filter(Boolean);
    }
  } catch { /* fără tipuri -> nicio schemă de apartament anunțată; restul neatins */ }
  // ILUMINAT DE SIGURANȚĂ: corp de evacuare desenat SAU bec cu kit de panică. Același semnal pe
  // care-l folosește regula de kit din backend — nu bifa din formular, ci ce e chiar pe plan.
  const areIluminatSiguranta = (planElements as Array<{ element_type?: string; kit_panica?: unknown }>)
    .some((e) => (e?.element_type || "") === "corp_evacuare" || e?.kit_panica === true);
  // PRIZA DE PĂMÂNT: conturul chiar desenat de inginer (pe nivelul fundației).
  const arePrizaPamant = (planElements as Array<{ element_type?: string }>)
    .some((e) => (e?.element_type || "") === "ground_electrode_path");
  const spatiiNume = [...new Set(
    (planElements as Array<{ element_type?: string; label?: string }>)
      .filter((e) => (e?.element_type || "") === "contur_spatiu_comercial")
      .map((e) => String(e?.label || "").trim()).filter(Boolean),
  )];
  const portiBloc = {
    // `has_teg` se derivă și el din CIRCUITE, nu se presupune. La un bloc comunul merge pe TCC,
    // deci nu există tablou general — iar lăsat pornit, borderoul promitea o schemă TEG pe care
    // nimeni n-o poate desena. Prins de câmpul `lipsa` al lui /schema-payloads, la verificarea pe
    // Render: exact rolul lui, să facă vizibil ce altfel dispărea.
    // La o casă TEG există întotdeauna, deci iese `true` și numerotarea rămâne cea de azi.
    has_teg: areTablou((n) => n.toUpperCase() === "TEG"),
    apartamente: tipuriAp.map((t) => String(t?.nume || "")).filter(Boolean),
    spatii: spatiiNume,
    // Grupurile, nu firidele: la Dan 4 firide fizice -> 3 planșe (P · ETAJ 1-2 · ETAJ 3). Lista
    // vine deja derivată din circuite, deci `areTablou` ar fi fost o a doua verificare a aceluiași
    // lucru — fără FDCP în circuite, gruparea iese goală de la sine.
    fdcp: fdcpNume,
    has_bmpt_fdcp: areTablou((n) => /^BMPT/i.test(n)),
    has_tcc: areTablou((n) => n.toUpperCase() === "TCC"),
    has_tecv: areTablou((n) => n.toUpperCase() === "TECV"),
    // DOAR schema camerei de pompe, nu și cele două PLANȘE ale ei: tabloul TEP se desenează ca
    // orice alt tablou, planurile de încăpere n-au încă producător. Fără despărțirea asta, poarta
    // ar fi anunțat trei planșe și ar fi livrat una — exact golul pe care-l închidem.
    has_schema_camera_pompe: areTablou((n) => n.toUpperCase() === "TEP"),
    // SCHEMA DE DISTRIBUȚIE: arborele tablourilor. Poarta e forma de BLOC a arborelui, nu o bifă —
    // o casă are doar TEG/TES/TE-CT și n-ar avea ce arăta acolo peste ce spune deja schema TEG.
    // Măsurat: niciun proiect existent n-are vreunul din tablourile astea, deci numerotarea
    // caselor rămâne byte-identică.
    has_distributie: areTablou((n) => /^(BMPT|FDCP|TCC|TECV|TEGD|TGD)/i.test(n)),
    // DETALIILE. `detaliu_priza_pamant` rămâne DOAR la bloc: non-regresia cerută acoperă explicit
    // o singură excepție (iluminatul de siguranță), iar aprinderea lui la case le-ar fi schimbat
    // numerotarea fără acord. Se poate lărgi oricând — e o listă.
    //
    // `detaliu_iluminat_siguranta` se aprinde ORIUNDE există iluminat de siguranță: detaliul e
    // generic (cerința I7 e a clădirii, nu a blocului), iar o casă cu corpuri de evacuare are
    // aceeași nevoie. Măsurat înainte: UN SINGUR proiect din bază are corpuri de evacuare, e de
    // test și nefinalizat — deci schimbarea e latentă pentru tot ce există azi.
    detalii: [
      ...(areIluminatSiguranta ? ["iluminat_siguranta"] : []),
      ...(areTablou((n) => /^(BMPT|FDCP|TCC|TECV|TEGD|TGD)/i.test(n)) && arePrizaPamant
        ? ["priza_pamant"] : []),
    ],
  };

  const TES_RX = /^TES(\d+)$/i;
  const panelsCurate = (Array.isArray(rd.panels) ? rd.panels : []).filter((p) => {
    const m = TES_RX.exec(String((p as { name?: string })?.name || ""));
    if (!m) return true;                                   // nu-i TES -> neatins
    const nivel = extraFloors[parseInt(m[1], 10) - 1];     // TES{i} <-> al i-lea nivel peste parter
    return !nivel || !coborareFloors.includes(String(nivel).trim().toLowerCase());
  });

  const webhookBody = {
    project_id: projectId,
    circuits,
    power_summary: rd.power_summary || {},
    panel: rd.panel || {},
    panels: panelsCurate,
    rooms: rd.rooms || [],
    project_info: rd.project_info || {},
    // FLAG DE PREZENTA, nu continut: nodurile de memoriu si caiet il folosesc doar ca sa stie
    // daca planul anotat exista, ca sa-l treaca in borderou ca IE.1. De cand planul anotat se
    // muta in Storage, prezenta lui se vede din CALE, nu din base64 — fara `|| path` aici,
    // golirea randurilor ar fi sters tacit o plansa din borderoul fiecarui memoriu.
    annotated_plan_base64: (rd.annotated_plan_base64 || rd.annotated_plan_path) ? "1" : null,
    has_tect: hasTect,
    // F1/F2-v2/memoriu: sursa EXPLICITA pt. clona finalize (numerotare corecta + FV regenerat + capitol memoriu).
    // Fara acestea, clona cade pe fallback-urile in-nod (numerotarea merge; FV regen + memoriu FV stau pe has_fv).
    extra_floors: extraFloors,
    has_fv: hasFv,
    // CURENTI SLABI: la finalize semnalul NU e bifa din formular, ci planşele CHIAR generate —
    // altfel un proiect cu bifa dar fara planşa desenata ar primi un numar IE pentru o planşa
    // inexistenta, si tot restul s-ar deplasa degeaba.
    has_cs: ((rd.planse_curenti_slabi as Array<{ regenerated?: boolean }> | undefined) || [])
      .some((p) => p?.regenerated),
    // DETECȚIE INCENDIU: același semnal ca la curenți slabi — planșele chiar generate, nu bifa.
    has_det: ((rd.planse_detectie as Array<{ regenerated?: boolean }> | undefined) || [])
      .some((p) => p?.regenerated),
    // NIVELURILE FĂRĂ TABLOU SECUNDAR: calculate mai sus (`coborareFloors`), fiindcă aceeași listă
    // filtrează și `panels`. Lista goală (proiectele de până acum) = numerotarea de azi, neschimbată.
    coborare_floors: coborareFloors,
    // PORȚILE DE BLOC, derivate mai sus din circuitele CHIAR generate. Pe o casă toate ies goale
    // sau false, deci numerotarea rămâne exact cea de azi — non-regresia e structurală.
    ...portiBloc,
    // TIPURILE de apartament, pentru schemele care își declară domeniul („AP-1: PARTER P1..P4 · …").
    tipuri_apartament: tipuriAp,
    fv_kw: fvKw,
    fv_soil_type: fvSoilType,
    faza,
    phase,
    // ALIMENTAREA (branșament propriu / din firida blocului): din formularul proiectului, ca
    // sub-tipul comercial. Nodurile n8n o pasează mai departe la memoriu, caiet și schemă.
    // Absentă (proiecte de dinainte) -> string gol -> backendul se poartă exact ca azi.
    alimentare: String(inputData.alimentare || ""),
    // SURSA DE CĂLDURĂ: același drum ca `alimentare`. Memoriul scrie din ea capitolul 2.2
    // („Sistemul termoenergetic"); absentă (proiecte de dinainte) -> capitolul lipsește, ca azi.
    heating_type: String(inputData.heating_type || ""),
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
    // ── REGISTRUL DE FINALIZARI ──────────────────────────────────────────────────────────
    // Se scrie DUPA ce n8n a livrat, si nu are voie sa strice livrarea: orice esec (arhivare sau
    // rand) se logheaza si raspunsul pleaca neschimbat catre client. `motiv` vine din corpul
    // cererii doar la re-finalizarea ceruta de un admin — vezi /api/admin/refinalizare.
    if (resp.ok) {
      try {
        const docs = culegeDocumente(parsed);
        const reg = await inregistreaza(
          {
            projectId, userId, faza: phase || faza,
            motiv: typeof body.motiv === "string" ? body.motiv : null,
            refinalizareA: typeof body.refinalizare_a === "string" ? body.refinalizare_a : null,
            declansatDe: body.ca_user ? declansatDe : null,
          },
          docs,
        );
        if (!reg.id) {
          console.error("[/api/finalize] finalizarea NU s-a inregistrat (livrarea a mers)");
        } else if (!reg.arhivat) {
          console.error("[/api/finalize] finalizare %s inregistrata, ARHIVARE PARTIALA: %s",
                        reg.id, reg.eroare);
        }
        (parsed as Record<string, unknown>).finalizare_id = reg.id;
        (parsed as Record<string, unknown>).finalizare_arhivata = reg.arhivat;
      } catch (e) {
        console.error("[/api/finalize] bloc registru esuat (livrarea a mers):", e);
      }
    }
    return NextResponse.json(parsed, { status: resp.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
