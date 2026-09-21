/**
 * Mutarea blob-urilor din rândurile bazei în Storage, cu referință în locul lor.
 *
 * DE CE. Tabelul `projects` ocupă 195 MB din cei 209 ai bazei, fiindcă PDF-urile stau ca base64
 * în `input_data` / `result_data`. La 23 de proiecte. Planul free dă 500 MB, deci mai încap vreo
 * 30-40 de proiecte, iar traficul lunar e alimentat de aceleași blob-uri, descărcate întregi la
 * fiecare deschidere de proiect — chiar și când te uiți la o singură planșă.
 *
 * Etapele 1-3 au mutat deja memoriul, schema monofilară și schemele per tablou; tiparul de acolo
 * e generalizat aici, ca următoarele chei să nu-l mai rescrie de fiecare dată.
 *
 * REGULA DE SIGURANȚĂ, moștenită din etapele anterioare și păstrată: base64-ul se șterge DOAR
 * după ce upload-ul a reușit. Orice eșec lasă base64-ul pe loc, iar cititorii îl preferă când
 * există — deci un upload picat înseamnă „nu s-a câștigat spațiu", niciodată „s-a pierdut un
 * document". Cititorii acceptă amândouă formele; vezi `rezolvaPdf` în lib/storage-read.ts.
 */
import type { SupabaseClient } from "@supabase/supabase-js";
import { createHash } from "crypto";

export const BUCKET = "project-files";

/** Curăță prefixul „data:...;base64," dacă există. */
export function bruta(b64: string): string {
  return b64.includes(",") ? b64.split(",", 2)[1] : b64;
}

export function amprenta(b64: string): string {
  return createHash("sha256").update(Buffer.from(bruta(b64), "base64")).digest("hex");
}

/** Numele de fișier, curățat: Storage refuză calea cu segmente ciudate. */
function curata(nume: string, implicit: string): string {
  const n = (nume || "").trim().replace(/[/\\]+/g, "-").replace(/[^\w.\- ]+/g, "").slice(0, 80);
  return n || implicit;
}

type Rezultat = { urcate: number; esuate: number; octeti: number };

async function urca(
  supa: SupabaseClient, cale: string, b64: string, contentType: string,
): Promise<boolean> {
  const { error } = await supa.storage
    .from(BUCKET)
    .upload(cale, Buffer.from(bruta(b64), "base64"), { contentType, upsert: true });
  if (error) {
    console.error("[storage-pdf] upload esuat pentru %s: %s", cale, error.message);
    return false;
  }
  return true;
}

/**
 * Mută blob-urile dintr-o listă de obiecte (`planse_iluminat`, `planse_forta`, `planuri`).
 * Fiecare element primește `<camp>_path` în locul lui `<camp>`; elementele fără blob rămân
 * neatinse. Obiectul primit NU e modificat — se întoarce o listă nouă.
 */
export async function mutaLista(
  supa: SupabaseClient, userId: string, projectId: string,
  lista: unknown, dosar: string,
  campuri: Array<{ camp: string; ext: string; tip: string }>,
): Promise<{ lista: unknown; rez: Rezultat }> {
  const rez: Rezultat = { urcate: 0, esuate: 0, octeti: 0 };
  if (!Array.isArray(lista)) return { lista, rez };
  const iesire = await Promise.all(lista.map(async (el, i) => {
    if (!el || typeof el !== "object") return el;
    const o = { ...(el as Record<string, unknown>) };
    for (const { camp, ext, tip } of campuri) {
      const b64 = typeof o[camp] === "string" ? (o[camp] as string) : "";
      if (b64.length <= 100) continue;
      const baza = curata(String(o.filename || o.name || ""), `${i}`).replace(/\.[^.]+$/, "");
      const cale = `${userId}/${projectId}/${dosar}/${i}-${baza}.${ext}`;
      if (await urca(supa, cale, b64, tip)) {
        o[`${camp}_path`] = cale;
        o[`${camp}_sha256`] = amprenta(b64);
        delete o[camp];
        rez.urcate++;
        rez.octeti += Math.floor((bruta(b64).length * 3) / 4);
      } else {
        rez.esuate++;                       // base64 ramane pe loc: cititorii il gasesc
      }
    }
    return o;
  }));
  return { lista: iesire, rez };
}

/**
 * Mută un blob scalar (`annotated_plan_base64`, `plan_base64`). Întoarce obiectul-părinte
 * modificat, cu `<campPath>` în locul lui `<camp>`.
 */
export async function mutaScalar(
  supa: SupabaseClient, userId: string, projectId: string,
  parinte: Record<string, unknown>, camp: string, campPath: string,
  numeFisier: string, tip = "application/pdf",
): Promise<{ parinte: Record<string, unknown>; rez: Rezultat }> {
  const rez: Rezultat = { urcate: 0, esuate: 0, octeti: 0 };
  const b64 = typeof parinte[camp] === "string" ? (parinte[camp] as string) : "";
  if (b64.length <= 100) return { parinte, rez };
  const o = { ...parinte };
  const cale = `${userId}/${projectId}/${numeFisier}`;
  if (await urca(supa, cale, b64, tip)) {
    o[campPath] = cale;
    o[`${campPath}_sha256`] = amprenta(b64);
    delete o[camp];
    rez.urcate++;
    rez.octeti += Math.floor((bruta(b64).length * 3) / 4);
  } else {
    rez.esuate++;
  }
  return { parinte: o, rez };
}

/**
 * Planurile ÎNCĂRCATE de client (`input_data.plan_floors_base64` = listă de obiecte cu `base64`,
 * `input_data.plan_base64` = scalar). Sunt INTRAREA proiectului, nu un livrabil: se păstrează
 * fiindcă editorul și regenerarea pornesc de la ele.
 */
export async function mutaIntrari(
  supa: SupabaseClient, userId: string, projectId: string, input: Record<string, unknown>,
): Promise<{ input: Record<string, unknown>; rez: Rezultat }> {
  let o = { ...input };
  const tot: Rezultat = { urcate: 0, esuate: 0, octeti: 0 };
  const aduna = (r: Rezultat) => { tot.urcate += r.urcate; tot.esuate += r.esuate; tot.octeti += r.octeti; };

  const l = await mutaLista(supa, userId, projectId, o.plan_floors_base64, "intrare",
                            [{ camp: "base64", ext: "pdf", tip: "application/pdf" }]);
  if (Array.isArray(o.plan_floors_base64)) o.plan_floors_base64 = l.lista;
  aduna(l.rez);

  const s = await mutaScalar(supa, userId, projectId, o, "plan_base64", "plan_path",
                             "intrare/plan.pdf");
  o = s.parinte;
  aduna(s.rez);
  return { input: o, rez: tot };
}

export function rezumat(r: Rezultat): string {
  return `${r.urcate} urcate (${(r.octeti / 1048576).toFixed(1)} MB)` +
         (r.esuate ? `, ${r.esuate} ESUATE — base64 ramane pe loc` : "");
}
