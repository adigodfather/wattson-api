import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { cerAdmin } from "@/lib/adminGuard";

// Acordare Z-coins pentru un raport de bug (dashboard admin, Faza 1.5). Ruleaza CA adminul
// (cookie session) -> functia DB admin_award_bug e SECURITY DEFINER si RE-verifica is_admin,
// apoi ATOMIC: sold + ledger credits_transactions (type bug_reward) + marcaj bug (rezolvat).
export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  // Poarta e cea COMUNA (`cerAdmin`), nu o copie locala: verificarea era identica pana la caracter
  // cu ea, iar o poarta copiata de patru ori e o poarta care intr-o zi va fi copiata gresit.
  const refuz = await cerAdmin();
  if (refuz) return refuz;
  // `supa` ramane necesar dupa poarta: RPC-ul trebuie sa ruleze CA adminul, ca `auth.uid()` din
  // `admin_award_bug` (SECURITY DEFINER care RE-verifica is_admin) sa-l vada.
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });

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
