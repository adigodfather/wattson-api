import { NextRequest, NextResponse } from "next/server";

// P4: ce conținut ar trebui să primească apartamentele de pe un nivel, de la cele identice de
// dedesubt. Proxy simplu spre FastAPI, pe modelul render-base-png (fără DB, fără ownership —
// elementele vin de la client, deja RLS-scoped, iar răspunsul NU scrie nimic).
//
// Backendul doar PROPUNE; inserturile le face clientul, ca la restul elementelor de plan
// (`save_plan_elements` e efectiv mort — nodul n8n nu-i pasează project_id). Același tipar ca la
// kitul de panică: regula trăiește în backend, scrierea în editor.
export const runtime = "nodejs";
export const maxDuration = 60;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  let body: { plan_elements?: unknown; floor?: string; project_id?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  if (!Array.isArray(body.plan_elements)) {
    return NextResponse.json({ error: "plan_elements necesar" }, { status: 400 });
  }

  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetch(`${FASTAPI}/apartamente-copiaza`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
      body: JSON.stringify({
        plan_elements: body.plan_elements,
        floor: String(body.floor || "parter"),
        project_id: String(body.project_id || ""),
      }),
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
