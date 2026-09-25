import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

import { fetchBackend } from "@/lib/backend-fetch";
import { pdfDinStorage } from "@/lib/pdf-din-storage";
import { masoara } from "@/lib/rateLimit";
// P1: extrage peretii din cleanBasePdf -> {walls, doors} (proxy server-side catre FastAPI).
// Necesita utilizator autentificat (anti-abuz). Fara IDOR: clientul trimite propriul PDF
// (cleanBasePdf din result_data); backend-ul NU citeste DB, doar extrage geometria din PDF.
export const runtime = "nodejs";
export const maxDuration = 60;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  let body: { pdf_base64?: string; pdf_path?: string; rooms?: unknown[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  let pdf = String(body.pdf_base64 || "");
  const cale = String(body.pdf_path || "");
  const rooms = Array.isArray(body.rooms) ? body.rooms : [];   // V4: optional -> room_geoms per camera
  // De cand fundalul curat sta in Storage, clientul n-are base64-ul: trimite CALEA, iar ruta il
  // aduce ea. Pana acum ruta stia doar de base64, deci extragerea peretilor tacea pe toate
  // proiectele — o gardă care nu se aprinde arata exact ca una care nu exista.
  if (!pdf && !cale) {
    return NextResponse.json({ error: "pdf_base64 sau pdf_path necesar" }, { status: 400 });
  }

  // ── Auth: utilizatorul trebuie sa fie autentificat ──
  let uid = "";
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
    uid = user.id;
  } catch {
    return NextResponse.json({ error: "Verificare autentificare esuata" }, { status: 500 });
  }

  // ── Limita de rata, PE UTILIZATOR (nu pe IP: un birou iese pe aceeasi adresa) ──
  const rl = await masoara(uid, "extract-geometry");
  if (rl.refuz) return rl.refuz;

  // Aducerea din Storage se face DUPA autentificare si DUPA limita: cu sesiunea utilizatorului,
  // deci politica `pf_owner_select` decide — calea nu e o portita spre fisierul altuia.
  if (!pdf) {
    const adus = await pdfDinStorage(cale);
    if (!adus) {
      await rl.gata(false);
      return NextResponse.json({ error: "Fundalul nu s-a putut citi din Storage" }, { status: 403 });
    }
    pdf = adus;
  }

  // ── Forward la FastAPI ──
  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetchBackend(`${FASTAPI}/extract-geometry`, { pdf_base64: pdf, rooms }, {
      headers: key ? { "x-zynapse-key": key } : {},
      bugetMs: 45000,
    });
    await rl.gata(resp.ok);
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
