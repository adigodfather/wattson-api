import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServerClient } from "@/lib/supabase";
import { isPhasePT } from "@/lib/constants";

const N8N_WEBHOOK = "https://www.ai-nord-vest.com/webhook/zynapse-electrical";

// Faza B.1: payload multi-etaj (până la 3 planuri base64) + N PDF-uri în răspuns.
export const runtime = "nodejs";
export const maxDuration = 120;

type Supa = ReturnType<typeof createServerClient>;

// INSERT proiect SERVER-SIDE (oglinda INSERT-ului client vechi). Rulează CA userul (RLS: own).
// input_data = body-ul MINUS cartus/page_format (ca payload-ul client), result_data = răspunsul n8n.
// Întoarce id-ul (uuid) sau null pe eroare (clientul face fallback la INSERT-ul lui).
async function saveProjectServerSide(
  supa: Supa, userId: string, parsed: Record<string, unknown>, data: Record<string, unknown>
): Promise<string | null> {
  const inputData: Record<string, unknown> = { ...parsed };
  delete inputData.cartus_firma;
  delete inputData.cartus_proiect;
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

  // ── POARTĂ DTAC+PT + SOLD-CHECK (server-side, pe MANUAL) — pornim DOAR dacă e permis + acoperit ──
  // Verificarea client (holdCost) e informativă și poate fi sărită apelând ruta direct; aici o IMPUNEM.
  // Debitarea REALĂ (pe desfășurata reală) se face pe SUCCES, mai jos.
  try {
    const { data: prof } = await supa
      .from("profiles").select("is_admin, credits_balance").eq("id", userId).single();
    if (isPhasePT(faza) && prof?.is_admin !== true) {
      return NextResponse.json(
        { error: "DTAC+PT este disponibil momentan doar pentru administratori. Selectează DTAC." },
        { status: 403 }
      );
    }
    const surface = Number(parsed?.surface_mp) || 0;
    const cost = surface > 0 ? Math.ceil(surface * (isPhasePT(faza) ? 3 : 1)) : 0;
    const balance = Number(prof?.credits_balance ?? 0);
    if (cost > 0 && balance < cost) {
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
