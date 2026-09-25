// ─── Limite de rata pe rutele care consuma procesare reala ──────────────────
// Scrisa O DATA si refolosita, ca poarta de admin: o limita copiata in sase rute e o limita care
// intr-o zi va fi copiata gresit.
//
// LA CE FOLOSESTE, DE FAPT (decizia lui Dan, si ea schimba pragurile):
// asta NU e o aparare impotriva unui atacator — pe aia o face deja poarta de sold din
// `/api/generate`, care refuza cu 402 inainte de orice procesare: cine vrea sa consume serios
// trebuie sa plateasca, adica sa se poarte ca un client. Limita de aici e o PLASA LA ACCIDENTE:
// o bucla infinita in interfata, un script care o ia razna, un `useEffect` care se re-declanseaza
// singur. Pragul se pune acolo unde comportamentul e clar ANORMAL, nu acolo unde incepe sa fie
// intens — altfel pedepseste omul care lucreaza, nu accidentul.
//
// PE UTILIZATOR, nu pe adresa IP: un birou cu cinci ingineri iese pe aceeasi adresa si s-ar bloca
// singur. Identitatea vine din sesiunea deja verificata de ruta.
//
// CONTORUL STA IN POSTGRES, nu in memorie: rutele sunt functii serverless pe Vercel, fara memorie
// intre invocari si posibil in instante paralele. Un contor in memorie s-ar reseta la fiecare
// pornire la rece si n-ar fi vazut de celelalte instante — adica n-ar limita nimic.

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "./supabase";
import { createAdminClient } from "./supabaseAdmin";

// ── PRAGURILE, PE RUTA, din masuratoarea pe un bloc de 5 niveluri ───────────────────────────────
// Reperul: un proiect de bloc face ~90 de apeluri in total, iar pragul trebuie sa lase CATEVA
// proiecte pe ora, nu unul singur. In dreapta: cate proiecte de bloc incap sub prag.
const PRAG: Record<string, number> = {
  // AUTOMATE — pornesc singure la fiecare schimbare de mod sau de nivel (`useEffect` cu
  // `mode`/`floor` in dependente). Cele mai dese, si cele care dau grosul cifrei pe proiect.
  "extract-geometry": 300,      // ~50/bloc -> ~6 proiecte pe ora
  "render-base-png": 200,       // ~25/bloc -> ~8 proiecte pe ora

  // CERUTE DE OM.
  "regenerate-plan": 200,       // 15/bloc (3 moduri x 5 niveluri) -> ~13 proiecte pe ora
  "validate-plan": 200,         // max 3 pe generare (incarcarea e plafonata la 3 fisiere)
  "apartamente-copiaza": 200,   // cateva pe proiect, si doar la blocuri

  // SINGURA pe care poarta de sold NU o acopera: ruleaza la incarcare, INAINTE de orice debitare,
  // si fiecare apel costa un Claude Vision. Un accident aici arde bani fara sa atinga vreun credit,
  // deci aici plasa se tine mai sus decat in rest. 1 apel per incercare de generare, deci 100
  // inseamna ~100 de incercari intr-o ora: imposibil de atins cu mana, dar destul de jos cat sa
  // opreasca repede o bucla.
  "vision-cartus": 100,
};
const PRAG_IMPLICIT = 200;

const FEREASTRA_MS = 60 * 60 * 1000;   // o ora
const ESECURI_LA_RAND = 3;
const PAUZA_MS = 60 * 1000;            // un minut: rupe o bucla de reincercari, nu pedepseste un om

export interface Masurator {
  /** 429 gata de intors, daca cererea nu are voie sa treaca. */
  refuz?: NextResponse;
  /** Se cheama DUPA lucru, cu verdictul. Fara ea, cererea ramane „pornita, fara verdict". */
  gata: (succes: boolean) => Promise<void>;
}

function raspuns429(mesaj: string, secunde: number): NextResponse {
  return NextResponse.json(
    { error: mesaj, reincearca_peste_secunde: secunde },
    { status: 429, headers: { "Retry-After": String(secunde) } },
  );
}

/**
 * Verifica limitele si INREGISTREAZA cererea. Intoarce `refuz` daca trebuie oprita.
 *
 * Randul se scrie la INCEPUT, nu la final: altfel zece cereri pornite simultan n-ar fi numarate
 * decat dupa ce se termina, iar limita ar fi ocolita exact de cazul pentru care exista — o bucla
 * care trimite in paralel.
 */
export async function masoara(userId: string, ruta: string): Promise<Masurator> {
  const admin = createAdminClient();
  const acum = Date.now();
  const nimic = async () => {};
  const prag = PRAG[ruta] ?? PRAG_IMPLICIT;

  try {
    // ── [1] Pauza dupa esecuri, PE RUTA ──────────────────────────────────────────────────────
    // Pe ruta, nu global: un PDF prost care pica la validare n-are de ce sa blocheze editorul.
    // Se uita doar la randurile CU VERDICT — cele „pornite" inca n-au ce spune.
    const { data: ultimele } = await admin
      .from("rate_events")
      .select("succes, created_at")
      .eq("user_id", userId).eq("ruta", ruta).not("succes", "is", null)
      .order("created_at", { ascending: false }).limit(ESECURI_LA_RAND);
    const cuVerdict = (ultimele || []) as Array<{ succes: boolean; created_at: string }>;
    if (cuVerdict.length === ESECURI_LA_RAND && cuVerdict.every(r => r.succes === false)) {
      // Un SUCCES reseteaza de la sine: daca ar fi existat unul mai nou, n-ar mai fi toate false.
      const ultimEsec = new Date(cuVerdict[0].created_at).getTime();
      const ramas = Math.ceil((ultimEsec + PAUZA_MS - acum) / 1000);
      if (ramas > 0) {
        return {
          refuz: raspuns429(
            "Ultimele trei încercări au eșuat, așa că am pus o pauză scurtă. " +
            "Verifică fișierul (PDF cu text vectorial, nu scanare) și reîncearcă peste un minut.",
            ramas),
          gata: nimic,
        };
      }
    }

    // ── [2] Limita pe ora, PE RUTA ───────────────────────────────────────────────────────────
    const deLa = new Date(acum - FEREASTRA_MS).toISOString();
    const { count, data: vechi } = await admin
      .from("rate_events")
      .select("created_at", { count: "exact" })
      .eq("user_id", userId).eq("ruta", ruta).gte("created_at", deLa)
      .order("created_at", { ascending: true }).limit(1);
    const folosite = count ?? 0;
    if (folosite >= prag) {
      // Se elibereaza cand cea mai VECHE cerere din fereastra iese din ea.
      const ceaMaiVeche = (vechi as Array<{ created_at: string }> | null)?.[0]?.created_at;
      const liber = ceaMaiVeche ? new Date(ceaMaiVeche).getTime() + FEREASTRA_MS : acum + FEREASTRA_MS;
      const secunde = Math.max(30, Math.ceil((liber - acum) / 1000));
      const minute = Math.max(1, Math.round(secunde / 60));
      return {
        refuz: raspuns429(
          `Ai trimis ${folosite} cereri de procesare în ultima oră, iar limita e ${prag}. ` +
          `Poți relua peste aproximativ ${minute} ${minute === 1 ? "minut" : "minute"}. ` +
          "Limita e o plasă de siguranță pentru cazul în care ceva se repetă singur — " +
          "nu e nimic în neregulă cu contul tău.",
          secunde),
        gata: nimic,
      };
    }

    // ── [3] Trece: inregistram cererea si intoarcem cum se inchide ───────────────────────────
    const { data: rand } = await admin
      .from("rate_events").insert({ user_id: userId, ruta }).select("id").single();
    const id = (rand as { id: number } | null)?.id;
    return {
      gata: async (succes: boolean) => {
        if (!id) return;
        try { await admin.from("rate_events").update({ succes }).eq("id", id); } catch { /* non-blocant */ }
      },
    };
  } catch (e) {
    // FAIL-OPEN, dinadins: daca baza nu raspunde, limitarea nu are voie sa opreasca productia.
    // Ea apara un buget, nu date — iar o garda care pica inchis ar transforma o indisponibilitate
    // de contor intr-o indisponibilitate de platforma.
    console.error("[rateLimit] contorul n-a raspuns, cererea trece:", e instanceof Error ? e.message : e);
    return { gata: nimic };
  }
}

/** Id-ul utilizatorului din sesiunea pe cookie, sau null. Sta aici fiindca trei dintre rutele
 *  limitate nu citeau sesiunea deloc — se bazau doar pe middleware — iar o limita PE UTILIZATOR
 *  are nevoie de identitate in ruta. E si a doua incuietoare la aceeasi usa. */
export async function idUtilizator(): Promise<string | null> {
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data: { user } } = await supa.auth.getUser();
    return user?.id ?? null;
  } catch {
    return null;
  }
}
