import { NextRequest, NextResponse } from "next/server";

import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { BUCKET } from "@/lib/storage-pdf";
import { fetchBackend } from "@/lib/backend-fetch";
// Fundal editor FORTA: randeaza baza CURATA (planuri[].pdf_base64) -> PNG + png_meta, prin FastAPI.
// Clientul trimite fie PDF-ul (proiecte vechi, base64 in rand), fie CALEA lui din Storage —
// caz in care il aduce ruta, cu sesiunea utilizatorului, deci tot RLS-ul decide.
// Middleware-ul cere sesiune (ruta NU e in PUBLIC_ROUTES).
export const runtime = "nodejs";
export const maxDuration = 60;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  let body: { pdf_base64?: string; pdf_path?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  let pdf = String(body.pdf_base64 || "");

  // ── FUNDALUL CURAT POATE VENI CA O CALE ────────────────────────────────────────────────────
  // De cand `planuri[].pdf_base64` sta in Storage, clientul n-ar mai avea PDF-ul in memorie: ar
  // trebui sa-l descarce doar ca sa-l trimita inapoi incoace — acelasi fisier prin retea de doua
  // ori, si prin limita de corp a functiilor Vercel. Cu `pdf_path`, ruta il aduce ea, cu sesiunea
  // utilizatorului: RLS-ul `pf_owner_select` decide daca are voie, deci calea nu e o portita.
  // Backendul de pe Render primeste tot base64 — el n-are credentiale Supabase.
  if (!pdf && body.pdf_path) {
    try {
      const cookieStore = await cookies();
      const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
      const { data, error } = await supa.storage.from(BUCKET).download(String(body.pdf_path));
      if (error || !data) {
        return NextResponse.json({ error: "Fundalul nu s-a putut citi din Storage" }, { status: 403 });
      }
      pdf = Buffer.from(await data.arrayBuffer()).toString("base64");
    } catch {
      return NextResponse.json({ error: "Citirea fundalului a esuat" }, { status: 500 });
    }
  }
  if (!pdf) {
    return NextResponse.json({ error: "pdf_base64 sau pdf_path necesar" }, { status: 400 });
  }

  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetchBackend(`${FASTAPI}/render-base-png`, { pdf_base64: pdf }, {
      headers: key ? { "x-zynapse-key": key } : {},
      bugetMs: 45000,
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
