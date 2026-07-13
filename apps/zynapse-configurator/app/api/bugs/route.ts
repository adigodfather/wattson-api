import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

// Raportare bug din widgetul de chat (Faza 1.5): INSERT in bug_reports (RLS: ruleaza CA userul).
// Adminul le vede in dashboard si acorda Z-coins MANUAL dupa verificare (admin_award_bug).
export const runtime = "nodejs";

const DAILY_LIMIT = 5;          // anti-spam: rapoarte/zi/user
const MIN_CHARS = 10;
const MAX_CHARS = 3000;

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
  const { data: { user } } = await supa.auth.getUser();
  if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });

  let content = "";
  try {
    const body = await req.json();
    content = String(body?.content ?? "").trim();
  } catch {
    return NextResponse.json({ error: "Body invalid" }, { status: 400 });
  }
  if (content.length < MIN_CHARS || content.length > MAX_CHARS) {
    return NextResponse.json(
      { error: `Descrierea trebuie să aibă între ${MIN_CHARS} și ${MAX_CHARS} caractere.` },
      { status: 400 }
    );
  }

  const dayStart = new Date();
  dayStart.setUTCHours(0, 0, 0, 0);
  const { count } = await supa
    .from("bug_reports")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id)
    .gte("created_at", dayStart.toISOString());
  if ((count ?? 0) >= DAILY_LIMIT) {
    return NextResponse.json(
      { error: `Ai trimis deja ${DAILY_LIMIT} rapoarte azi. Revino mâine.` },
      { status: 429 }
    );
  }

  const { error } = await supa.from("bug_reports")
    .insert({ user_id: user.id, content, status: "nou" });
  if (error) {
    console.error("[/api/bugs] insert esuat:", error.message);
    return NextResponse.json({ error: "Salvarea a eșuat. Încearcă din nou." }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
