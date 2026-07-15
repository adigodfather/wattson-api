// Gruparea BOM pe cele 8 sectiuni functionale (restructurare BOM, bucata 3 — DOAR afisare).
// Datele vin cu campul `sectiune` (bom.py bucata 1+2: TEG / TES n / TE-CT / ILUMINAT / FORTA /
// PRIZA DE PAMANT - LOCUINTA / SISTEM FOTOVOLTAIC / PRIZA DE PAMANT - FOTOVOLTAIC).
// Proiecte VECHI (finalizate inainte de restructurare) NU au `sectiune` -> hasSections=false ->
// suprafata cade pe afisarea PLATA de dinainte (non-regresie, zero randuri pierdute).

export type BomRow = Record<string, unknown>;

// Ordinea FIXA a sectiunilor dupa TES (TEG=0, TES n=1, apoi acestea).
const FIXED_AFTER_TES = [
  "TE-CT",
  "ILUMINAT",
  "FORTA",
  "PRIZA DE PAMANT - LOCUINTA",
  "SISTEM FOTOVOLTAIC",
  "PRIZA DE PAMANT - FOTOVOLTAIC",
];

function isTes(sec: string): boolean {
  return /^TES(\s|\d|$)/.test(sec);
}

// Rang de sortare: [grup, sub-index]. TEG intai, apoi TES 1/2/... (dupa numar), apoi lista fixa,
// apoi necunoscut/"Diverse" la coada.
export function sectionRank(sec: string): [number, number] {
  if (sec === "TEG") return [0, 0];
  if (isTes(sec)) return [1, parseInt(sec.replace(/\D/g, ""), 10) || 0];
  const i = FIXED_AFTER_TES.indexOf(sec);
  if (i >= 0) return [2 + i, 0];
  return [999, 0];
}

// Eticheta afisata (cu diacritice) pentru cheia ASCII a sectiunii.
export function sectionLabel(sec: string): string {
  switch (sec) {
    case "TEG": return "Tablou general (TEG)";
    case "TE-CT": return "Tablou TE-CT (cameră tehnică)";
    case "ILUMINAT": return "Iluminat";
    case "FORTA": return "Forță";
    case "PRIZA DE PAMANT - LOCUINTA": return "Priză de pământ — locuință";
    case "SISTEM FOTOVOLTAIC": return "Sistem fotovoltaic";
    case "PRIZA DE PAMANT - FOTOVOLTAIC": return "Priză de pământ — fotovoltaic";
    case "Diverse": return "Diverse";
    default: return isTes(sec) ? `Tablou secundar (${sec})` : sec;
  }
}

export function hasSections(bom: readonly BomRow[] | null | undefined): boolean {
  return (bom || []).some((r) => r && r.sectiune != null && String(r.sectiune) !== "");
}

// Grupeaza randurile pe `sectiune`, in ordinea de mai sus. Sectiunile GOALE nu apar (nu se creeaza
// intrare fara randuri). Randurile fara `sectiune` -> "Diverse" (la coada; nu ar trebui sa existe).
export function groupBomBySection(
  bom: readonly BomRow[] | null | undefined,
): Array<{ key: string; label: string; rows: BomRow[] }> {
  const map = new Map<string, BomRow[]>();
  for (const r of bom || []) {
    const k = r && r.sectiune != null && String(r.sectiune) !== "" ? String(r.sectiune) : "Diverse";
    const arr = map.get(k);
    if (arr) arr.push(r);
    else map.set(k, [r]);
  }
  return [...map.entries()]
    .sort((a, b) => {
      const ra = sectionRank(a[0]);
      const rb = sectionRank(b[0]);
      return ra[0] - rb[0] || ra[1] - rb[1] || a[0].localeCompare(b[0]);
    })
    .map(([key, rows]) => ({ key, label: sectionLabel(key), rows }));
}
