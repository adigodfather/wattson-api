import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

// P1: extrage peretii din cleanBasePdf -> {walls, doors} (proxy server-side catre FastAPI).
// Necesita utilizator autentificat (anti-abuz). Fara IDOR: clientul trimite propriul PDF
// (cleanBasePdf din result_data); backend-ul NU citeste DB, doar extrage geometria din PDF.
export const runtime = "nodejs";
export const maxDuration = 60;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  let body: { pdf_base64?: string; rooms?: unknown[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const pdf = String(body.pdf_base64 || "");
  const rooms = Array.isArray(body.rooms) ? body.rooms : [];   // V4: optional -> room_geoms per camera
  if (!pdf) {
    return NextResponse.json({ error: "pdf_base64 necesar" }, { status: 400 });
  }

  // ── Auth: utilizatorul trebuie sa fie autentificat ──
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
  } catch {
    return NextResponse.json({ error: "Verificare autentificare esuata" }, { status: 500 });
  }

  // ── Forward la FastAPI ──
  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetch(`${FASTAPI}/extract-geometry`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
      body: JSON.stringify({ pdf_base64: pdf, rooms }),
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
