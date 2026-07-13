import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";

// Acordare Z-coins pentru un raport de bug (dashboard admin, Faza 1.5). Ruleaza CA adminul
// (cookie session) -> functia DB admin_award_bug e SECURITY DEFINER si RE-verifica is_admin,
// apoi ATOMIC: sold + ledger credits_transactions (type bug_reward) + marcaj bug (rezolvat).
export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
  const { data: { user } } = await supa.auth.getUser();
  if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
  const { data: prof } = await supa.from("profiles").select("is_admin").eq("id", user.id).single();
  if (prof?.is_admin !== true) return NextResponse.json({ error: "Doar admin" }, { status: 403 });

  let bugId = "", amount = 0;
  try {
    const body = await req.json();
    bugId = String(body?.bug_id ?? "");
    amount = Math.floor(Number(body?.amount ?? 0));
  } catch {
    return NextResponse.json({ error: "Body invalid" }, { status: 400 });
  }
  if (!bugId || !(amount > 0)) {
    return NextResponse.json({ error: "bug_id + suma pozitivă necesare" }, { status: 400 });
  }

  const { data, error } = await supa.rpc("admin_award_bug", { p_bug_id: bugId, p_amount: amount });
  if (error) {
    console.error("[/api/admin/award-bug] rpc esuat:", error.message);
    return NextResponse.json({ error: error.message }, { status: 400 });
  }
  return NextResponse.json(data ?? { ok: true });
}
