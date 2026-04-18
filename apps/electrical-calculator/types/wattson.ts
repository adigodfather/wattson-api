export interface Room {
  name: string;
  level: string;
  function: "day" | "night" | "circulation" | "bathroom" | "kitchen" | "technical/storage" | "other";
  area_m2: number;
  height_m: number;
  window_sill_height_m?: number;
  has_tv: boolean;
  has_nightstands: boolean;
}

export interface ProjectPayload {
  project_id: string;
  building: {
    type: string;
    levels: string;
    climate_zone: string;
    insulation_level: "slaba" | "medie" | "buna" | "foarte_buna";
    main_entrance?: string;
    total_area_m2: number;
    total_volume_m3: number;
  };
  heating: {
    type: "pdc_air_water" | "pdc_air_air" | "gas_boiler" | "electric_boiler" | "geothermal" | "none";
    pdc_phase?: "mono" | "tri";
    has_acm_boiler: boolean;
    has_ventilation: boolean;
    has_hrv: boolean;
  };
  has_floor_heating: boolean;
  rooms: Room[];
}

export interface Circuit {
  id: string;
  panel: string;
  usage: string;
  device?: string;
  breaker_a?: number;
  cable?: string;
  notes?: string;
  power_kw?: number;
  phase?: string;
  poles?: string;
}

export interface CalcResponse {
  project_id: string;
  status: "success";
  climate_zone: string;
  heating_circuits: {
    pdc: Circuit | null;
    boiler: Circuit | null;
    pump: Circuit | null;
    ventilation: Circuit | null;
  };
  rooms: Array<{
    name: string;
    level?: string;
    function: string;
    area_m2: number;
    sockets: Array<{ type: string; count: number; height_m: number; notes: string }>;
    lights: Array<{ type: string; count: number; notes: string }>;
  }>;
  circuits_te_ct: Circuit[];
  circuits_teg: Circuit[];
  circuits_all: Circuit[];
  memoriu_tehnic: string;
}
