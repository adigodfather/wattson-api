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
  } catch {
    return NextResponse.json({ error: "Verificare/citire esuata" }, { status: 500 });
  }

  const circuits = Array.isArray(rd.circuits) ? (rd.circuits as unknown[]) : [];
  if (circuits.length === 0) {
    return NextResponse.json(
      { error: "Proiectul nu are circuite calculate (result_data.circuits gol) — nu poate fi finalizat." },
      { status: 400 }
    );
  }

  // Trimitem DOAR ce consuma nodurile-doc (circuits/power_summary/panels/rooms/project_info + cartus),
  // NU blob-urile mari (planse/planuri/scheme base64 ~4MB din result_data). annotated_plan_base64 e
  // folosit de memoriu doar ca sa listeze titlurile planselor -> trimitem un placeholder scurt truthy.
  const hasTect = rd.has_tect === true
    || circuits.some((c) => (c as { panel?: string })?.panel === "TE-CT");
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
  };

  // ── Forward la webhook-ul n8n de finalizare ──
  try {
    const resp = await fetch(N8N_FINALIZE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(webhookBody),
    });
    const text = await resp.text();
    try {
      return NextResponse.json(JSON.parse(text), { status: resp.status });
    } catch {
      return NextResponse.json(
        { error: "n8n a returnat non-JSON (posibil timeout)", preview: text.slice(0, 200) },
        { status: 502 }
      );
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
