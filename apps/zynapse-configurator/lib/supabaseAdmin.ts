// Client Supabase cu service role — DOAR server-side (rute API de plată).
// Ocolește RLS pentru scrieri în payments + apel RPC de creditare.
// NU importa niciodată din cod client; cheia e secretă.
import { createClient } from "@supabase/supabase-js";

export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error(
      "[supabaseAdmin] NEXT_PUBLIC_SUPABASE_URL sau SUPABASE_SERVICE_ROLE_KEY lipsește. " +
      "Seteaz-o în Vercel + .env.local."
    );
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
