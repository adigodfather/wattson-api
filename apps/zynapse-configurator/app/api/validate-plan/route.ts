import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

// POARTA DE VALIDARE plan (determinista, fara AI): proxy autentificat catre FastAPI /validate-plan.
// Ruleaza INAINTE de /api/vision-cartus (primul consum Anthropic) -> input respins = 0 consum.
// Model: app/api/extract-geometry/route.ts (auth user + x-zynapse-key).
export const runtime = "nodejs";
export const maxDuration = 60;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  let body: { pdf_base64?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const pdf = String(body.pdf_base64 || "");
  if (!pdf) {
    return NextResponse.json({ error: "pdf_base64 necesar" }, { status: 400 });
  }

  // ── Auth: utilizatorul trebuie sa fie autentificat (anti-abuz) ──
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
  } catch {
    return NextResponse.json({ error: "Verificare autentificare esuata" }, { status: 500 });
  }

  // ── Forward la FastAPI (cu cheia interna) ──
  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetch(`${FASTAPI}/validate-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
      body: JSON.stringify({ pdf_base64: pdf }),
    });
    const text = await resp.text();
    try {
      return NextResponse.json(JSON.parse(text), { status: resp.status });
    } catch {
      // backend non-JSON (timeout Render) -> poarta e DEFENSIVA: permite (nu blocam useri pe infra)
      return NextResponse.json({ status: "ok", note: "backend indisponibil — permis defensiv" });
    }
  } catch {
    return NextResponse.json({ status: "ok", note: "backend inaccesibil — permis defensiv" });
  }
}
