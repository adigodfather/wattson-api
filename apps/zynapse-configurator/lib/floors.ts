// AXA DE NIVELURI — deschisă (N niveluri). Oglinda exactă a `floors.py` din backend.
//
// Reconciliază cele 3 codificări care existau în paralel:
//   1) result_data.rooms[].floor   = POZIȚIA planșei (0/1/2...)  + rooms[].plan_type
//   2) plan_elements.floor          = eticheta canonică ("parter"/"etaj"/"mansarda")
//   3) editor (vechi)               = "etaj1"  (≠ "etaj")  ← bug-ul eliminat la M2a
//
// P0: până aici axa era un enum ÎNCHIS de trei. Pe un bloc S+P+2E+E3 retras cele cinci niveluri
// reale cădeau pe două — `s.includes("etaj")` prindea etajele 1, 2 și 3 deopotrivă, iar subsolul
// cădea pe ramura implicită = parter. Nu se pierdea nimic, se AMESTECA: elementele a trei etaje
// ajungeau sub aceeași etichetă `plan_elements.floor`, deci pe aceleași circuite.
//
// TREI noțiuni distincte, ușor de confundat fiindcă toate se scriau cândva "index":
//   eticheta canonică  — IDENTITATEA nivelului ("parter", "etaj", "etaj 2", "subsol"). Ce se scrie
//                        în `plan_elements.floor` și ce compari ca să știi dacă două lucruri sunt
//                        pe același nivel.
//   poziția planșei    — ordinalul 0..N-1 în `planse_iluminat[]` / `planuri[]`. Ce ține editorul în
//                        `editorPlansaIdx` și ce e `rooms[].floor`.
//   indexul vertical   — ordinea fizică pe verticală, cu semn (subsol -1, parter 0, etaj n = n).
//                        Doar pentru sortare.
//
// Pe proiectele existente (parter / etaj / mansardă, în ordinea asta) toate trei coincid numeric —
// de-aia confuzia nu s-a văzut niciodată. Cu un subsol nu mai coincid.
//
// NON-REGRESIE: floorCanonic("parter"|"etaj"|"mansarda") și floorCanonic(0|1|2) dau exact ce dădeau.

/** Eticheta canonică a unui nivel. Axă DESCHISĂ — nu mai e o uniune închisă de trei. */
export type FloorCanonic = string;

/** Nivelurile implicite, în ordinea planșelor. Convenția moștenită: indexul 2 înseamnă mansardă. */
const BY_INDEX: FloorCanonic[] = ["parter", "etaj", "mansarda"];

export const PARTER = "parter";
export const MANSARDA = "mansarda";

const DIACR: Record<string, string> = {
  ă: "a", â: "a", î: "i", ș: "s", ş: "s", ț: "t", ţ: "t",
};

function norm(value: string): string {
  let t = value.trim().toLowerCase();
  t = [...t].map((c) => DIACR[c] ?? c).join("");
  t = t.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  if (t.startsWith("plan ")) t = t.slice(5).trim();
  if (t.endsWith(" retras")) t = t.slice(0, -7).trim();   // un etaj retras e tot etajul lui
  return t;
}

function fromInt(i: number): FloorCanonic {
  if (i === 0) return PARTER;
  if (i === 1) return "etaj";
  if (i === 2) return MANSARDA;              // MOȘTENIT: 2 a însemnat dintotdeauna mansardă
  if (i > 0) return `etaj ${i}`;
  return i === -1 ? "subsol" : `subsol ${-i}`;
}

/**
 * Parsarea propriu-zisă: eticheta canonică, sau `null` dacă șirul NU numește un nivel.
 * Distincția contează: `floorCanonic` întoarce "parter" și pentru un parter real, și pentru gunoi —
 * iar pe un bloc cu subsol parterul nu mai e planșa [0], deci "nerecunoscut" nu mai poate fi tratat
 * ca "parter" fără să strice lista nivelurilor.
 */
function parse(value: string | number | null | undefined): FloorCanonic | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? fromInt(Math.trunc(value)) : null;
  const s = norm(String(value));
  if (!s) return null;
  if (/^-?\d+$/.test(s)) return fromInt(parseInt(s, 10));
  if (s.startsWith("mansard")) return MANSARDA;
  if (s.startsWith("demisol")) return "demisol";
  if (s.startsWith("parter")) return PARTER;
  let m = /^subsol\s*(\d*)$/.exec(s);
  if (m) {
    const n = m[1] ? parseInt(m[1], 10) : 1;
    return n <= 1 ? "subsol" : `subsol ${n}`;
  }
  m = /^etaj\s*(\d*)$/.exec(s) || /^e\s*(\d+)$/.exec(s);   // "etaj2", "E3" (notația din planurile de bloc)
  if (m) {
    const n = m[1] ? parseInt(m[1], 10) : 1;
    return n <= 1 ? "etaj" : `etaj ${n}`;
  }
  return null;
}

/** ORICE codificare de nivel → eticheta canonică. Necunoscut/lipsă → "parter" (ca până acum). */
export function floorCanonic(value: string | number | null | undefined): FloorCanonic {
  return parse(value) ?? PARTER;
}

/** Șirul NUMEȘTE un nivel? Pentru cazurile unde „nerecunoscut" ≠ „parter". */
export function floorKnown(value: string | number | null | undefined): boolean {
  return parse(value) !== null;
}

function numSuffix(canonic: string, fallback: number): number {
  const p = canonic.split(" ");
  return p.length > 1 && /^\d+$/.test(p[1]) ? parseInt(p[1], 10) : fallback;
}

/**
 * Indexul VERTICAL (cu semn): subsol -1, parter 0, etaj n = n, mansardă 2 (moștenit) sau deasupra
 * etajelor când sunt mai multe. Pentru SORTARE și pentru comparații de egalitate între etichete.
 * NU e poziția planșei — vezi `platePos`.
 */
export function floorIndex(
  value: string | number | null | undefined,
  levels?: ReadonlyArray<string | number | null | undefined>,
): number {
  const c = floorCanonic(value);
  if (c === PARTER) return 0;
  if (c === "demisol") return -1;
  if (c === MANSARDA) {
    let top = 0;
    for (const f of levels ?? []) {
      const fc = floorCanonic(f);
      if (fc === "etaj" || fc.startsWith("etaj ")) top = Math.max(top, numSuffix(fc, 1));
    }
    return Math.max(2, top + 1);
  }
  if (c.startsWith("subsol")) return -numSuffix(c, 1);
  return numSuffix(c, 1);
}

/** Eticheta de AFIȘARE: "parter" → "Parter", "etaj 2" → "Etaj 2". */
export function floorLabel(value: string | number | null | undefined): string {
  const c = floorCanonic(value);
  return c.charAt(0).toUpperCase() + c.slice(1);
}

/**
 * Nivelurile proiectului, în ORDINEA PLANȘELOR, din `result_data.planuri[].type`.
 *
 * Sursa e tipul planșei fiindcă el poartă numele REAL al nivelului (o casă P+M dă `plan_mansarda`,
 * nu `plan_etaj`). Tip nerecunoscut → se completează din convenția moștenită pe poziția lui, exact
 * ce făcea editorul înainte — și de-aia cele 10 proiecte cu `plan_generic` din bază rămân neatinse.
 */
export function floorLevels(
  planuri?: ReadonlyArray<{ type?: string | null } | null> | null,
  count?: number,
): FloorCanonic[] {
  const n = Math.max(count ?? 0, planuri?.length ?? 0, 1);
  const out: FloorCanonic[] = [];
  for (let i = 0; i < n; i++) {
    const t = String(planuri?.[i]?.type ?? "").trim();
    // `floorKnown`, nu `floorCanonic`: tipul „plan_generic" (10 proiecte în bază) nu numește niciun
    // nivel, deci cade pe convenția de poziție — exact ce făcea editorul înainte. Iar un
    // „plan_parter" aflat pe poziția 1 (bloc cu subsol dedesubt) rămâne parter, nu devine „etaj".
    out.push(floorKnown(t) ? floorCanonic(t) : (BY_INDEX[i] ?? `etaj ${i}`));
  }
  return out;
}

/** Poziția planșei (0..N-1) pentru un nivel dat în ORICE codificare. -1 dacă nu e în listă. */
export function platePos(
  value: string | number | null | undefined,
  levels: ReadonlyArray<FloorCanonic>,
): number {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "string" && /^\d+$/.test(value.trim())) return parseInt(value.trim(), 10);
  return levels.indexOf(floorCanonic(value));
}

/** Eticheta nivelului de pe planșa `idx`. Fără listă → convenția moștenită (parter/etaj/mansardă). */
export function floorForPlate(idx: number, levels?: ReadonlyArray<FloorCanonic>): FloorCanonic {
  if (levels && idx >= 0 && idx < levels.length) return levels[idx];
  return BY_INDEX[idx] ?? (idx > 0 ? `etaj ${idx}` : PARTER);
}

/**
 * Nivelurile CANONICE ordonate de jos în sus, fără duplicate. Oglinda `floors.sort_floors`.
 * Ordinea e a indexului vertical, nu alfabetică — subsolul vine ÎNAINTEA parterului.
 */
export function sortFloors(values: ReadonlyArray<string | number | null | undefined>): FloorCanonic[] {
  const labels = (values ?? []).map(floorCanonic);
  const seen = new Set<string>();
  const out: Array<[number, number, string]> = [];
  for (const c of labels) {
    if (seen.has(c)) continue;
    seen.add(c);
    // departajare la index egal: subsolul e sub demisol (amândouă stau la -1).
    out.push([floorIndex(c, labels), c.startsWith("subsol") ? 0 : 1, c]);
  }
  out.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return out.map((t) => t[2]);
}
