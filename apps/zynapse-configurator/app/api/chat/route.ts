import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { CHAT_SYSTEM_PROMPT } from "@/lib/chat-prompt";

// Chat AI V1 (Faza 1): auth + rate limit + persistenta AICI (repo); orchestrarea LLM = Faza 2
// (workflow n8n NOU, separat de productie). Pattern-ul de securitate = /api/generate:
// FE -> ruta asta (sesiune Supabase, ruleaza CA userul -> RLS ownership pe chat_messages)
// -> webhook n8n cu x-webhook-secret. Fara webhook configurat -> raspuns stub (chat in configurare).
export const runtime = "nodejs";
export const maxDuration = 60;

const DAILY_LIMIT = Number(process.env.CHAT_DAILY_LIMIT || 25);   // mesaje user/zi (decizia Dan: 20-30)
const HISTORY_MAX = 10;          // cate mesaje din istoric acceptam de la client (stateless)
const MSG_MAX_CHARS = 2000;      // gard pe lungimea unui mesaj (cost LLM)

type ChatMsg = { role: "user" | "assistant"; content: string };

export async function POST(req: NextRequest) {
  // ── sesiunea userului (doar logati) ──
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
  const { data: { user } } = await supa.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
  }

  // ── body: { message, history? } ──
  let message = "";
  let history: ChatMsg[] = [];
  try {
    const body = await req.json();
    message = String(body?.message ?? "").trim();
    if (Array.isArray(body?.history)) {
      history = (body.history as ChatMsg[])
        .filter(m => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
        .slice(-HISTORY_MAX)
        .map(m => ({ role: m.role, content: m.content.slice(0, MSG_MAX_CHARS) }));
    }
  } catch {
    return NextResponse.json({ error: "Body invalid" }, { status: 400 });
  }
  if (!message) return NextResponse.json({ error: "Mesaj gol" }, { status: 400 });
  if (message.length > MSG_MAX_CHARS) {
    return NextResponse.json({ error: `Mesajul e prea lung (max ${MSG_MAX_CHARS} caractere).` }, { status: 400 });
  }

  // ── Faza 2 neconfigurata -> stub (fara salvare, fara consum de limita) ──
  const webhook = process.env.N8N_CHAT_WEBHOOK_URL || "";
  if (!webhook) {
    return NextResponse.json({
      reply: "Chatul e în configurare — revino curând. Între timp, întrebările despre platformă au răspunsuri în paginile de ajutor.",
      configured: false,
    });
  }

  // ── rate limit: mesajele user de AZI (UTC) din chat_messages ──
  const dayStart = new Date();
  dayStart.setUTCHours(0, 0, 0, 0);
  const { count, error: cntErr } = await supa
    .from("chat_messages")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id)
    .eq("role", "user")
    .gte("created_at", dayStart.toISOString());
  if (cntErr) {
    console.error("[/api/chat] count esuat:", cntErr.message);
    return NextResponse.json({ error: "Eroare internă. Încearcă din nou." }, { status: 500 });
  }
  if ((count ?? 0) >= DAILY_LIMIT) {
    return NextResponse.json(
      { error: `Ai atins limita de ${DAILY_LIMIT} mesaje pe zi. Revino mâine.` },
      { status: 429 }
    );
  }

  // ── salveaza mesajul userului (RLS: ruleaza ca userul) ──
  const { error: insErr } = await supa.from("chat_messages")
    .insert({ user_id: user.id, role: "user", content: message });
  if (insErr) console.error("[/api/chat] insert user esuat:", insErr.message);

  // ── forward la workflow-ul n8n de chat (Faza 2). Contractul raspunsului: { reply: string } ──
  let reply = "";
  try {
    const res = await fetch(webhook, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.N8N_WEBHOOK_SECRET ? { "x-webhook-secret": process.env.N8N_WEBHOOK_SECRET } : {}),
      },
      body: JSON.stringify({
        system: CHAT_SYSTEM_PROMPT,
        message,
        history,                    // stateless: clientul trimite ultimele N mesaje
        user_id: user.id,           // pt. log/debug in n8n (fara alte date personale)
      }),
    });
    if (!res.ok) throw new Error(`n8n ${res.status}`);
    const data = await res.json();
    reply = String(data?.reply ?? "").trim();
    if (!reply) throw new Error("raspuns gol");
  } catch (e) {
    console.error("[/api/chat] webhook esuat:", e instanceof Error ? e.message : e);
    return NextResponse.json(
      { error: "Asistentul nu a putut răspunde. Încearcă din nou în câteva momente." },
      { status: 502 }
    );
  }

  // ── salveaza raspunsul (sub acelasi user_id — RLS ownership) + intoarce ──
  const { error: insErr2 } = await supa.from("chat_messages")
    .insert({ user_id: user.id, role: "assistant", content: reply });
  if (insErr2) console.error("[/api/chat] insert assistant esuat:", insErr2.message);

  return NextResponse.json({ reply, remaining: DAILY_LIMIT - (count ?? 0) - 1 });
}
