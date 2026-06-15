import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

const N8N_WEBHOOK = "https://www.ai-nord-vest.com/webhook/zynapse-electrical";

// Faza B.1: payload multi-etaj (până la 3 planuri base64) + N PDF-uri în răspuns.
export const runtime = "nodejs";
export const maxDuration = 120;

export async function POST(req: NextRequest) {
  const contentType = req.headers.get("content-type") || "";

  // Citim body-ul ca text (configurator trimite JSON) și-l păstrăm pentru forward.
  let rawBody: string;
  try {
    rawBody = await req.text();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to read request body";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  // ── POARTĂ DTAC+PT (server-side): non-admin NU poate genera o fază cu 'PT' ──
  // UI-ul ascunde opțiunea; aici o IMPUNEM (un non-admin ar putea forța faza prin API direct).
  try {
    const parsed = JSON.parse(rawBody);
    const faza = String(parsed?.cartus_proiect?.faza ?? parsed?.faza ?? "");
    if (/PT/i.test(faza)) {
      const cookieStore = await cookies();
      const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
      const { data: { user } } = await supa.auth.getUser();
      let isAdmin = false;
      if (user) {
        const { data: prof } = await supa
          .from("profiles").select("is_admin").eq("id", user.id).single();
        isAdmin = prof?.is_admin === true;
      }
      if (!isAdmin) {
        return NextResponse.json(
          { error: "DTAC+PT este disponibil momentan doar pentru administratori. Selectează DTAC." },
          { status: 403 }
        );
      }
    }
  } catch {
    // body non-JSON / fără fază -> lăsăm să treacă (n8n validează); nu blocăm din parsing
  }

  try {
    const upstream = await fetch(N8N_WEBHOOK, {
      method: "POST",
      headers: { "Content-Type": contentType || "application/json" },
      body: rawBody,
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
