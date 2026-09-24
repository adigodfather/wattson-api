import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabaseAdmin";
import { ruleazaAbonamente } from "@/lib/facturiServicii";

// FLUXUL ZILNIC: emite facturile de abonament scadente azi.
// Nu e o ruta de admin — o cheama n8n, deci autorizarea e pe `ZYNAPSE_INTERNAL_KEY`, acelasi secret
// server-to-server folosit deja de `/api/extract-geometry` si `/api/finalize`. Fara cheie in mediu,
// ruta REFUZA tot: mai bine nu ruleaza decat sa ruleze neprotejata.
//
// IDEMPOTENTA nu sta aici, ci in BAZA: indexul unic (abonament_id, perioada) respinge a doua
// factura din aceeasi luna, chiar daca fluxul e pornit de doua ori sau se reia dupa o eroare.
// De-aia ruta poate fi chemata linistit de cate ori vrei.
//
// ORA: 9:00 dimineata (decizia lui Dan). Ceasul sta in n8n, nu aici — Schedule Trigger zilnic.
// ATENTIE la fusul din n8n: ziua scadentei se calculeaza pe Europe/Bucharest (`aziRo`), deci DATA
// iese bine oricum, dar „9:00" iese la 12:00 romanesti daca instanta n8n e lasata pe UTC.
// Ziua maxima e 25, deci nu exista luna in care scadenta sa nu pice.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;   // mai multe abonamente, fiecare cu emitere + PDF + email

export async function POST(req: NextRequest) {
  const asteptat = (process.env.ZYNAPSE_INTERNAL_KEY || "").trim();
  if (!asteptat) {
    return NextResponse.json({ error: "ZYNAPSE_INTERNAL_KEY lipsă pe server" }, { status: 503 });
  }
  const primit = (req.headers.get("x-zynapse-key") || "").trim();
  if (primit !== asteptat) return NextResponse.json({ error: "Neautorizat" }, { status: 401 });

  try {
    const r = await ruleazaAbonamente(createAdminClient());
    // Raspunsul e citit de n8n: `esuate > 0` e semnalul pe care se poate pune o alarma, ca un esec
    // sa nu ramana doar in tabel. Fara asta, fluxul ar raporta „succes" si cand n-a emis nimic.
    return NextResponse.json({ ok: r.esuate === 0, ...r });
  } catch (e) {
    return NextResponse.json({ ok: false, error: e instanceof Error ? e.message : "eroare" }, { status: 500 });
  }
}
