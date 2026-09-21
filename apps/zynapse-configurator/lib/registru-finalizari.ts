/**
 * Înregistrarea unei finalizări: ce s-a livrat, când, și cu ce amprente.
 *
 * Până acum, după o finalizare rămâneau în urmă doar `projects.finalized = true` și documentele
 * din răspunsul HTTP. Nu se putea spune ce anume a primit clientul. Când s-a găsit regresia
 * cartușului (numărul de proiect lipsă de pe schemele regenerate din P9 încoace), a trebuit dedus
 * din commituri cine primise documente greșite — iar răspunsul a fost o estimare, nu o certitudine.
 *
 * Două principii, amândouă cu preț:
 *   ARHIVAREA NU BLOCHEAZĂ LIVRAREA. Dacă urcarea copiilor în Storage eșuează, rândul se scrie
 *     oricum, cu `arhivat=false` și motivul în clar. Clientul își primește documentele; eșecul
 *     rămâne vizibil în registru, nu înghițit într-un log.
 *   NICI ÎNREGISTRAREA NU BLOCHEAZĂ. Dacă scrierea rândului eșuează, finalizarea merge mai
 *     departe și se loghează. Un registru care poate opri livrarea ar fi mai scump decât lipsa lui.
 */
import { createHash } from "crypto";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { BUCKET } from "@/lib/storage-pdf";

export type Document = { nume: string; tip: string; base64: string };

/** Documentele livrate, culese din răspunsul n8n — fără să știm dinainte toate cheile. */
export function culegeDocumente(raspuns: Record<string, unknown>): Document[] {
  const out: Document[] = [];
  const adauga = (nume: string, b64: unknown, tip: string) => {
    if (typeof b64 === "string" && b64.length > 100) {
      out.push({ nume, tip, base64: b64.includes(",") ? b64.split(",", 2)[1] : b64 });
    }
  };
  // schemele si plansele: liste de obiecte cu pdf_base64
  for (const cheie of ["schemas", "planse_iluminat", "planse_forta", "planuri", "detalii"]) {
    const lista = raspuns[cheie];
    if (!Array.isArray(lista)) continue;
    lista.forEach((el, i) => {
      if (!el || typeof el !== "object") return;
      const o = el as Record<string, unknown>;
      const nume = String(o.filename || o.plansa_nr || o.name || `${cheie}-${i}`);
      adauga(`${cheie}/${nume}.pdf`, o.pdf_base64, "application/pdf");
    });
  }
  // documentele scalare: orice cheie `*_base64` / `*_docx_base64` de la radacina raspunsului
  for (const [k, v] of Object.entries(raspuns)) {
    if (!k.endsWith("_base64") || typeof v !== "string") continue;
    const docx = k.includes("docx");
    adauga(
      k.replace(/_base64$/, "") + (docx ? ".docx" : ".pdf"),
      v,
      docx ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
           : "application/pdf",
    );
  }
  return out;
}

function sha(buf: Buffer): string {
  return createHash("sha256").update(buf).digest("hex");
}

/** Numele de fișier, curățat — Storage refuză segmentele ciudate. */
function curata(nume: string, implicit: string): string {
  const n = nume.replace(/[/\\]+/g, "-").replace(/[^\w.\- ]+/g, "").slice(0, 90);
  return n || implicit;
}

export type Inregistrare = {
  projectId: string;
  userId: string;
  faza?: string | null;
  motiv?: string | null;
  refinalizareA?: string | null;
  declansatDe?: string | null;
};

/**
 * Arhivează documentele și scrie rândul. Întoarce id-ul finalizării, sau null dacă nici rândul
 * n-a putut fi scris (caz în care finalizarea merge mai departe — vezi principiile de sus).
 */
export async function inregistreaza(
  info: Inregistrare, documente: Document[],
): Promise<{ id: string | null; arhivat: boolean; eroare: string | null }> {
  const admin = createAdminClient();
  const id = crypto.randomUUID();
  const radacina = `${info.userId}/${info.projectId}/finalizari/${id}`;

  const meta: Array<Record<string, unknown>> = [];
  let arhivat = true;
  const greseli: string[] = [];

  for (const [i, d] of documente.entries()) {
    const buf = Buffer.from(d.base64, "base64");
    const cale = `${radacina}/${curata(d.nume, String(i))}`;
    // Amprenta se calculeaza INDIFERENT de arhivare: chiar daca nu se poate pastra o copie, se
    // poate spune mai tarziu daca documentul livrat era acelasi lucru cu ce iese azi.
    const rand: Record<string, unknown> = {
      nume: d.nume, tip: d.tip, octeti: buf.length, sha256: sha(buf), cale: null,
    };
    const { error } = await admin.storage.from(BUCKET)
      .upload(cale, buf, { contentType: d.tip, upsert: true });
    if (error) {
      arhivat = false;
      greseli.push(`${d.nume}: ${error.message}`);
    } else {
      rand.cale = cale;
    }
    meta.push(rand);
  }

  // Amprenta SETULUI: sha256 peste amprentele documentelor, in ordinea culegerii. Doua finalizari
  // cu aceeasi amprenta au livrat acelasi lucru; diferite -> se vede EXACT care document difera.
  const amprentaSet = sha(Buffer.from(meta.map((m) => m.sha256).join("\n"), "utf8"));
  const eroare = greseli.length ? greseli.join(" · ").slice(0, 900) : null;

  try {
    const { error } = await admin.from("finalizari").insert({
      id,
      project_id: info.projectId,
      user_id: info.userId,
      faza: info.faza ?? null,
      documente: meta,
      amprenta_set: amprentaSet,
      motiv: info.motiv ?? null,
      refinalizare_a: info.refinalizareA ?? null,
      declansat_de: info.declansatDe ?? null,
      arhivat,
      arhivare_eroare: eroare,
    });
    if (error) {
      console.error("[registru] scrierea randului a esuat (finalizarea continua):", error.message);
      return { id: null, arhivat, eroare };
    }
  } catch (e) {
    console.error("[registru] scrierea randului a aruncat (finalizarea continua):", e);
    return { id: null, arhivat, eroare };
  }
  return { id, arhivat, eroare };
}
