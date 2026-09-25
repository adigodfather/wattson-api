import { NextRequest, NextResponse } from 'next/server';
import { masoara, idUtilizator } from "@/lib/rateLimit";

const N8N_VISION_CARTUS_URL =
  'https://www.ai-nord-vest.com/webhook/zynapse-vision-cartus';

// App Router config: Node runtime + extended timeout (Vision call: 10-30s)
export const runtime = 'nodejs';
export const maxDuration = 60;

export async function POST(request: NextRequest) {
  // Cea mai scumpa dintre cele sase: trece prin n8n la Claude Vision. Nu citea sesiunea deloc.
  const uid = await idUtilizator();
  if (!uid) return NextResponse.json({ error: 'Neautentificat' }, { status: 401 });
  const rl = await masoara(uid, "vision-cartus");
  if (rl.refuz) return rl.refuz;

  try {
    // Forward FormData as multipart/form-data to n8n
    const formData = await request.formData();

    const res = await fetch(N8N_VISION_CARTUS_URL, {
      method: 'POST',
      // FAZA 3A: secretul webhook-ului (n8n îl ignoră până activăm Header Auth pe nod — FAZA 3B).
      // NU setăm Content-Type manual — fetch pune singur multipart boundary-ul pentru FormData.
      headers: {
        ...(process.env.N8N_WEBHOOK_SECRET ? { 'x-webhook-secret': process.env.N8N_WEBHOOK_SECRET } : {}),
      },
      body: formData,
    });

    await rl.gata(res.ok);
    if (!res.ok) {
      return NextResponse.json(
        { error: `Vision API error: ${res.status}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    await rl.gata(false);
    console.error('[/api/vision-cartus] Error:', error);
    return NextResponse.json(
      { error: 'Vision cartus analysis failed' },
      { status: 500 }
    );
  }
}
