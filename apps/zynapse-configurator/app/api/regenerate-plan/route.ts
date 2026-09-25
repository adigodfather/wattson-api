import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

import { fetchBackend } from "@/lib/backend-fetch";
import { pdfDinStorage } from "@/lib/pdf-din-storage";
import { masoara } from "@/lib/rateLimit";
import { urcaPdf } from "@/lib/storage-pdf";
// "Obtine plan" sub-pas 1a — proxy server-side catre FastAPI /regenerate-plan.
// Securitate: verifica proprietatea proiectului (anti-IDOR) inainte de a chema backend-ul,
// fiindca backend-ul citeste plan_elements cu service-role (ocoleste RLS).
export const runtime = "nodejs";
export const maxDuration = 120;

const FASTAPI = "https://wattson-api.onrender.com";

export async function POST(req: NextRequest) {
  let body: { project_id?: string; floor?: string; base_pdf_base64?: string; base_pdf_path?: string; plan_type?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const projectId = String(body.project_id || "");
  const floor = String(body.floor || "parter");
  let base = String(body.base_pdf_base64 || "");
  const calePdf = String(body.base_pdf_path || "");
  // Poarta era BINARA (`=== "forta" ? "forta" : "iluminat"`), deci orice tip necunoscut devenea
  // tacut planşa de iluminat. Acum lista e explicita: ce nu-i in ea cade tot pe iluminat, dar
  // curenti_slabi trece.
  const PLAN_TYPES = ["iluminat", "forta", "curenti_slabi", "detectie_incendiu"] as const;
  const planType = (PLAN_TYPES as readonly string[]).includes(String(body.plan_type))
    ? String(body.plan_type) : "iluminat";
  // Fundalul curat vine ORI ca base64 (proiecte vechi), ORI ca o cale in Storage (toate cele de
  // azi). Ruta accepta amandoua; fara asta, „Obtine plan" era rupt pe TOATE proiectele.
  if (!projectId || (!base && !calePdf)) {
    return NextResponse.json({ error: "project_id + base_pdf_base64 sau base_pdf_path necesare" }, { status: 400 });
  }

  // ── Ownership: utilizatorul autentificat trebuie sa detina proiectul ──
  let userId = "";
  let supaUser: ReturnType<typeof createServerClient> | null = null;
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
    const { data: proj } = await supa
      .from("projects").select("id").eq("id", projectId).eq("user_id", user.id).single();
    if (!proj) return NextResponse.json({ error: "Proiect inexistent sau neautorizat" }, { status: 403 });
    userId = user.id;
    supaUser = supa;
  } catch {
    return NextResponse.json({ error: "Verificare proprietate esuata" }, { status: 500 });
  }

  // ── Forward la FastAPI ──
  // ── Limita de rata, PE UTILIZATOR (nu pe IP: un birou iese pe aceeasi adresa) ──
  const rl = await masoara(userId, "regenerate-plan");
  if (rl.refuz) return rl.refuz;

  // DUPA verificarea de proprietate si dupa limita: se aduce cu sesiunea utilizatorului, deci
  // politica din Storage decide daca are voie.
  if (!base) {
    const adus = await pdfDinStorage(calePdf);
    if (!adus) {
      await rl.gata(false);
      return NextResponse.json({ error: "Planul original nu s-a putut citi din Storage" }, { status: 403 });
    }
    base = adus;
  }

  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const resp = await fetchBackend(`${FASTAPI}/regenerate-plan`, { project_id: projectId, floor, base_pdf_base64: base, plan_type: planType }, {
      headers: key ? { "x-zynapse-key": key } : {},
      bugetMs: 95000,
    });
    await rl.gata(resp.ok);
    const text = await resp.text();
    try {
      const j = JSON.parse(text) as Record<string, unknown>;

      // ── PLANȘA REGENERATĂ URCĂ ÎN STORAGE, AICI ────────────────────────────────────────────
      // De ce în rută și nu în client: proprietarul e deja verificat mai sus, iar PDF-ul trece
      // oricum pe aici la întoarcere — deci nu se plătește niciun transfer în plus. Clientul
      // primește și base64-ul (îl afișează din memorie, fără nicio cerere) ȘI calea, dar persistă
      // în rând DOAR calea. Fără asta, fiecare „Obține plan" ar scrie iar 1-2 MB în rând, și
      // golirea de dinainte ar fi fost degeaba.
      //
      // Dacă urcarea eșuează, `pdf_path` lipsește și clientul persistă base64-ul ca înainte:
      // se pierde spațiul câștigat, nu planșa.
      const b64 = typeof j.pdf_base64 === "string" ? j.pdf_base64 : "";
      if (resp.ok && b64.length > 100 && userId && supaUser) {
        const s = await urcaPdf(supaUser, userId, projectId,
                               `planse/regen/${planType}-${floor || "parter"}-${Date.now()}.pdf`, b64);
        if (s) j.pdf_path = s;
      }
      return NextResponse.json(j, { status: resp.status });
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
