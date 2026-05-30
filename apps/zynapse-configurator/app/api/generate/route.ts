import { NextRequest, NextResponse } from "next/server";

const N8N_WEBHOOK = "https://www.ai-nord-vest.com/webhook/zynapse-electrical";

// Faza B.1: payload multi-etaj (până la 3 planuri base64) + N PDF-uri în răspuns.
export const runtime = "nodejs";
export const maxDuration = 120;

export async function POST(req: NextRequest) {
  const contentType = req.headers.get("content-type") || "";

  let body: Blob | string;
  try {
    body = await req.blob();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to read request body";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  try {
    const upstream = await fetch(N8N_WEBHOOK, {
      method: "POST",
      headers: { "Content-Type": contentType },
      body,
    });

    // Citim ca text mai întâi, ca să nu crăpăm pe HTML (ex. pagină 504 de la reverse-proxy n8n)
    const text = await upstream.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: upstream.status });
    } catch {
      console.error("[/api/generate] Backend returned non-JSON:", text.slice(0, 500));
      return NextResponse.json({
        error: "Backend timeout sau eroare de procesare",
        details: `HTTP ${upstream.status} — răspuns non-JSON (probabil timeout reverse-proxy n8n)`,
        preview: text.slice(0, 200),
        recommendation: "Încearcă cu mai puține planuri sau contactează administratorul",
      }, { status: 502 });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
