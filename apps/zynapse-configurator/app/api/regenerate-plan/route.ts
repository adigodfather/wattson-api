import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

// "Obtine plan" sub-pas 1a — proxy server-side catre FastAPI /regenerate-plan.
// Securitate: verifica proprietatea proiectului (anti-IDOR) inainte de a chema backend-ul,
// fiindca backend-ul citeste plan_elements cu service-role (ocoleste RLS).
export const runtime = "nodejs";
export const maxDuration = 120;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  let body: { project_id?: string; floor?: string; base_pdf_base64?: string; plan_type?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const projectId = String(body.project_id || "");
  const floor = String(body.floor || "parter");
  const base = String(body.base_pdf_base64 || "");
  const planType = body.plan_type === "forta" ? "forta" : "iluminat";   // F4: doar iluminat/forta
  if (!projectId || !base) {
    return NextResponse.json({ error: "project_id + base_pdf_base64 necesare" }, { status: 400 });
  }

  // ── Ownership: utilizatorul autentificat trebuie sa detina proiectul ──
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
    const { data: proj } = await supa
      .from("projects").select("id").eq("id", projectId).eq("user_id", user.id).single();
    if (!proj) return NextResponse.json({ error: "Proiect inexistent sau neautorizat" }, { status: 403 });
  } catch {
    return NextResponse.json({ error: "Verificare proprietate esuata" }, { status: 500 });
  }

  // ── Forward la FastAPI ──
  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetch(`${FASTAPI}/regenerate-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
      body: JSON.stringify({ project_id: projectId, floor, base_pdf_base64: base, plan_type: planType }),
    });
    const text = await resp.text();
    try {
      return NextResponse.json(JSON.parse(text), { status: resp.status });
    } catch {
      return NextResponse.json(
        { error: "Backend a returnat non-JSON (posibil timeout)", preview: text.slice(0, 200) },
        { status: 502 }
      );
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
