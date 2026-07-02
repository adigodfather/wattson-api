import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { isPhasePT } from "@/lib/constants";

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

  // Body parsat O SINGURĂ DATĂ (poate fi multi-MB cu planuri base64) — refolosit de poarta
  // DTAC+PT și de sold-check. Non-JSON -> null (n8n validează; nu blocăm din parsing).
  let parsed: Record<string, unknown> | null = null;
  try {
    parsed = JSON.parse(rawBody);
  } catch {
    parsed = null;
  }
  const cartusProiect = (parsed?.cartus_proiect ?? {}) as Record<string, unknown>;
  const faza = String(cartusProiect?.faza ?? parsed?.faza ?? "");

  // ── POARTĂ DTAC+PT (server-side): non-admin NU poate genera o fază cu 'PT' ──
  // UI-ul ascunde opțiunea; aici o IMPUNEM (un non-admin ar putea forța faza prin API direct).
  // ── SOLD-CHECK (server-side): generarea pornește DOAR dacă soldul acoperă costul ──
  // Verificarea client-side (holdCost din configurator) e informativă și poate fi sărită
  // apelând ruta direct; aici o IMPUNEM. Debitarea reală rămâne consume_credits (idempotentă,
  // DUPĂ generare) — aici doar VERIFICĂM, nu debităm.
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    if (!user) {
      // middleware-ul redirectează deja ne-autentificații; plasă de siguranță pt. apel API direct
      return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
    }
    const { data: prof } = await supa
      .from("profiles").select("is_admin, credits_balance").eq("id", user.id).single();

    if (isPhasePT(faza) && prof?.is_admin !== true) {
      return NextResponse.json(
        { error: "DTAC+PT este disponibil momentan doar pentru administratori. Selectează DTAC." },
        { status: 403 }
      );
    }

    // formula IDENTICĂ cu genCostZ (client, CREDIT_PRICING {dtac:1, pt:2} -> 1 Z/mp DTAC, 3 Z/mp PT)
    // și cu consume_credits (DB: 3 else 1). Suprafața = cea manuală (ca la holdCost);
    // consume_credits facturează oricum pe max(real, manual) la final.
    const surface = Number(parsed?.surface_mp) || 0;
    const cost = surface > 0 ? Math.ceil(surface * (isPhasePT(faza) ? 3 : 1)) : 0;
    const balance = Number(prof?.credits_balance ?? 0);
    if (cost > 0 && balance < cost) {
      return NextResponse.json(
        { error: `Sold insuficient: ai nevoie de ${cost} Z-Coins, ai ${balance}. Cumpără credite din pagina principală (Acasă).` },
        { status: 402 }
      );
    }
  } catch (err) {
    // eroare NEAȘTEPTATĂ la verificare (ex. Supabase indisponibil) -> nu pornim generarea
    // pe orb (ar ocoli și poarta PT și soldul); clientul afișează eroarea și userul reîncearcă.
    const message = err instanceof Error ? err.message : "verificare sold eșuată";
    return NextResponse.json({ error: `Verificare cont eșuată: ${message}` }, { status: 500 });
  }

  try {
    const upstream = await fetch(N8N_WEBHOOK, {
      method: "POST",
      headers: {
        "Content-Type": contentType || "application/json",
        // FAZA 3A: secretul webhook-ului (n8n îl ignoră până activăm Header Auth pe nod — FAZA 3B).
        // Nesetat în env -> nu trimitem nimic (stare identică cu azi).
        ...(process.env.N8N_WEBHOOK_SECRET ? { "x-webhook-secret": process.env.N8N_WEBHOOK_SECRET } : {}),
      },
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
