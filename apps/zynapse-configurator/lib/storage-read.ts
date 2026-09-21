/**
 * Citirea unui document care poate sta fie în rând (base64), fie în Storage (cale).
 *
 * Proiectele vechi au base64 în `result_data`; cele noi au o cale în bucketul privat. Până când
 * toate rândurile sunt golite (pasul final al migrării, făcut abia după confirmare), AMÂNDOUĂ
 * formele circulă în același timp — deci fiecare cititor trebuie să le accepte pe amândouă, în
 * ordinea asta: base64 dacă există (e deja în memorie, zero cereri), altfel URL semnat.
 *
 * Un cititor care ar ști doar de una dintre forme ar deschide un proiect GOL, fără să dea eroare.
 */
import { createClient } from "@/lib/supabase";

export const BUCKET = "project-files";

/** Sursă pentru <iframe>/<img>: `data:` din base64, sau URL semnat din Storage. */
export async function sursaPdf(
  base64?: string | null, cale?: string | null, secunde = 3600,
): Promise<string | null> {
  if (base64) return `data:application/pdf;base64,${base64}`;
  if (!cale) return null;
  try {
    const { data } = await createClient().storage.from(BUCKET).createSignedUrl(cale, secunde);
    return data?.signedUrl ?? null;
  } catch (e) {
    console.error("[storage-read] URL semnat esuat pentru %s:", cale, e);
    return null;
  }
}

/** La fel, pentru PNG (previzualizările planșelor). */
export async function sursaPng(
  base64?: string | null, cale?: string | null, secunde = 3600,
): Promise<string | null> {
  if (base64) return `data:image/png;base64,${base64}`;
  if (!cale) return null;
  try {
    const { data } = await createClient().storage.from(BUCKET).createSignedUrl(cale, secunde);
    return data?.signedUrl ?? null;
  } catch (e) {
    console.error("[storage-read] URL semnat PNG esuat pentru %s:", cale, e);
    return null;
  }
}

/**
 * Conținutul brut, ca base64 — pentru cazurile în care un document trebuie TRIMIS mai departe
 * (editorul, regenerarea, finalizarea), nu doar afișat.
 */
export async function base64Pdf(
  base64?: string | null, cale?: string | null,
): Promise<string | null> {
  if (base64) return base64;
  if (!cale) return null;
  try {
    const { data, error } = await createClient().storage.from(BUCKET).download(cale);
    if (error || !data) {
      console.error("[storage-read] download esuat pentru %s:", cale, error?.message);
      return null;
    }
    const buf = new Uint8Array(await data.arrayBuffer());
    let s = "";
    for (let i = 0; i < buf.length; i += 0x8000) {
      s += String.fromCharCode.apply(null, Array.from(buf.subarray(i, i + 0x8000)));
    }
    return btoa(s);
  } catch (e) {
    console.error("[storage-read] citire esuata pentru %s:", cale, e);
    return null;
  }
}

/** Descărcare în browser, din oricare dintre cele două forme. */
export async function descarca(
  base64: string | null | undefined, cale: string | null | undefined, numeFisier: string,
  descarcaB64: (b64: string, nume: string) => void,
): Promise<boolean> {
  if (base64) { descarcaB64(base64, numeFisier); return true; }
  if (!cale) return false;
  try {
    const { data, error } = await createClient().storage
      .from(BUCKET).createSignedUrl(cale, 60, { download: numeFisier });
    if (error || !data?.signedUrl) {
      console.error("[storage-read] URL de descarcare esuat:", error?.message);
      return false;
    }
    const a = document.createElement("a");
    a.href = data.signedUrl;
    a.click();
    return true;
  } catch (e) {
    console.error("[storage-read] descarcare esuata:", e);
    return false;
  }
}
