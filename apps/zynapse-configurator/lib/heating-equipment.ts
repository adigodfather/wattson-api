// T3 — ECHIPAMENTELE DE INCALZIRE auto-plasabile (functii PURE: fara React/Konva/DB).
//
// heatingEquipmentFromCircuits(circuits) -> lista echipamentelor de incalzire din CIRCUITELE REALE
// (result_data.circuits): type="dedicat" + cheie de echipament de incalzire. NU depinde de panel —
// merge identic pe has_tech_room bifat (TE-CT) si nebifat (redirectate pe TEG).
// AC / cuptor / EV / HRV / internet / receptoare libere = EXCLUSE (chei separate).
//
// Cheile = ECHIVALENTUL TS al _equip_key din enrich_circuits.py (substring specific -> generic,
// pe text normalizat fara diacritice). TINE-LE SINCRON: dedup-ul de la finalize leaga elementul
// auto-plasat de circuitul lui prin ACEEASI cheie — un label care mapeaza diferit aici vs Python
// ar crea circuit duplicat.

export type DedicatCircuit = { type?: string | null; description?: string | null; usage?: string | null };
export type HeatingEquipment = { label: string; key: string; mountHeight: number };

// aceeasi ordine specific -> generic ca _EQUIP_KEYS (enrich_circuits.py)
const EQUIP_KEYS: [string, string][] = [
  ["boiler", "boiler"], ["cuptor", "cuptor"],
  ["pdc", "pdc"], ["pompa de caldura", "pdc"], ["pompa caldura", "pdc"], ["aer-apa", "pdc"],
  ["sol-apa", "pdc"], ["pompa circulatie", "pompa"], ["pompa recirculare", "pompa"],
  ["automatizare", "bms"], ["bms", "bms"],
  ["centrala", "centrala"],
  ["distribuitor de zona", "distribuitor_zona"], ["distribuitor zona", "distribuitor_zona"],
  ["distribuitor de nivel", "distribuitor_zona"], ["distribuitor nivel", "distribuitor_zona"],
  ["distribuitor", "distribuitor"],
  ["recuperare", "hrv"], ["hrv", "hrv"], ["aer conditionat", "ac"], ["conditionat", "ac"],
  ["internet", "internet"], ["retea", "internet"],
  ["incarcare", "ev"], ["statie incarcare", "ev"], ["masina electrica", "ev"], ["ev_charger", "ev"],
];

// inaltimile de montaj PER TIP (decizia Dan) — DOAR cheile de aici sunt "echipamente de incalzire"
const HEATING_HEIGHTS: Record<string, number> = {
  boiler: 1.5, pdc: 0.3, pompa: 0.5, bms: 1.5, distribuitor: 0.5, distribuitor_zona: 0.5, centrala: 1.5,
};

function normalize(s: string | null | undefined): string {
  return (s || "").trim().toLowerCase()
    .replace(/ă/g, "a").replace(/â/g, "a").replace(/î/g, "i").replace(/ș/g, "s").replace(/ț/g, "t");
}

export function equipKey(label: string | null | undefined): string | null {
  const t = normalize(label);
  for (const [kw, k] of EQUIP_KEYS) {
    if (t.includes(kw)) return k;
  }
  return null;
}

// Clasificare TECH (camera tehnica) vs EXTRA pentru RANDAREA rubricilor din editorul de forta: un label e
// "tech" daca cheia lui de echipament e o cheie de INCALZIRE (in HEATING_HEIGHTS) — boiler/pdc/pompa/bms/
// distribuitor/centrala. Radiator/VCV au equipKey=null -> se clasifica separat in FE prin heatingReceptorDef
// (HEATING_RECEPTOR_TYPES). PURA: doar clasificare de afisare, fara efect pe circuite/enrich/handler-e.
export function isTechReceptorLabel(label: string | null | undefined): boolean {
  const k = equipKey(label);
  return !!k && k in HEATING_HEIGHTS;
}

export function heatingEquipmentFromCircuits(circuits: DedicatCircuit[] | null | undefined): HeatingEquipment[] {
  const out: HeatingEquipment[] = [];
  const seen = new Set<string>();
  for (const c of circuits || []) {
    if (!c || c.type !== "dedicat") continue;               // doar dedicate (nu prize/iluminat/sub_tablou)
    const label = (c.description || c.usage || "").toString().trim();
    if (!label || seen.has(label)) continue;                // dedup pe label (2 pompe = 2 labels diferite)
    const key = equipKey(label);
    if (!key || !(key in HEATING_HEIGHTS)) continue;        // doar echipamente de INCALZIRE
    seen.add(label);
    out.push({ label, key, mountHeight: HEATING_HEIGHTS[key] });
  }
  return out;
}
