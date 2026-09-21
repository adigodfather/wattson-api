/**
 * Apel către FastAPI cu reîncercare pe „ocupat", nu cu eroare în față.
 *
 * De la etapa 1, backendul lasă o singură operație grea odată: două încărcări simultane de planuri
 * se adunau în memorie și omorau instanța de 512 MB pentru TOȚI. Cererea a doua primește acum
 * 503 + `Retry-After` — corect pentru server, dar pentru client înseamnă „a eșuat", deși n-a
 * eșuat nimic: doar trebuia așteptat. Inventariat înainte de a scrie asta: NICIUNUL dintre cei
 * opt apelanți (rutele Vercel) și nici nodul n8n de adnotare nu reîncercau.
 *
 * Reîncercarea respectă `Retry-After` și se oprește după `maxIncercari`, ca să nu țină o rută
 * Vercel ocupată peste bugetul ei (60 s pentru validare/geometrie/randare, 120 s pentru
 * regenerare). Se reîncearcă DOAR 503 — un 413 „plan prea complex" e un răspuns definitiv, nu o
 * coadă, iar reîncercarea lui ar irosi timpul degeaba.
 */

const IMPLICIT_MAX = 3;
const IMPLICIT_ASTEPTARE_MS = 5000;
const PLAFON_ASTEPTARE_MS = 15000;

export type BackendOpts = {
  /** Câte încercări în total (prima + reîncercări). Implicit 3. */
  maxIncercari?: number;
  /** Bugetul total al rutei; reîncercarea se oprește dacă l-ar depăși. */
  bugetMs?: number;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

/** Cât așteptăm înainte de reîncercare: ce spune serverul, plafonat. */
function asteptare(resp: Response): number {
  const h = resp.headers.get("Retry-After");
  const s = h ? Number(h) : NaN;
  const ms = Number.isFinite(s) && s > 0 ? s * 1000 : IMPLICIT_ASTEPTARE_MS;
  return Math.min(ms, PLAFON_ASTEPTARE_MS);
}

export async function fetchBackend(
  url: string,
  body: unknown,
  opts: BackendOpts = {},
): Promise<Response> {
  const max = Math.max(1, opts.maxIncercari ?? IMPLICIT_MAX);
  const buget = opts.bugetMs ?? 45000;
  const pornit = Date.now();
  let ultim: Response | null = null;

  for (let i = 0; i < max; i++) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      body: JSON.stringify(body),
      signal: opts.signal,
    });
    if (resp.status !== 503) return resp;

    ultim = resp;
    const pauza = asteptare(resp);
    // Dacă pauza ne-ar scoate din bugetul rutei, mai bine întoarcem 503 acum: un client care
    // primește răspunsul are ce face cu el, unul care expiră nu are.
    if (i === max - 1 || Date.now() - pornit + pauza > buget) break;
    await new Promise((r) => setTimeout(r, pauza));
  }
  return ultim as Response;
}
