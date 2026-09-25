// ─── Un PDF din Storage, adus SERVER-SIDE, ca base64 ────────────────────────
// Scris o data si refolosit de cele trei rute care au nevoie de fundalul curat
// (render-base-png, extract-geometry, regenerate-plan). Pana acum codul asta exista intr-un singur
// loc, iar celelalte doua rute nu stiau deloc de cai — de-aia „Obtine plan" s-a rupt pe TOATE
// proiectele dupa ce blob-urile au trecut in Storage: cititorul fusese migrat pe jumatate.
//
// Se descarca CU SESIUNEA utilizatorului, nu cu service role: politica `pf_owner_select` din
// Storage decide daca are voie, deci calea nu e o portita spre fisierele altuia. Backendul de pe
// Render primeste tot base64 — el n-are credentiale Supabase.

import { cookies } from "next/headers";
import { createServerClient } from "./supabase";
import { BUCKET } from "./storage-pdf";

export async function pdfDinStorage(cale: string): Promise<string | null> {
  try {
    const cookieStore = await cookies();
    const supa = createServerClient({ get: (n) => cookieStore.get(n), set: () => {} });
    const { data, error } = await supa.storage.from(BUCKET).download(cale);
    if (error || !data) return null;
    return Buffer.from(await data.arrayBuffer()).toString("base64");
  } catch {
    return null;
  }
}
