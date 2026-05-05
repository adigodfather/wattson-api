from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Literal
import math
import os
import base64
import io

app = FastAPI(
    title="ZYNAPSE Core API",
    description="Motor inteligent de calcul pentru proiecte electrice – ZYNAPSE",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
#  CONSTANTE
# -------------------------------------------------

COP_BY_TYPE = {
    "pdc_air_water": 4.0,
    "pdc_air_air": 3.5,
    "geothermal": 4.5,
}

ZONE_TEMP = {
    "I": -12,
    "II": -15,
    "III": -18,
    "IV": -21,
    "V": -25,
}

SNOW_LOAD_BY_ZONE = {
    "I": 1.0, "II": 1.5, "III": 2.0, "IV": 2.5, "V": 3.0,
}

INSULATION_W_M2 = {
    "slaba": 70.0,
    "medie": 60.0,
    "buna": 50.0,
    "foarte_buna": 40.0,
}

# (curent_max_A, sectiune_mm2) — tabel selectie cablu
CABLE_SECTIONS = [
    (6,          "1.5"),
    (10,         "2.5"),
    (16,         "4"),
    (25,         "6"),
    (32,         "10"),
    (40,         "16"),
    (63,         "25"),
    (float("inf"), "35"),
]

MCB_STEPS = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125]

BUILDING_CATEGORY_MAP = {
    "rezidential": ["casa_unifamiliala", "duplex", "apartament", "duplex_vila"],
    "public":      ["camin_cultural", "scoala", "birou", "spital", "institutie", "sala_sport", "biserica"],
    "industrial":  ["hala", "depozit", "atelier", "fabrica", "productie", "hala_productie", "ferma", "statie_tehnologica"],
    "bloc":        ["bloc_locuinte", "bloc_mixt", "bloc_mic"],
    "comercial":   ["magazin", "restaurant", "hotel", "mall", "comercial", "spatiu_comercial_bloc", "hotel_pensiune"],
}

NORMATIVE_BY_CATEGORY = {
    "rezidential": "I7-2011, NP 061-2002",
    "public":      "I7-2011, NP 061-2002, P118-99 (PSI), SR EN 12464-1 (iluminat)",
    "industrial":  "PE 155, SR EN 60529 (IP), SR EN 60204 (masini)",
    "bloc":        "I7-2011, NP 061-2002, SR EN 50522",
    "comercial":   "I7-2011, NP 031 (PSI comercial)",
}

CATEGORY_LABELS = {
    "rezidential": "Rezidential",
    "public":      "Cladire Publica",
    "industrial":  "Hala Industriala",
    "bloc":        "Bloc de Locuinte",
    "comercial":   "Spatiu Comercial",
}

# -------------------------------------------------
#  MODELE DE INTRARE
# -------------------------------------------------


class MotorData(BaseModel):
    name: str
    power_kw: float
    phase: str = "tri"  # mono / tri
    count: int = 1


class ExtraEquipment(BaseModel):
    type: str   # boiler/ac/hrv/internet/solar/ev_charger/custom
    name: str
    power_kw: float = 0.0
    phase: str = "mono"  # mono / tri / none


class Building(BaseModel):
    type: str
    levels: str
    climate_zone: Optional[str] = None
    climate_source: Optional[str] = None  # e.g. "jud. Bihor" — auto-detected by Vision
    insulation_level: Literal["slaba", "medie", "buna", "foarte_buna"]
    main_entrance: Optional[str] = None
    total_area_m2: float
    total_volume_m3: float


class Heating(BaseModel):
    type: str  # pdc_air_water/pdc_air_air/pdc_ground_water/gas_boiler/electric_boiler/geothermal/district_heating/existing/none
    has_acm_boiler: bool = False
    has_ventilation: bool = False
    has_hrv: bool = False
    pdc_phase: Optional[Literal["mono", "tri"]] = "tri"
    distribution: Optional[str] = None  # floor_heating/fan_coil/electric_radiator/radiant_ceiling/existing


class Room(BaseModel):
    name: str
    level: Optional[str] = None
    area_m2: float
    height_m: float
    window_sill_height_m: Optional[float] = None
    function: str  # day/night/circulation/bathroom/kitchen/technical/storage/other
                   # hall/office/corridor/sanitary/kitchen_pub (public)
                   # production/warehouse/office_ind/compressor/electrical (industrial)
    has_tv: bool = False
    has_nightstands: bool = False


class ProjectData(BaseModel):
    project_id: str
    building: Building
    heating: Heating
    rooms: List[Room]
    has_floor_heating: bool = False
    notes: Optional[str] = None
    building_category: Optional[str] = None
    extra_equipment: Optional[List[ExtraEquipment]] = None
    power_phase: Optional[str] = "mono"         # mono / tri
    heating_distribution: Optional[str] = None  # floor_heating/fan_coil/…
    # Climate (top-level, from Vision auto-detect or frontend default)
    climate_zone: Optional[str] = "II"
    climate_auto_detected: Optional[bool] = False
    climate_source: Optional[str] = None
    # Height regime (from frontend manual controls or Vision)
    levels_string: Optional[str] = None
    levels_auto_detected: Optional[bool] = False
    has_basement: Optional[bool] = False
    floors_above_ground: Optional[int] = 0
    has_attic: Optional[bool] = False
    # Industrial
    motors: Optional[List[MotorData]] = None
    has_compressed_air: bool = False
    has_overhead_crane: bool = False
    ip_zone: str = "IP20"
    has_explosive_zone: bool = False
    # Bloc
    floors: Optional[int] = None
    apartments_per_floor: Optional[int] = None
    has_elevator: bool = False
    has_fire_pump: bool = False


# -------------------------------------------------
#  UTILITARE
# -------------------------------------------------


def detect_building_category(building_type: str) -> str:
    t = building_type.lower()
    for category, types in BUILDING_CATEGORY_MAP.items():
        if any(bt in t for bt in types):
            return category
    if any(k in t for k in ["casa", "duplex", "apart"]):
        return "rezidential"
    if any(k in t for k in ["hala", "fabrica", "atelier", "depozit", "productie"]):
        return "industrial"
    if any(k in t for k in ["bloc"]):
        return "bloc"
    if any(k in t for k in ["magazin", "restaurant", "hotel", "mall", "comercial"]):
        return "comercial"
    if any(k in t for k in ["scoala", "spital", "camin", "birou", "institutie"]):
        return "public"
    return "rezidential"


def resolve_climate_zone(building: Building) -> str:
    if building.climate_zone:
        z = building.climate_zone.strip().upper().replace("ZONA", "").strip()
        if z in ZONE_TEMP:
            return z
    return "II"


def resolve_climate_zone_from_data(data: "ProjectData") -> str:
    if data.climate_zone:
        z = data.climate_zone.strip().upper().replace("ZONA", "").strip()
        if z in ZONE_TEMP:
            return z
    return resolve_climate_zone(data.building)


def next_mcb(current_a: float) -> int:
    for step in MCB_STEPS:
        if step >= current_a:
            return step
    return MCB_STEPS[-1]


def cable_for_current(current_a: float) -> str:
    for limit, section in CABLE_SECTIONS:
        if current_a <= limit:
            return section
    return "35"


# -------------------------------------------------
#  UTILITARE – PDC / TE-CT
# -------------------------------------------------


def calc_extra_equipment_circuits(
    equipment: List[ExtraEquipment],
    panel: str = "TEG",
) -> List[dict]:
    circuits = []
    for i, eq in enumerate(equipment):
        tag = i + 1
        if eq.type == "boiler":
            circuits.append({
                "id": f"C_BOILER_{tag}", "panel": panel,
                "usage": f"Boiler ACM — {eq.name}",
                "type": "boiler", "breaker_a": 16,
                "cable": "3x2,5 mm² NYM", "rcd_30ma": True,
                "notes": "Circuit dedicat boiler ACM, MCB 16A, RCCB 30mA.",
            })
        elif eq.type == "ac":
            circuits.append({
                "id": f"C_AC_{tag}", "panel": panel,
                "usage": f"Aer condiționat — {eq.name}",
                "type": "ac", "breaker_a": 16,
                "cable": "3x2,5 mm² NYM", "rcd_30ma": True,
                "notes": "Circuit dedicat AC, MCB 16A, RCCB 30mA.",
            })
        elif eq.type == "hrv":
            circuits.append({
                "id": f"C_HRV_{tag}", "panel": panel,
                "usage": f"Ventilație HRV — {eq.name}",
                "type": "hrv", "breaker_a": 10,
                "cable": "3x1,5 mm² NYM",
                "notes": "Circuit ventilație cu recuperare căldură, MCB 10A.",
            })
        elif eq.type == "ev_charger":
            if eq.phase == "tri":
                circuits.append({
                    "id": f"C_EV_{tag}", "panel": panel,
                    "usage": f"Stație EV — {eq.name}",
                    "type": "ev_charger", "phase": "trifazat", "breaker_a": 16,
                    "cable": "5x6 mm² NYM", "rcd_30ma": True,
                    "notes": "Stație EV trifazată: MCB 3P 16A, RCCB 3P 25A/30mA, NYM 5x6.",
                })
            else:
                circuits.append({
                    "id": f"C_EV_{tag}", "panel": panel,
                    "usage": f"Stație EV — {eq.name}",
                    "type": "ev_charger", "breaker_a": 32,
                    "cable": "3x6 mm² NYM", "rcd_30ma": True,
                    "notes": "Stație EV monofazată: MCB 32A, RCCB 30mA, NYM 3x6.",
                })
        elif eq.type == "solar":
            if eq.phase == "tri":
                circuits.append({
                    "id": f"C_PV_{tag}", "panel": panel,
                    "usage": f"Invertor FV — {eq.name}",
                    "type": "solar", "breaker_a": 20,
                    "cable": "5x4 mm² NYM",
                    "notes": "Invertor fotovoltaic trifazat: MCB 2P 20A, NYM 5x4.",
                })
            else:
                circuits.append({
                    "id": f"C_PV_{tag}", "panel": panel,
                    "usage": f"Invertor FV — {eq.name}",
                    "type": "solar", "breaker_a": 20,
                    "cable": "3x4 mm² NYM",
                    "notes": "Invertor fotovoltaic monofazat: MCB 2P 20A, NYM 3x4.",
                })
        elif eq.type == "internet":
            pass  # No power circuit needed
        elif eq.type == "custom" and eq.power_kw > 0:
            if eq.phase == "tri":
                i_calc = eq.power_kw * 1000 / 692.0
            else:
                i_calc = eq.power_kw * 1000 / 230.0
            mcb = next_mcb(i_calc * 1.25)
            section = cable_for_current(i_calc * 1.25)
            prefix = "5" if eq.phase == "tri" else "3"
            circuits.append({
                "id": f"C_CUST_{tag}", "panel": panel,
                "usage": eq.name,
                "type": "custom", "breaker_a": mcb,
                "cable": f"{prefix}x{section} mm²",
                "notes": (
                    f"Echipament custom: {eq.power_kw} kW, "
                    f"I={i_calc:.1f}A, MCB {mcb}A."
                ),
            })
    return circuits


def calc_pdc_power_kw(building: Building, heating: Heating, climate_zone: str) -> float:
    if not heating.type.startswith("pdc") and heating.type != "geothermal":
        return 0.0
    w_per_m2 = INSULATION_W_M2.get(building.insulation_level, 50.0)
    zone_delta = {"I": -5.0, "II": 0.0, "III": 3.0, "IV": 5.0, "V": 8.0}
    w_per_m2 += zone_delta.get(climate_zone, 0.0)
    if building.total_area_m2 <= 250 and building.insulation_level in ["buna", "foarte_buna"]:
        return 10.0
    return round(building.total_area_m2 * w_per_m2 / 1000.0, 1)


def choose_pdc_circuit(
    power_kw: float,
    phase: str = "tri",
    pdc_type: str = "pdc_air_water",
) -> Optional[dict]:
    if power_kw <= 0:
        return None
    cop = COP_BY_TYPE.get(pdc_type, 4.0)
    p_el_kw = power_kw / cop
    if phase == "tri":
        ia = math.ceil(p_el_kw / (0.4 * 0.92 * 1.73))
        if power_kw <= 10:
            breaker, cable = 16, "5x2,5 mm² CYYF"
        elif power_kw <= 14:
            breaker, cable = 20, "5x4 mm² CYYF"
        else:
            breaker, cable = 25, "5x6 mm² CYYF"
        return {
            "device": "PDC", "phase": "trifazat", "poles": "3P+N",
            "power_kw_thermal": power_kw, "power_kw_electric": round(p_el_kw, 2),
            "current_a_calc": ia, "breaker_a": breaker, "cable": cable,
            "notes": f"Circuit trifazat PDC, COP ~{cop}.",
        }
    ia = math.ceil(p_el_kw / 0.23)
    if power_kw <= 10:
        breaker, cable = 20, "3x4 mm² CYYF"
    else:
        breaker, cable = 25, "3x6 mm² CYYF"
    return {
        "device": "PDC", "phase": "monofazat", "poles": "1P+N",
        "power_kw_thermal": power_kw, "power_kw_electric": round(p_el_kw, 2),
        "current_a_calc": ia, "breaker_a": breaker, "cable": cable,
        "notes": f"Circuit monofazat PDC, COP ~{cop}.",
    }


def choose_boiler_circuit(building: Building, heating: Heating) -> Optional[dict]:
    if not heating.has_acm_boiler:
        return None
    p_kw = 2.0 if building.total_area_m2 <= 200 else 3.0
    breaker = 16 if p_kw <= 2.5 else 20
    return {
        "device": "Boiler ACM", "power_kw": p_kw, "breaker_a": breaker,
        "cable": "3x2,5 mm² CYYF", "notes": "Circuit monofazat dedicat pentru boiler ACM.",
    }


def choose_pump_circuit() -> dict:
    return {
        "device": "Pompa circulatie", "power_kw": 0.3, "breaker_a": 10,
        "cable": "3x1,5 mm² CYYF", "notes": "Circuit monofazat pentru pompa de circulatie.",
    }


def choose_ventilation_circuit(heating: Heating) -> Optional[dict]:
    if not heating.has_ventilation and not heating.has_hrv:
        return None
    return {
        "device": "Ventilatie / recuperare", "power_kw": 0.2, "breaker_a": 10,
        "cable": "3x1,5 mm² CYYF", "notes": "Circuit monofazat pentru unitate de ventilatie / HRV.",
    }


# -------------------------------------------------
#  CAMERE – PRIZE + ILUMINAT (rezidential)
# -------------------------------------------------


def calc_room_electrics(room: Room) -> dict:
    sockets = []
    lights = []
    if room.has_nightstands:
        sockets.append({
            "type": "priza_noptiera", "count": 2, "height_m": 0.6,
            "notes": "Prize la 0,6 m la fiecare noptiera.",
        })
    if room.has_tv:
        h_tv = 1.8 if room.function in ["day"] else 0.6
        sockets.append({
            "type": "priza_TV", "count": 1, "height_m": h_tv,
            "notes": f"TV – priza la ~{h_tv} m.",
        })
    func = room.function
    if func in ["day", "night"]:
        lights.append({"type": "candelabru_central", "count": 1,
                       "notes": "Corp plafon central (lustra LED / pendul)."})
        if room.area_m2 > 20:
            lights.append({"type": "spoturi_sau_benzi", "count": math.ceil(room.area_m2 / 5),
                           "notes": "Iluminat accent / ambiental pentru camera mare."})
    elif func == "bathroom":
        lights.append({"type": "aplica_IP44", "count": 1,
                       "notes": "Corp cu IP44 sau mai mare (zona umeda)."})
    elif func == "kitchen":
        lights.append({"type": "plafoniera_LED", "count": 1,
                       "notes": "Plafoniera LED centrala; benzi LED deasupra blatului."})
    elif func == "circulation":
        lights.append({"type": "plafoniera_slim", "count": max(1, math.ceil(room.area_m2 / 8)),
                       "notes": "Iluminat general circulatie."})
    else:
        lights.append({"type": "plafoniera", "count": 1, "notes": "Iluminat general."})
    return {
        "name": room.name, "level": room.level, "function": room.function,
        "area_m2": room.area_m2, "sockets": sockets, "lights": lights,
    }


# -------------------------------------------------
#  CIRCUITE REZIDENTIAL – TE-CT + TEG
# -------------------------------------------------


def build_circuits_te_ct(
    pdc_circuit: Optional[dict],
    boiler_circuit: Optional[dict],
    pump_circuit: Optional[dict],
    ventilation_circuit: Optional[dict],
    has_floor_heating: bool,
) -> List[dict]:
    circuits = []
    idx = 1

    def add(device_dict: Optional[dict], usage_name: str):
        nonlocal idx
        if not device_dict:
            return
        circuits.append({"id": f"TECT_{idx}", "panel": "TE-CT", "usage": usage_name, **device_dict})
        idx += 1

    add(pdc_circuit, "Alimentare PDC")
    add(boiler_circuit, "Boiler ACM")
    add(pump_circuit, "Pompa circulatie")
    add(ventilation_circuit, "Ventilatie / recuperare")
    circuits.append({
        "id": f"TECT_{idx}", "panel": "TE-CT", "usage": "Automatizare CT",
        "device": "Automatizare", "breaker_a": 10, "cable": "3x1,5 mm² CYYF",
        "notes": "Alimentare automatizare centrala / PDC.",
    })
    idx += 1
    circuits.append({
        "id": f"TECT_{idx}", "panel": "TE-CT", "usage": "Circuit rezerva",
        "device": "Rezerva", "breaker_a": 16, "cable": "3x2,5 mm² CYYF",
        "notes": "Circuit de rezerva pentru echipamente viitoare.",
    })
    idx += 1
    if has_floor_heating:
        circuits.append({
            "id": f"TECT_{idx}", "panel": "TE-CT",
            "usage": "Distribuitor incalzire in pardoseala",
            "device": "Distribuitor IP", "power_kw": 0.5, "breaker_a": 16,
            "cable": "3x2,5 mm² CYYF",
            "notes": "Alimentare distribuitor IP (pompe / actuatoare).",
        })
    return circuits


def build_circuits_teg(data: ProjectData) -> List[dict]:
    circuits = []
    total_area = sum(r.area_m2 for r in data.rooms)
    has_kitchen = any(r.function == "kitchen" for r in data.rooms)
    has_bathroom = any(r.function == "bathroom" for r in data.rooms)

    num_light = max(1, math.ceil(total_area / 60.0))
    for i in range(num_light):
        circuits.append({
            "id": f"TEG_L{i+1}", "panel": "TEG", "usage": "Iluminat interior",
            "type": "iluminat", "breaker_a": 10, "cable": "3x1,5 mm² CYYF",
            "notes": "Circuit iluminat general.",
        })
    circuits.append({
        "id": "TEG_EX1", "panel": "TEG", "usage": "Iluminat exterior",
        "type": "iluminat", "breaker_a": 10, "cable": "3x1,5 mm² CYYF",
        "notes": "Aplice LED cu senzor crepuscular la intrari / terase.",
    })
    num_sockets = max(1, math.ceil(total_area / 40.0))
    for i in range(num_sockets):
        circuits.append({
            "id": f"TEG_P{i+1}", "panel": "TEG", "usage": "Prize generale",
            "type": "prize", "breaker_a": 16, "cable": "3x2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Prize generale camere zi / dormitoare (max ~5 prize / circuit).",
        })
    if has_kitchen:
        circuits.append({
            "id": "TEG_PB1", "panel": "TEG", "usage": "Prize blaturi bucatarie",
            "type": "prize", "breaker_a": 20, "cable": "3x2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Prize blaturi bucatarie – consumatoare mici.",
        })
        circuits.append({
            "id": "TEG_PB2", "panel": "TEG", "usage": "Electrocasnice bucatarie",
            "type": "prize", "breaker_a": 20, "cable": "3x2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Cuptor / masina spalat vase / aparate dedicate.",
        })
    if has_bathroom:
        circuits.append({
            "id": "TEG_MSR1", "panel": "TEG", "usage": "Masina spalat rufe",
            "type": "prize", "breaker_a": 16, "cable": "3x2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Circuit dedicat masina de spalat rufe.",
        })
    return circuits


# -------------------------------------------------
#  CLADIRI PUBLICE
# -------------------------------------------------


def calc_public_circuits(data: ProjectData) -> List[dict]:
    circuits = []
    idx_ilm = idx_prz = idx_frt = idx_ip44 = 1
    total_power_w = 0.0
    has_evacuation_zone = False

    for room in data.rooms:
        func = room.function
        area = room.area_m2

        if func in ["corridor", "circulation"]:
            has_evacuation_zone = True
            circuits.append({
                "id": f"C_ILM_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "lux": 150, "notes": f"Coridor/hol {room.name}, 100-150 lux.",
            })
            idx_ilm += 1
            total_power_w += area * 15

        elif func == "hall":
            circuits.append({
                "id": f"C_ILM_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat sala {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "lux": 400, "notes": f"Sala/aula {room.name}, 300-500 lux.",
            })
            idx_ilm += 1
            circuits.append({
                "id": f"C_FRT_{idx_frt:02d}", "panel": "TG",
                "usage": f"Forta scena {room.name}",
                "type": "forta", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                "notes": f"Circuit forta scena/echipamente {room.name}, MCB 16A.",
            })
            idx_frt += 1
            total_power_w += area * 40 + 3000

        elif func == "office":
            circuits.append({
                "id": f"C_ILM_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "lux": 500, "notes": f"Birou/oficiu {room.name}, 500 lux.",
            })
            idx_ilm += 1
            num_prz = max(1, math.ceil(area / 30))
            for _ in range(num_prz):
                circuits.append({
                    "id": f"C_PRZ_{idx_prz:02d}", "panel": "TG",
                    "usage": f"Prize {room.name}",
                    "type": "prize", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                    "rcd_30ma": True, "notes": f"Prize birou {room.name}, h=0.30m, 1 priza/mp.",
                })
                idx_prz += 1
            total_power_w += area * 80

        elif func == "sanitary":
            circuits.append({
                "id": f"C_IP44_{idx_ip44:02d}", "panel": "TG",
                "usage": f"Circuit umed {room.name}",
                "type": "ip44", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                "rcd_10ma": True, "ip": "IP44",
                "notes": f"Grup sanitar {room.name}: IP44, RCCB 10mA, priza IP44 la h=1.20m.",
            })
            idx_ip44 += 1
            total_power_w += 500

        elif func == "kitchen_pub":
            circuits.append({
                "id": f"C_FRT_{idx_frt:02d}", "panel": "TG",
                "usage": f"Forta bucatarie {room.name}",
                "type": "forta", "phase": "tri", "breaker_a": 32, "cable": "NYM 5x4 mm²",
                "notes": f"Bucatarie publica {room.name}: trifazat 32A, hota, echipamente.",
            })
            idx_frt += 1
            total_power_w += 15000

        elif func in ["storage", "technical/storage"]:
            circuits.append({
                "id": f"C_ILM_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "lux": 100, "notes": f"Depozit/magazie {room.name}, 100 lux.",
            })
            idx_ilm += 1
            circuits.append({
                "id": f"C_PRZ_{idx_prz:02d}", "panel": "TG",
                "usage": f"Priza forta {room.name}",
                "type": "prize", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                "notes": f"1 priza forta {room.name}.",
            })
            idx_prz += 1
            total_power_w += area * 10 + 500

        else:
            circuits.append({
                "id": f"C_ILM_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "notes": f"Iluminat general {room.name}.",
            })
            idx_ilm += 1
            total_power_w += area * 15

    if has_evacuation_zone:
        circuits.append({
            "id": "C_IL_EV", "panel": "TG",
            "usage": "Iluminat evacuare",
            "type": "iluminat_evacuare", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
            "notes": "Iluminat de evacuare cu baterie backup, circuit separat. Obligatoriu P118.",
        })

    total_power_kw = total_power_w / 1000.0
    is_three_phase = total_power_kw > 15
    bransament_note = (
        f"Bransament trifazat obligatoriu (putere estimata {total_power_kw:.1f} kW > 15 kW)."
        if is_three_phase
        else f"Bransament monofazat (putere estimata {total_power_kw:.1f} kW)."
    )
    circuits.insert(0, {
        "id": "TG_INTRARE", "panel": "TG",
        "usage": "Tablou general – intrare",
        "type": "tablou", "breaker_a": 63, "cable": "—",
        "notes": f"MCB 3P 63A tip C, RCCB 63A/300mA pe intrare. {bransament_note}",
    })
    return circuits


# -------------------------------------------------
#  HALE INDUSTRIALE
# -------------------------------------------------


def calc_industrial_circuits(data: ProjectData) -> List[dict]:
    circuits = []
    idx_ilm = idx_f16 = idx_f32 = idx_mot = 1
    total_power_kw = 0.0
    ip_zone = data.ip_zone if data.ip_zone not in ("IP20", "") else "IP65"

    for room in data.rooms:
        func = room.function
        area = room.area_m2

        if func == "production":
            circuits.append({
                "id": f"C_ILM_HAL_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat hala {room.name}",
                "type": "iluminat", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                "ip": ip_zone, "lux": 300,
                "notes": f"Corpuri industriale {ip_zone}, 300 lux. {room.name}.",
            })
            idx_ilm += 1
            for _ in range(max(1, math.ceil(area / 60))):
                circuits.append({
                    "id": f"C_PRZ_F16_{idx_f16:02d}", "panel": "TG",
                    "usage": f"Prize forta 16A {room.name}",
                    "type": "prize_forta", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                    "notes": f"Prize forta monofazat, max 6 prize/circuit. {room.name}.",
                })
                idx_f16 += 1
            circuits.append({
                "id": f"C_PRZ_F32_{idx_f32:02d}", "panel": "TG",
                "usage": f"Prize forta trifazat {room.name}",
                "type": "prize_forta_tri", "phase": "tri", "breaker_a": 32, "cable": "5x6 mm²",
                "notes": f"Prize CEE 32A trifazat {room.name}.",
            })
            idx_f32 += 1
            total_power_kw += area * 0.3 + area * 0.06

        elif func == "warehouse":
            circuits.append({
                "id": f"C_ILM_HAL_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat depozit {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "ip": "IP44", "lux": 150,
                "notes": f"Iluminat depozit IP44, 150 lux. {room.name}.",
            })
            idx_ilm += 1
            circuits.append({
                "id": f"C_PRZ_F16_{idx_f16:02d}", "panel": "TG",
                "usage": f"Prize forta {room.name}",
                "type": "prize_forta", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                "notes": f"Prize forta dispersate depozit {room.name}.",
            })
            idx_f16 += 1
            total_power_kw += area * 0.015

        elif func == "compressor":
            circuits.append({
                "id": "C_AIR_COMP", "panel": "TM",
                "usage": f"Forta compresoare {room.name}",
                "type": "forta", "phase": "tri", "breaker_a": 32, "cable": "5x6 mm²",
                "notes": f"Circuit dedicat trifazat 32A compresoare {room.name}.",
            })
            total_power_kw += 7.5

        elif func in ["office", "office_ind", "day", "night", "bathroom", "kitchen"]:
            circuits.append({
                "id": f"C_ILM_HAL_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat birou {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "notes": f"Birou industrial {room.name} – standard rezidential.",
            })
            idx_ilm += 1
            circuits.append({
                "id": f"C_PRZ_F16_{idx_f16:02d}", "panel": "TG",
                "usage": f"Prize birou {room.name}",
                "type": "prize", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
                "rcd_30ma": True, "notes": f"Prize birou {room.name}.",
            })
            idx_f16 += 1
            total_power_kw += area * 0.05

        elif func == "electrical":
            pass  # Camera electrica — nu necesita circuite proprii

        else:
            circuits.append({
                "id": f"C_ILM_HAL_{idx_ilm:02d}", "panel": "TG",
                "usage": f"Iluminat {room.name}",
                "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
                "notes": f"Iluminat {room.name}.",
            })
            idx_ilm += 1

    # Motoare electrice → tablou motoare (TM)
    motor_circuits = []
    motors_power_kw = 0.0
    if data.motors:
        for motor in data.motors:
            for _ in range(motor.count):
                if motor.phase == "tri":
                    inom = motor.power_kw * 1000 / (math.sqrt(3) * 400 * 0.85)
                else:
                    inom = motor.power_kw * 1000 / (230 * 0.85)
                mcb_a = next_mcb(2.5 * inom)
                section = cable_for_current(inom * 1.25)
                phase_str = "trifazat" if motor.phase == "tri" else "monofazat"
                prefix = "5" if motor.phase == "tri" else "3"
                motor_circuits.append({
                    "id": f"C_MOT_{idx_mot:02d}", "panel": "TM",
                    "usage": f"Motor {motor.name}",
                    "type": "motor", "phase": phase_str,
                    "power_kw": motor.power_kw,
                    "current_nominal_a": round(inom, 1),
                    "breaker_a": mcb_a, "cable": f"{prefix}x{section} mm²",
                    "notes": (
                        f"Motor {motor.name}, {motor.power_kw} kW {phase_str}. "
                        f"Inom={inom:.1f}A, MCB={mcb_a}A."
                    ),
                })
                idx_mot += 1
                motors_power_kw += motor.power_kw

    if data.has_overhead_crane:
        motor_circuits.append({
            "id": "C_MACARA", "panel": "TM", "usage": "Pod rulant (macara)",
            "type": "forta", "phase": "trifazat", "breaker_a": 63, "cable": "5x16 mm²",
            "notes": "Circuit dedicat pod rulant, trifazat 63A.",
        })
        motors_power_kw += 15

    if data.has_compressed_air and not any(r.function == "compressor" for r in data.rooms):
        motor_circuits.append({
            "id": "C_AIR", "panel": "TM", "usage": "Instalatie aer comprimat",
            "type": "forta", "phase": "trifazat", "breaker_a": 32, "cable": "5x6 mm²",
            "notes": "Circuit trifazat 32A pentru compresor aer.",
        })
        motors_power_kw += 5.5

    total_power_kw += motors_power_kw
    demand_kw = total_power_kw * 0.7  # coeficient simultaneitate

    circuits.insert(0, {
        "id": "TG_INTRARE", "panel": "TG",
        "usage": "Tablou general industrial – intrare",
        "type": "tablou", "breaker_a": 125, "cable": "—",
        "notes": (
            f"TG principal. Putere instalata estimata: {total_power_kw:.1f} kW, "
            f"cerere de calcul (ks=0.7): {demand_kw:.1f} kW."
        ),
    })
    if motor_circuits:
        circuits.append({
            "id": "TM_INTRARE", "panel": "TM", "usage": "Tablou motoare – intrare",
            "type": "tablou", "breaker_a": 63, "cable": "5x16 mm²",
            "notes": f"Tablou motoare separat de TG. Putere motoare: {motors_power_kw:.1f} kW.",
        })
        circuits.extend(motor_circuits)

    return circuits


# -------------------------------------------------
#  BLOCURI DE LOCUINTE
# -------------------------------------------------


def calc_bloc_circuits(data: ProjectData) -> List[dict]:
    circuits = []
    floors = data.floors or 4
    apts_per_floor = data.apartments_per_floor or 4
    total_apts = floors * apts_per_floor

    i_apart = total_apts * 25 * 0.6
    i_services = 0
    if data.has_elevator:
        i_services += 32
    if data.has_fire_pump:
        i_services += 32
    i_total = i_apart + i_services + 16  # +16 pentru servicii comune
    tgb_mcb = next_mcb(i_total)

    circuits.append({
        "id": "TGB_INTRARE", "panel": "TGB",
        "usage": "Tablou general bloc – intrare",
        "type": "tablou", "breaker_a": tgb_mcb, "cable": "—",
        "notes": (
            f"TGB: {total_apts} apartamente × 25A × 0.6 + servicii = {i_total:.0f}A → MCB {tgb_mcb}A. "
            f"Structura: TE → TGB → TE_01..TE_{floors:02d} → TA."
        ),
    })

    for f in range(1, floors + 1):
        te_mcb = next_mcb(apts_per_floor * 25 * 0.8)
        circuits.append({
            "id": f"TE_{f:02d}", "panel": "TGB",
            "usage": f"Tablou etaj {f}",
            "type": "tablou_etaj", "breaker_a": te_mcb, "cable": "NYY 5x10 mm²",
            "notes": f"Tablou etaj {f}: {apts_per_floor} apartamente, MCB {te_mcb}A.",
        })

    circuits.append({
        "id": "C_ILM_COM", "panel": "TGB", "usage": "Iluminat comun scari",
        "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
        "notes": "Iluminat scari/holuri comune cu senzor de miscare, MCB 10A.",
    })
    circuits.append({
        "id": "C_ILM_SUB", "panel": "TGB", "usage": "Iluminat subsol/parcare",
        "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
        "notes": "Iluminat subsol si parcare, MCB 10A.",
    })
    circuits.append({
        "id": "C_PRIZE_COM", "panel": "TGB", "usage": "Prize comune",
        "type": "prize", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
        "rcd_30ma": True,
        "notes": "Prize curierat, curatenie, intretinere.",
    })

    if data.has_elevator:
        circuits.append({
            "id": "C_LIFT", "panel": "TGB", "usage": "Lift",
            "type": "forta", "phase": "trifazat", "breaker_a": 32, "cable": "5x6 mm²",
            "notes": "Circuit dedicat lift trifazat, MCB 3P 32A. Dimensionare finala din fisa tehnica ascensor.",
        })

    if data.has_fire_pump:
        circuits.append({
            "id": "C_POMP_INC", "panel": "TGB", "usage": "Pompa incendiu",
            "type": "forta", "phase": "trifazat", "breaker_a": 32, "cable": "5x6 mm²",
            "priority": True,
            "notes": "Circuit prioritar pompa incendiu, trifazat 32A. Alimentat direct din TGB fara intrerupere automata.",
        })

    circuits.append({
        "id": "TA_STANDARD", "panel": "TA",
        "usage": "Tablou apartament – model standard",
        "type": "tablou_apartament", "breaker_a": 25, "cable": "NYY 3x6 mm²",
        "notes": (
            f"Model TA: MCB principal 25A. "
            f"Circuite interne: iluminat 3x10A, prize 3x16A, bucatarie 2x20A, baie 16A."
        ),
    })

    return circuits


# -------------------------------------------------
#  COMERCIAL
# -------------------------------------------------


def calc_comercial_circuits(data: ProjectData) -> List[dict]:
    circuits = []
    btype = data.building.type.lower()

    circuits.append({
        "id": "TG_INTRARE", "panel": "TG",
        "usage": "Tablou general comercial – intrare",
        "type": "tablou", "breaker_a": 63, "cable": "—",
        "notes": "TG principal. MCB 3P 63A, RCCB 300mA. Alimentare TC (tablou comercial) + TT (tablou tehnic).",
    })
    circuits.append({
        "id": "TC_INTRARE", "panel": "TC",
        "usage": "Tablou comercial",
        "type": "tablou", "breaker_a": 40, "cable": "5x10 mm²",
        "notes": "Tablou comercial separat de tabloul tehnic (TT).",
    })
    circuits.append({
        "id": "C_ILM_GEN", "panel": "TC",
        "usage": "Iluminat general",
        "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
        "lux": 500, "notes": "Iluminat general spatiu comercial, 500 lux.",
    })

    if any(k in btype for k in ["magazin", "retail", "comercial"]):
        circuits.append({
            "id": "C_VITRINE", "panel": "TC", "usage": "Iluminat vitrine",
            "type": "iluminat", "breaker_a": 10, "cable": "NYM 3x1,5 mm²",
            "notes": "Circuit iluminat vitrine, dimabil, separat de iluminatul general.",
        })
        circuits.append({
            "id": "C_CASA", "panel": "TC", "usage": "Casa de marcat + UPS",
            "type": "prize", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
            "notes": "Circuit dedicat casa de marcat + UPS mic, MCB 16A.",
        })
        circuits.append({
            "id": "C_PRZ_COM", "panel": "TC", "usage": "Prize comerciale generale",
            "type": "prize", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
            "rcd_30ma": True, "notes": "Prize generale spatiu comercial, RCCB 30mA.",
        })

    if any(k in btype for k in ["restaurant", "bar"]):
        circuits.append({
            "id": "C_BUCATARIE", "panel": "TC", "usage": "Forta bucatarie industriala",
            "type": "forta", "phase": "tri", "breaker_a": 63, "cable": "5x10 mm²",
            "notes": "Bucatarie industriala trifazat 63A, 5x10mm². Tablou dedicat recomandat.",
        })
        circuits.append({
            "id": "C_SALON", "panel": "TC", "usage": "Iluminat + prize salon",
            "type": "mixt", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
            "notes": "Salon restaurant: iluminat + prize, ambiant dimabil.",
        })
        circuits.append({
            "id": "C_TERASA", "panel": "TC", "usage": "Terasa (IP44)",
            "type": "ip44", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
            "ip": "IP44", "rcd_30ma": True, "notes": "Circuit terasa exterior IP44, RCCB 30mA.",
        })

    if "hotel" in btype:
        room_count = len(data.rooms) if data.rooms else 10
        circuits.append({
            "id": "C_CAMERE", "panel": "TC",
            "usage": f"Circuite camere hotel ({room_count} camere)",
            "type": "prize", "breaker_a": 12, "cable": "NYM 3x2,5 mm²",
            "notes": f"{room_count} camere × 12A. Fiecare camera pe MCB dedicat prin tablou etaj.",
        })
        circuits.append({
            "id": "C_RECEPTIE", "panel": "TC", "usage": "Receptie + back-office",
            "type": "prize", "breaker_a": 20, "cable": "NYM 3x2,5 mm²",
            "notes": "Receptie hotel: prize, calculator, imprimanta, casa.",
        })
        circuits.append({
            "id": "C_LIFT_H", "panel": "TG", "usage": "Lift hotel",
            "type": "forta", "phase": "trifazat", "breaker_a": 32, "cable": "5x6 mm²",
            "notes": "Circuit lift hotel trifazat 32A.",
        })

    if "mall" in btype:
        circuits.append({
            "id": "C_ANCHOR", "panel": "TG",
            "usage": "Anchor stores (magazine ancorare)",
            "type": "forta", "phase": "trifazat", "breaker_a": 125, "cable": "5x35 mm²",
            "notes": "Circuite anchor stores separate, trifazat 125A. Contorizare individuala.",
        })
        circuits.append({
            "id": "C_CIRCULATII", "panel": "TG", "usage": "Circulatii + iluminat comun",
            "type": "iluminat", "breaker_a": 40, "cable": "NYM 3x10 mm²",
            "notes": "Iluminat circulatii mall, coridoare, zone comune.",
        })
        circuits.append({
            "id": "C_PARCARE", "panel": "TG", "usage": "Parcare",
            "type": "iluminat", "breaker_a": 20, "cable": "NYM 3x4 mm²", "ip": "IP44",
            "notes": "Iluminat parcare IP44, senzori de miscare.",
        })

    if not any(k in btype for k in ["magazin", "retail", "restaurant", "bar", "hotel", "mall", "comercial"]):
        circuits.append({
            "id": "C_PRZ_COM", "panel": "TC", "usage": "Prize spatiu comercial",
            "type": "prize", "breaker_a": 16, "cable": "NYM 3x2,5 mm²",
            "rcd_30ma": True, "notes": "Prize generale spatiu comercial, RCCB 30mA.",
        })

    return circuits


# -------------------------------------------------
#  MEMORIU TEHNIC ADAPTAT
# -------------------------------------------------


def build_memoriu(
    data: ProjectData,
    climate_zone: str,
    building_category: str,
    pdc_circuit: Optional[dict],
    boiler_circuit: Optional[dict],
    pump_circuit: Optional[dict],
    ventilation_circuit: Optional[dict],
    room_results: List[dict],
    circuits_main: List[dict],
    circuits_secondary: Optional[List[dict]] = None,
) -> str:
    lines = []
    b = data.building
    h = data.heating
    cat_label = CATEGORY_LABELS.get(building_category, building_category.title())

    # Height regime
    levels_str = data.levels_string or b.levels or "P"
    has_basement = data.has_basement or False
    floors_above = data.floors_above_ground or 0
    has_attic = data.has_attic or False
    num_levels = 1 + floors_above + (1 if has_attic else 0) + (1 if has_basement else 0)

    # Climate
    temp_ext = ZONE_TEMP.get(climate_zone, -15)
    snow_load = SNOW_LOAD_BY_ZONE.get(climate_zone, 1.5)
    climate_source = data.climate_source or b.climate_source
    climate_auto = data.climate_auto_detected or False

    lines.append(f"MEMORIU TEHNIC — INSTALATIE ELECTRICA {cat_label.upper()}")
    lines.append("=" * 60)
    lines.append("")

    # ── 1. DATE GENERALE ──────────────────────────────────────────────────────
    lines.append("1. DATE GENERALE")
    lines.append(f"Proiect: {data.project_id}")
    lines.append(f"Tip cladire: {b.type}, categorie: {cat_label}.")
    lines.append(f"Regim de inaltime: {levels_str}")
    lines.append(f"Numar niveluri: {num_levels}")
    lines.append(f"Suprafata utila totala: {b.total_area_m2} mp")
    lines.append(f"Volum incalzit: {b.total_volume_m3} mc")
    if b.main_entrance:
        lines.append(f"Intrare principala: {b.main_entrance}.")
    lines.append(f"Izolatie termica: {b.insulation_level}.")
    lines.append("")

    # ── 2. DATE CLIMATICE ─────────────────────────────────────────────────────
    lines.append("2. DATE CLIMATICE SI DE AMPLASAMENT")
    lines.append(f"Zona climatica: {climate_zone} conform C107/2005")
    lines.append(f"Temperatura exterioara de calcul: {temp_ext}°C")
    lines.append(f"Zona de vant: conform CR 1-1-4/2012")
    lines.append(f"Zona de zapada: {snow_load} kN/mp conform CR 1-1-3/2012")
    if climate_auto and climate_source:
        lines.append(f"Detectat automat din: {climate_source}")
    lines.append("")

    # ── 3. BAZA DE PROIECTARE ─────────────────────────────────────────────────
    lines.append("3. BAZA DE PROIECTARE")
    base_normative = [
        "I7/2011 — Normativ privind proiectarea, executia si exploatarea instalatiilor electrice",
        "NP 061-2002 — Normativ pentru proiectarea si executarea sistemelor de iluminat",
        "C107/2005 — Normativ privind calculul termotehnic al elementelor de constructie ale cladirilor",
        "CR 1-1-3/2012 — Evaluarea actiunii zapezii asupra constructiilor",
        "CR 1-1-4/2012 — Cod de proiectare. Evaluarea actiunii vantului",
        "P118/1999 — Norme de siguranta la foc",
        "SR EN 61439 — Tablouri electrice de joasa tensiune",
    ]
    category_extra_norms: dict = {
        "public":     [
            "SR EN 12464-1 — Cerinte de iluminat pentru locuri de munca in interior",
            "PE 003/1979 — Normativ privind utilizarea rationala a energiei electrice",
        ],
        "industrial": [
            "SR EN 60529 — Grade de protectie asigurate prin carcase (cod IP)",
            "SR EN 60204-1 — Siguranta masinilor. Echipament electric al masinilor",
        ],
        "bloc":       [
            "SR EN 50522 — Punerea la pamant a instalatiilor electrice",
            "NP 061-2002 — Proiectarea si executarea sistemelor de iluminat artificial",
        ],
        "comercial":  [
            "NP 031 — Normativ pentru proiectarea, executia si exploatarea constructiilor si instalatiilor aferente spatiilor comerciale",
        ],
    }
    for norm in base_normative:
        lines.append(f"- {norm}")
    for norm in category_extra_norms.get(building_category, []):
        lines.append(f"- {norm}")
    lines.append("")

    # ── 4. SISTEM TERMOENERGETIC ──────────────────────────────────────────────
    heating_labels = {
        "pdc_air_water":    "Pompa de caldura aer-apa",
        "pdc_air_air":      "Pompa de caldura aer-aer",
        "pdc_ground_water": "Pompa de caldura sol-apa (geotermala)",
        "gas_boiler":       "Centrala pe gaz",
        "electric_boiler":  "Centrala electrica",
        "geothermal":       "Sistem geothermal",
        "district_heating": "Termoficare (retea urbana)",
        "existing":         "Sistem existent (fara modificari)",
        "none":             "Fara incalzire centralizata",
    }
    dist_labels = {
        "floor_heating":     "incalzire in pardoseala",
        "fan_coil":          "ventiloconvector",
        "electric_radiator": "radiator electric",
        "radiant_ceiling":   "tavan radiant",
        "existing":          "sistem existent",
    }
    lines.append("4. SISTEM TERMOENERGETIC")
    lines.append(f"Tip generare caldura: {heating_labels.get(h.type, h.type)}.")
    if data.heating_distribution:
        lines.append(f"Tip distributie caldura: {dist_labels.get(data.heating_distribution, data.heating_distribution)}.")
    if pdc_circuit:
        lines.append(
            f"Circuit PDC: {pdc_circuit['power_kw_thermal']} kW termica, "
            f"{pdc_circuit['power_kw_electric']} kW electrica, "
            f"MCB {pdc_circuit['breaker_a']}A, cablu {pdc_circuit['cable']}."
        )
    if boiler_circuit:
        lines.append(f"Boiler ACM: {boiler_circuit['power_kw']} kW, MCB {boiler_circuit['breaker_a']}A.")
    if ventilation_circuit:
        lines.append(f"Ventilatie/HRV: MCB {ventilation_circuit['breaker_a']}A.")
    lines.append("")

    # ── 5. SPECIFICATII CATEGORIE ─────────────────────────────────────────────
    if building_category == "public":
        lines.append("5. SPECIFICATII CLADIRE PUBLICA")
        lines.append("- Iluminat de siguranta/evacuare obligatoriu conform P118-99.")
        lines.append("- Niveluri de iluminare conform SR EN 12464-1.")
        lines.append("- Protectie diferentiala 10mA in zone umede (grupuri sanitare).")
        lines.append("")
    elif building_category == "industrial":
        lines.append("5. SPECIFICATII HALA INDUSTRIALA")
        lines.append(f"- Grad de protectie echipamente: {data.ip_zone or 'IP65'}.")
        if data.has_explosive_zone:
            lines.append("- ATENTIE: Zone cu pericol de explozie (ATEX) — conform SR EN 60079.")
        if data.has_overhead_crane:
            lines.append("- Pod rulant: circuit dedicat trifazat 63A, conform SR EN 60204.")
        if data.has_compressed_air:
            lines.append("- Instalatie aer comprimat: circuit trifazat 32A.")
        lines.append("")
    elif building_category == "bloc":
        lines.append("5. SPECIFICATII BLOC DE LOCUINTE")
        lines.append(f"- Numar etaje: {data.floors or '?'}, apartamente/etaj: {data.apartments_per_floor or '?'}.")
        lines.append("- Structura: TE → TGB → Tablouri etaj → Tablouri apartament.")
        if data.has_elevator:
            lines.append("- Lift: circuit dedicat trifazat, conform EN 81.")
        if data.has_fire_pump:
            lines.append("- Pompa incendiu: circuit prioritar trifazat, nu se intrerupe automat.")
        lines.append("")
    elif building_category == "comercial":
        lines.append("5. SPECIFICATII SPATIU COMERCIAL")
        lines.append("- Tablou comercial (TC) separat de tabloul tehnic (TT).")
        lines.append("- Iluminat vitrine pe circuit separat dimabil.")
        lines.append("- Casa de marcat pe circuit dedicat cu UPS.")
        lines.append("")

    # ── 6. CAMERE ─────────────────────────────────────────────────────────────
    if room_results:
        lines.append("6. REZUMAT CAMERE")
        for r in room_results:
            lines.append(f"- {r['name']} ({r['area_m2']} mp):")
            for s in r.get("sockets", []):
                lines.append(f"    . {s['type']} x{s['count']} la h~{s['height_m']}m ({s['notes']})")
            for lgt in r.get("lights", []):
                lines.append(f"    . Iluminat: {lgt['type']} x{lgt['count']} ({lgt['notes']})")
        lines.append("")

    # ── 7. CIRCUITE ELECTRICE ─────────────────────────────────────────────────
    if circuits_main:
        lines.append("7. LISTA CIRCUITE PRINCIPALE")
        for c in circuits_main:
            lines.append(
                f"  - {c['id']}: {c.get('usage', '?')} — MCB {c.get('breaker_a', '?')}A, "
                f"cablu {c.get('cable', '?')}. {c.get('notes', '')}"
            )
        lines.append("")

    if circuits_secondary:
        lines.append("7b. CIRCUITE TABLOU TERMIC (TE-CT)")
        for c in circuits_secondary:
            lines.append(
                f"  - {c['id']}: {c.get('usage', '?')} — MCB {c.get('breaker_a', '?')}A, "
                f"cablu {c.get('cable', '?')}."
            )
        lines.append("")

    # ── 8. ECHIPAMENTE SPECIALE ───────────────────────────────────────────────
    if data.extra_equipment:
        active = [e for e in data.extra_equipment if e.type != "internet"]
        if active:
            lines.append("8. ECHIPAMENTE SPECIALE")
            for eq in active:
                phase_lbl = "trifazat" if eq.phase == "tri" else "monofazat"
                if eq.power_kw > 0:
                    lines.append(f"  - {eq.name}: {eq.power_kw} kW {phase_lbl}, circuit dedicat.")
                else:
                    lines.append(f"  - {eq.name}: circuit dedicat.")
            lines.append("")

    lines.append("Toate circuitele vor fi verificate si dimensionate definitiv conform normativelor in vigoare.")
    return "\n".join(lines)


# -------------------------------------------------
#  ENDPOINT PRINCIPAL
# -------------------------------------------------


@app.post("/calc-electric")
def calc_electric(data: ProjectData):
    climate_zone = resolve_climate_zone_from_data(data)
    building_category = data.building_category or detect_building_category(data.building.type)

    pdc_power_kw = calc_pdc_power_kw(data.building, data.heating, climate_zone)
    pdc_phase = data.heating.pdc_phase or "tri"
    pdc_circuit = (
        choose_pdc_circuit(power_kw=pdc_power_kw, phase=pdc_phase, pdc_type=data.heating.type)
        if pdc_power_kw > 0 else None
    )
    boiler_circuit = choose_boiler_circuit(data.building, data.heating)
    pump_circuit = (
        choose_pump_circuit()
        if data.heating.type in ["pdc_air_water", "gas_boiler", "electric_boiler", "geothermal"]
        else None
    )
    ventilation_circuit = choose_ventilation_circuit(data.heating)
    room_results = [calc_room_electrics(r) for r in data.rooms]

    if building_category == "public":
        circuits_teg = calc_public_circuits(data)
        circuits_te_ct = build_circuits_te_ct(
            pdc_circuit, boiler_circuit, pump_circuit, ventilation_circuit, data.has_floor_heating
        )
    elif building_category == "industrial":
        circuits_teg = calc_industrial_circuits(data)
        circuits_te_ct = build_circuits_te_ct(
            pdc_circuit, boiler_circuit, pump_circuit, ventilation_circuit, data.has_floor_heating
        )
    elif building_category == "bloc":
        circuits_teg = calc_bloc_circuits(data)
        circuits_te_ct = []
    elif building_category == "comercial":
        circuits_teg = calc_comercial_circuits(data)
        circuits_te_ct = build_circuits_te_ct(
            pdc_circuit, boiler_circuit, pump_circuit, ventilation_circuit, data.has_floor_heating
        )
    else:
        # rezidential (default)
        circuits_te_ct = build_circuits_te_ct(
            pdc_circuit, boiler_circuit, pump_circuit, ventilation_circuit, data.has_floor_heating
        )
        circuits_teg = build_circuits_teg(data)

    # Extra equipment circuits (boiler, AC, EV charger, solar, HRV…)
    extra_circuits: List[dict] = []
    if data.extra_equipment:
        extra_circuits = calc_extra_equipment_circuits(data.extra_equipment)

    circuits_all = circuits_te_ct + circuits_teg + extra_circuits

    memoriu = build_memoriu(
        data=data,
        climate_zone=climate_zone,
        building_category=building_category,
        pdc_circuit=pdc_circuit,
        boiler_circuit=boiler_circuit,
        pump_circuit=pump_circuit,
        ventilation_circuit=ventilation_circuit,
        room_results=room_results,
        circuits_main=circuits_teg,
        circuits_secondary=circuits_te_ct if circuits_te_ct else None,
    )

    return {
        "project_id": data.project_id,
        "status": "success",
        "building_category": building_category,
        "climate_zone": climate_zone,
        "climate_source": data.building.climate_source,
        "levels_string": data.building.levels,
        "heating_circuits": {
            "pdc": pdc_circuit,
            "boiler": boiler_circuit,
            "pump": pump_circuit,
            "ventilation": ventilation_circuit,
        },
        "rooms": room_results,
        "circuits_te_ct": circuits_te_ct,
        "circuits_teg": circuits_teg,
        "circuits_extra": extra_circuits,
        "circuits_all": circuits_all,
        "memoriu_tehnic": memoriu,
    }


# -------------------------------------------------
#  ADNOTARE PLAN
# -------------------------------------------------

class RoomWithCircuits(BaseModel):
    name: str
    function: str
    bbox: Optional[dict] = None  # {x, y, w, h} in pixels
    sockets: Optional[List[dict]] = None
    lights: Optional[List[dict]] = None


class AnnotatePlanRequest(BaseModel):
    plan_base64: str   # raw base64 (no data: prefix) OR data:image/...;base64,...
    plan_type: str = "image/png"
    rooms_with_circuits: List[RoomWithCircuits]
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None


@app.post("/annotate-plan")
def annotate_plan(req: AnnotatePlanRequest):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return {"error": "Pillow not installed"}

    # Decode image
    b64 = req.plan_base64
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    img_bytes = base64.b64decode(b64)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    for room in req.rooms_with_circuits:
        bbox = room.bbox
        if not bbox:
            continue
        cx = int(bbox.get("x", 0) + bbox.get("w", 0) / 2)
        cy = int(bbox.get("y", 0) + bbox.get("h", 0) / 2)

        socket_count = sum(s.get("count", 0) for s in (room.sockets or []))
        light_count  = sum(l.get("count", 0) for l in (room.lights or []))

        # Draw light symbol: blue circle + cross
        if light_count > 0:
            r = 12
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         outline="#3B82F6", fill=(59, 130, 246, 60), width=2)
            draw.line([cx - r + 3, cy, cx + r - 3, cy], fill="#3B82F6", width=2)
            draw.line([cx, cy - r + 3, cx, cy + r - 3], fill="#3B82F6", width=2)

        # Draw socket symbol: orange circle + 2 horizontal lines
        if socket_count > 0:
            ox = cx + (16 if light_count > 0 else 0)
            oy = cy
            r = 10
            draw.ellipse([ox - r, oy - r, ox + r, oy + r],
                         outline="#F59E0B", fill=(245, 158, 11, 60), width=2)
            draw.line([ox - 5, oy - 3, ox + 5, oy - 3], fill="#F59E0B", width=2)
            draw.line([ox - 5, oy + 3, ox + 5, oy + 3], fill="#F59E0B", width=2)

        # Draw panel symbol for technical rooms: green square
        if room.function in ("technical", "electrical"):
            sx, sy, sw, sh = int(bbox["x"]) + 4, int(bbox["y"]) + 4, 20, 20
            draw.rectangle([sx, sy, sx + sw, sy + sh],
                           fill=(34, 197, 94, 200), outline="#22C55E", width=2)

        # Draw switch symbol for circulation/hall: red semicircle
        if room.function in ("circulation", "hall"):
            r = 10
            bx = int(bbox["x"]) + 4
            by = int(bbox["y"]) + 4
            draw.arc([bx - r, by - r, bx + r, by + r], 0, 180,
                     fill="#EF4444", width=2)

    # Encode result
    out = io.BytesIO()
    img.save(out, format="PNG")
    encoded = base64.b64encode(out.getvalue()).decode()
    return {"annotated_plan_base64": f"data:image/png;base64,{encoded}"}


# -------------------------------------------------
#  SCHEMĂ MONOFILARĂ (POST /generate-schema)
# -------------------------------------------------

class CircuitSchema(BaseModel):
    nr: int
    faza: str = "R"
    tip: str = "iluminat"
    destinatie: str
    Pi_kW: float = 0.0
    Ia_A: float = 0.0
    protectie: str = ""
    diferential: bool = False
    afdd: bool = False
    cablu: str = ""
    pozare: str = ""
    nr_corpuri: int = 0
    simbol: str = ""


class TablouInfo(BaseModel):
    name: str
    Pi: float = 0.0
    Pa: float = 0.0
    Ia: float = 0.0
    alimentare_kv: str = "0.4"
    protectie_generala: str = ""


class ProjectInfoSchema(BaseModel):
    beneficiar: str = ""
    titlu_proiect: str = ""
    adresa: str = ""
    proiect_nr: str = ""
    data: str = ""
    faza: str = "DTAC"


class GenerateSchemaRequest(BaseModel):
    project_info: Optional[ProjectInfoSchema] = None
    tablou: TablouInfo
    circuits: List[CircuitSchema]


def _build_schema_pdf(req: GenerateSchemaRequest) -> bytes:
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A3
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor, white
    except ImportError:
        raise RuntimeError("reportlab not installed")

    circuits = req.circuits
    N = len(circuits)
    tablou = req.tablou
    pinfo = req.project_info or ProjectInfoSchema()

    buf = io.BytesIO()
    pw, ph = A3[1], A3[0]   # A3 landscape: 1190.55 × 841.89 pt
    c = rl_canvas.Canvas(buf, pagesize=(pw, ph))

    # ── Nested drawing helpers (close over c, mm, white)
    def draw_mcb(cx, cy, w, h, color):
        c.setFillColor(white); c.setStrokeColor(color); c.setLineWidth(0.8)
        c.rect(cx - w / 2, cy - h / 2, w, h, fill=1, stroke=1)
        c.line(cx - w / 2 + 0.5, cy + h / 2 - 0.5, cx + w / 2 - 0.5, cy - h / 2 + 0.5)

    def draw_rcd(cx, cy, r, color):
        c.setFillColor(white); c.setStrokeColor(color); c.setLineWidth(0.8)
        c.circle(cx, cy, r, fill=1, stroke=1)
        c.setFillColor(color); c.setFont("Helvetica", max(4.0, r * 0.85))
        c.drawCentredString(cx, cy - r * 0.38, "Δ")

    # ── Colors
    TIP_COL = {
        "iluminat":   HexColor("#1E40AF"),
        "prize":      HexColor("#D97706"),
        "alimentare": HexColor("#15803D"),
        "forta":      HexColor("#15803D"),
        "rezerva":    HexColor("#6B7280"),
        "motoare":    HexColor("#15803D"),
    }
    C_BORDER  = HexColor("#1E293B")
    C_HEADER  = HexColor("#0F172A")
    C_BUSBAR  = HexColor("#F59E0B")
    C_TEXT    = HexColor("#334155")
    C_DIM     = HexColor("#94A3B8")
    C_ROW_ALT = HexColor("#F8FAFC")
    C_TBL_LN  = HexColor("#CBD5E1")

    # ── Layout constants (all in mm; y measured from bottom-left)
    ML, MR, MT, MB = 12, 12, 10, 10
    PH_mm = 297; PW_mm = 420
    CX = ML; CW = PW_mm - ML - MR   # 396 mm content width

    HDR_H   = 30
    HDR_BOT = PH_mm - MT - HDR_H    # 257 mm — bottom of header
    BUS_Y   = HDR_BOT - 20          # 237 mm — busbar y
    BR_BOT  = MB + 100              # 110 mm — branch bottom
    TBL_TOP = BR_BOT - 5            # 105 mm — table top
    TBL_BOT = MB + 22               # 32 mm  — table bottom
    FTR_TOP = TBL_BOT               # 32 mm  — footer top
    FTR_BOT = MB                    # 10 mm  — footer bottom

    # ── Branch geometry
    PITCH = min(25.0, CW / max(N, 1))
    PITCH = max(PITCH, 10.0)
    TOT_BW = PITCH * N
    BX0 = CX + (CW - TOT_BW) / 2   # leftmost branch center x (mm)

    def bx(i):
        return BX0 + (i + 0.5) * PITCH

    # ── Outer border
    c.setStrokeColor(C_BORDER); c.setLineWidth(1.5)
    c.rect(ML * mm, MB * mm, CW * mm, (PH_mm - MT - MB) * mm)

    # ── Header background
    c.setFillColor(C_HEADER); c.setStrokeColor(C_HEADER)
    c.rect(ML * mm, HDR_BOT * mm, CW * mm, HDR_H * mm, fill=1, stroke=0)

    # Header text
    c.setFillColor(white); c.setFont("Helvetica-Bold", 13)
    c.drawString((ML + 5) * mm, (HDR_BOT + 18) * mm,
                 f"SCHEMA MONOFILARA — {tablou.name}")
    c.setFont("Helvetica", 8); c.setFillColor(C_DIM)
    c.drawString((ML + 5) * mm, (HDR_BOT + 10) * mm,
                 f"Pi = {tablou.Pi:.2f} kW   Pa = {tablou.Pa:.2f} kW   "
                 f"Ia = {tablou.Ia:.2f} A   U = {tablou.alimentare_kv} kV   "
                 f"Prot. gen.: {tablou.protectie_generala}")
    info_parts = [
        f"Beneficiar: {pinfo.beneficiar}" if pinfo.beneficiar else "",
        f"Adresa: {pinfo.adresa}" if pinfo.adresa else "",
        f"Proiect: {pinfo.titlu_proiect}" if pinfo.titlu_proiect else "",
    ]
    c.drawString((ML + 5) * mm, (HDR_BOT + 4) * mm,
                 "   ".join(p for p in info_parts if p))

    # ── Incoming feeder (vertical line left of branches)
    feeder_x = max(BX0 - 12, ML + 8)   # mm
    c.setStrokeColor(C_BUSBAR); c.setLineWidth(2.5)
    c.line(feeder_x * mm, HDR_BOT * mm, feeder_x * mm, BUS_Y * mm)

    # General MCB on feeder
    mcb_cy = HDR_BOT - 10   # mm
    draw_mcb(feeder_x * mm, mcb_cy * mm, 5 * mm, 8 * mm, C_BUSBAR)
    c.setFillColor(C_BUSBAR); c.setFont("Helvetica", 6)
    c.drawString((feeder_x + 3) * mm, mcb_cy * mm,
                 (tablou.protectie_generala or "MCB gen.")[:18])

    # ── Busbar (thick horizontal line)
    bus_xl = min(feeder_x, BX0 - 3) * mm
    bus_xr = (BX0 + TOT_BW + 3) * mm
    c.setStrokeColor(C_BUSBAR); c.setLineWidth(5)
    c.line(bus_xl, BUS_Y * mm, bus_xr, BUS_Y * mm)
    c.setFillColor(C_BUSBAR); c.setFont("Helvetica-Bold", 7)
    c.drawString(bus_xl, (BUS_Y + 2) * mm, f"{tablou.alimentare_kv} kV")

    # ── Branches
    for i, circ in enumerate(circuits):
        cx_mm = bx(i)
        color = TIP_COL.get(circ.tip, TIP_COL["rezerva"])

        # Vertical line from busbar to branch bottom
        c.setStrokeColor(color); c.setLineWidth(1.5)
        c.line(cx_mm * mm, BUS_Y * mm, cx_mm * mm, (BR_BOT + 12) * mm)

        # Phase label just below busbar
        c.setFillColor(color); c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(cx_mm * mm, (BUS_Y - 5) * mm, circ.faza)

        # MCB symbol
        sw = min(PITCH * 0.38, 4.5)
        mcb_sym_cy = BUS_Y - 14   # mm
        draw_mcb(cx_mm * mm, mcb_sym_cy * mm, sw * mm, 7 * mm, color)

        # Protection rating label
        prot_tok = ""
        for tok in circ.protectie.split(","):
            tok = tok.strip()
            if any(ch.isdigit() for ch in tok) and "A" in tok:
                prot_tok = tok[:9]; break
        if not prot_tok:
            prot_tok = circ.protectie[:9]
        c.setFillColor(color)
        c.setFont("Helvetica", min(6.0, max(5.0, PITCH * 0.44)))
        c.drawCentredString(cx_mm * mm, (mcb_sym_cy - 3.5 - 2.5) * mm, prot_tok)

        cur_y = mcb_sym_cy - 3.5 - 6   # mm, cursor moving down

        # RCD / differential
        if circ.diferential:
            r_rcd = min(PITCH * 0.22, 3.5)
            cur_y -= r_rcd
            draw_rcd(cx_mm * mm, cur_y * mm, r_rcd * mm, color)
            cur_y -= r_rcd + 2

        # AFDD
        if circ.afdd:
            afs = 3.5
            cur_y -= afs
            c.setFillColor(color); c.setStrokeColor(color); c.setLineWidth(0.5)
            c.rect((cx_mm - afs / 2) * mm, (cur_y - afs / 2) * mm,
                   afs * mm, afs * mm, fill=1, stroke=1)
            c.setFillColor(white); c.setFont("Helvetica-Bold", 5)
            c.drawCentredString(cx_mm * mm, (cur_y - 1.5) * mm, "A")
            cur_y -= afs / 2 + 2

        # Load symbol (fixed position near branch bottom)
        load_y = BR_BOT + 18   # mm
        lr = min(PITCH * 0.28, 4.0)
        c.setStrokeColor(color); c.setLineWidth(1.5)

        if circ.tip == "iluminat":
            c.setFillColor(HexColor("#DBEAFE"))
            c.circle(cx_mm * mm, load_y * mm, lr * mm, fill=1, stroke=1)
            c.line((cx_mm - lr) * mm, load_y * mm, (cx_mm + lr) * mm, load_y * mm)
            c.line(cx_mm * mm, (load_y - lr) * mm, cx_mm * mm, (load_y + lr) * mm)
        elif circ.tip == "prize":
            c.setFillColor(HexColor("#FEF3C7"))
            c.circle(cx_mm * mm, load_y * mm, lr * mm, fill=1, stroke=1)
            c.setLineWidth(1)
            c.line((cx_mm - lr * 0.5) * mm, (load_y + lr * 0.3) * mm,
                   (cx_mm + lr * 0.5) * mm, (load_y + lr * 0.3) * mm)
            c.line((cx_mm - lr * 0.5) * mm, (load_y - lr * 0.3) * mm,
                   (cx_mm + lr * 0.5) * mm, (load_y - lr * 0.3) * mm)
        elif circ.tip in ("alimentare", "forta", "motoare"):
            c.setFillColor(HexColor("#DCFCE7")); c.setStrokeColor(color)
            p = c.beginPath()
            p.moveTo(cx_mm * mm, (load_y + lr) * mm)
            p.lineTo((cx_mm + lr) * mm, load_y * mm)
            p.lineTo((cx_mm + lr * 0.5) * mm, load_y * mm)
            p.lineTo((cx_mm + lr * 0.5) * mm, (load_y - lr) * mm)
            p.lineTo((cx_mm - lr * 0.5) * mm, (load_y - lr) * mm)
            p.lineTo((cx_mm - lr * 0.5) * mm, load_y * mm)
            p.lineTo((cx_mm - lr) * mm, load_y * mm)
            p.close()
            c.drawPath(p, fill=1, stroke=1)
        else:  # rezerva / unknown
            c.setFillColor(HexColor("#F1F5F9")); c.setStrokeColor(color)
            c.setDash([2, 2])
            c.rect((cx_mm - lr) * mm, (load_y - lr) * mm,
                   2 * lr * mm, 2 * lr * mm, fill=1, stroke=1)
            c.setDash([])

        # Count label below load symbol
        if circ.nr_corpuri > 0:
            c.setFillColor(color); c.setFont("Helvetica", 6)
            c.drawCentredString(cx_mm * mm, (load_y - lr - 2.5) * mm,
                                f"\xd7{circ.nr_corpuri}")

        # Circuit number at branch bottom
        c.setFillColor(C_TEXT); c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(cx_mm * mm, (BR_BOT + 5) * mm, str(circ.nr))

    # ── Data table
    hdrs    = ["Nr.", "Faza", "Tip", "Destinatie", "Pi kW", "Ia A",
               "Protectie", "Cablu", "Pozare"]
    col_pct = [0.04, 0.05, 0.07, 0.24, 0.06, 0.06, 0.18, 0.15, 0.15]
    tot_p   = sum(col_pct)
    col_ws  = [p / tot_p * (CW - 4) for p in col_pct]   # widths in mm

    tbl_x  = ML + 2
    tbl_w  = CW - 4
    row_h  = min((TBL_TOP - TBL_BOT) / max(N + 1.5, 2), 6.5)
    row_h  = max(row_h, 3.5)

    # Header row
    hdr_y = TBL_TOP - row_h
    c.setFillColor(C_BORDER)
    c.rect(tbl_x * mm, hdr_y * mm, tbl_w * mm, row_h * mm, fill=1, stroke=0)
    xc = tbl_x
    for hdr, cw_mm in zip(hdrs, col_ws):
        c.setFillColor(white); c.setFont("Helvetica-Bold", 6)
        c.drawString((xc + 0.8) * mm, (hdr_y + 1.2) * mm, hdr)
        xc += cw_mm

    # Data rows
    for i, circ in enumerate(circuits):
        ry = hdr_y - (i + 1) * row_h
        if ry < TBL_BOT:
            break
        c.setFillColor(C_ROW_ALT if i % 2 == 0 else white)
        c.setStrokeColor(C_TBL_LN); c.setLineWidth(0.3)
        c.rect(tbl_x * mm, ry * mm, tbl_w * mm, row_h * mm, fill=1, stroke=1)
        tc = TIP_COL.get(circ.tip, TIP_COL["rezerva"])
        vals = [str(circ.nr), circ.faza, circ.tip[:6],
                circ.destinatie[:32], f"{circ.Pi_kW:.2f}", f"{circ.Ia_A:.2f}",
                circ.protectie[:24], circ.cablu[:20], circ.pozare[:20]]
        xc = tbl_x
        for j, (val, cw_mm) in enumerate(zip(vals, col_ws)):
            c.setFillColor(tc if j in (0, 2) else C_TEXT)
            c.setFont("Helvetica-Bold" if j == 0 else "Helvetica", 6)
            c.drawString((xc + 0.8) * mm, (ry + 1.2) * mm, val)
            xc += cw_mm

    # ── Legend (bottom-left footer)
    leg_x = ML + 2; leg_y = FTR_TOP - 2
    c.setFont("Helvetica-Bold", 7); c.setFillColor(C_TEXT)
    c.drawString(leg_x * mm, (leg_y - 4) * mm, "LEGENDA:")
    for k, (lc, lbl) in enumerate([
        (TIP_COL["iluminat"],   "Iluminat"),
        (TIP_COL["prize"],      "Prize"),
        (TIP_COL["alimentare"], "Alimentare / Forta"),
        (TIP_COL["rezerva"],    "Rezerva"),
    ]):
        lx = leg_x + 22 + k * 43
        ly = leg_y - 4
        c.setFillColor(lc); c.setStrokeColor(lc)
        c.rect(lx * mm, ly * mm, 5 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(C_TEXT); c.setFont("Helvetica", 6)
        c.drawString((lx + 6) * mm, ly * mm, lbl)

    # ── Title block (bottom-right footer)
    tb_w = 85; tb_h = FTR_TOP - FTR_BOT - 2
    tb_x = ML + CW - tb_w - 2; tb_y = FTR_BOT + 1
    c.setStrokeColor(C_BORDER); c.setLineWidth(0.5); c.setFillColor(white)
    c.rect(tb_x * mm, tb_y * mm, tb_w * mm, tb_h * mm, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 7); c.setFillColor(C_BORDER)
    c.drawString((tb_x + 2) * mm, (tb_y + tb_h - 5) * mm,
                 (pinfo.titlu_proiect or "SCHEMA MONOFILARA")[:38])
    c.setFont("Helvetica", 6)
    c.drawString((tb_x + 2) * mm, (tb_y + tb_h - 9) * mm,
                 f"Nr.: {pinfo.proiect_nr}   Faza: {pinfo.faza}   Data: {pinfo.data}")
    c.drawString((tb_x + 2) * mm, (tb_y + tb_h - 13) * mm,
                 f"Beneficiar: {(pinfo.beneficiar or '')[:32]}")
    c.drawString((tb_x + 2) * mm, (tb_y + 2) * mm,
                 f"Adresa: {(pinfo.adresa or '')[:38]}")

    # App signature
    c.setFont("Helvetica", 5); c.setFillColor(C_DIM)
    c.drawRightString((ML + CW - 2) * mm, (MB + 1) * mm,
                      "Generat automat de ZYNAPSE · I7-2011 · zynapse.ro")

    c.save()
    return buf.getvalue()


@app.post("/generate-schema-b64")
def generate_schema_b64(req: GenerateSchemaRequest):
    """Returns schema as base64-encoded PDF inside JSON — for n8n integration."""
    try:
        pdf_bytes = _build_schema_pdf(req)
    except RuntimeError as e:
        return {"error": str(e)}
    encoded = base64.b64encode(pdf_bytes).decode()
    return {"schema_monofilara_pdf": f"data:application/pdf;base64,{encoded}"}


@app.post("/generate-schema")
def generate_schema(req: GenerateSchemaRequest):
    from fastapi.responses import Response as FastAPIResponse
    try:
        pdf_bytes = _build_schema_pdf(req)
    except RuntimeError as e:
        return {"error": str(e)}
    tablou_name = req.tablou.name.replace(" ", "-").replace("/", "-").lower()
    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="schema-monofilara-{tablou_name}.pdf"'
            ),
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}


# -------------------------------------------------
#  SERVIRE FRONTEND STATIC
# -------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
