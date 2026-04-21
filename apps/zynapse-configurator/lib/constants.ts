export const BUILDING_TYPES = [
  { value: "casa_unifamiliala", label: "Casă unifamilială" },
  { value: "duplex", label: "Duplex" },
  { value: "apartament", label: "Apartament" },
  { value: "bloc_mic", label: "Bloc mic / townhouse" },
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

export interface FormData {
  project_id: string;
  building_type: string;
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
};
