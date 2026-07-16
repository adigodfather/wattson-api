import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { isPhasePT } from "@/lib/constants";

const N8N_WEBHOOK = "https://www.ai-nord-vest.com/webhook/zynapse-electrical";
const FASTAPI = "https://wattson-api.onrender.com";

// FIX BILLING: suprafata CONSTRUITA (amprenta) re-extrasa DETERMINIST din textul vectorial al planurilor
// din payload, SERVER-SIDE (nu ne incredem in client). Determinist -> aceeasi valoare pe care userul o
// vede in modal (din /validate-plan) => display == billing, fara HMAC. source=None (raster/format nou/
// backend down/timeout) -> intoarce null => apelantul cade pe Vision (result_data) si, daca si aia
// lipseste, fail-closed. Zero Anthropic. Dovedit: 6cc18f12 -> 80 (nu 240), ef83000c -> 245.73.
async function extractConstruitaMp(parsed: Record<string, unknown> | null): Promise<number | null> {
  try {
    const key = process.env.ZYNAPSE_INTERNAL_KEY;
    const r = await fetch(`${FASTAPI}/extract-surface`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(key ? { "x-zynapse-key": key } : {}) },
      body: JSON.stringify({
        plan_floors_base64: (parsed?.plan_floors_base64 as unknown[]) ?? [],
        plan_base64: (parsed?.plan_base64 as string) ?? "",
      }),
    });
    if (!r.ok) return null;
    const j = (await r.json()) as { construita_mp?: unknown };
    return typeof j?.construita_mp === "number" && j.construita_mp > 0 ? j.construita_mp : null;
  } catch {
    return null;   // backend down/timeout -> fallback Vision (nu blocam useri pe infra)
  }
}

// Faza B.1: payload multi-etaj (până la 3 planuri base64) + N PDF-uri în răspuns.
export const runtime = "nodejs";
// P+M complet (2 planuri, desen becuri pe Render free) raspunde la ~118s -> pe muchia lui 120
// => Vercel taia functia dupa INSERT dar inainte de consume_credits + plan_elements (proiect orfan).
// 300 acopera P+M cu marja (planul permite: finalize/route.ts foloseste deja 300 in productie).
export const maxDuration = 300;

type Supa = ReturnType<typeof createServerClient>;

// INSERT proiect SERVER-SIDE (oglinda INSERT-ului client vechi). Rulează CA userul (RLS: own).
// input_data = body-ul MINUS cartus_firma/page_format, result_data = răspunsul n8n.
// FIX CARTUS (decizia Dan): `cartus_proiect` (cartușul CONFIRMAT în modal) RĂMÂNE în input_data ca
// AUDIT TRAIL — înainte era șters, deci nu exista nicăieri în DB urma a ce a confirmat userul.
// Întoarce id-ul (uuid) sau null pe eroare (clientul face fallback la INSERT-ul lui).
async function saveProjectServerSide(
  supa: Supa, userId: string, parsed: Record<string, unknown>, data: Record<string, unknown>
): Promise<string | null> {
  const inputData: Record<string, unknown> = { ...parsed };
  delete inputData.cartus_firma;
  delete inputData.page_format;
  const projectNr = String(parsed?.project_id ?? "").trim();
  const row = {
    user_id: userId,
    project_id: projectNr || `AUTO-${Date.now()}`,          // coloana NOT NULL (nr. proiect, text)
    building_type: (parsed?.building_type as string) ?? null,
    levels: (parsed?.levels_string as string) ?? null,
    climate_zone: (data?.climate_zone as string) || "II",
    insulation_level: (parsed?.insulation_level as string) ?? null,
    heating_type: (parsed?.heating_type as string) ?? null,
    status: "completed",
    input_data: inputData,
    result_data: data,
    memoriu_text: (data?.memoriu_tehnic as string) ?? null,
  };
  const { data: inserted, error } = await supa.from("projects").insert(row).select("id").single();
  if (error || !inserted) {
    console.error("[/api/generate] server INSERT projects esuat:", error?.message);
    return null;
  }
  return (inserted as { id: string }).id;
}

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
  // DTAC+PT, sold-check și INSERT-ul server-side. Non-JSON -> null (n8n validează).
  let parsed: Record<string, unknown> | null = null;
  try {
    parsed = JSON.parse(rawBody);
  } catch {
    parsed = null;
  }
  const cartusProiect = (parsed?.cartus_proiect ?? {}) as Record<string, unknown>;
  const faza = String(cartusProiect?.faza ?? parsed?.faza ?? "");

  // ── Sesiune user (o singură dată) — refolosită de sold-check, lock, INSERT, consume ──
  const cookieStore = await cookies();
  const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
  let userId: string;
  try {
    const { data: { user } } = await supa.auth.getUser();
    if (!user) {
      // middleware-ul redirectează deja ne-autentificații; plasă de siguranță pt. apel API direct
      return NextResponse.json({ error: "Neautentificat" }, { status: 401 });
    }
    userId = user.id;
  } catch (err) {
    const message = err instanceof Error ? err.message : "verificare cont eșuată";
    return NextResponse.json({ error: `Verificare cont eșuată: ${message}` }, { status: 500 });
  }

  // suprafata CONSTRUITA determinista (re-extrasa server-side) — calculata O DATA aici, refolosita la SUCCES.
  let construitaMp: number | null = null;
  // ── SOLD-CHECK (server-side, pe greatest(CONSTRUITA determinista, MANUAL)) — pornim DOAR dacă e acoperit ──
  // Verificarea client (holdCost) e informativă și poate fi sărită apelând ruta direct; aici o IMPUNEM.
  // Debitarea REALĂ (pe suprafata reală) se face pe SUCCES, mai jos.
  // LANSARE (Dan, 2026-07-13): poarta "DTAC+PT doar admin" a fost SCOASĂ — faza PT e live pentru
  // toți; costul diferă oricum pe fază (3/mp vs 1/mp) prin isPhasePT, aici și în consume_credits.
  try {
    const { data: prof } = await supa
      .from("profiles").select("is_admin, credits_balance").eq("id", userId).single();
    const surface = Number(parsed?.surface_mp) || 0;
    // FIX billing (P0-1): suprafata declarata TREBUIE sa fie > 0. Fara ea, cost=0 -> poarta trecea
    // SI consume_credits(p_surface_mp<=0) intorcea EARLY "Suprafata invalida" cu 0 debit / fara tranzactie
    // -> generare GRATUITA repetabila. Respinge AICI, INAINTE de lock + forward la n8n (nu se consuma
    // Anthropic Vision degeaba). Debitul real ramane pe greatest(desfasurata Vision, manual) in consume_credits.
    if (!(surface > 0)) {
      return NextResponse.json(
        { error: "Suprafață invalidă: introdu suprafața construită (mp) înainte de generare." },
        { status: 400 }
      );
    }
    // FIX BILLING: re-extrage CONSTRUITA determinista din planuri (server-side) -> baza reala de pret.
    // greatest(construita, declarat): declaratul ramane MINIM (anti-subdeclarare). null (text lipsa/backend
    // down) -> cade pe declarat aici; billing-ul real + fail-closed se decid pe SUCCES (avem si Vision).
    construitaMp = await extractConstruitaMp(parsed);
    const billSurface = Math.max(construitaMp ?? 0, surface);
    const cost = Math.ceil(billSurface * (isPhasePT(faza) ? 3 : 1));
    const balance = Number(prof?.credits_balance ?? 0);
    if (balance < cost) {
      return NextResponse.json(
        { error: `Sold insuficient: ai nevoie de ${cost} Z-Coins, ai ${balance}. Cumpără credite din pagina principală (Acasă).` },
        { status: 402 }
      );
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "verificare sold eșuată";
    return NextResponse.json({ error: `Verificare cont eșuată: ${message}` }, { status: 500 });
  }

  // ── LOCK: 1 generare simultană / user (anti-abuz concurență). Acquire atomic + TTL 5 min. ──
  try {
    const { data: acquired, error: lockErr } = await supa.rpc("acquire_generation_lock");
    if (lockErr) {
      // RPC-ul lock a eșuat -> NU pornim pe orb (am ocoli controlul); userul reîncearcă.
      return NextResponse.json({ error: `Verificare cont eșuată: ${lockErr.message}` }, { status: 500 });
    }
    if (acquired !== true) {
      return NextResponse.json(
        { error: "Ai deja o generare în curs. Așteaptă să se termine înainte de a porni alta." },
        { status: 429 }
      );
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "lock eșuat";
    return NextResponse.json({ error: `Verificare cont eșuată: ${message}` }, { status: 500 });
  }

  // De aici înainte, lock-ul E OBȚINUT -> se eliberează în `finally` pe TOATE căile.
  try {
    const upstream = await fetch(N8N_WEBHOOK, {
      method: "POST",
      headers: {
        "Content-Type": contentType || "application/json",
        ...(process.env.N8N_WEBHOOK_SECRET ? { "x-webhook-secret": process.env.N8N_WEBHOOK_SECRET } : {}),
        // FIX plan_elements (03.07): cheia interna FastAPI curge PRIN webhook -> nodurile Code n8n
        // o citesc din headerele webhook-ului si o trimit la FastAPI ($env nu ajunge in task runner).
        ...(process.env.ZYNAPSE_INTERNAL_KEY ? { "x-zynapse-key": process.env.ZYNAPSE_INTERNAL_KEY } : {}),
      },
      body: rawBody,
    });

    // Citim ca text mai întâi, ca să nu crăpăm pe HTML (ex. pagină 504 de la reverse-proxy n8n)
    const text = await upstream.text();
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(text);
    } catch {
      console.error("[/api/generate] Backend returned non-JSON:", text.slice(0, 500));
      return NextResponse.json({
        error: "Backend timeout sau eroare de procesare",
        details: `HTTP ${upstream.status} — răspuns non-JSON (probabil timeout reverse-proxy n8n)`,
        preview: text.slice(0, 200),
        recommendation: "Încearcă cu mai puține planuri sau contactează administratorul",
      }, { status: 502 });   // finally eliberează lock-ul
    }

    // n8n eroare HTTP sau {status:"error"} -> propagă; NU salvăm/debităm (finally eliberează lock).
    if (!upstream.ok) {
      return NextResponse.json(data, { status: upstream.status });
    }
    if (data?.status === "error") {
      return NextResponse.json(data, { status: 200 });
    }

    // ── FIX BILLING: injecteaza CONSTRUITA determinista in surfaces.construita_mp INAINTE de save+consume.
    // Migrarea consume_credits (pasul FINAL) o citeste: greatest(coalesce(construita_mp, desfasurata_mp), declarat).
    // FAIL-CLOSED: nicio suprafata detectata (nici textul plansei, nici Vision) DAR plan procesat (rooms) ->
    // NU salvam / NU debitam pe declarat-only (gaura de facturare exploatabila). ──
    {
      const pinfo = ((data.project_info && typeof data.project_info === "object")
        ? data.project_info : {}) as Record<string, unknown>;
      const surfaces = ((pinfo.surfaces && typeof pinfo.surfaces === "object")
        ? pinfo.surfaces : {}) as Record<string, unknown>;
      const visionConstr = typeof surfaces.construita_mp === "number" ? (surfaces.construita_mp as number) : null;
      const visionDesf = typeof surfaces.desfasurata_mp === "number" ? (surfaces.desfasurata_mp as number) : null;
      if (construitaMp != null) {
        surfaces.construita_mp = construitaMp;        // sursa DETERMINISTA (text vectorial) — autoritara la billing
        surfaces.surface_source = "text_vectorial";
        pinfo.surfaces = surfaces;
        data.project_info = pinfo;
      }
      const roomsArr = data.rooms as unknown[] | undefined;
      const hasRooms = Array.isArray(roomsArr) && roomsArr.length > 0;
      const anySurface = construitaMp != null || visionConstr != null || visionDesf != null;
      if (!anySurface && hasRooms) {
        return NextResponse.json({
          error: "Suprafața nu a putut fi detectată din plan (nici din textul planșei, nici din analiză). " +
                 "Reîncarcă exportul PDF vectorial din CAD (cu bilanțul de suprafețe vizibil) sau reîncearcă.",
        }, { status: 422 });   // finally eliberează lock; NU salvăm, NU debităm pe declarat-only
      }
    }

    // ── FIX CARTUS: cartușul CONFIRMAT în modal devine SURSA UNICĂ de adevăr în result_data.project_info,
    // INAINTE de save. De ce aici: schemele se REGENEREAZĂ la finalizare, iar n8n-finalize reconstruiește
    // cartușul din result_data.project_info (până acum = Vision BRUT) -> numărul de proiect + șeful de
    // proiect editate de user se pierdeau (planșele mergeau: ele-s ștampilate în n8n MAIN din
    // wb.cartus_proiect și NU se regenerează). Un singur loc, ZERO n8n, ZERO backend (precedentul billing).
    // MAPARE OBLIGATORIE (nume divergente): numar_proiect->proiect_nr, data_proiect->data.
    // MERGE, nu overwrite: câmpurile care NU vin din modal (plansa_nr, surfaces, ...) rămân din Vision.
    // Fallback: fără cartus_proiect în payload (sau câmp gol) -> se păstrează Vision (nu crapă). ──
    {
      const CARTUS_MAP: Array<[string, string]> = [
        ["numar_proiect", "proiect_nr"],     // nume divergente (modal -> project_info)
        ["data_proiect", "data"],            // nume divergente
        ["sef_proiect", "sef_proiect"],
        ["titlu_proiect", "titlu_proiect"],
        ["beneficiar", "beneficiar"],
        ["amplasament", "amplasament"],
        ["faza", "faza"],
      ];
      const pinfo = ((data.project_info && typeof data.project_info === "object")
        ? data.project_info : {}) as Record<string, unknown>;
      let merged = 0;
      for (const [src, dst] of CARTUS_MAP) {
        const v = cartusProiect[src];
        if (typeof v === "string" && v.trim()) { pinfo[dst] = v.trim(); merged++; }
      }
      if (merged > 0) data.project_info = pinfo;   // 0 câmpuri confirmate -> project_info neatins (Vision)
    }

    // ── SUCCES: persistă + debitează SERVER-SIDE (nu depinde de client). ──
    // INSERT proiect -> consume_credits (pe desfășurata REALĂ din răspuns) -> increment.
    // Semnalul pt. client = `saved_project_id`: prezent -> clientul NU mai inserează (foloseste id-ul asta,
    // reface DOAR consume idempotent ca plasă de siguranță). Absent (INSERT server eșuat) -> clientul face
    // calea VECHE completă (insert+consume+increment) -> degradare grațioasă, fără proiect pierdut.
    try {
      const projectId = await saveProjectServerSide(supa, userId, parsed || {}, data);
      if (projectId) {
        // debitare pe desfășurata reală (consume_credits: idempotent pe project_id + drain-to-zero)
        try {
          const surface = Number(parsed?.surface_mp) || 0;
          const { data: creditsRes } = await supa.rpc("consume_credits", {
            p_surface_mp: surface, p_phase: faza, p_project_id: projectId,
          });
          (data as Record<string, unknown>).credits_result = creditsRes ?? null;
        } catch (e) {
          console.error("[/api/generate] consume_credits esuat:", e);
        }
        try {
          await supa.rpc("increment_projects_used");   // NEidempotent -> server o face O SINGURĂ dată
        } catch (e) {
          console.error("[/api/generate] increment_projects_used esuat:", e);
        }

        // ── ETAPA 1 Storage (Problema 5): memoriul .docx -> bucket privat, referință în DB. ──
        // DUPĂ consume/increment (fluxul de credite NEATINS). Upload cu sesiunea userului (RLS
        // pf_owner_insert: path <uid>/...). Ordinea anti-pierdere: INSERT-ul a salvat DEJA base64;
        // abia după UPLOAD reușit facem UPDATE cu path în loc de base64. Orice eșec (upload SAU
        // update) -> base64 rămâne în DB și în răspuns (fallback, proiectul/memoriul nu se pierd).
        try {
          const memB64 = typeof data.memoriu_docx_base64 === "string" ? (data.memoriu_docx_base64 as string) : "";
          if (memB64.length > 100) {
            const storagePath = `${userId}/${projectId}/memoriu.docx`;
            const rawB64 = memB64.includes(",") ? memB64.split(",", 2)[1] : memB64;
            const { error: upErr } = await supa.storage
              .from("project-files")
              .upload(storagePath, Buffer.from(rawB64, "base64"), {
                contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                upsert: true,
              });
            if (upErr) {
              console.error("[/api/generate] upload memoriu in Storage esuat (fallback base64):", upErr.message);
            } else {
              const updated: Record<string, unknown> = { ...data, memoriu_docx_path: storagePath };
              delete updated.memoriu_docx_base64;
              const { error: updErr } = await supa
                .from("projects").update({ result_data: updated }).eq("id", projectId);
              if (updErr) {
                // DB a rămas cu base64 -> răspunsul trebuie să rămână consistent (tot base64)
                console.error("[/api/generate] update referinta memoriu esuat (fallback base64):", updErr.message);
              } else {
                delete (data as Record<string, unknown>).memoriu_docx_base64;
                (data as Record<string, unknown>).memoriu_docx_path = storagePath;
              }
            }
          }
        } catch (e) {
          console.error("[/api/generate] bloc Storage memoriu esuat (fallback base64):", e);
        }

        // ── ETAPA 2 Storage: schema monofilară (scalar) -> bucket + ELIMINARE DUPLICAT. ──
        // result_data avea schema de 2 ori: schema_monofilara_pdf + schema_monofilara_pdf_base64
        // (identice; ~874 kB dublati). _pdf_base64 NU e citit nicaieri -> se STERGE mereu (duplicat
        // mort), chiar daca upload-ul esueaza. schema_monofilara_pdf -> Storage + path; fallback
        // base64 daca upload esueaza. Afisajul principal (schemas[] per tablou) NEATINS in etapa asta.
        try {
          const schB64 = typeof data.schema_monofilara_pdf === "string" ? (data.schema_monofilara_pdf as string) : "";
          if (schB64.length > 100) {
            const schPath = `${userId}/${projectId}/schema_monofilara.pdf`;
            const rawSch = schB64.includes(",") ? schB64.split(",", 2)[1] : schB64;
            const { error: schUpErr } = await supa.storage
              .from("project-files")
              .upload(schPath, Buffer.from(rawSch, "base64"), { contentType: "application/pdf", upsert: true });
            const updated: Record<string, unknown> = { ...data };
            delete updated.schema_monofilara_pdf_base64;          // duplicatul mort — sters MEREU
            if (!schUpErr) {
              updated.schema_monofilara_path = schPath;
              delete updated.schema_monofilara_pdf;               // originalul e in Storage
            } else {
              console.error("[/api/generate] upload schema in Storage esuat (fallback base64):", schUpErr.message);
            }
            const { error: schUpdErr } = await supa
              .from("projects").update({ result_data: updated }).eq("id", projectId);
            if (schUpdErr) {
              console.error("[/api/generate] update referinta schema esuat (fallback base64):", schUpdErr.message);
            } else {
              // raspunsul catre client = starea din DB
              delete (data as Record<string, unknown>).schema_monofilara_pdf_base64;
              if (!schUpErr) {
                delete (data as Record<string, unknown>).schema_monofilara_pdf;
                (data as Record<string, unknown>).schema_monofilara_path = schPath;
              }
            }
          }
        } catch (e) {
          console.error("[/api/generate] bloc Storage schema esuat (fallback base64):", e);
        }

        // ── ETAPA 3 Storage: schemas[] (o schema PER TABLOU) -> bucket, path PER ELEMENT. ──
        // Bucla CLASICA cu index (nu .entries()/destructurare). Fallback PER ELEMENT: un upload
        // esuat -> acel element ramane pe base64, restul merg pe Storage. Un singur UPDATE la final;
        // raspunsul catre client se muta pe noile elemente DOAR dupa UPDATE reusit (consistenta DB).
        try {
          const schemasArr = Array.isArray(data.schemas) ? (data.schemas as Record<string, unknown>[]) : [];
          if (schemasArr.length > 0) {
            let anyMoved = false;
            const newSchemas: Record<string, unknown>[] = [];
            for (let i = 0; i < schemasArr.length; i++) {
              const el: Record<string, unknown> = { ...(schemasArr[i] || {}) };
              const elB64 = typeof el.pdf_base64 === "string" ? (el.pdf_base64 as string) : "";
              if (elB64.length > 100) {
                const elPath = `${userId}/${projectId}/schema_tablou_${i}.pdf`;
                const rawEl = elB64.includes(",") ? elB64.split(",", 2)[1] : elB64;
                const { error: elUpErr } = await supa.storage
                  .from("project-files")
                  .upload(elPath, Buffer.from(rawEl, "base64"), { contentType: "application/pdf", upsert: true });
                if (!elUpErr) {
                  el.pdf_path = elPath;
                  delete el.pdf_base64;
                  anyMoved = true;
                } else {
                  console.error(`[/api/generate] upload schemas[${i}] esuat (fallback base64):`, elUpErr.message);
                }
              }
              newSchemas.push(el);
            }
            if (anyMoved) {
              const updated: Record<string, unknown> = { ...data, schemas: newSchemas };
              const { error: updErr } = await supa
                .from("projects").update({ result_data: updated }).eq("id", projectId);
              if (updErr) {
                console.error("[/api/generate] update schemas[] esuat (fallback base64):", updErr.message);
              } else {
                (data as Record<string, unknown>).schemas = newSchemas;
              }
            }
          }
        } catch (e) {
          console.error("[/api/generate] bloc Storage schemas[] esuat (fallback base64):", e);
        }

        (data as Record<string, unknown>).saved_project_id = projectId;
      }
      // proiectId null -> NU setăm saved_project_id -> clientul face fallback (insert+consume+increment)
    } catch (e) {
      console.error("[/api/generate] bloc salvare server esuat:", e);
      // fără saved_project_id -> client fallback
    }

    return NextResponse.json(data, { status: 200 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  } finally {
    // ELIBERARE LOCK pe TOATE căile (succes, 502, throw). TTL 5 min = plasă dacă ruta moare complet.
    try {
      await supa.rpc("release_generation_lock");
    } catch (e) {
      console.error("[/api/generate] release_generation_lock esuat (TTL va curăța):", e);
    }
  }
}
