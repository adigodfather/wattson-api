// M2a — UN singur sistem de etaje pentru editorul de plan.
//
// Reconciliază cele 3 codificări care existau în paralel:
//   1) result_data.rooms[].floor   = index numeric (0/1/2)         + rooms[].plan_type = "parter"/"etaj"/"mansarda"
//   2) plan_elements.floor          = string canonic ("parter"/"etaj"/"mansarda")
//   3) editor (vechi)               = "etaj1"  (≠ "etaj")  ← bug-ul pe care îl eliminăm
//
// CANONIC = "parter" / "etaj" / "mansarda" (cum produce planLabel în vision-rooms + n8n).
// Index: parter=0, etaj=1, mansarda=2 (= ordinea planșelor în planse_iluminat[] = rooms[].floor).
//
// NU schimbăm ce scrie n8n / Vision la sursă — doar normalizăm la citire/scriere în frontend,
// ca tot editorul să folosească UN sistem coerent.

export type FloorCanonic = "parter" | "etaj" | "mansarda";

const BY_INDEX: FloorCanonic[] = ["parter", "etaj", "mansarda"];

/** Normalizează ORICE codificare de etaj la canonic. Necunoscut/lipsă → "parter" (zero regresie single-floor). */
export function floorCanonic(value: string | number | null | undefined): FloorCanonic {
  if (value === null || value === undefined || value === "") return "parter";
  if (typeof value === "number") return BY_INDEX[value] ?? "parter";
  const s = String(value).trim().toLowerCase();
  if (/^\d+$/.test(s)) return BY_INDEX[Number(s)] ?? "parter";   // "0"/"1"/"2" (rooms[].floor)
  if (s.includes("mansard")) return "mansarda";                  // "mansarda", "plan_mansarda"
  if (s.includes("etaj")) return "etaj";                         // "etaj", "etaj1", "plan_etaj"
  return "parter";                                               // "parter", "plan_parter", necunoscut
}

/** Indexul etajului (parter=0, etaj=1, mansarda=2) din orice codificare. Pentru comparații pe index. */
export function floorIndex(value: string | number | null | undefined): number {
  return BY_INDEX.indexOf(floorCanonic(value));
}
