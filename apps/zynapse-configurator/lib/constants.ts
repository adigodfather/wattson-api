// ─── 3 user-facing building categories (PAS 1) ───────────────────────────────

export const BUILDING_CATEGORIES_3 = [
  { value: "rezidential", label: "Rezidențial", icon: "🏠", desc: "Case, duplexuri, blocuri, hoteluri" },
  { value: "public",      label: "Public",      icon: "🏛️", desc: "Școli, spitale, cămine culturale" },
  { value: "industrial",  label: "Industrial",  icon: "🏭", desc: "Hale, depozite, ateliere" },
] as const;

// ─── Subtypes per category (PAS 2) ───────────────────────────────────────────

export const BUILDING_SUBTYPES: Record<string, { value: string; label: string }[]> = {
  rezidential: [
    { value: "casa_unifamiliala",    label: "Casă unifamilială" },
    { value: "duplex",               label: "Duplex / Vilă" },
    { value: "bloc_locuinte",        label: "Bloc de locuințe" },
    { value: "spatiu_comercial_bloc",label: "Spațiu comercial în bloc" },
    { value: "hotel_pensiune",       label: "Hotel / Pensiune" },
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
  phase: string;  // "mono" | "tri" | "none"
}

export const EXTRA_EQUIPMENT_DEFAULTS: {
  type: string; label: string; icon: string; default_kw: number; default_phase: string;
}[] = [
  { type: "boiler",     label: "Boiler ACM",                             icon: "🛁", default_kw: 2,   default_phase: "mono" },
  { type: "ac",         label: "Aer condiționat",                        icon: "❄️", default_kw: 2.5, default_phase: "mono" },
  { type: "hrv",        label: "Ventilație cu recuperare căldură (HRV)", icon: "🌀", default_kw: 0.2, default_phase: "mono" },
  { type: "internet",   label: "Rețea date / Internet (prize RJ45)",     icon: "🌐", default_kw: 0,   default_phase: "none" },
  { type: "solar",      label: "Panouri fotovoltaice",                   icon: "☀️", default_kw: 5,   default_phase: "mono" },
  { type: "ev_charger", label: "Stație încărcare mașină electrică",      icon: "🚗", default_kw: 7.4, default_phase: "mono" },
];

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
  power_phase: string;          // "mono" | "tri"
  insulation_level: string;
  heating_type: string;         // generation type
  heating_distribution: string;
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
  power_phase: "mono",
  insulation_level: "",
  heating_type: "",
  heating_distribution: "",
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
  schema_monofilara_pdf?: string | null;
  schemas?: Array<{ name: string; plansa_nr: string; pdf_base64: string; page_format?: string }> | null;
  // n8n response fields — parallel to FastAPI circuits_all / heating_circuits
  circuits?: Circuit[];
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
}
