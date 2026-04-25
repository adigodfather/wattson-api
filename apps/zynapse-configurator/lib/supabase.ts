import { createBrowserClient } from "@supabase/ssr";
import { createServerClient as createSupabaseServerClient, type CookieOptions } from "@supabase/ssr";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export function createClient() {
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}

export function createServerClient(
  cookieStore: {
    get: (name: string) => { value: string } | undefined;
    set: (name: string, value: string, options: CookieOptions) => void;
  }
) {
  return createSupabaseServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      get(name) {
        return cookieStore.get(name)?.value;
      },
      set(name, value, options) {
        cookieStore.set(name, value, options);
      },
      remove(name, options) {
        cookieStore.set(name, "", options);
      },
    },
  });
}
