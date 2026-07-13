// ─── 3 user-facing building categories (PAS 1) ───────────────────────────────

export const BUILDING_CATEGORIES_3 = [
  { value: "rezidential", label: "Rezidențial", icon: "🏠", desc: "Case, duplexuri, blocuri, hoteluri" },
  { value: "public",      label: "Public",      icon: "🏛️", desc: "Școli, spitale, cămine culturale" },
  { value: "industrial",  label: "Industrial",  icon: "🏭", desc: "Hale, depozite, ateliere" },
] as const;

// ─── Subtypes per category (PAS 2) ───────────────────────────────────────────

// `soon: true` = sub-tip vizibil dar NE-selectabil (badge "Curând") — fluxul generic genereaza,
// dar fara logica dedicata (apartamente multiple / coloane de bloc / spatii comune) nu-i lansabil.
export const BUILDING_SUBTYPES: Record<string, { value: string; label: string; soon?: boolean }[]> = {
  rezidential: [
    { value: "casa_unifamiliala",    label: "Casă unifamilială" },
    { value: "duplex",               label: "Duplex / Vilă" },
    { value: "bloc_locuinte",        label: "Bloc de locuințe",         soon: true },
    { value: "spatiu_comercial_bloc",label: "Spațiu comercial în bloc", soon: true },
    { value: "hotel_pensiune",       label: "Hotel / Pensiune",         soon: true },
  ],
  public: [
    { value: "camin_cultural",  label: "Cămin cultural / Sală eveniment" },
    { value: "scoala",          label: "Școală / Grădiniță" },
    { value: "spital",          label: "Spital / Clinică" },
    { value: "institutie",      label: "Instituție / Primărie" },
    { value: "biserica",        label: "Biserică" },
    { value: "sala_sport",      label: "Sală sport" },
  ],
  industrial: [
    { value: "hala_productie",      label: "Hală producție" },
    { value: "depozit",             label: "Depozit / Logistică" },
    { value: "atelier",             label: "Atelier / Service" },
    { value: "ferma",               label: "Fermă" },
    { value: "statie_tehnologica",  label: "Stație tehnologică" },
  ],
};

// ─── Faza proiect (Epic 3.11) — pentru moment DOAR DTAC e activă ───────────────

export const FAZA_PROIECT_OPTIONS = [
  { value: "DTAC",     label: "DTAC",      enabled: true },
  { value: "DTAC+PT",  label: "DTAC + PT", enabled: true },
  { value: "PT",       label: "PT",        enabled: false, tooltip: "Disponibil curând (lansare Q2 2026)" },
] as const;

// Detecție robustă a fazei PT, indiferent de format ("DTAC+PT", "D.T.A.C. + P.T.", "PT", "P.T.").
// Normalizează (lowercase + scoate tot ce nu e literă) apoi caută "pt".
// ACEEAȘI regulă ca în funcția DB consume_credits (sursă unică de logică pe frontend).
// Mapare: dtac->1/mp; orice conține "pt" (dtacpt / pt) -> 3/mp. ("dtac" NU conține "pt".)
export function isPhasePT(faza: string | null | undefined): boolean {
  return (faza || "").toLowerCase().replace(/[^a-z]/g, "").includes("pt");
}

// Admin gate: user_id-ul inginerului (Dan). Uneltele de debug (ex. overlay "pereti" din editor) sunt
// vizibile DOAR lui in productie, dar codul lor ramane functional (nu-l stergem).
export const ADMIN_USER_ID = "1ff11302-b070-43b2-95bc-9f880388e87b";

// ─── Insulation ───────────────────────────────────────────────────────────────

export const INSULATION = [
  { value: "slaba",       label: "Slabă  (> 70 W/m²)" },
  { value: "medie",       label: "Medie  (~60 W/m²)" },
  { value: "buna",        label: "Bună  (~50 W/m²)" },
  { value: "foarte_buna", label: "Foarte bună  (< 40 W/m²)" },
];

// ─── Heating generation (TIP GENERARE CĂLDURĂ) ───────────────────────────────

export const HEATING_GENERATION = [
  { value: "pdc_air_water",    label: "Pompă de căldură aer-apă" },
  { value: "pdc_ground_water", label: "Pompă de căldură sol-apă (geotermală)" },
  { value: "gas_boiler",       label: "Centrală pe gaz" },
  { value: "electric_boiler",  label: "Centrală electrică" },
  { value: "district_heating", label: "Termoficare (rețea urbană)" },
  { value: "existing",         label: "Sistem existent (fără modificări)" },
];

// Faza 2 TE-CT: default-ul checkbox-ului "am camera tehnica" PER SURSA (decizia Dan):
// BIFAT pe sursele care produc TE-CT natural (PDC aer/sol + centrala electrica);
// NEBIFAT pe gaz/termoficare/existing (echipamentele merg pe TEG, in alta incapere).
export function defaultTechRoom(heatingType: string | null | undefined): boolean {
  return ["pdc_air_water", "pdc_ground_water", "electric_boiler"].includes((heatingType || "").trim());
}

// ─── Heating distribution (TIP DISTRIBUȚIE CĂLDURĂ) ─────────────────────────

export const HEATING_DISTRIBUTION = [
  { value: "floor_heating",     label: "Încălzire în pardoseală" },
  { value: "fan_coil",          label: "Ventiloconvector" },
  { value: "electric_radiator", label: "Radiator electric" },
  { value: "radiant_ceiling",   label: "Tavan radiant" },
  { value: "existing",          label: "Sistem existent" },
];

// ─── Extra equipment presets ──────────────────────────────────────────────────

export interface ExtraEquipment {
  type: string;
  name: string;
  power_kw: number;
  phase: string;   // "mono" | "tri" | "none"
  phases?: number; // 1 | 3 — derivat din `phase` pentru backend (auto-select PDC / cuptor)
  room?: string;   // încăperea unde se montează (doar pt. echipamente custom)
  package_kw?: number; // FV: pachetul discret (5/10/15/20) — sursa schemei FV (power_kw rămâne = pachet, compat n8n)
  soil_type?: string;  // FV: tipul de sol (priza de pământ dedicată) — chei din FV_SOIL_OPTIONS, default "agricol"
}

// FV se livrează în PACHETE fixe (schema monofilară FV = șablon per pachet) — fără putere liberă.
export const FV_PACKAGE_OPTIONS = [5, 10, 15, 20] as const;

// G-UI: tipurile de sol pentru priza de pământ FV (dropdown pe cardul FV, conform studiului geo).
// CHEILE IDENTICE cu FV_GROUNDING_TARUSI din schema_fv.py — ține-le SINCRON (o cheie diferită
// cade silențios pe default-ul agricol în backend). Etichete simple (rezistivitatea = în breviar).
export const FV_SOIL_OPTIONS = [
  { key: "mlastinos",   label: "Mlăștinos" },
  { key: "argila",      label: "Argilă umedă" },
  { key: "agricol",     label: "Agricol" },        // DEFAULT (100 Ω·m, = fallback-ul backend)
  { key: "nisip_umed",  label: "Nisip umed" },
  { key: "nisip_uscat", label: "Nisip uscat" },
  { key: "pietris",     label: "Pietriș" },
] as const;
export const FV_SOIL_DEFAULT = "agricol";

// Backward-compat: proiecte vechi cu power_kw liber (ex. 10.3) -> pachetul cel mai apropiat
// (egalitate -> în sus). OGLINDA lui snap_fv_package din schema_fv.py — ține-le sincron.
export function snapFvPackage(powerKw: number | null | undefined): number {
  const p = Number(powerKw);
  if (!Number.isFinite(p) || p <= 0) return 5;
  return [...FV_PACKAGE_OPTIONS].sort((a, b) => (Math.abs(a - p) - Math.abs(b - p)) || (b - a))[0];
}

export const EXTRA_EQUIPMENT_DEFAULTS: {
  type: string; label: string; icon: string; default_kw: number; default_phase: string; panel_target?: string;
  fvPackage?: boolean;   // FV: cardul se randează cu selector de pachete (5/10/15/20), fără mono/tri
}[] = [
  { type: "boiler",          label: "Boiler ACM",                             icon: "🛁", default_kw: 2,   default_phase: "mono" },
  { type: "cuptor_electric", label: "Cuptor electric",                        icon: "🍳", default_kw: 2,   default_phase: "mono", panel_target: "TEG" },
  { type: "ac",         label: "Aer condiționat",                        icon: "❄️", default_kw: 2.5, default_phase: "mono" },
  { type: "hrv",        label: "Ventilație cu recuperare căldură (HRV)", icon: "🌀", default_kw: 0.2, default_phase: "mono" },
  { type: "internet",   label: "Rețea date / Internet (prize RJ45)",     icon: "🌐", default_kw: 0,   default_phase: "none" },
  // FV: MEREU trifazat + pachete discrete (nu putere liberă) — cardul are selector 5/10/15/20 kW.
  { type: "solar",      label: "Panouri fotovoltaice",                   icon: "☀️", default_kw: 5,   default_phase: "tri", fvPackage: true },
  { type: "ev_charger", label: "Stație încărcare mașină electrică",      icon: "🚗", default_kw: 7.4, default_phase: "mono" },
];

// ─── Regula 10: receptoare termice plasabile pe PLAN (mod forță) ──────────────
// element_type = "alimentare_receptor" (FĂRĂ tip nou / migrație); diferențiate prin LABEL.
// Label-ul EXACT contează: "Distribuitor zona" declanșează _is_zone_distributor în backend
// (draw_elements) → TEG/TES + circuit dedicat, NU TE-CT / NU se contopește cu cel principal.
// VCV + radiatoarele se GRUPEAZĂ (compute_circuits, plafon 2 kW, mono/tri separate); distribuitorul
// de zonă = dedicat 1:1. default_w/default_phase se scriu pe plan_elements la plasare (fallback în
// backend dacă null: radiator 1500W, VCV 100W, distribuitor 300W).
export const HEATING_RECEPTOR_TYPES: {
  label: string; default_w: number; default_phase: "mono" | "tri"; default_height: number;
  editablePower: boolean; editablePhase: boolean;
  visibleFor: string[];   // H5: valorile EXACTE de heating_distribution la care butonul apare in paleta
}[] = [
  { label: "Radiator electric", default_w: 1500, default_phase: "mono", default_height: 0.3, editablePower: true, editablePhase: true,  visibleFor: ["electric_radiator"] },
  { label: "VCV",               default_w: 100,  default_phase: "mono", default_height: 2.2, editablePower: true, editablePhase: true,  visibleFor: ["fan_coil"] },
  { label: "Distribuitor zona", default_w: 300,  default_phase: "mono", default_height: 0.5, editablePower: true, editablePhase: false, visibleFor: ["floor_heating", "radiant_ceiling", "fan_coil"] },
];

// H5: butoanele termice apar STRICT dupa emisia aleasa in formular (heating_distribution). Helper PUR.
// floor_heating + radiant_ceiling -> Distribuitor zona (aceleasi bucle/actuatoare/distribuitor de zona) ;
// fan_coil -> VCV + Distribuitor zona ; electric_radiator -> Radiator electric.
// Orice altceva (existing / "radiatoare pe apa" / gol / necunoscut) -> [] (ascunse complet, nu propunem
// echipamente gresite cand sistemul nu e cunoscut). Fara override, fara "adauga oricum".
export function visibleHeatingReceptors(heatingDistribution: string | null | undefined) {
  const d = (heatingDistribution || "").trim();
  if (!d) return [];
  return HEATING_RECEPTOR_TYPES.filter(t => t.visibleFor.includes(d));
}

// ─── H6: receptoare NON-termice din paleta, gate-uite pe formular ─────────────
// Boilerul apare cu SAU-logic: din SISTEMUL de incalzire (heating_type care implica boiler ACM: PDC /
// centrala cu boiler) SAU din bifa "Boiler ACM" din formularul de echipamente (equipment.boiler.enabled).
// Restul (AC/cuptor/HRV/EV/internet) = din echipamentele BIFATE (equipment[type].enabled -> extra_equipment).
// Fotovoltaicele EXCLUSE (Dan separat). Gating pe TIP; cantitatea e libera (plasezi cate unitati vrei).
// heating_type care implica boiler ACM: PDC aer-apa / sol-apa + centrala gaz / electrica (nu termoficare/existing).
export const BOILER_HEATING_TYPES = ["pdc_air_water", "pdc_ground_water", "gas_boiler", "electric_boiler"];

export type EquipmentReceptorButton = {
  et: "alimentare_receptor" | "receptor_internet";
  label: string;      // label PERSISTAT pe plan_elements (declanseaza logica backend) + textul din lista
  btnText: string;    // textul butonului: "+ Alimentare {btnText}" (internet = "+ Retea internet")
  // equipment: vizibil daca equipType e bifat. heatingType (boiler): vizibil daca heating_type implica
  // boiler ACM SAU equipType ("boiler") e bifat (SAU-logic).
  gate: { kind: "equipment"; equipType: string } | { kind: "heatingType"; equipType: string };
};
// Ordinea = ordinea afisata in paleta (boiler, cuptor, AC, HRV, EV, internet).
export const EQUIPMENT_RECEPTOR_BUTTONS: EquipmentReceptorButton[] = [
  { et: "alimentare_receptor", label: "boiler",           btnText: "boiler",           gate: { kind: "heatingType", equipType: "boiler" } },
  { et: "alimentare_receptor", label: "Cuptor electric",  btnText: "cuptor electric",  gate: { kind: "equipment", equipType: "cuptor_electric" } },
  { et: "alimentare_receptor", label: "Aer conditionat",  btnText: "aer condiționat",  gate: { kind: "equipment", equipType: "ac" } },
  { et: "alimentare_receptor", label: "HRV",              btnText: "HRV",              gate: { kind: "equipment", equipType: "hrv" } },
  { et: "alimentare_receptor", label: "Statie incarcare", btnText: "stație încărcare", gate: { kind: "equipment", equipType: "ev_charger" } },
  { et: "receptor_internet",   label: "internet",         btnText: "rețea internet",   gate: { kind: "equipment", equipType: "internet" } },
];

// H6: butoanele NON-termice vizibile pt. gate-ul curent. Boiler -> heating_type; restul -> echipamente bifate.
export function visibleEquipmentReceptors(
  gate: { heatingType?: string | null; enabledEquipment?: string[] }
): EquipmentReceptorButton[] {
  const ht = (gate.heatingType || "").trim();
  const enabled = new Set(gate.enabledEquipment || []);
  return EQUIPMENT_RECEPTOR_BUTTONS.filter(b => {
    const byEquip = enabled.has(b.gate.equipType);   // bifat in formularul de echipamente
    // H6: boilerul = SAU-logic (heating_type implica boiler ACM SAU bifa "Boiler ACM" activa); restul = doar bifa.
    return b.gate.kind === "heatingType" ? (BOILER_HEATING_TYPES.includes(ht) || byEquip) : byEquip;
  });
}

// ─── Motor (industrial) ───────────────────────────────────────────────────────

export interface Motor {
  name: string;
  power_kw: number;
  phase: string;
  count: number;
}

// ─── Form state ───────────────────────────────────────────────────────────────

export interface FormData {
  project_id: string;
  building_category: string;    // "rezidential" | "public" | "industrial"
  building_type: string;        // subtype value
  surface_mp: number;           // suprafață construită declarată (mp), pentru calcul Z-Coins
  power_phase: string;          // "mono" | "tri"
  insulation_level: string;
  heating_type: string;         // generation type
  heating_distribution: string;
  // Faza 2 TE-CT: "am camera tehnica" -> echipamentele de incalzire pe TE-CT (bifat) sau TEG (nebifat).
  // Default per sursa (defaultTechRoom): bifat pe PDC/centrala electrica, nebifat pe gaz/termoficare/existing.
  has_tech_room: boolean;
  notes: string;
  main_entrance: string;
  // Manual height (Vision may override; always sent as fallback)
  has_basement: boolean;
  floors_above_ground: number;
  has_attic: boolean;
  // Bloc specifics (shown when building_type === "bloc_locuinte")
  floors: string;
  apartments_per_floor: string;
  has_elevator: boolean;
  has_fire_pump: boolean;
  // Industrial specifics
  has_compressed_air: boolean;
  has_overhead_crane: boolean;
  ip_zone: string;
}

export const INITIAL_FORM: FormData = {
  project_id: "",
  building_category: "",
  building_type: "",
  surface_mp: 0,
  power_phase: "mono",
  insulation_level: "",
  heating_type: "",
  heating_distribution: "",
  has_tech_room: true,
  notes: "",
  main_entrance: "",
  has_basement: false,
  floors_above_ground: 0,
  has_attic: false,
  floors: "",
  apartments_per_floor: "",
  has_elevator: false,
  has_fire_pump: false,
  has_compressed_air: false,
  has_overhead_crane: false,
  ip_zone: "IP65",
};

// ─── Backend response types ───────────────────────────────────────────────────

export interface Circuit {
  id: string;
  panel: string;
  usage: string;
  breaker_a: number;
  cable: string;
  notes?: string;
  [key: string]: unknown;
}

export interface RoomResult {
  name: string;
  level?: string;
  function: string;
  area_m2: number;
  sockets: { type: string; count: number; height_m: number; notes: string }[];
  lights: { type: string; count: number; notes: string }[];
}

export interface ProjectResult {
  status: string;
  project_id: string;
  building_category?: string;
  climate_zone: string;
  climate_source?: string;
  levels_string?: string;
  heating_circuits: {
    pdc?: {
      power_kw_thermal: number;
      power_kw_electric: number;
      breaker_a: number;
      cable: string;
      phase: string;
    };
    boiler?: { power_kw: number; breaker_a: number; cable: string };
    pump?: { breaker_a: number; cable: string };
    ventilation?: { breaker_a: number; cable: string } | null;
  };
  rooms: RoomResult[];
  circuits_te_ct: Circuit[];
  circuits_teg: Circuit[];
  circuits_all: Circuit[];
  memoriu_tehnic: string;
  ai_notes?: string;
  annotated_plan_base64?: string | null;
  plan_annotated_base64?: string | null;
  schema_pdf?: string | null;
  schema_monofilara_pdf?: string | null;
  // Etapa 2 Storage: referinta schemei scalar in bucket privat (<uid>/<pid>/schema_monofilara.pdf).
  // Cititorul verifica base64 INTAI, apoi path. Duplicatul schema_monofilara_pdf_base64 e eliminat.
  schema_monofilara_path?: string | null;
  // Etapa 3 Storage: pdf_base64 devine optional — proiectele NOI au pdf_path (bucket privat,
  // <uid>/<pid>/schema_tablou_<i>.pdf); cele vechi raman pe base64. Cititorii verifica base64 INTAI.
  schemas?: Array<{ name: string; plansa_nr: string; pdf_base64?: string | null; pdf_path?: string | null; page_format?: string;
    description?: string | null; filename?: string | null }> | null;
  has_tect?: boolean;   // emis de n8n in result_data (folosit de numerotarea-mirror)
  // Planuri de arhitectura cu cartus Zynapse (swap cartus) — separate de schemas[]
  planuri?: Array<{
    name: string; plansa_nr: string; pdf_base64: string;
    description?: string; filename?: string; size_bytes?: number;
    type?: string; panel?: string | null; expanded?: boolean;
  }> | null;
  has_planuri?: boolean;
  // Planșe de iluminat (plan cu becuri desenate din bbox Vision) — DTAC+PT
  planse_iluminat?: Array<{
    type?: string;
    name: string;
    pdf_base64: string;
    filename?: string;
    source_plansa_nr?: string;
    rooms_found?: number;
    elements_drawn?: number;
    // ADITIV (editor interactiv): forwardate din /draw-plan-elements prin n8n
    png_base64?: string | null;
    png_meta?: {
      dpi?: number; scale?: number;
      pdf_width_pt?: number; pdf_height_pt?: number;
      png_width_px?: number; png_height_px?: number;
    } | null;
    centers?: Array<{ x: number; y: number; label?: string; element_type?: string; power_w?: number | null }>;
    switches?: Array<{ x: number; y: number; angle?: number; room?: string | number | null }>;
    regenerated?: boolean;   // true după "Obține plan" -> pdf_base64 = planul regenerat (cabluri+editări), nu ciorna Vision
  }> | null;
  // M3: planșe de FORȚĂ persistate (oglindă planse_iluminat, per etaj). Fără png separat
  // (fundalul editorului de forță = png-ul de iluminat). Doar pdf_base64 = planșa forță finală.
  planse_forta?: Array<{
    type?: string;
    name: string;
    pdf_base64: string;
    filename?: string;
    source_plansa_nr?: string;
    regenerated?: boolean;
  }> | null;
  has_planse_iluminat?: boolean;
  // Memoriu tehnic (.docx) generat de FastAPI /generate-memoriu prin n8n
  memoriu_docx_base64?: string | null;
  // Etapa 1 Storage (Problema 5): referinta in bucket privat project-files (<uid>/<pid>/memoriu.docx).
  // Cititorul verifica base64 INTAI (vechi + finalizat proaspat), apoi path (proiecte noi).
  memoriu_docx_path?: string | null;
  memoriu_filename?: string;
  memoriu_size_bytes?: number;
  // n8n response fields — parallel to FastAPI circuits_all / heating_circuits
  circuits?: Circuit[];
  circuits_source?: string;   // "plan (enrich)" | "vision (fallback)" — traceabilitate unificare (Faza 2)
  power_summary?: {
    installed_kw?: number;
    absorbed_kw?: number;
    current_a?: number;
    main_breaker_a?: number;
    connection?: string;
    simultaneity_ks?: number;
  };
  output_phase?: string;
  project_info?: {
    titlu_proiect?: string;
    beneficiar?: string;
    amplasament?: string;
    sef_proiect?: string;
    proiect_nr?: string;
    data?: string;
    faza?: string;
    plansa_nr?: string;
  } | null;
  project_name?: string;
  beneficiary?: string;
  address?: string;
  designer?: string;
  bom?: Array<{
    category: string;
    item: string;
    quantity: number;
    unit: string;
    notes?: string;
  }> | null;
  bom_source?: string;   // "plan (unified)" | "n8n (fallback)" — traceabilitate BOM unificat
}

// Planșa de iluminat REGENERATĂ (după "Obține plan": cabluri + editări) ÎNLOCUIEȘTE tot ce se afișează;
// draftul Vision (neregenerat) se ASCUNDE (e doar ciornă). DTAC (fără planse_iluminat) -> planuri ca înainte.
type ShownPlansa = { name: string; pdf_base64: string; filename?: string; plansa_nr?: string; source_plansa_nr?: string; type?: string; ie_label?: string };

// ── NUMEROTAREA PLANSELOR — OGLINDA compute_plansa_numbering (plansa_numbering.py): modifici una
// -> modifici AMBELE. Ordinea: iluminat (toate nivelurile) -> forta (toate) -> TEG -> TES/nivel ->
// TE-CT (daca) -> FV (MEREU ultima). Titlurile = varianta FARA diacritice: Python emite cu
// diacritice, dar cartusul le transpune la ASCII la stampare (cartus_swap._txt) -> mirror-ul
// reproduce LITERAL ce se vede pe plansa (cerinta Dan: cartus == download == fisier).
// Etichetele de nivel oglindesc _FLOOR_INT_LABEL {1:etaj, 2:mansarda} (conventia circuitelor).
export type PlansaNumEntry = { nr: string; tip: string; nivel: string | null; titlu: string };
export function plansaTitlu(tip: string, nivel?: string | null): string {
  const nl = (nivel || "").trim().toUpperCase();
  if (tip === "plan_iluminat") return `PLAN ${nl} INSTALATII ELECTRICE DE ILUMINAT`;
  if (tip === "plan_forta") return `PLAN ${nl} INSTALATII ELECTRICE DE FORTA`;
  if (tip === "schema_teg") return "SCHEMA ELECTRICA MONOFILARA TABLOU ELECTRIC GENERAL";
  if (tip === "schema_tes") return `SCHEMA ELECTRICA MONOFILARA TABLOU ELECTRIC SECUNDAR ${nl}`;
  if (tip === "schema_tect") return "SCHEMA ELECTRICA MONOFILARA TABLOU ELECTRIC CENTRALA TERMICA";
  if (tip === "schema_fv") return "SCHEMA ELECTRICA MONOFILARA SISTEM FOTOVOLTAIC";
  return "PLANSA";
}
export function computePlansaNumbering(opts: {
  extraFloors?: string[]; hasTect?: boolean; hasTes?: boolean | null; hasFv?: boolean;
}): PlansaNumEntry[] {
  const extra = (opts.extraFloors || []).filter(f => (f || "").trim());
  const floors = ["parter", ...extra];
  const tesOn = opts.hasTes == null ? extra.length > 0 : !!opts.hasTes;
  const sheets: Array<[string, string | null]> = [];
  for (const fl of floors) sheets.push(["plan_iluminat", fl]);
  for (const fl of floors) sheets.push(["plan_forta", fl]);
  sheets.push(["schema_teg", null]);
  if (tesOn) for (const fl of extra) sheets.push(["schema_tes", fl]);
  if (opts.hasTect) sheets.push(["schema_tect", null]);
  if (opts.hasFv) sheets.push(["schema_fv", null]);   // FV = MEREU ultima plansa IE
  return sheets.map(([tip, nivel], i) => ({
    nr: `IE.${i + 1}`, tip, nivel, titlu: plansaTitlu(tip, nivel),
  }));
}
// nume de fisier sigur: fara caractere ilegale; spatiile raman (ex. "IE.1 PLAN PARTER ....pdf")
export const sanitizePdfName = (s: string) => s.replace(/[\\/:*?"<>|]/g, "").replace(/\s+/g, " ").trim();

// tipul unei intrari schemas[] (name/description/filename, insensibil la diacritice/majuscule)
export function schemaTipFor(s: { name?: string | null; description?: string | null; filename?: string | null }):
  "schema_teg" | "schema_tes" | "schema_tect" | "schema_fv" | null {
  const t = `${s?.name || ""} ${s?.description || ""} ${s?.filename || ""}`.toLowerCase()
    .replace(/[ăâ]/g, "a").replace(/î/g, "i").replace(/[șş]/g, "s").replace(/[țţ]/g, "t")
    .replace(/[_\-.]/g, " ");
  if (t.includes("fotovoltaic") || /(^|\s)fv(\s|$)/.test(t)) return "schema_fv";
  if (t.includes("te ct") || t.includes("tect") || t.includes("centrala termica")) return "schema_tect";
  if (t.includes("tes")) return "schema_tes";
  if (t.includes("teg") || t.includes("general")) return "schema_teg";
  return null;
}
// numerotarea derivata din result (universal, inclusiv proiecte vechi cu metadata stale):
// nivelurile din planse_iluminat (la DTAC: din nr. schemelor TES), TE-CT/FV din has_tect + schemas.
export function plansaNumberingFromResult(result: ProjectResult): PlansaNumEntry[] {
  const il = result.planse_iluminat || [];
  const tipuri = (result.schemas || []).map(schemaTipFor);
  const nTes = tipuri.filter(t => t === "schema_tes").length;
  const nExtra = il.length > 1 ? il.length - 1 : nTes;
  const extraFloors = Array.from({ length: nExtra }, (_, i) => ["etaj", "mansarda"][i] || `nivel ${i + 2}`);
  return computePlansaNumbering({
    extraFloors,
    hasTect: !!result.has_tect || tipuri.includes("schema_tect"),
    hasFv: tipuri.includes("schema_fv"),
  });
}
// schemas[i] -> intrarea de numerotare (TEG/TE-CT/FV unice; TES in ordinea aparitiei = ordinea nivelurilor)
export function mapSchemasToNumbering(
  schemas: Array<{ name?: string | null; description?: string | null; filename?: string | null }>,
  entries: PlansaNumEntry[]
): (PlansaNumEntry | null)[] {
  const tes = entries.filter(e => e.tip === "schema_tes");
  let tesIdx = 0;
  return (schemas || []).map(s => {
    const tip = schemaTipFor(s);
    if (!tip) return null;
    if (tip === "schema_tes") { const e = tes[tesIdx] || null; tesIdx += 1; return e; }
    return entries.find(e => e.tip === tip) || null;
  });
}

// M3: planșele FINALE de afișat în istoric/livrabile = iluminat (regenerate) APOI forță (regenerate).
// CONSECVENȚĂ (Dan): numele afișat + fișierul descărcat = LITERAL titlul din cartuș ("IE.N TITLU",
// din mirror) — nu sufixele vechi ("— Iluminat") și nu numerotarea secvențială peste subsetul
// regenerat. source_plansa_nr (numărul FINAL ștampilat la redraw) are prioritate la mapare;
// fallback = poziția etajului în listă.
export function iluminatPlanseToShow(result: ProjectResult): { planse: ShownPlansa[]; draftPending: boolean } {
  const il = result.planse_iluminat || [];
  if (il.length) {
    const regenIl = il.filter(p => p.regenerated);
    if (!regenIl.length) return { planse: [], draftPending: true };   // doar ciornă Vision -> ascunde + placeholder
    const fo = result.planse_forta || [];
    const regenFo = fo.filter(p => p.regenerated);
    const num = plansaNumberingFromResult(result);
    const ilE = num.filter(e => e.tip === "plan_iluminat");
    const foE = num.filter(e => e.tip === "plan_forta");
    const out: ShownPlansa[] = [];
    const push = (p: ShownPlansa, e: PlansaNumEntry | undefined) => {
      const disp = e ? `${e.nr} ${e.titlu}` : p.name;
      out.push({
        ...p, name: disp, ie_label: "",              // numele conține deja IE.N -> fără prefix dublu
        plansa_nr: undefined, source_plansa_nr: undefined,
        filename: e ? `${sanitizePdfName(disp)}.pdf` : p.filename,
      });
    };
    for (const p of regenIl) push(p, ilE.find(x => x.nr === p.source_plansa_nr) || ilE[il.indexOf(p)]);
    for (const p of regenFo) push(p, foE.find(x => x.nr === p.source_plansa_nr) || foE[fo.indexOf(p)]);
    return { planse: out, draftPending: false };
  }
  return { planse: result.planuri || [], draftPending: false };   // DTAC: planuri ca înainte
}
