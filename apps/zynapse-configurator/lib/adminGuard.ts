// ─── Poarta de admin, intr-un singur loc ────────────────────────────────────
// Acelasi tipar ca la `award-bug` si `invoice-resend`: sesiunea din cookie + `is_admin` re-verificat
// pe server. Scrisa o data si refolosita, ca sa nu existe o ruta care verifica altfel decat
// celelalte — o poarta copiata de cinci ori e o poarta care intr-o zi va fi copiata gresit.

import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { createServerClient } from "./supabase";

export async function cerAdmin(): Promise<NextResponse | null> {
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
  const { data: { user } } = await supa.auth.getUser();
  if (!user) return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
  const { data: prof } = await supa.from("profiles").select("is_admin").eq("id", user.id).single();
  if (prof?.is_admin !== true) return NextResponse.json({ error: "Doar admin" }, { status: 403 });
  return null;   // null = trecut
}
