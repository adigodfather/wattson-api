import { NextRequest, NextResponse } from "next/server";

import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { BUCKET } from "@/lib/storage-pdf";
import { fetchBackend } from "@/lib/backend-fetch";
import { pdfDinStorage } from "@/lib/pdf-din-storage";
import { masoara, idUtilizator } from "@/lib/rateLimit";
// Fundal editor FORTA: randeaza baza CURATA (planuri[].pdf_base64) -> PNG + png_meta, prin FastAPI.
// Clientul trimite fie PDF-ul (proiecte vechi, base64 in rand), fie CALEA lui din Storage —
// caz in care il aduce ruta, cu sesiunea utilizatorului, deci tot RLS-ul decide.
// Middleware-ul cere sesiune (ruta NU e in PUBLIC_ROUTES).
export const runtime = "nodejs";
export const maxDuration = 60;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  // Ruta nu citea sesiunea deloc — se baza doar pe middleware. Pentru o limita PE UTILIZATOR e
  // nevoie de identitate aici, iar verificarea in ruta e oricum a doua incuietoare la aceeasi usa.
  const uid = await idUtilizator();
  if (!uid) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
  const rl = await masoara(uid, "render-base-png");
  if (rl.refuz) return rl.refuz;

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
    // Aceeasi functie ca la extract-geometry si regenerate-plan: o singura implementare a
    // „adu PDF-ul din Storage cu sesiunea utilizatorului". Cand codul asta exista DOAR aici,
    // celelalte doua rute n-au stiut de cai si „Obtine plan" s-a rupt pe toate proiectele.
    const adus = await pdfDinStorage(String(body.pdf_path));
    if (!adus) {
      return NextResponse.json({ error: "Fundalul nu s-a putut citi din Storage" }, { status: 403 });
    }
    pdf = adus;
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
