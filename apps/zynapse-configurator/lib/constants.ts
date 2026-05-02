export const BUILDING_TYPES = [
  // Rezidential
  { value: "casa_unifamiliala", label: "Casă unifamilială" },
  { value: "duplex",            label: "Duplex" },
  { value: "apartament",        label: "Apartament" },
  // Bloc
  { value: "bloc_locuinte",     label: "Bloc de locuințe" },
  { value: "bloc_mixt",         label: "Bloc mixt" },
  // Public
  { value: "camin_cultural",    label: "Cămin cultural" },
  { value: "scoala",            label: "Școală / Grădiniță" },
  { value: "birou",             label: "Clădire birouri" },
  { value: "spital",            label: "Spital / Clinică" },
  { value: "institutie",        label: "Instituție publică" },
  // Industrial
  { value: "hala",              label: "Hală industrială" },
  { value: "depozit",           label: "Depozit / Logistică" },
  { value: "atelier",           label: "Atelier / Workshop" },
  { value: "fabrica",           label: "Fabrică" },
  // Comercial
  { value: "magazin",           label: "Magazin / Retail" },
  { value: "restaurant",        label: "Restaurant / Bar" },
  { value: "hotel",             label: "Hotel" },
  { value: "mall",              label: "Mall / Centru comercial" },
];

export const BUILDING_CATEGORIES = [
  { value: "rezidential", label: "Rezidențial" },
  { value: "public",      label: "Clădire publică" },
  { value: "industrial",  label: "Hală industrială" },
  { value: "bloc",        label: "Bloc de locuințe" },
  { value: "comercial",   label: "Spațiu comercial" },
];

export const COMMERCIAL_SUBTYPES = [
  { value: "magazin",    label: "Magazin / Retail" },
  { value: "restaurant", label: "Restaurant / Bar" },
  { value: "hotel",      label: "Hotel" },
  { value: "mall",       label: "Mall / Centru comercial" },
];

export const LEVELS = ["P", "P+M", "P+1", "P+1+M", "P+2", "D+P+M", "D+P+1", "D+P+1+M"];

export const CLIMATE_ZONES = [
  { value: "I",   label: "Zona I — −12°C" },
  { value: "II",  label: "Zona II — −15°C" },
  { value: "III", label: "Zona III — −18°C" },
  { value: "IV",  label: "Zona IV — −21°C" },
];

export const INSULATION = [
  { value: "slaba",       label: "Slabă  (> 70 W/m²)" },
  { value: "medie",       label: "Medie  (~60 W/m²)" },
  { value: "buna",        label: "Bună  (~50 W/m²)" },
  { value: "foarte_buna", label: "Foarte bună  (< 40 W/m²)" },
];

export const HEATING = [
  { value: "pdc_air_water",    label: "PDC Aer–Apă" },
  { value: "pdc_air_air",      label: "PDC Aer–Aer" },
  { value: "gas_boiler",       label: "Centrală pe gaz" },
  { value: "electric_boiler",  label: "Centrală electrică" },
  { value: "geothermal",       label: "Geotermală" },
  { value: "none",             label: "Fără încălzire centralizată" },
];

export interface Motor {
  name: string;
  power_kw: number;
  phase: string;   // "mono" | "tri"
  count: number;
}

export interface FormData {
  project_id: string;
  building_type: string;
  building_category: string;
  levels: string;
  climate_zone: string;
  insulation_level: string;
  main_entrance: string;
  heating_type: string;
  pdc_phase: string;
  has_acm_boiler: boolean;
  has_ventilation: boolean;
  has_hrv: boolean;
  has_floor_heating: boolean;
  notes: string;
  // Bloc
  floors: string;
  apartments_per_floor: string;
  has_elevator: boolean;
  has_fire_pump: boolean;
  // Industrial
  has_compressed_air: boolean;
  has_overhead_crane: boolean;
  ip_zone: string;
  // Comercial
  commercial_subtype: string;
}

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
}

export const INITIAL_FORM: FormData = {
  project_id: "",
  building_type: "",
  building_category: "",
  levels: "",
  climate_zone: "II",
  insulation_level: "",
  main_entrance: "",
  heating_type: "",
  pdc_phase: "mono",
  has_acm_boiler: true,
  has_ventilation: false,
  has_hrv: false,
  has_floor_heating: false,
  notes: "",
  // Bloc
  floors: "",
  apartments_per_floor: "",
  has_elevator: false,
  has_fire_pump: false,
  // Industrial
  has_compressed_air: false,
  has_overhead_crane: false,
  ip_zone: "IP65",
  // Comercial
  commercial_subtype: "",
};
