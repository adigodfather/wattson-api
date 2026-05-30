import { NextRequest, NextResponse } from 'next/server';

const N8N_VISION_CARTUS_URL =
  'https://www.ai-nord-vest.com/webhook/zynapse-vision-cartus';

// App Router config: Node runtime + extended timeout (Vision call: 10-30s)
export const runtime = 'nodejs';
export const maxDuration = 60;

export async function POST(request: NextRequest) {
  try {
    // Forward FormData as multipart/form-data to n8n
    const formData = await request.formData();

    const res = await fetch(N8N_VISION_CARTUS_URL, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: `Vision API error: ${res.status}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('[/api/vision-cartus] Error:', error);
    return NextResponse.json(
      { error: 'Vision cartus analysis failed' },
      { status: 500 }
    );
  }
}
