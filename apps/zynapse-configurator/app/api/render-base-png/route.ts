import { NextRequest, NextResponse } from "next/server";

// Fundal editor FORTA: randeaza baza CURATA (planuri[].pdf_base64) -> PNG + png_meta, prin FastAPI.
// Proxy simplu (fara DB): clientul trimite PDF-ul lui (deja RLS-scoped din result). Middleware-ul cere
// sesiune (ruta NU e in PUBLIC_ROUTES). Model: app/api/regenerate-plan/route.ts (fara ownership — zero DB).
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

  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetch(`${FASTAPI}/render-base-png`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
      body: JSON.stringify({ pdf_base64: pdf }),
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
