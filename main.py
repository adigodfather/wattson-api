# redeploy v4.1 — lighting fix
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from schema_generator import (
    SchemaRequest as SchemaRequestV2,
    generate_schema_pdf,
    build_sample_request,
)
from memoriu_generator import build_memoriu_docx
from cartus_swap import swap_cartus_plan
import draw_elements
from pydantic import BaseModel
from typing import List, Optional, Literal
import math
import os
import hmac
import base64
import io
import time as _time
import logging
import json
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

try:
    from pdf2image import convert_from_bytes
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

try:
    from supabase_client import (
        save_project, save_project_file, log_action,
        get_norme_prize, get_norme_iluminat, get_norme_alimentari,
        get_reguli_cablu, get_reguli_protectie, get_tip_cladire,
        get_app_setting,
    )
    _SUPABASE_AVAILABLE = True
    logger.info("[supabase] client importat cu succes — persistența activă")
except Exception as e:
    _SUPABASE_AVAILABLE = False
    logger.error(
        "[supabase] IMPORT EȘUAT — persistența e DEZACTIVATĂ (no-op). "
        "Proiectele NU se vor salva în baza de date. Cauză: %r", e,
        exc_info=True,
    )

    def save_project(*a, **kw): return kw.get("project_data", {}).get("project_id", "")
    def save_project_file(*a, **kw): pass
    def log_action(*a, **kw): pass
    def get_norme_prize(): return {}
    def get_norme_iluminat(): return {}
    def get_norme_alimentari(): return {}
    def get_reguli_cablu(): return {}
    def get_reguli_protectie(): return {}
    def get_tip_cladire(cod): return {}
    def get_app_setting(key, default=None): return default


def safe_log(user_id, actiune, **kwargs):
    try:
        log_action(user_id, actiune, **kwargs)
    except Exception as e:
        logger.error("[audit_log] Failed to log %r: %s", actiune, e)


BUILDING_TYPE_MAP = {
    # English
    "residential":      "locuinta",
    "apartment":        "bloc",
    "office":           "birouri",
    "commercial":       "comercial",
    "industrial":       "industrial",
    "cultural":         "cultural",
    "school":           "scoala",
    "healthcare":       "sanatate",
    "sports":           "sport",
    "restaurant":       "restaurant",
    # Romanian — direct and compound subtype values from the frontend form
    "locuinta":         "locuinta",
    "casa":             "locuinta",
    "casa_unifamiliala":"locuinta",
    "duplex":           "locuinta",
    "vila":             "locuinta",
    "bloc":             "bloc",
    "bloc_locuinte":    "bloc",
    "apartament":       "bloc",
    "birouri":          "birouri",
    "birou":            "birouri",
    "spatiu_comercial_bloc": "comercial",
    "comercial":        "comercial",
    "magazin":          "comercial",
    "industrial":       "industrial",
    "hala":             "industrial",
    "hala_productie":   "industrial",
    "depozit":          "industrial",
    "atelier":          "industrial",
    "ferma":            "industrial",
    "statie_tehnologica":"industrial",
    "cultural":         "cultural",
    "camin_cultural":   "cultural",
    "camin":            "cultural",
    "scoala":           "scoala",
    "gradinita":        "scoala",
    "institutie":       "scoala",
    "sanatate":         "sanatate",
    "spital":           "sanatate",
    "cabinet":          "sanatate",
    "sport":            "sport",
    "sala_sport":       "sport",
    "baza_sportiva":    "sport",
    "restaurant":       "restaurant",
    "hotel_pensiune":   "restaurant",
    "hotel":            "restaurant",
    "pensiune":         "restaurant",
    "biserica":         "cultural",
    "primarie":         "cultural",
}


app = FastAPI(
    title="ZYNAPSE Core API",
    description="Motor inteligent de calcul pentru proiecte electrice – ZYNAPSE",
    version="4.0.0",
)

# CORS restrans la domeniile proprii: nimeni legitim nu apeleaza API-ul din BROWSER
# (toti apelantii sunt server-side: n8n + rutele Next de pe Vercel — verificat in audit).
# allow_credentials scos (invalid oricum cu wildcard; nu folosim cookies).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.zynapse.org", "https://zynapse.org"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── AUTENTIFICARE INTERNA (x-zynapse-key) — FAIL-CLOSED IN PRODUCTIE (P1-1) ──
# VECHI (fail-open): cheie NESETATA -> middleware NO-OP -> TOT API-ul public. Anti-pattern:
# securitatea depindea de PREZENTA env-ului (rollback / mediu Preview fara cheie -> API public).
# NOU (fail-closed): in PRODUCTIE (Render seteaza automat env RENDER; sau fortezi ZYNAPSE_REQUIRE_KEY=1)
# cheia e OBLIGATORIE -> lipsa ei da 503 la tot, NU acces liber. Local (fara RENDER) ramane no-op
# pentru dezvoltare/teste. Exceptii: GET / si /health (monitorizare Render) + preflight OPTIONS (CORS).
# Apelantii legitimi (rute Vercel extract-geometry/regenerate-plan/crop + noduri n8n) trimit mereu cheia.
# Compara constant-time (hmac.compare_digest) anti-timing, in loc de !=.
# NOTA: daca ZYNAPSE_INTERNAL_KEY E setat (starea de azi), fix-ul e no-op pt. traficul curent.
# DEPLOY: confirma ZYNAPSE_INTERNAL_KEY setat pe Render INAINTE de push (altfel 503 la tot).
# Rollback: seteaza ZYNAPSE_REQUIRE_KEY=0 nu ajuta (RENDER ramane) -> pune cheia, ori sterge gate-ul.
_PUBLIC_PATHS = {"/", "/health"}
_REQUIRE_KEY = bool((os.environ.get("RENDER") or "").strip()) or \
    (os.environ.get("ZYNAPSE_REQUIRE_KEY") or "").strip() == "1"


@app.middleware("http")
async def _require_zynapse_key(request, call_next):
    if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    expected = (os.environ.get("ZYNAPSE_INTERNAL_KEY") or "").strip()
    if not expected:
        # FAIL-CLOSED: fara cheie configurata in productie NU servim (altfel API public).
        if _REQUIRE_KEY:
            return JSONResponse(
                {"error": "Server misconfigured: ZYNAPSE_INTERNAL_KEY not set"},
                status_code=503,
            )
        return await call_next(request)  # dev local (fara RENDER): no-op
    provided = (request.headers.get("x-zynapse-key") or "").strip()
    if not hmac.compare_digest(provided, expected):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    return await call_next(request)


logger.info("=== ZYNAPSE STARTUP ===")
logger.info(f"SUPABASE_URL set: {bool(os.environ.get('SUPABASE_URL'))}")
logger.info(f"SUPABASE_SERVICE_KEY set: {bool(os.environ.get('SUPABASE_SERVICE_KEY'))}")
logger.info(f"ANTHROPIC_API_KEY set: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
logger.info(f"ZYNAPSE_INTERNAL_KEY set (auth activa): {bool(os.environ.get('ZYNAPSE_INTERNAL_KEY'))}")

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
    project_info: Optional[dict] = None
    user_id: Optional[str] = None


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
                "cable": "3x2,5 mm² CYY-F", "rcd_30ma": True,
                "notes": "Circuit dedicat boiler ACM, MCB 16A, RCCB 30mA.",
            })
        elif eq.type == "ac":
            circuits.append({
                "id": f"C_AC_{tag}", "panel": panel,
                "usage": f"Aer condiționat — {eq.name}",
                "type": "ac", "breaker_a": 16,
                "cable": "3x2,5 mm² CYY-F", "rcd_30ma": True,
                "notes": "Circuit dedicat AC, MCB 16A, RCCB 30mA.",
            })
        elif eq.type == "hrv":
            circuits.append({
                "id": f"C_HRV_{tag}", "panel": panel,
                "usage": f"Ventilație HRV — {eq.name}",
                "type": "hrv", "breaker_a": 10,
                "cable": "3x1,5 mm² CYY-F",
                "notes": "Circuit ventilație cu recuperare căldură, MCB 10A.",
            })
        elif eq.type == "ev_charger":
            if eq.phase == "tri":
                circuits.append({
                    "id": f"C_EV_{tag}", "panel": panel,
                    "usage": f"Stație EV — {eq.name}",
                    "type": "ev_charger", "phase": "trifazat", "breaker_a": 16,
                    "cable": "5x6 mm² CYY-F", "rcd_30ma": True,
                    "notes": "Stație EV trifazată: MCB 3P 16A, RCCB 3P 25A/30mA, CYY-F 5x6.",
                })
            else:
                circuits.append({
                    "id": f"C_EV_{tag}", "panel": panel,
                    "usage": f"Stație EV — {eq.name}",
                    "type": "ev_charger", "breaker_a": 32,
                    "cable": "3x6 mm² CYY-F", "rcd_30ma": True,
                    "notes": "Stație EV monofazată: MCB 32A, RCCB 30mA, CYY-F 3x6.",
                })
        elif eq.type == "solar":
            if eq.phase == "tri":
                circuits.append({
                    "id": f"C_PV_{tag}", "panel": panel,
                    "usage": f"Invertor FV — {eq.name}",
                    "type": "solar", "breaker_a": 20,
                    "cable": "5x4 mm² CYY-F",
                    "notes": "Invertor fotovoltaic trifazat: MCB 2P 20A, CYY-F 5x4.",
                })
            else:
                circuits.append({
                    "id": f"C_PV_{tag}", "panel": panel,
                    "usage": f"Invertor FV — {eq.name}",
                    "type": "solar", "breaker_a": 20,
                    "cable": "3x4 mm² CYY-F",
                    "notes": "Invertor fotovoltaic monofazat: MCB 2P 20A, CYY-F 3x4.",
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


def calculate_lighting_circuits(rooms, building_category, levels_string=None):
    """
    I7-2011: max 0.7kW per circuit iluminat, max 8 corpuri
    Rezidential: MAXIM 2 circuite total pentru casa
    Public: 1 circuit per zona functionala
    Industrial: 1 circuit per hala
    """
    circuits = []

    # ─── REZIDENTIAL ───────────────────────────────────────────
    if building_category in ("rezidential", None, ""):
        # Putere totala iluminat: 10W/mp LED
        total_area = sum(r.get("area_m2", 0) for r in rooms)
        total_power_w = total_area * 10  # W
        total_power_kw = total_power_w / 1000

        # Numarul de circuite: max 0.7kW fiecare, minim 1
        num_circuits = max(1, math.ceil(total_power_kw / 0.7))

        # La ORICE cladire rezidentiala: MAXIM 2 circuite
        num_circuits = min(num_circuits, 2)

        power_per_circuit = round(total_power_kw / num_circuits, 3)

        labels = [
            "Iluminat general nivel 1",
            "Iluminat general nivel 2",
            "Iluminat tehnic (subsol/exterior)"
        ]

        for i in range(num_circuits):
            circuits.append({
                "id": f"C_IL_{i+1}",
                "name": labels[i] if i < len(labels) else f"Iluminat zona {i+1}",
                "type": "iluminat",
                "power_kw": power_per_circuit,
                "breaker_a": 10,
                "breaker_type": "MCB",
                "breaker_curve": "C",
                "cable": "NYM 3x1.5 mm²",
                "rcd_required": False,
                "rcd_ma": None,
                "notes": f"{round(total_area/num_circuits)} mp / circuit"
            })

        return circuits

    # ─── CLADIRI PUBLICE ────────────────────────────────────────
    elif building_category == "public":
        # Grupeaza camerele pe zone functionale
        zone_sali = [r for r in rooms if any(k in r.get("name","").lower()
                     for k in ["sala", "sală", "aula", "conference", "sedinta"])]
        zone_birouri = [r for r in rooms if any(k in r.get("name","").lower()
                        for k in ["birou", "oficiu", "secretariat", "cabinet"])]
        zone_holuri = [r for r in rooms if any(k in r.get("name","").lower()
                       for k in ["hol", "coridor", "circulatie", "circulație", "casa scarii"])]
        zone_sanitare = [r for r in rooms if any(k in r.get("name","").lower()
                         for k in ["sanitar", "baie", "wc", "toaleta", "cabina", "dus"])]
        zone_tehnice = [r for r in rooms if any(k in r.get("name","").lower()
                        for k in ["magazie", "depozit", "tehnic", "centrala", "subsol"])]

        def add_zone_circuits(zone_rooms, prefix, label, w_per_m2, ip44=False):
            if not zone_rooms:
                return
            total_w = sum(r.get("area_m2", 0) for r in zone_rooms) * w_per_m2
            n = max(1, math.ceil(total_w / 700))
            pw = round(total_w / 1000 / n, 3)
            for i in range(n):
                suffix = f"_{i+1}" if n > 1 else ""
                circuits.append({
                    "id": f"{prefix}{suffix}",
                    "name": f"{label}{' (zona ' + str(i+1) + ')' if n > 1 else ''}",
                    "type": "iluminat",
                    "power_kw": pw,
                    "breaker_a": 10 if pw <= 0.7 else 16,
                    "breaker_type": "MCB",
                    "breaker_curve": "C",
                    "cable": "NYM 3x1.5 mm²",
                    "rcd_required": ip44,
                    "rcd_ma": 30 if ip44 else None,
                    "notes": "IP44" if ip44 else ""
                })

        add_zone_circuits(zone_sali, "C_IL_SAL", "Iluminat sali", 15)
        add_zone_circuits(zone_birouri, "C_IL_BIR", "Iluminat birouri", 12)
        add_zone_circuits(zone_holuri, "C_IL_CIR", "Iluminat circulatii", 8)
        add_zone_circuits(zone_sanitare, "C_IL_SAN", "Iluminat sanitar", 10, ip44=True)
        add_zone_circuits(zone_tehnice, "C_IL_TEH", "Iluminat tehnic", 6)

        # Circuit evacuare obligatoriu la public
        circuits.append({
            "id": "C_IL_EV",
            "name": "Iluminat evacuare (urgenta)",
            "type": "iluminat_evacuare",
            "power_kw": 0.2,
            "breaker_a": 10,
            "breaker_type": "MCB",
            "breaker_curve": "C",
            "cable": "NYM 3x1.5 mm²",
            "rcd_required": False,
            "rcd_ma": None,
            "notes": "Circuit dedicat, baterie backup, IP44"
        })

        return circuits

    # ─── INDUSTRIAL ─────────────────────────────────────────────
    elif building_category == "industrial":
        hale = [r for r in rooms if any(k in r.get("name","").lower()
                for k in ["hala", "hală", "productie", "productie", "atelier", "depozit"])]
        birouri = [r for r in rooms if any(k in r.get("name","").lower()
                   for k in ["birou", "oficiu", "vestiar"])]

        if hale:
            total_w = sum(r.get("area_m2", 0) for r in hale) * 20  # 20W/mp industrial
            n = max(1, math.ceil(total_w / 700))
            pw = round(total_w / 1000 / n, 3)
            for i in range(n):
                suffix = f"_{i+1}" if n > 1 else ""
                circuits.append({
                    "id": f"C_IL_HAL{suffix}",
                    "name": f"Iluminat hala{' zona ' + str(i+1) if n > 1 else ''} (IP65)",
                    "type": "iluminat",
                    "power_kw": pw,
                    "breaker_a": 16,
                    "breaker_type": "MCB",
                    "breaker_curve": "C",
                    "cable": "NYM 3x1.5 mm²",
                    "rcd_required": False,
                    "rcd_ma": None,
                    "notes": "Corpuri industriale IP65"
                })

        if birouri:
            total_w = sum(r.get("area_m2", 0) for r in birouri) * 12
            circuits.append({
                "id": "C_IL_BIR",
                "name": "Iluminat birouri industriale",
                "type": "iluminat",
                "power_kw": round(total_w / 1000, 3),
                "breaker_a": 10,
                "breaker_type": "MCB",
                "breaker_curve": "C",
                "cable": "NYM 3x1.5 mm²",
                "rcd_required": False,
                "rcd_ma": None,
                "notes": ""
            })

        return circuits

    # ─── BLOC ───────────────────────────────────────────────────
    elif building_category == "bloc":
        circuits.append({
            "id": "C_IL_COM_P",
            "name": "Iluminat comun parter",
            "type": "iluminat",
            "power_kw": 0.2,
            "breaker_a": 10,
            "breaker_type": "MCB",
            "breaker_curve": "C",
            "cable": "NYM 3x1.5 mm²",
            "rcd_required": False,
            "rcd_ma": None,
            "notes": "Senzor miscare recomandat"
        })
        circuits.append({
            "id": "C_IL_COM_E",
            "name": "Iluminat comun etaje",
            "type": "iluminat",
            "power_kw": 0.3,
            "breaker_a": 10,
            "breaker_type": "MCB",
            "breaker_curve": "C",
            "cable": "NYM 3x1.5 mm²",
            "rcd_required": False,
            "rcd_ma": None,
            "notes": "Senzor miscare recomandat"
        })
        return circuits

    # ─── DEFAULT (fallback) ──────────────────────────────────────
    else:
        total_area = sum(r.get("area_m2", 0) for r in rooms)
        total_kw = total_area * 10 / 1000
        n = min(2, max(1, math.ceil(total_kw / 0.7)))
        for i in range(n):
            circuits.append({
                "id": f"C_IL_{i+1}",
                "name": f"Iluminat general {i+1}",
                "type": "iluminat",
                "power_kw": round(total_kw / n, 3),
                "breaker_a": 10,
                "breaker_type": "MCB",
                "breaker_curve": "C",
                "cable": "NYM 3x1.5 mm²",
                "rcd_required": False,
                "rcd_ma": None,
                "notes": ""
            })
        return circuits


def build_circuits_teg(data: ProjectData) -> List[dict]:
    circuits = []
    total_area = sum(r.area_m2 for r in data.rooms)
    has_kitchen = any(r.function == "kitchen" for r in data.rooms)
    has_bathroom = any(r.function == "bathroom" for r in data.rooms)

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
            "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 IP44",
            "rcd_10ma": True, "afdd": True,
            "notes": "Circuit dedicat masina de spalat rufe, RCCB 10mA zona umeda (I7-2011).",
        })
    return circuits


# -------------------------------------------------
#  CLADIRI PUBLICE
# -------------------------------------------------


def calc_public_circuits(data: ProjectData) -> List[dict]:
    circuits = []
    idx_prz = idx_frt = idx_ip44 = 1
    total_power_w = 0.0

    zone_sal = [r for r in data.rooms if r.function == "hall"]
    zone_bir = [r for r in data.rooms if r.function == "office"]
    zone_san = [r for r in data.rooms if r.function == "sanitary"]
    zone_dep = [r for r in data.rooms if r.function in ["storage", "technical/storage"]]
    zone_buc = [r for r in data.rooms if r.function == "kitchen_pub"]

    # Zone SAL — forta scena per sala
    for room in zone_sal:
        circuits.append({
            "id": f"C_FRT_{idx_frt:02d}", "panel": "TG",
            "usage": f"Forta scena {room.name}",
            "type": "forta", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
            "notes": f"Circuit forta scena/echipamente {room.name}, MCB 16A.",
        })
        idx_frt += 1
        total_power_w += room.area_m2 * 40 + 3000

    # Zone BIR — prize birouri
    for room in zone_bir:
        num_prz = max(1, math.ceil(room.area_m2 / 30))
        for _ in range(num_prz):
            circuits.append({
                "id": f"C_PRZ_{idx_prz:02d}", "panel": "TG",
                "usage": f"Prize {room.name}",
                "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
                "rcd_30ma": True,
                "notes": f"Prize birou {room.name}, h=0.30m, 1 priza/3mp.",
            })
            idx_prz += 1
        total_power_w += room.area_m2 * 80

    # Zone SAN — priza IP44 per incapere sanitara
    for room in zone_san:
        circuits.append({
            "id": f"C_IP44_{idx_ip44:02d}", "panel": "TG",
            "usage": f"Circuit umed {room.name}",
            "type": "ip44", "breaker_a": 16, "cable": "CYY-F 3x2,5 IP44",
            "rcd_10ma": True, "ip": "IP44",
            "notes": f"Grup sanitar {room.name}: CYY-F IP44, RCCB 10mA, priza IP44 h=1.20m.",
        })
        idx_ip44 += 1
        total_power_w += 500

    # Zone DEP — priza forta per magazie
    for room in zone_dep:
        circuits.append({
            "id": f"C_PRZ_{idx_prz:02d}", "panel": "TG",
            "usage": f"Priza forta {room.name}",
            "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
            "notes": f"1 priza forta {room.name}.",
        })
        idx_prz += 1
        total_power_w += room.area_m2 * 10 + 500

    # Zone BUC — bucatarie publica
    for room in zone_buc:
        circuits.append({
            "id": f"C_FRT_{idx_frt:02d}", "panel": "TG",
            "usage": f"Forta bucatarie {room.name}",
            "type": "forta", "phase": "tri", "breaker_a": 32, "cable": "CYY-F 5x4 mm²",
            "notes": f"Bucatarie publica {room.name}: trifazat 32A, hota, echipamente.",
        })
        idx_frt += 1
        total_power_w += 15000

    # Adaugam estimare iluminat la puterea totala (pentru bransament)
    total_power_w += sum(r.area_m2 for r in data.rooms) * 15

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
    idx_f16 = idx_f32 = idx_mot = 1
    total_power_kw = 0.0
    ip_zone = data.ip_zone if data.ip_zone not in ("IP20", "") else "IP65"

    for room in data.rooms:
        func = room.function
        area = room.area_m2

        if func == "production":
            for _ in range(max(1, math.ceil(area / 60))):
                circuits.append({
                    "id": f"C_PRZ_F16_{idx_f16:02d}", "panel": "TG",
                    "usage": f"Prize forta 16A {room.name}",
                    "type": "prize_forta", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
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
                "id": f"C_PRZ_F16_{idx_f16:02d}", "panel": "TG",
                "usage": f"Prize forta {room.name}",
                "type": "prize_forta", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
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
                "id": f"C_PRZ_F16_{idx_f16:02d}", "panel": "TG",
                "usage": f"Prize birou {room.name}",
                "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
                "rcd_30ma": True, "notes": f"Prize birou {room.name}.",
            })
            idx_f16 += 1
            total_power_kw += area * 0.05

        elif func == "electrical":
            pass  # Camera electrica — nu necesita circuite proprii

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
        "id": "C_IL_COM_SUB", "panel": "TGB", "usage": "Iluminat subsol/parcare",
        "type": "iluminat", "breaker_a": 10, "cable": "CYY-F 3x1,5 mm²",
        "notes": "Iluminat subsol si parcare, MCB 10A.",
    })
    circuits.append({
        "id": "C_PRIZE_COM", "panel": "TGB", "usage": "Prize comune",
        "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
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
            f"Circuite interne: iluminat 2x10A (C_IL_1+C_IL_2), prize 3x16A, bucatarie 2x20A, baie 16A."
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
        "type": "iluminat", "breaker_a": 10, "cable": "CYY-F 3x1,5 mm²",
        "lux": 500, "notes": "Iluminat general spatiu comercial, 500 lux.",
    })

    if any(k in btype for k in ["magazin", "retail", "comercial"]):
        circuits.append({
            "id": "C_VITRINE", "panel": "TC", "usage": "Iluminat vitrine",
            "type": "iluminat", "breaker_a": 10, "cable": "CYY-F 3x1,5 mm²",
            "notes": "Circuit iluminat vitrine, dimabil, separat de iluminatul general.",
        })
        circuits.append({
            "id": "C_CASA", "panel": "TC", "usage": "Casa de marcat + UPS",
            "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
            "notes": "Circuit dedicat casa de marcat + UPS mic, MCB 16A.",
        })
        circuits.append({
            "id": "C_PRZ_COM", "panel": "TC", "usage": "Prize comerciale generale",
            "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
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
            "type": "mixt", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
            "notes": "Salon restaurant: iluminat + prize, ambiant dimabil.",
        })
        circuits.append({
            "id": "C_TERASA", "panel": "TC", "usage": "Terasa (IP44)",
            "type": "ip44", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
            "ip": "IP44", "rcd_30ma": True, "notes": "Circuit terasa exterior IP44, RCCB 30mA.",
        })

    if "hotel" in btype:
        room_count = len(data.rooms) if data.rooms else 10
        circuits.append({
            "id": "C_CAMERE", "panel": "TC",
            "usage": f"Circuite camere hotel ({room_count} camere)",
            "type": "prize", "breaker_a": 12, "cable": "CYY-F 3x2,5 mm²",
            "notes": f"{room_count} camere × 12A. Fiecare camera pe MCB dedicat prin tablou etaj.",
        })
        circuits.append({
            "id": "C_RECEPTIE", "panel": "TC", "usage": "Receptie + back-office",
            "type": "prize", "breaker_a": 20, "cable": "CYY-F 3x2,5 mm²",
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
            "type": "iluminat", "breaker_a": 40, "cable": "CYY-F 3x10 mm²",
            "notes": "Iluminat circulatii mall, coridoare, zone comune.",
        })
        circuits.append({
            "id": "C_PARCARE", "panel": "TG", "usage": "Parcare",
            "type": "iluminat", "breaker_a": 20, "cable": "CYY-F 3x4 mm²", "ip": "IP44",
            "notes": "Iluminat parcare IP44, senzori de miscare.",
        })

    if not any(k in btype for k in ["magazin", "retail", "restaurant", "bar", "hotel", "mall", "comercial"]):
        circuits.append({
            "id": "C_PRZ_COM", "panel": "TC", "usage": "Prize spatiu comercial",
            "type": "prize", "breaker_a": 16, "cable": "CYY-F 3x2,5 mm²",
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
    pi = data.project_info or {}

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
    titlu = pi.get("titlu_proiect") or data.project_id
    lines.append(f"Titlu proiect: {titlu}")
    if pi.get("proiect_nr"):
        lines.append(f"Nr. proiect: {pi['proiect_nr']}")
    if pi.get("beneficiar"):
        lines.append(f"Beneficiar: {pi['beneficiar']}")
    if pi.get("amplasament"):
        lines.append(f"Amplasament: {pi['amplasament']}")
    if pi.get("faza"):
        lines.append(f"Faza: {pi['faza']}")
    if pi.get("data"):
        lines.append(f"Data: {pi['data']}")
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
    if pi.get("sef_proiect"):
        lines.append("")
        lines.append(f"Intocmit: {pi['sef_proiect']}")
    return "\n".join(lines)


# -------------------------------------------------
#  ENDPOINT PRINCIPAL
# -------------------------------------------------


@app.post("/calc-electric")
def calc_electric(data: ProjectData):
    _t0 = _time.time()
    logger.info("=== CALC REQUEST START ===")
    logger.info(f"user_id in request: {repr(data.user_id)}")
    logger.info(f"building_type in request: {repr(getattr(data.building, 'type', None))}")
    logger.info(f"building_category in request: {repr(data.building_category)}")
    climate_zone = resolve_climate_zone_from_data(data)
    building_category = (data.building_category or "").strip() or detect_building_category(data.building.type)
    if not building_category:
        building_category = "rezidential"

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

    # Circuite iluminat — I7-2011: max 0.7kW/circuit, grupate pe categorii
    _rooms_for_lighting = [{"area_m2": r.area_m2, "name": r.name} for r in data.rooms]
    lighting_circuits = calculate_lighting_circuits(_rooms_for_lighting, building_category)

    circuits_all = lighting_circuits + circuits_te_ct + circuits_teg + extra_circuits

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

    _pi = data.project_info or {}
    response = {
        "project_id": data.project_id,
        "status": "success",
        "project_info": _pi,
        "project_name": _pi.get("titlu_proiect") or data.project_id,
        "beneficiary": _pi.get("beneficiar", ""),
        "address": _pi.get("amplasament", ""),
        "designer": _pi.get("sef_proiect", ""),
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
        "circuits": circuits_all,
        "memoriu_tehnic": memoriu,
    }

    # Map building_type to Romanian for Supabase
    _btype_raw = (
        getattr(data, "building_type", None)
        or (data.building.type if data.building else None)
        or (data.project_info or {}).get("tip_cladire")
        or "cultural"
    )
    _tip_ro = BUILDING_TYPE_MAP.get((_btype_raw or "").lower(), _btype_raw or "cultural")
    response["tip_cladire_ro"] = _tip_ro

    logger.info("=== CALC REQUEST ===")
    logger.info(f"user_id received: {repr(data.user_id)}")
    logger.info(f"building_type raw: {repr(_btype_raw)}")
    logger.info(f"tip_cladire_ro mapped: {repr(_tip_ro)}")
    logger.info(f"circuits_all count: {len(response.get('circuits_all', []))}")
    logger.info(f"circuits_teg count: {len(response.get('circuits_teg', []))}")
    logger.info(f"response keys: {list(response.keys())}")

    _durata_ms = int((_time.time() - _t0) * 1000)
    _supabase_project_id: Optional[str] = None
    if data.user_id:
        try:
            _supabase_project_id = save_project(data.user_id, response)
            response["supabase_project_id"] = _supabase_project_id
            response["saved"] = True
        except Exception as e:
            logger.error("[save_project] Failed: %s", e)
            response["saved"] = False
    else:
        response["saved"] = False
    safe_log(
        user_id=data.user_id,
        actiune="calc-electric",
        proiect_id=_supabase_project_id or data.project_id,
        durata_ms=_durata_ms,
        succes=True,
    )
    return response


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

    # Decode image / PDF
    b64 = req.plan_base64
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    img_bytes = base64.b64decode(b64)

    is_pdf = img_bytes[:4] == b"%PDF" or "pdf" in (req.plan_type or "").lower()
    if is_pdf:
        if not _PDF_AVAILABLE:
            return {"error": "pdf2image not installed", "annotated_plan_base64": None}
        try:
            pages = convert_from_bytes(img_bytes, dpi=150, first_page=1, last_page=1)
            if not pages:
                return {"error": "PDF empty", "annotated_plan_base64": None}
            img = pages[0].convert("RGBA")
        except Exception as e:
            return {"error": f"PDF conversion failed: {str(e)}", "annotated_plan_base64": None}
    else:
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except Exception as e:
            return {"error": f"Image decode failed: {str(e)}", "annotated_plan_base64": None}

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
def generate_schema_b64(request: SchemaRequestV2):
    """Varianta base64 pentru n8n / clienti JSON-only. Schema v2 panoramica."""
    try:
        pdf_bytes = generate_schema_pdf(request)
        return {
            "success": True,
            "pdf_base64": base64.b64encode(pdf_bytes).decode('utf-8'),
            "filename": f"{request.tablou_nume}_schema_monofilara.pdf",
            "size_bytes": len(pdf_bytes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  MULTI-SCHEMA ENGINE (POST /generate-schema)
# -------------------------------------------------

class CircuitInputNew(BaseModel):
    id: str = ""
    type: str = "prize"
    description: str = ""
    power_w: float = 0
    breaker_a: int = 16
    breaker_type: str = "MCB-1P-C"
    cable_type: str = "CYY-F 3x2.5"
    pozare: str = "IPEY 18mm"
    outlets: int = 0
    lighting_points: int = 0
    is_bathroom: bool = False
    is_dedicated: bool = False
    room: Optional[str] = None
    rccb_group: Optional[str] = None
    level: Optional[str] = None      # e.g. "etaj_1", "mansarda", "parter"


class PowerSummaryNew(BaseModel):
    installed_kw: float = 0
    absorbed_kw: float = 0
    current_a: float = 0
    main_breaker_a: int = 63
    connection: str = "Monofazat 230V+N+PE"
    simultaneity_ks: float = 0.7
    main_breaker_type: Optional[str] = None


class PanelInfoNew(BaseModel):
    rccb_groups: List[dict] = []
    has_spd: bool = True
    name: Optional[str] = None


class EquipmentInfoNew(BaseModel):
    boiler_acm: bool = False
    aer_conditionat: bool = False
    pdc: bool = False
    pompe_circulatie: bool = False
    ventilatie_hrv: bool = False


class GenerateSchemaMultiRequest(BaseModel):
    project_info: Optional[dict] = None
    power_summary: PowerSummaryNew = PowerSummaryNew()
    panel: PanelInfoNew = PanelInfoNew()
    circuits: List[CircuitInputNew] = []
    equipment: Optional[EquipmentInfoNew] = None
    page_format: Optional[str] = None   # "A4"/"A3"/"A2"/"A1"/"A2+A3" or None=auto
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    bom: Optional[list] = None
    building_type: Optional[str] = None


def _next_plansa_nr(pinfo: dict) -> int:
    pn = pinfo.get("plansa_nr", "") or ""
    import re as _re
    m = _re.search(r"\d+", pn)
    return int(m.group()) + 1 if m else 3


# ── Floor detection ──────────────────────────────────────────────────────────
# Ordered: most specific first; checked against combined "level + room + id" text
_FLOOR_PATTERNS: List[tuple] = [
    ("ETAJ2",    ["ETAJ 2", "ETAJ2", "ET.2", " E2 ", "E2-", "-E2", "/E2", "E2/",
                  "NIVEL 2", "FLOOR 2"]),
    ("ETAJ1",    ["ETAJ 1", "ETAJ1", "ET.1", " E1 ", "E1-", "-E1", "/E1", "E1/",
                  "NIVEL 1", "FLOOR 1"]),
    ("MANSARDA", ["MANSARDA", "MANSARD", " MAN ", "MAN-", "-MAN", "/MAN",
                  "MANS-", " MANS "]),
    ("DEMISOL",  ["DEMISOL", "DEMIS ", " DEM ", "DEM-", " DS ", "DS-", "-DS",
                  "/DS", "DS/"]),
    ("SUBSOL",   ["SUBSOL", " SS ", "SS-", "-SS", "/SS", "SS/",
                  "SUB-", " SUB "]),
]

_FLOOR_INFO: dict = {
    "ETAJ1":    ("ETAJ 1",   "TES-E1",  "TABLOU ELECTRIC SECUNDAR ETAJ 1"),
    "ETAJ2":    ("ETAJ 2",   "TES-E2",  "TABLOU ELECTRIC SECUNDAR ETAJ 2"),
    "MANSARDA": ("MANSARDA", "TES-MAN", "TABLOU ELECTRIC SECUNDAR MANSARDA"),
    "DEMISOL":  ("DEMISOL",  "TES-DS",  "TABLOU ELECTRIC SECUNDAR DEMISOL"),
    "SUBSOL":   ("SUBSOL",   "TES-SS",  "TABLOU ELECTRIC SECUNDAR SUBSOL"),
}

_FLOOR_ORDER = ["ETAJ1", "ETAJ2", "MANSARDA", "DEMISOL", "SUBSOL"]
_BREAKER_SIZES = [10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125]
OVERFLOW_LIMIT = 16


def _detect_floor(level: Optional[str], room: Optional[str], cid: str = "") -> str:
    """Return canonical floor key: PARTER / ETAJ1 / ETAJ2 / MANSARDA / DEMISOL / SUBSOL."""
    txt = " " + " ".join(p.upper() for p in [level or "", room or "", cid or ""] if p) + " "
    for floor_key, patterns in _FLOOR_PATTERNS:
        if any(p in txt for p in patterns):
            return floor_key
    return "PARTER"


def _breaker_for_current(ia: float) -> int:
    for a in _BREAKER_SIZES:
        if a >= ia * 1.25:
            return a
    return 125


def _feeder_cable(ia: float) -> str:
    for max_a, size in [(16, "2.5"), (25, "4"), (35, "6"), (50, "10"), (63, "16"), (80, "25")]:
        if ia <= max_a:
            return f"CYY-F 5×{size}mmp"
    return "CYY-F 5×35mmp"


def _sort_and_number_circuits(circuits: List[dict]) -> List[dict]:
    """Sort in I7-2011 order, renumber C1…Cn, append REZERVA at end."""
    def _key(c):
        t    = c.get("type", "prize")
        bath = c.get("is_bathroom", False)
        pw   = c.get("power_w", 0)
        room = (c.get("room") or "").lower()
        if t == "iluminat" and not bath: return (0, room, 0)
        if t == "prize"    and not bath: return (1, room, 0)
        if t == "dedicat":               return (2, "", -pw)
        if t == "prize"    and bath:     return (3, room, 0)
        if t == "iluminat" and bath:     return (4, room, 0)
        return (5, room, 0)

    out = [dict(c) for c in sorted(circuits, key=_key)]
    for i, c in enumerate(out):
        c["id"] = f"C{i + 1}"

    max_ba = max((c.get("breaker_a", 16) for c in out), default=16)
    rez_ba = max(10, round(max_ba * 0.3 / 10) * 10)
    out.append({
        "id": f"C{len(out) + 1}", "type": "rezerva",
        "description": "REZERVA", "power_w": 0,
        "breaker_a": rez_ba, "breaker_type": "MCB-1P-C",
        "cable_type": "—", "pozare": "—",
        "outlets": 0, "lighting_points": 0,
        "is_bathroom": False, "is_dedicated": False,
        "room": None, "rccb_group": None,
    })
    return out


# ── Page format registry ─────────────────────────────────────────────────────
# max_circuits: how many branches fit on one page of this format
_PAGE_FMT_INFO: dict = {
    "A4": {"max_circuits": 8},
    "A3": {"max_circuits": 14},
    "A2": {"max_circuits": 22},
    "A1": {"max_circuits": 35},
    "A0": {"max_circuits": 55},
}


def _auto_page_format(n: int) -> str:
    """Select the smallest format that fits n circuits on one page."""
    if n <= 10: return "A4"
    if n <= 18: return "A3"
    if n <= 30: return "A2"
    if n <= 50: return "A1"
    return "A2"   # 50+ → auto-split into A2 pages


def _page_size_pt(fmt: str) -> tuple:
    """Return (width_pt, height_pt) for landscape orientation."""
    from reportlab.lib.pagesizes import A4, A3, A2, A1, A0
    _m = {"A4": A4, "A3": A3, "A2": A2, "A1": A1, "A0": A0}
    p = _m.get(fmt.upper(), A3)
    return p[1], p[0]   # landscape: larger dim is width


def _get_tect_circuits(equipment: Optional[EquipmentInfoNew]) -> List[dict]:
    if not equipment:
        return []
    c_list, n = [], 1

    def _add(**kw):
        nonlocal n
        c_list.append({"id": f"C{n}", **kw})
        n += 1

    _add(type="iluminat", description="ILUMINAT CT", power_w=150,
         breaker_a=10, breaker_type="MCB-1P-B",
         cable_type="CYY-F 3x1.5", pozare="IPEY 16mm", lighting_points=2)
    if equipment.pdc:
        _add(type="dedicat", description="ALIM. PDC", power_w=5000,
             breaker_a=16, breaker_type="MCB-3P-C",
             cable_type="CYY-F 5x2.5", pozare="IPEY 25mm")
    if equipment.pdc or equipment.pompe_circulatie:
        _add(type="dedicat", description="ALIM. POMPE CIRCULATIE", power_w=500,
             breaker_a=16, breaker_type="MCB-1P-C",
             cable_type="CYY-F 3x2.5", pozare="IPEY 18mm")
    _add(type="dedicat", description="ALIM. AUTOMATIZARE", power_w=300,
         breaker_a=16, breaker_type="MCB-1P-C",
         cable_type="CYY-F 3x2.5", pozare="IPEY 18mm")
    if equipment.boiler_acm:
        _add(type="dedicat", description="PRIZA BOILER TERMOELECTRIC", power_w=2000,
             breaker_a=16, breaker_type="MCB-1P-C",
             cable_type="CYY-F 3x2.5 IP44", pozare="IPEY 18mm", is_bathroom=True)
    _add(type="prize", description="PRIZA LUCRU CT", power_w=920,
         breaker_a=16, breaker_type="MCB-1P-C",
         cable_type="CYY-F 3x2.5", pozare="IPEY 18mm", outlets=2, is_bathroom=True)
    return c_list


def _draw_schema_page(cv, panel_name, panel_desc, plansa_nr,
                      circuits, pinfo, ps, rccb_groups,
                      has_spd, main_cable, is_trifazat,
                      pw: float = None, ph: float = None):
    """Draw one electrical single-line schema page — Romanian DTAC/PT style, I7-2011."""
    try:
        from reportlab.lib.pagesizes import A3
        from reportlab.lib.colors import HexColor, black, white
    except ImportError:
        raise RuntimeError("reportlab not installed")

    _A3W = A3[1]                          # 1190.55 pt — scale base (A3 landscape width)
    PW   = pw if pw is not None else _A3W
    PH   = ph if ph is not None else A3[0]
    sc   = PW / _A3W   # scale: 1.0 @ A3 · 0.707 @ A4 · 1.414 @ A2 · 2.0 @ A1
    N    = len(circuits)

    def s(v): return v * sc   # scale a point value

    # Fixed-size corner blocks (120mm × 80mm cartus, 80mm × 55mm legenda)
    _MM     = 72 / 25.4
    TITLE_W = round(120 * _MM)   # 340 pt
    TITLE_H = round(80  * _MM)   # 227 pt
    LGD_W   = round(80  * _MM)   # 227 pt
    LGD_H   = round(55  * _MM)   # 156 pt

    # Scaled layout constants
    MARGIN     = s(12)
    TITLE_X    = PW - MARGIN - TITLE_W
    TABLE_X    = MARGIN
    TABLE_W    = TITLE_X - TABLE_X - s(6)
    TABLE_H    = TITLE_H
    TABLE_Y    = MARGIN
    NOTA_H     = s(16)
    SCHEMA_BOT = TABLE_Y + TABLE_H + NOTA_H
    SCHEMA_TOP = PH - s(10)
    HDR_H      = s(50)
    HDR_BOT    = SCHEMA_TOP - HDR_H
    BUS_Y      = SCHEMA_BOT + s(165)
    BRANCH_BOT = SCHEMA_BOT + s(8)
    BRANCH_TOP = BUS_Y - s(22)
    BUS_X_S    = s(115)
    BUS_X_E    = PW - MARGIN
    BRK_X      = s(65)
    SPACING    = (BUS_X_E - BUS_X_S) / max(N, 1)
    SPACING    = max(SPACING, s(35))

    # Scaled font sizes
    FS_PANEL = max(7.0, 13.0 * sc)
    FS_HDR   = max(5.0,  8.0 * sc)
    FS_SUBT  = max(4.5,  7.0 * sc)
    FS_CONN  = max(4.0,  7.0 * sc)
    FS_LBL   = max(5.5,  7.5 * sc)
    FS_SM    = max(4.5,  6.5 * sc)
    FS_CART  = max(6.0,  8.0 * sc)
    FS_TBL   = max(7.0,  9.0 * sc)

    # ── Colors ──────────────────────────────────────────────────────────────
    CGRAY_L = HexColor("#E5E7EB"); CGRAY_M = HexColor("#9CA3AF")
    CGRAY_D = HexColor("#374151"); CBUSBAR = HexColor("#1E293B")
    CHDR_BG = HexColor("#1E3A5F"); CBLUE   = HexColor("#1D4ED8")
    CAMBER  = HexColor("#B45309"); CGREEN  = HexColor("#15803D")
    CREZV   = HexColor("#6B7280")

    def _ckt_color(ctype, is_bath=False):
        if ctype == "iluminat":                           return CBLUE
        if ctype == "prize" and is_bath:                  return HexColor("#7C3AED")
        if ctype == "prize":                              return CAMBER
        if ctype in ("dedicat", "forta", "alimentare"):   return CGREEN
        return CREZV

    # ── Helpers ──────────────────────────────────────────────────────────────
    def rtext(x, y, txt, fs, angle=-90, bold=False, col=None):
        cv.saveState()
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", max(3.0, fs))
        cv.setFillColor(col or CGRAY_D)
        cv.translate(x, y); cv.rotate(angle)
        cv.drawCentredString(0, 0, str(txt))
        cv.restoreState()

    def mcb_sym(x, cy, bw=None, bh=None, n_poles=1):
        bw = (bw or s(14)) + max(n_poles - 1, 0) * s(5)
        bh = bh or s(22)
        cv.setFillColor(white); cv.setStrokeColor(black); cv.setLineWidth(s(0.8))
        cv.rect(x - bw/2, cy - bh/2, bw, bh, fill=1, stroke=1)
        cv.setLineWidth(s(0.6))
        cv.line(x - bw/2 + s(1), cy + bh/2 - s(2), x + bw/2 - s(1), cy - bh/2 + s(2))
        if n_poles >= 3:
            for k in range(1, n_poles):
                xk = x - bw/2 + k * bw / n_poles
                cv.line(xk, cy - bh/2, xk, cy + bh/2)

    def rccb_sym(x, cy):
        mcb_sym(x, cy + s(8))
        cv.setFillColor(white); cv.setStrokeColor(black); cv.setLineWidth(s(0.8))
        cv.circle(x, cy - s(6), s(6), fill=1, stroke=1)
        cv.setFont("Helvetica-Bold", max(3.5, s(6))); cv.setFillColor(black)
        cv.drawCentredString(x, cy - s(7.5), "Δ")

    def load_sym(x, y, ctype, is_bath=False, outlets=0, lpts=0):
        """Load-end symbol per I7-2011: ⊗ iluminat, ● prize, ↓ dedicat, □-- rezerva."""
        col = _ckt_color(ctype, is_bath)
        cv.setLineWidth(s(0.9))
        if ctype == "rezerva":
            r = s(7)
            cv.setFillColor(HexColor("#F3F4F6")); cv.setStrokeColor(CREZV)
            cv.setDash([s(3), s(2)])
            cv.rect(x - r, y - r, 2 * r, 2 * r, fill=1, stroke=1)
            cv.setDash()
        elif ctype == "iluminat":
            r = s(9)
            cv.setStrokeColor(col); cv.setFillColor(white)
            cv.circle(x, y, r, fill=1, stroke=1)
            cv.setLineWidth(s(0.9))
            cv.line(x - r * .68, y + r * .68, x + r * .68, y - r * .68)
            cv.line(x + r * .68, y + r * .68, x - r * .68, y - r * .68)
            if is_bath:
                cv.setFont("Helvetica-Bold", max(3.0, s(5.5))); cv.setFillColor(col)
                cv.drawCentredString(x + r + s(4), y + s(2), "S")
            if lpts:
                cv.setFont("Helvetica", max(3.0, s(5.0))); cv.setFillColor(col)
                cv.drawCentredString(x, y - r - s(5), f"{lpts}b")
        elif ctype == "prize":
            r = s(7) if is_bath else s(6)
            cv.setFillColor(col); cv.setStrokeColor(col)
            cv.circle(x, y, r, fill=1, stroke=1)
            if is_bath:
                cv.setFont("Helvetica-Bold", max(2.5, s(4.5))); cv.setFillColor(white)
                cv.drawCentredString(x, y - s(1.5), "IP")
                cv.setFont("Helvetica", max(2.5, s(4.0))); cv.setFillColor(col)
                cv.drawCentredString(x, y - r - s(5), "IP44")
            elif outlets:
                cv.setFont("Helvetica", max(3.0, s(5.0))); cv.setFillColor(col)
                cv.drawCentredString(x, y - r - s(5), f"{outlets}p")
        else:   # dedicat / forta / alimentare — downward arrow ↓
            cv.setStrokeColor(col); cv.setFillColor(col)
            cv.setLineWidth(s(1.2))
            cv.line(x, y + s(8), x, y - s(3))
            pth = cv.beginPath()
            pth.moveTo(x, y - s(10))
            pth.lineTo(x - s(5), y - s(3))
            pth.lineTo(x + s(5), y - s(3))
            pth.close()
            cv.drawPath(pth, fill=1, stroke=0)

    def tbl_cell(x, y, w, h, txt, fs=7, align='l', bold=False, col=None):
        """Cell with text wrapping on up to 3 lines to avoid overlap."""
        fs = max(3.5, fs)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", fs)
        cv.setFillColor(col or CGRAY_D)
        pad = s(2.5)
        avail_w = w - pad * 2
        t = str(txt)
        char_w = fs * 0.55
        max_chars = max(1, int(avail_w / char_w))

        lines = []
        words = t.split()
        current = ""
        for word in words:
            candidate = (current + " " + word).strip() if current else word
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word[:max_chars]
                if len(lines) >= 2:
                    break
        if current and len(lines) < 3:
            lines.append(current)
        if not lines:
            lines = [t[:max_chars]]

        line_h = fs * 1.15
        total_h = line_h * len(lines)
        start_y = y + (h - total_h) / 2 + line_h * 0.75
        for i, line in enumerate(lines):
            ly = start_y + (len(lines) - 1 - i) * line_h
            if align == 'c':
                cv.drawCentredString(x + w / 2, ly, line)
            elif align == 'r':
                cv.drawRightString(x + w - pad, ly, line)
            else:
                cv.drawString(x + pad, ly, line)

    # ── Page ─────────────────────────────────────────────────────────────────
    cv.setFillColor(white); cv.rect(0, 0, PW, PH, fill=1, stroke=0)
    cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(1.2))
    cv.rect(s(7), s(7), PW - s(14), PH - s(14), fill=0, stroke=1)
    cv.setLineWidth(s(0.4)); cv.setStrokeColor(CGRAY_M)
    cv.rect(s(10), s(10), PW - s(20), PH - s(20), fill=0, stroke=1)

    # ── 1. Header block (top-left) ───────────────────────────────────────────
    HDR_W = s(215)
    cv.setFillColor(CHDR_BG); cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(0.8))
    cv.rect(MARGIN, HDR_BOT, HDR_W, HDR_H, fill=1, stroke=1)
    cv.setFont("Helvetica-Bold", FS_HDR); cv.setFillColor(white)
    cv.drawString(MARGIN + s(5), HDR_BOT + HDR_H * 0.78,
                  f"Pi = {ps.installed_kw:.2f} kW    Pa = {ps.absorbed_kw:.2f} kW")
    cv.drawString(MARGIN + s(5), HDR_BOT + HDR_H * 0.55,
                  f"Ia = {ps.current_a:.2f} A    MCB {ps.main_breaker_a}A")
    cv.setFont("Helvetica", FS_CONN); cv.setFillColor(HexColor("#93C5FD"))
    cv.drawString(MARGIN + s(5), HDR_BOT + HDR_H * 0.28, ps.connection[:40])
    cv.setFont("Helvetica", max(3.5, FS_CONN - 1)); cv.setFillColor(HexColor("#93C5FD"))
    cv.drawString(MARGIN + s(5), HDR_BOT + s(5),
                  f"ku={ps.simultaneity_ks:.2f}")

    # ── 2. Panel title ────────────────────────────────────────────────────────
    cv.setFont("Helvetica-Bold", FS_PANEL); cv.setFillColor(CGRAY_D)
    cv.drawCentredString(PW / 2, HDR_BOT + HDR_H * 0.55, f"{panel_name}  —  {panel_desc}")
    cv.setFont("Helvetica", FS_SUBT); cv.setFillColor(CGRAY_M)
    cv.drawCentredString(PW / 2, HDR_BOT + HDR_H * 0.28,
                         (pinfo.get("titlu_proiect") or "")[:80])
    cv.setStrokeColor(CGRAY_M); cv.setLineWidth(s(0.5))
    cv.line(MARGIN, HDR_BOT - s(2), PW - MARGIN, HDR_BOT - s(2))
    cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(1.5))
    cv.line(MARGIN, HDR_BOT - s(4), PW - MARGIN, HDR_BOT - s(4))

    # ── 3. Main breaker ───────────────────────────────────────────────────────
    MCB_MAIN_CY = BUS_Y + s(78)
    cv.setStrokeColor(black); cv.setLineWidth(s(1.5))
    cv.line(BRK_X, HDR_BOT - s(8), BRK_X, MCB_MAIN_CY + s(13))
    mcb_sym(BRK_X, MCB_MAIN_CY, bw=s(16), bh=s(24), n_poles=3 if is_trifazat else 1)
    if has_spd:
        cv.setFillColor(HexColor("#FEF3C7")); cv.setStrokeColor(CGRAY_D)
        cv.setLineWidth(s(0.7))
        cv.rect(BRK_X - s(14), MCB_MAIN_CY + s(28), s(28), s(16), fill=1, stroke=1)
        cv.setFont("Helvetica-Bold", max(4.0, s(6))); cv.setFillColor(CGRAY_D)
        cv.drawCentredString(BRK_X, MCB_MAIN_CY + s(35), "SPD T2")
    cv.setFont("Helvetica-Bold", max(4.5, s(6.5))); cv.setFillColor(CGRAY_D)
    cv.drawCentredString(BRK_X, MCB_MAIN_CY + s(18), "C0")
    cv.setFont("Helvetica", max(4.0, s(5.5)))
    cv.drawCentredString(BRK_X, MCB_MAIN_CY - s(17),
                         f"{'3P+N' if is_trifazat else '1P+N'}, {ps.main_breaker_a}A C")
    rtext(BRK_X - s(24), BUS_Y + s(38), main_cable, FS_SM, angle=90, col=CGRAY_M)
    cv.setStrokeColor(black); cv.setLineWidth(s(1.5))
    cv.line(BRK_X, MCB_MAIN_CY - s(12), BRK_X, BUS_Y)
    cv.setFillColor(black); cv.circle(BRK_X, BUS_Y, s(3), fill=1)

    # ── 4. Busbar ─────────────────────────────────────────────────────────────
    cv.setStrokeColor(CBUSBAR); cv.setLineWidth(s(3.5))
    cv.line(BUS_X_S, BUS_Y, BUS_X_E, BUS_Y)
    cv.setFont("Helvetica-Bold", max(4.5, s(6))); cv.setFillColor(CBUSBAR)
    cv.drawString(BUS_X_S, BUS_Y + s(5), "400V" if is_trifazat else "230V")
    cv.setStrokeColor(HexColor("#2563EB")); cv.setLineWidth(s(1.2))
    cv.setDash([s(4), s(2)])
    cv.line(BUS_X_S, BUS_Y - s(9), BUS_X_E, BUS_Y - s(9))
    cv.setDash()
    cv.setFont("Helvetica", max(3.5, s(5))); cv.setFillColor(HexColor("#2563EB"))
    cv.drawString(BUS_X_S, BUS_Y - s(15), "N")
    cv.setStrokeColor(HexColor("#16A34A")); cv.setLineWidth(s(1.2))
    cv.line(BUS_X_S, BUS_Y - s(17), BUS_X_E, BUS_Y - s(17))
    cv.setFont("Helvetica", max(3.5, s(5))); cv.setFillColor(HexColor("#16A34A"))
    cv.drawString(BUS_X_S, BUS_Y - s(23), "PE")

    # ── 5. RCCB groups (above busbar) ────────────────────────────────────────
    ckt_ids = [ckt.get("id", f"C{i+1}") for i, ckt in enumerate(circuits)]
    for grp in rccb_groups:
        gids = grp.get("circuits", [])
        g_a  = grp.get("rating_a", 40)
        g_ma = grp.get("sensitivity_ma", 30)
        gi   = [i for i, cid in enumerate(ckt_ids) if cid in gids]
        if not gi: continue
        xf = BUS_X_S + (gi[0]  + 0.5) * SPACING
        xl = BUS_X_S + (gi[-1] + 0.5) * SPACING
        xm = (xf + xl) / 2
        RY = BUS_Y + s(32)
        cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(0.6))
        cv.line(xf, BUS_Y + s(3), xf, RY)
        cv.line(xl, BUS_Y + s(3), xl, RY)
        cv.line(xf, RY, xl, RY)
        cv.setFillColor(white); cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(0.7))
        cv.rect(xm - s(12), RY + s(2), s(24), s(13), fill=1, stroke=1)
        cv.circle(xm, RY + s(21), s(5), fill=0, stroke=1)
        cv.setFont("Helvetica", max(3.5, s(5))); cv.setFillColor(CGRAY_D)
        cv.drawCentredString(xm, RY + s(6), "Δ")
        cv.setFont("Helvetica", max(3.5, s(5.5)))
        cv.drawCentredString(xm, RY + s(29), f"{g_a}A/{g_ma}mA")

    # ── 6. Circuit branches ───────────────────────────────────────────────────
    PHASES = ["R", "S", "T"]
    ph_idx = 0
    for i, ckt in enumerate(circuits):
        xc     = BUS_X_S + (i + 0.5) * SPACING
        ctype  = ckt.get("type", "prize")
        is3p   = "3P" in ckt.get("breaker_type", "")
        ba     = ckt.get("breaker_a", 16)
        is_b   = ckt.get("is_bathroom", False)
        cid    = ckt.get("id", f"C{i+1}")
        desc   = (ckt.get("description", "") or "")
        ol     = ckt.get("outlets", 0)
        lp     = ckt.get("lighting_points", 0)
        ph     = "RST" if is3p else PHASES[ph_idx % 3]
        if not is3p: ph_idx += 1
        is_rez = ctype == "rezerva"
        col    = _ckt_color(ctype, is_b)

        # Phase + branch-number label above busbar (rotated -90°)
        rtext(xc, BUS_Y + s(14), f"{cid}({ph})", FS_LBL, angle=-90, col=CGRAY_D)
        # Breaker rating just below busbar
        rtext(xc, BUS_Y - s(6),
              f"{ba}A", max(3.5, s(4.5)), angle=-90, col=CGRAY_M)

        MCB_CY = BRANCH_BOT + (BRANCH_TOP - BRANCH_BOT) * 0.68
        LOAD_Y = BRANCH_BOT + s(20)

        # Dashed branch line for rezerva
        lw = s(0.8)
        cv.setStrokeColor(col); cv.setLineWidth(lw)
        if is_rez: cv.setDash([s(3), s(2)])
        cv.line(xc, BUS_Y - s(24), xc, MCB_CY + (s(24) if is_b else s(14)))
        cv.setDash()

        # Breaker symbol
        if is_b and not is_rez:
            rccb_sym(xc, MCB_CY)
        else:
            mcb_sym(xc, MCB_CY, n_poles=3 if is3p else 1)

        # Line from breaker to load
        cv.setStrokeColor(col); cv.setLineWidth(lw)
        if is_rez: cv.setDash([s(3), s(2)])
        cv.line(xc, MCB_CY - (s(18) if is_b else s(12)), xc, LOAD_Y + s(13))
        cv.setDash()

        load_sym(xc, LOAD_Y, ctype, is_bath=is_b, outlets=ol, lpts=lp)

        # Circuit ID + description rotated -90° at branch bottom
        rtext(xc, BRANCH_BOT + s(5), f"{cid} {desc[:16]}", FS_SM,
              angle=-90, col=CREZV if is_rez else CGRAY_D)

    # ── 7. Data table — 7 columns, C0 row, circuit rows ──────────────────────
    # Column proportions: Nr.6 / Destinatie22 / Pi12 / Ia12 / Protectie22 / Cablu14 / Pozare12
    _PCT  = [6, 22, 12, 12, 22, 14, 12]
    _HDRS = ["Nr.", "Destinatie", "Pi kW", "Ia A", "Protectie", "Cablu", "Pozare"]
    _CWS  = [p_ / 100 * TABLE_W for p_ in _PCT]

    HDR_ROW_H = s(18)
    # Reserve space for C0 row + all circuit rows
    DATA_ROWS = len(circuits) + 1   # +1 for C0
    avail = TABLE_H - HDR_ROW_H - s(1)
    RH = min(s(22), avail / max(DATA_ROWS, 1))
    RH = max(RH, s(10))

    # Table outer border
    cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(0.8))
    cv.rect(TABLE_X, TABLE_Y, TABLE_W, TABLE_H, fill=0, stroke=1)

    def _draw_row(vals_aligns, y, rh, bg):
        x0 = TABLE_X
        for j, ((val, al), cw) in enumerate(zip(vals_aligns, _CWS)):
            cv.setFillColor(bg); cv.setStrokeColor(CGRAY_M); cv.setLineWidth(s(0.3))
            cv.rect(x0, y, cw, rh, fill=1, stroke=1)
            tbl_cell(x0, y, cw, rh, val, FS_TBL, al)
            x0 += cw

    # Header row
    hdr_y = TABLE_Y + TABLE_H - HDR_ROW_H
    x0 = TABLE_X
    for hdr, cw in zip(_HDRS, _CWS):
        cv.setFillColor(CGRAY_L); cv.setStrokeColor(CGRAY_M); cv.setLineWidth(s(0.4))
        cv.rect(x0, hdr_y, cw, HDR_ROW_H, fill=1, stroke=1)
        tbl_cell(x0, hdr_y, cw, HDR_ROW_H, hdr, FS_TBL, 'c', bold=True)
        x0 += cw

    # C0 row (main breaker / intreruptor general)
    c0_y = hdr_y - RH
    _u0  = 400 * (3 ** 0.5) * 0.9 if is_trifazat else 230 * 0.92
    _ia0 = ps.current_a
    _p0  = f"MCB {'3P' if is_trifazat else '1P'} {ps.main_breaker_a}A C 10kA"
    _draw_row([
        ("C0", 'c'), ("Intreruptor general", 'l'),
        (f"{ps.installed_kw:.2f}", 'c'), (f"{_ia0:.2f}", 'c'),
        (_p0[:24], 'l'), ((main_cable or "—")[:22], 'l'), ("—", 'c'),
    ], c0_y, RH, HexColor("#EFF6FF"))
    # Highlight C0 ID cell with panel color
    cv.setFillColor(CHDR_BG)
    cv.rect(TABLE_X, c0_y, _CWS[0], RH, fill=1, stroke=0)
    tbl_cell(TABLE_X, c0_y, _CWS[0], RH, "C0", FS_TBL, 'c', bold=True, col=white)

    # Circuit rows
    for i, ckt in enumerate(circuits):
        ry = c0_y - (i + 1) * RH
        if ry < TABLE_Y: break
        bg     = HexColor("#F9FAFB") if i % 2 == 0 else white
        ba_r   = ckt.get("breaker_a", 16)
        is3p_r = "3P" in ckt.get("breaker_type", "")
        is_b_r = ckt.get("is_bathroom", False)
        pw_kw  = ckt.get("power_w", 0) / 1000
        u_r    = 400 * (3 ** 0.5) * 0.9 if is3p_r else 230 * 0.92
        ia_r   = pw_kw * 1000 / u_r if pw_kw > 0 else 0
        ct_r   = ckt.get("type", "prize")
        is_rez_r = ct_r == "rezerva"
        if is_rez_r:
            prot_r = "—"
        else:
            prot_r = f"MCB {'3P' if is3p_r else '1P'}+N {ba_r}A C"
            if is_b_r: prot_r += " RCD30"
        _draw_row([
            (ckt.get("id", f"C{i+1}"), 'c'),
            (ckt.get("description", "") or "", 'l'),
            (f"{pw_kw:.2f}" if not is_rez_r else "—", 'c'),
            (f"{ia_r:.2f}"  if not is_rez_r else "—", 'c'),
            (prot_r, 'l'),
            (ckt.get("cable_type", "") or "", 'l'),
            (ckt.get("pozare", "") or "", 'l'),
        ], ry, RH, bg)
        # Color-coded ID cell
        cv.setFillColor(_ckt_color(ct_r, is_b_r) if not is_rez_r else CREZV)
        cv.rect(TABLE_X, ry, _CWS[0], RH, fill=1, stroke=0)
        tbl_cell(TABLE_X, ry, _CWS[0], RH,
                 ckt.get("id", f"C{i+1}"), FS_TBL, 'c', bold=True, col=white)

    # ── 8. Cartus — fixed 120mm × 80mm, bottom-right ─────────────────────────
    TX, TY_, TW, TH_ = TITLE_X, TABLE_Y, TITLE_W, TITLE_H
    # Double border
    cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(1.5))
    cv.rect(TX, TY_, TW, TH_, fill=0, stroke=1)
    cv.setLineWidth(s(0.4)); cv.setStrokeColor(CGRAY_M)
    cv.rect(TX + s(2.5), TY_ + s(2.5), TW - s(5), TH_ - s(5), fill=0, stroke=1)

    NR = 8; rh_t = TH_ / NR
    col1 = TX + TW * 0.38; col2 = TX + TW * 0.72
    cv.setStrokeColor(CGRAY_M); cv.setLineWidth(s(0.3))
    for r_ in range(1, NR):
        cv.line(TX + s(2.5), TY_ + r_ * rh_t, TX + TW - s(2.5), TY_ + r_ * rh_t)
    cv.line(col1, TY_ + s(2.5), col1, TY_ + TH_ - s(2.5))
    cv.line(col2, TY_ + s(2.5), col2, TY_ + TH_ - s(2.5))

    def _tcell(txt, x, y, w, h, bold=False, center=False, col_=None):
        tbl_cell(x + s(2), y + s(1), w - s(4), h - s(2), txt, FS_CART,
                 'c' if center else 'l', bold=bold, col=col_ or CGRAY_D)

    pi = pinfo

    def trow(c1, c2, c3, rft, b1=False):
        ry_ = TY_ + (NR - 1 - rft) * rh_t
        _tcell(c1[:22],  TX,   ry_, col1 - TX, rh_t, bold=b1, col_=CHDR_BG if b1 else CGRAY_D)
        _tcell(c2[:28],  col1, ry_, col2 - col1, rh_t)
        _tcell(c3[:20],  col2, ry_, TX + TW - col2, rh_t)

    # Row 0: highlighted project title (full width)
    cv.setFillColor(HexColor("#EFF6FF"))
    cv.rect(TX + s(2.5), TY_ + s(2.5), TW - s(5), rh_t - s(2.5), fill=1, stroke=0)
    # Titlu pe MAI MULTE LINII in interiorul chenarului (acelasi wrap ca Beneficiar/Amplasament,
    # via tbl_cell), nu o singura linie care iese afara la titluri lungi (ex. casa LASAK).
    tbl_cell(TX + s(2.5), TY_ + s(2.5), TW - s(5), rh_t - s(2.5),
             (pi.get("titlu_proiect") or "SCHEMA MONOFILARA"),
             max(5.0, FS_CART + 0.5), 'c', bold=True, col=CBUSBAR)

    trow("Beneficiar:", (pi.get("beneficiar") or "")[:40], "", 1)
    trow("Amplasament:", (pi.get("amplasament") or "")[:40], "", 2)
    trow("Proiectant:", (pi.get("sef_proiect") or "")[:26],
         f"Nr.: {pi.get('proiect_nr', '')}", 3)
    trow("Verificat: ____________", f"Faza: {pi.get('faza', 'DTAC')}",
         f"Pl.: {plansa_nr}", 4)
    trow("Data:", pi.get("data", "")[:22], "Scara: 1:___", 5)
    trow("PROIECT", "INSTALATII ELECTRICE", "", 6, b1=True)
    trow("ZYNAPSE v4", "I7-2011  NP 061-2002", "", 7, b1=True)

    cv.setStrokeColor(CGRAY_D); cv.setLineWidth(s(0.8))
    cv.line(TX + s(2.5), TY_ + rh_t, TX + TW - s(2.5), TY_ + rh_t)

    # ── 9. Legenda — fixed 80mm × 55mm, double border, right of schema ────────
    LX   = PW - MARGIN - LGD_W
    LY_L = HDR_BOT - s(5) - LGD_H
    if LY_L > BUS_Y + s(55):
        # Double border
        cv.setFillColor(HexColor("#FAFAFA")); cv.setStrokeColor(CGRAY_M)
        cv.setLineWidth(s(0.6)); cv.rect(LX, LY_L, LGD_W, LGD_H, fill=1, stroke=1)
        cv.setLineWidth(s(0.3))
        cv.rect(LX + s(2), LY_L + s(2), LGD_W - s(4), LGD_H - s(4), fill=0, stroke=1)
        cv.setFont("Helvetica-Bold", max(4.5, s(6.5))); cv.setFillColor(CGRAY_D)
        cv.drawString(LX + s(5), LY_L + LGD_H - s(9), "LEGENDA")
        lgd_items = [
            ("MCB",    CGRAY_D, "Disjunctor TM (MCB-C)"),
            ("RCCB",   CGRAY_D, "Prot. diferentiala"),
            ("⊗", CBLUE,   "Corp iluminat (LL)"),
            ("●", CAMBER,  "Priza 230V (LP)"),
            ("↓", CGREEN,  "Receptor dedicat"),
            ("□--", CREZV, "Rezerva circuit"),
        ]
        item_h = (LGD_H - s(12)) / max(len(lgd_items), 1)
        for j, (sym, scol, txt) in enumerate(lgd_items):
            yy = LY_L + LGD_H - s(12) - j * item_h
            if yy < LY_L + s(4): break
            cv.setFont("Helvetica-Bold", max(3.5, s(7))); cv.setFillColor(scol)
            cv.drawString(LX + s(5), yy, sym)
            cv.setFont("Helvetica", max(3.5, s(6))); cv.setFillColor(CGRAY_D)
            cv.drawString(LX + s(28), yy, txt)

    # ── 10. Nota (2 lines) ────────────────────────────────────────────────────
    nota_top = SCHEMA_BOT - s(1)
    ks = getattr(ps, 'simultaneity_ks', 0.7)
    cv.setFont("Helvetica", max(3.5, s(5.5))); cv.setFillColor(CGRAY_M)
    cv.drawString(TABLE_X + s(2), nota_top - s(6),
                  f"Nota 1: I7-2011 Tab. 3.5 — ku={ks:.2f}. "
                  "Protectiile se verifica si se inlocuiesc daca nivelul Isc "
                  "difera de cel de calcul.")
    if NOTA_H > s(13):
        cv.drawString(TABLE_X + s(2), nota_top - s(12),
                      "Nota 2: Executantul va respecta prevederile I7-2011, "
                      "SR EN 60364, Legea 10/1995 si legislatia in vigoare la "
                      "data executiei lucrarii.")

    # ── Watermark ─────────────────────────────────────────────────────────────
    cv.setFont("Helvetica", max(3.5, s(5))); cv.setFillColor(CGRAY_M)
    cv.drawRightString(TITLE_X - s(8), TABLE_Y + s(2),
                       "Generat automat · ZYNAPSE v4.0 · I7-2011 · zynapse.ro")


def _generate_multi_schema(req: GenerateSchemaMultiRequest) -> list:
    try:
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        raise RuntimeError("reportlab not installed")

    ps      = req.power_summary
    pinfo   = req.project_info or {}
    equip   = req.equipment or EquipmentInfoNew()
    rgrps   = req.panel.rccb_groups or []
    has_spd = req.panel.has_spd
    is_tri  = "Trifazat" in (ps.connection or "")
    base_n  = _next_plansa_nr(pinfo)
    results: list = []

    all_ckts = [c.model_dump() for c in req.circuits if c.type != "date"]

    # ── Group circuits by floor ──────────────────────────────────────────────
    by_floor: dict = {}
    for c in all_ckts:
        fl = _detect_floor(c.get("level"), c.get("room"), c.get("id", ""))
        by_floor.setdefault(fl, []).append(c)

    # Circuits on PARTER go to TEG; everything else gets a TES panel.
    # Fallback: if no floor info at all, all circuits are PARTER.
    tes_floors  = [f for f in _FLOOR_ORDER if f in by_floor]
    parter_ckts = by_floor.get("PARTER", all_ckts if not tes_floors else [])

    # ── Build feeder circuits TEG → each TES panel ──────────────────────────
    feeder_circuits: list = []
    tes_panel_meta: dict  = {}   # floor → {ckts, feeder_id, main_breaker_a, cable}

    for floor in tes_floors:
        tes_ckts   = by_floor[floor]
        total_pw_w = sum(c.get("power_w", 0) for c in tes_ckts)
        ks         = ps.simultaneity_ks or 0.7
        total_ia   = total_pw_w * ks / (230 * 0.92)
        brk        = _breaker_for_current(total_ia)
        cable      = _feeder_cable(total_ia)
        _, tes_name, _ = _FLOOR_INFO[floor]
        fid = f"F-{tes_name[4:]}"   # "F-E1", "F-E2", "F-MAN", "F-DS", "F-SS"

        feeder_circuits.append({
            "id": fid, "type": "dedicat",
            "description": f"ALIM. {tes_name}",
            "power_w": total_pw_w * ks,
            "breaker_a": brk, "breaker_type": "MCB-1P-C",
            "cable_type": cable, "pozare": "IPEY 25mm",
            "outlets": 0, "lighting_points": 0,
            "is_bathroom": False, "is_dedicated": True,
        })
        tes_panel_meta[floor] = {
            "ckts": tes_ckts, "feeder_id": fid,
            "main_breaker_a": brk, "cable": cable,
        }

    teg_ckts = parter_ckts + feeder_circuits

    # Resolve requested format ("A4"/"A3"/"A2"/"A1"/"A2+A3" or auto)
    req_fmt = (req.page_format or "").upper().strip()

    # ── Helper: render one logical panel (with auto A/B overflow split) ──────
    def _render(name, desc, ie_nr, ckts, p_ps, p_rgrps, p_spd, p_cable, p_tri):
        # Sort & number circuits; rebuild RCCB groups from per-circuit rccb_group field
        ckts = _sort_and_number_circuits(ckts)
        _rgrp_map: dict = {}
        for _c in ckts:
            _gn = _c.get("rccb_group")
            if _gn:
                _rgrp_map.setdefault(_gn, []).append(_c["id"])
        if _rgrp_map:
            p_rgrps = [{"circuits": ids, "rating_a": 40, "sensitivity_ma": 30}
                       for ids in _rgrp_map.values()]
        # Per-panel format: A2+A3 gives TEG→A2, others→A3; explicit overrides auto
        if req_fmt == "A2+A3":
            fmt = "A2" if name == "TEG" else "A3"
        elif req_fmt == "A1+A3":
            fmt = "A1" if name == "TEG" else "A3"
        elif req_fmt == "A0+A3":
            fmt = "A0" if name == "TEG" else "A3"
        elif req_fmt in _PAGE_FMT_INFO:
            fmt = req_fmt
        else:
            fmt = _auto_page_format(len(ckts))   # auto: pick smallest that fits

        max_c     = _PAGE_FMT_INFO[fmt]["max_circuits"]
        _pw, _ph  = _page_size_pt(fmt)
        chunks    = (
            [ckts[i:i + max_c] for i in range(0, len(ckts), max_c)]
            if len(ckts) > max_c else [ckts]
        )
        for part, chunk in enumerate(chunks):
            suffix = chr(ord("A") + part) if len(chunks) > 1 else ""
            p_name = f"{name}{'-' + suffix if suffix else ''}"
            p_nr   = f"{ie_nr}{suffix}"
            chunk_pw = sum(c.get("power_w", 0) for c in chunk)
            u = 400 * (3 ** 0.5) * 0.9 if p_tri else 230 * 0.92
            chunk_ps = PowerSummaryNew(
                installed_kw    = chunk_pw / 1000,
                absorbed_kw     = chunk_pw / 1000 * p_ps.simultaneity_ks,
                current_a       = chunk_pw / 1000 * 1000 / u,
                main_breaker_a  = p_ps.main_breaker_a,
                connection      = p_ps.connection,
                simultaneity_ks = p_ps.simultaneity_ks,
            ) if len(chunks) > 1 else p_ps
            buf = io.BytesIO()
            cv  = rl_canvas.Canvas(buf, pagesize=(_pw, _ph))
            _draw_schema_page(
                cv, p_name, desc, p_nr, chunk, pinfo, chunk_ps,
                p_rgrps if part == 0 else [],
                p_spd   if part == 0 else False,
                p_cable if part == 0 else f"Continuare {name}-{chr(ord('A') + part - 1)}",
                p_tri, pw=_pw, ph=_ph,
            )
            cv.save()
            results.append({
                "name": p_name, "plansa_nr": p_nr,
                "pdf_base64": "data:application/pdf;base64,"
                              + base64.b64encode(buf.getvalue()).decode(),
            })

    # ── 1. TEG — always (PARTER + feeders to TES panels) ────────────────────
    _render(
        "TEG", "TABLOU ELECTRIC GENERAL",
        f"IE.{base_n}", teg_ckts, ps, rgrps, has_spd,
        "CYABY 5×10mmp / De la BMPT" if is_tri else "CYY-F 3×10mmp / De la BMPT",
        is_tri,
    )
    next_n = base_n + 1

    # ── 2. TE-CT — if thermal equipment present (always IE.4) ─────────────
    needs_tect = equip.boiler_acm or equip.pdc or equip.pompe_circulatie or equip.ventilatie_hrv
    if needs_tect:
        tect_c  = _get_tect_circuits(equip)
        tect_pw = sum(c.get("power_w", 0) for c in tect_c)
        tect_ps = PowerSummaryNew(
            installed_kw=tect_pw / 1000, absorbed_kw=tect_pw / 1000,
            current_a=tect_pw / 230 / 0.92, main_breaker_a=32,
            connection="Monofazat 230V+N+PE", simultaneity_ks=1.0,
        )
        _render("TE-CT", "TABLOU ELECTRIC CENTRALA TERMICA",
                f"IE.{next_n}", tect_c, tect_ps, [], False,
                "CYY-F 5×4mmp / De la TEG", False)
        next_n += 1

    # ── 3. TES-En — one per detected floor above PARTER (IE.5+) ─────────────
    for floor in tes_floors:
        meta             = tes_panel_meta[floor]
        _, tes_name, tes_desc = _FLOOR_INFO[floor]
        tes_ckts         = meta["ckts"]
        tes_pw           = sum(c.get("power_w", 0) for c in tes_ckts)
        tes_ps           = PowerSummaryNew(
            installed_kw    = tes_pw / 1000,
            absorbed_kw     = tes_pw / 1000 * ps.simultaneity_ks,
            current_a       = tes_pw / 230 / 0.92,
            main_breaker_a  = meta["main_breaker_a"],
            connection      = "Monofazat 230V+N+PE",
            simultaneity_ks = ps.simultaneity_ks,
        )
        _render(
            tes_name, tes_desc,
            f"IE.{next_n}", tes_ckts, tes_ps, [], False,
            f"{meta['cable']} / De la TEG, Circuit {meta['feeder_id']}",
            False,
        )
        next_n += 1

    return results


@app.post("/generate-schema")
def generate_schema(request: SchemaRequestV2):
    """
    Genereaza schema electrica monofilara in format panoramic v2.
    Inaltime fixa 297mm, latime variabila (420/594/841mm).
    Multi-page pentru >18 circuite.
    """
    try:
        pdf_bytes = generate_schema_pdf(request)
        filename = f"{request.tablou_nume}_schema_monofilara.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/generate-schema/test")
def generate_schema_test():
    """
    Endpoint de testare cu date hardcoded (31 circuite, 2 pagini A1).
    Deschide direct in browser: https://wattson-api.onrender.com/generate-schema/test
    """
    try:
        sample = build_sample_request()
        pdf_bytes = generate_schema_pdf(sample)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="test_schema.pdf"'}
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


# kept for internal reference — no longer exposed as endpoint
def _generate_schema_multi_legacy(req: GenerateSchemaMultiRequest):
    """Legacy multi-panel generator. Not exposed. Use /generate-schema (v2) instead."""
    _t0 = _time.time()
    logger.info(f"legacy multi-schema: user_id={repr(req.user_id)}, circuits={len(req.circuits or [])}")

    try:
        schemas = _generate_multi_schema(req)
    except Exception as e:
        safe_log(
            user_id=req.user_id,
            actiune="generate-schema",
            proiect_id=req.project_id,
            durata_ms=int((_time.time() - _t0) * 1000),
            succes=False,
            eroare=str(e),
        )
        return {"error": str(e), "schemas": []}

    _durata_ms = int((_time.time() - _t0) * 1000)
    saved_project_id: Optional[str] = req.project_id

    if req.user_id:
        try:
            # Circuits are Pydantic models — convert to plain dicts for storage
            circuits_list = [
                c.model_dump() if hasattr(c, "model_dump") else dict(c)
                for c in (req.circuits or [])
            ]
            project_data = {
                "circuits":      circuits_list,
                "circuits_all":  circuits_list,
                "bom":           req.bom or [],
                "power_summary": req.power_summary.model_dump() if req.power_summary else {},
                "project_info":  req.project_info or {},
                "building_type": req.building_type or "cultural",
                "output_phase":  (req.project_info or {}).get("faza") or "DTAC",
            }
            saved_project_id = save_project(req.user_id, project_data)
            logger.info(f"project saved: {saved_project_id}")
        except Exception as e:
            logger.error("[save_project] Failed: %s", e)

    if saved_project_id and schemas:
        for s in schemas:
            try:
                save_project_file(
                    project_id=saved_project_id,
                    tip=f"schema_{s.get('name', 'monofilara').lower().replace(' ', '_')}",
                    pdf_base64=s.get("pdf_base64", ""),
                    plansa_nr=s.get("plansa_nr"),
                    page_format=s.get("page_format"),
                )
            except Exception as e:
                logger.error("[save_project_file] Failed: %s", e)

    safe_log(
        user_id=req.user_id,
        actiune="generate-schema",
        proiect_id=saved_project_id,
        durata_ms=_durata_ms,
        succes=True,
    )
    return {
        "schemas": schemas,
        "saved": bool(saved_project_id and req.user_id),
        "project_id": saved_project_id,
    }


@app.get("/health")
async def health():
    import os
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    sb_ok = False
    sb_err = None

    if not url or not key:
        sb_err = f"missing: url={bool(url)} key={bool(key)}"
    else:
        try:
            from supabase import create_client
            c = create_client(url, key)
            r = c.table("app_settings").select("key").limit(1).execute()
            sb_ok = True
        except Exception as e:
            sb_err = str(e)

    return {
        "status": "ok",
        "version": "4.0.0",
        "supabase": sb_ok,
        "supabase_error": sb_err,
        "env_url": bool(url),
        "env_key": bool(key),
    }


# -------------------------------------------------
#  MEMORIU TEHNIC (.docx)  —  POST /generate-memoriu
# -------------------------------------------------

class MemoriuCartusProiect(BaseModel):
    beneficiar: str = ""
    titlu_proiect: str = ""
    amplasament: str = ""
    numar_proiect: str = ""
    faza: str = ""


class MemoriuCartusFirma(BaseModel):
    firma_nume: str = ""
    firma_reg_com: str = ""
    firma_cui: str = ""
    firma_tel: str = ""
    firma_email: str = ""
    firma_atestat: str = ""
    firma_logo_url: str = ""
    sef_proiect: str = ""
    proiectant_nume: str = ""


class MemoriuPlansa(BaseModel):
    nr: str = ""
    titlu: str = ""


class GenerateMemoriuRequest(BaseModel):
    cartus_proiect: MemoriuCartusProiect = MemoriuCartusProiect()
    cartus_firma: MemoriuCartusFirma = MemoriuCartusFirma()
    planse: List[MemoriuPlansa] = []
    # M5 (brevier de calcul) — date REALE pt. brevier. Optional (default gol -> backward-compat:
    # cererile vechi/fara aceste campuri merg normal; brevierul B le foloseste cand exista).
    circuits: List[dict] = []        # circuite (type/power_w/cable_type) -> putere iluminat reala
    power_summary: dict = {}         # current_a (Ic TEG), main_breaker_a, installed_kw, ...


@app.post("/generate-memoriu")
def generate_memoriu(request: GenerateMemoriuRequest):
    """Genereaza memoriul tehnic instalatii electrice ca .docx, returnat base64.
    Acelasi pattern ca /generate-schema-b64 (erori cu status 200 pentru n8n)."""
    try:
        docx_bytes = build_memoriu_docx(request.model_dump())
        numar = (request.cartus_proiect.numar_proiect or "proiect").strip()
        safe_numar = numar.replace("/", "-").replace(" ", "_") or "proiect"
        return {
            "success": True,
            "docx_base64": base64.b64encode(docx_bytes).decode("utf-8"),
            "filename": f"Memoriu_Tehnic_{safe_numar}.docx",
            "size_bytes": len(docx_bytes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  SWAP CARTUS PLAN (.pdf overlay)  —  POST /swap-cartus-plan
# -------------------------------------------------

class SwapCartusFirma(BaseModel):
    firma_nume: str = ""
    firma_reg_com: str = ""
    firma_cui: str = ""
    firma_tel: str = ""
    firma_email: str = ""
    firma_logo_url: str = ""
    sef_proiect: str = ""
    proiectant_nume: str = ""


class SwapCartusProiect(BaseModel):
    beneficiar: str = ""
    titlu_proiect: str = ""
    amplasament: str = ""
    numar_proiect: str = ""
    faza: str = ""
    sef_proiect: str = ""     # confirmat in modalul cartusului (Vision propune, inginerul confirma)


class SwapCartusRequest(BaseModel):
    pdf_base64: str = ""
    cartus_firma: SwapCartusFirma = SwapCartusFirma()
    cartus_proiect: SwapCartusProiect = SwapCartusProiect()
    plansa_nr: str = ""
    plansa_titlu: str = ""
    rooms: Optional[list] = None   # bbox-uri Vision (fracții 0-1, {x,y,w,h}) -> mascare margini. Lipsă -> fără mascare.


@app.post("/swap-cartus-plan")
def swap_cartus_plan_endpoint(request: SwapCartusRequest):
    """Detecteaza cartusul arhitectului pe planul PDF si il inlocuieste cu cartusul
    firmei (overlay vectorial, format + scara pastrate). Erori cu status 200 (n8n)."""
    try:
        return swap_cartus_plan(request.model_dump())
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  DRAW PLAN ELEMENTS (.pdf overlay)  —  POST /draw-plan-elements
# -------------------------------------------------

class DrawPlanElementsRequest(BaseModel):
    pdf_base64: str = ""
    plansa_nr: str = ""
    plan_type: str = "iluminat"  # deocamdată doar iluminat (becuri)
    rooms: Optional[list] = None  # camere cu bbox Vision (fracții 0-1); lipsă -> fallback regex
    apply_geometry: bool = False  # True DOAR pe faza PT (din n8n) -> centroid geometric din pereți
    project_id: str = ""          # uuid Supabase (din save_project) -> persistă elementele în plan_elements (OPȚIONAL)
    floor: str = "parter"         # eticheta etaj pt. plan_elements (idempotență per project_id+floor)


@app.post("/draw-plan-elements")
def draw_plan_elements_endpoint(request: DrawPlanElementsRequest):
    try:
        return draw_elements.draw_plan_elements(request.model_dump())
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  ENRICH CIRCUITS (Faza 2)  —  POST /enrich-circuits
#  Circuite IMBOGATITE din PLAN (plan_elements) -> format result_data.circuits, ca schema+memoriu
#  (Finalize) sa fie consistente cu PLANUL, nu cu Vision. Fail-safe: eroare -> success:False +
#  circuits:[] (caller-ul /api/finalize cade pe circuitele vechi Vision -> nu blocheaza finalizarea).
# -------------------------------------------------

class EnrichCircuitsRequest(BaseModel):
    plan_elements: list = []
    form: dict = {}
    base_circuits: list = []   # result_data.circuits — TE-CT + feed coloana se PRESERVA de aici


@app.post("/enrich-circuits")
def enrich_circuits_endpoint(request: EnrichCircuitsRequest):
    try:
        import enrich_circuits as _ec
        circuits = _ec.enrich_circuits(request.plan_elements or [], request.form or {},
                                       base_circuits=request.base_circuits or [])
        return {"success": True, "circuits": circuits, "count": len(circuits)}
    except Exception as e:
        return {"success": False, "error": str(e), "circuits": []}


# -------------------------------------------------
#  BOM / LISTA DE CANTITATI (antemasuratori)  —  POST /bom
#  7 categorii (sigurante/cabluri/prize/becuri/tablouri/receptoare/tuburi) din SURSA UNIFICATA
#  (enrich_circuits + plan_elements) -> CONSISTENT cu schema/memoriu (aceleasi numere). Metri:
#  scala per-proiect din area_m2 (fallback fix ~1:71). Self-contained: citeste DB pe project_id.
# -------------------------------------------------

class BomRequest(BaseModel):
    project_id: str = ""
    base_pdf_base64: str = ""   # pt. W/H (scala per-proiect); OPTIONAL -> fallback scala fixa
    form: dict = {}             # extra_equipment (puteri receptoare), ca la enrich
    waste: float = 1.0          # adaos la capete (1.0 = fara; 1.10 = +10%)


@app.post("/bom")
def bom_endpoint(request: BomRequest):
    """Lista de cantitati din circuitele UNIFICATE (enrich) + plan_elements. Fail-safe: eroare ->
    success:False. Citeste plan_elements + result_data (rooms/area_m2 + circuits) din DB (service-role)."""
    try:
        import bom as _bom
        import enrich_circuits as _ec
        if not request.project_id:
            return {"success": False, "error": "project_id lipseste", "rows": []}
        from supabase_client import supabase as _supa
        rows = (_supa.table("plan_elements").select("*")
                .eq("project_id", request.project_id).execute().data) or []
        proj = (_supa.table("projects").select("result_data")
                .eq("id", request.project_id).single().execute().data) or {}
        rd = (proj.get("result_data") or {})
        _rooms = rd.get("rooms") or []
        base_circuits = rd.get("circuits") or []
        # W/H din base_pdf (scala per-proiect exacta); lipsa -> derive_scale cade pe scala fixa.
        _W = _H = 0.0
        if request.base_pdf_base64:
            try:
                import fitz
                _raw = request.base_pdf_base64.split(",", 1)[1] if "," in request.base_pdf_base64 else request.base_pdf_base64
                _doc = fitz.open(stream=base64.b64decode(_raw), filetype="pdf")
                _W, _H = _doc[0].rect.width, _doc[0].rect.height
                _doc.close()
            except Exception:
                _W = _H = 0.0
        # ACELEASI circuite ca schema/memoriu (enrich) + cablurile desenate (compute_cables).
        circuits = _ec.enrich_circuits(rows, request.form or {}, base_circuits=base_circuits)
        cables, _cstats = draw_elements.compute_cables(rows)
        scale, ssrc = _bom.derive_scale(_rooms, _W, _H)
        out = _bom.build_bom(rows, circuits, cables, scale, waste=float(request.waste or 1.0))
        return {"success": True, "scale_m_per_px": round(scale, 6), "scale_source": ssrc,
                "rows": out["rows"], "summary": out["summary"]}
    except Exception as e:
        return {"success": False, "error": str(e), "rows": []}


# -------------------------------------------------
#  NUMEROTARE PLANSE (IE.1..IE.N)  —  POST /plansa-numbering
#  SINGURA sursa de adevar pt. numerotarea secventiala (fara goluri, ordinea fixa) din ce EXISTA.
#  Wrapper subtire peste plansa_numbering.compute_plansa_numbering (pura, testata izolat). n8n (Faza 2B)
#  o cheama, apoi restampeaza fiecare PDF cu /restamp-plansa. Sub x-zynapse-key (middleware global).
# -------------------------------------------------

class PlansaNumberingRequest(BaseModel):
    extra_floors: List[str] = []   # niveluri peste parter, in ordine (ex. ["etaj"] / ["etaj","mansarda"])
    has_tect: bool = False         # exista tablou centrala termica -> schema TE-CT (ultima)
    has_tes: Optional[bool] = None # override; implicit = exista cel putin un nivel peste parter


@app.post("/plansa-numbering")
def plansa_numbering_endpoint(request: PlansaNumberingRequest):
    """Lista ORDONATA a planselor EXISTENTE, IE.1..IE.N fara goluri. Erori status 200 (n8n)."""
    try:
        from plansa_numbering import compute_plansa_numbering
        planse = compute_plansa_numbering(request.extra_floors or [], bool(request.has_tect), request.has_tes)
        return {"success": True, "planse": planse, "count": len(planse)}
    except Exception as e:
        return {"success": False, "error": str(e), "planse": []}


# -------------------------------------------------
#  RESTAMP PLANSA (nr + titlu final pe cartus)  —  POST /restamp-plansa
#  Re-stampeaza numarul FINAL (IE.N) + numele pe cartusul unui PDF gata (cartus_swap.restamp_plansa,
#  reutilizeaza metadata zy_cartus_plansa/zy_cartus_title). Asa numarul TIPARIT = numarul din documente.
# -------------------------------------------------

class RestampPlansaRequest(BaseModel):
    pdf_base64: str = ""
    plansa_nr: str = ""            # IE.N final (din /plansa-numbering)
    plansa_titlu: str = ""         # numele complet al plansei (din /plansa-numbering)


@app.post("/restamp-plansa")
def restamp_plansa_endpoint(request: RestampPlansaRequest):
    """Re-stampeaza nr + titlu pe cartus. PDF fara metadata -> no-op defensiv. Erori status 200 (n8n)."""
    try:
        from cartus_swap import restamp_plansa
        if not request.pdf_base64:
            return {"success": False, "error": "pdf_base64 lipseste"}
        return restamp_plansa(request.pdf_base64, request.plansa_nr, request.plansa_titlu or None)
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  REGENERATE PLAN (Obtine plan, sub-pas 1a)  —  POST /regenerate-plan
# -------------------------------------------------

class RegeneratePlanRequest(BaseModel):
    project_id: str = ""
    floor: str = "parter"
    base_pdf_base64: str = ""   # BAZA CURATA = planuri[].pdf_base64 (cartus+mask, FARA becuri)
    plan_type: str = "iluminat"   # F4: ce DESENAM (iluminat=becuri/...; forta=prize). default backward-compat


@app.post("/regenerate-plan")
def regenerate_plan_endpoint(request: RegeneratePlanRequest):
    """SUB-PAS 1a: citeste plan_elements EDITAT din DB (service-role, ocoleste RLS) si
    redeseneaza becuri+intrerupatoare pe baza curata. Tablouri SKIP (1c), fara cabluri."""
    try:
        if not request.base_pdf_base64:
            return {"success": False, "error": "base_pdf_base64 lipseste (baza curata)"}
        if not request.project_id:
            return {"success": False, "error": "project_id lipseste"}
        # citeste elementele EDITATE din DB (service-role)
        try:
            from supabase_client import supabase
            # F4: citeste TOATE elementele etajului (iluminat+forta+ambele) -> assign_circuits numara
            # n_iluminat din becuri => prizele continua C3+ cross-plan; redraw deseneaza doar subsetul cerut.
            rows = (supabase.table("plan_elements").select("*")
                    .eq("project_id", request.project_id)
                    .eq("floor", request.floor)
                    .execute().data) or []
        except Exception as e:
            return {"success": False, "error": "citire plan_elements esuata: {}".format(e)}
        # C3c: asociaza prize->camera (din result_data.rooms) + numeroteaza circuite -> scrie circuit_id
        # pe prize (in-memory pt. C4 + persista in DB). Defensiv: ORICE eroare NU strica regenerarea.
        _rooms = []   # FAZA 2a: bbox camere (pt. rutarea prizelor pe perimetru la redraw); [] daca citirea pica
        try:
            import fitz
            from supabase_client import supabase as _supa
            _raw = request.base_pdf_base64.split(",", 1)[1] if "," in request.base_pdf_base64 else request.base_pdf_base64
            _doc = fitz.open(stream=base64.b64decode(_raw), filetype="pdf")
            _W, _H = _doc[0].rect.width, _doc[0].rect.height
            _doc.close()
            _proj = (_supa.table("projects").select("result_data")
                     .eq("id", request.project_id).single().execute().data) or {}
            # NOTA multi-etaj: result_data.rooms = camere (azi TOATE proiectele sunt mono-etaj/parter).
            # Follow-up: cand apar etaje, rooms ar trebui tag-uite pe floor + filtrate pe request.floor.
            _rooms = ((_proj.get("result_data") or {}).get("rooms")) or []
            _ci = draw_elements.assign_circuits(rows, _rooms, _W, _H)
            for _u in _ci.get("updates", []):
                if _u.get("changed"):
                    _supa.table("plan_elements").update(
                        {"circuit_id": _u["circuit_id"], "room": _u["room"]}).eq("id", _u["id"]).execute()
        except Exception as _e:
            print("[regenerate-plan] assign_circuits skip:", _e)   # defensiv: regenerarea continua
        # COLOANE: feed-urile sub_tablou (TEG->TE-CT/TES) din result_data.circuits -> desenate teal +
        # in legenda. Sectiunea = cable_type-ul feed-ului (normativ, din schema initiala). Defensiv.
        _feeds = []
        try:
            from supabase_client import supabase as _supa2
            _pr = (_supa2.table("projects").select("result_data")
                   .eq("id", request.project_id).single().execute().data) or {}
            _circs = ((_pr.get("result_data") or {}).get("circuits")) or []
            _feeds = [c for c in _circs if isinstance(c, dict) and c.get("type") == "sub_tablou"]
        except Exception as _e2:
            print("[regenerate-plan] feeds skip:", _e2)
        # PAS 2 (numerotare): planul regenerat primeste numarul FINAL IE.N + titlul din AUTORITATE
        # (pick_plan_entry -> compute_plansa_numbering — ACEEASI ca borderoul memoriului + nodul n8n
        # "Numerotare Planse") in loc sa mosteneasca numarul planului de baza (forta parter iesea IE.1
        # in loc de IE.3). Defensiv: ORICE esec -> None -> redraw = comportamentul vechi.
        _pl_nr = _pl_titlu = None
        try:
            from plansa_numbering import pick_plan_entry
            try:
                _rd2 = (_pr.get("result_data") or {})          # reuse fetch-ul din blocul feeds
            except Exception:
                _rd2 = {}
            if not _rd2:
                from supabase_client import supabase as _supa3
                _rd2 = (((_supa3.table("projects").select("result_data")
                          .eq("id", request.project_id).single().execute().data) or {})
                        .get("result_data")) or {}
            _ent = pick_plan_entry(_rd2, request.plan_type, request.floor)
            if _ent:
                _pl_nr, _pl_titlu = _ent.get("nr"), _ent.get("nume")
        except Exception as _e3:
            print("[regenerate-plan] numerotare skip:", _e3)
        return draw_elements.redraw_from_plan_elements(
            request.base_pdf_base64, rows, draw_plan_type=request.plan_type, feeds=_feeds, rooms=_rooms,
            plansa_nr=_pl_nr, plansa_titlu=_pl_titlu)
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  EXTRACT GEOMETRY (pereti din cleanBasePdf, P1)  —  POST /extract-geometry
# -------------------------------------------------

class ExtractGeometryRequest(BaseModel):
    pdf_base64: str = ""   # cleanBasePdf (planuri[].pdf_base64) -> coordonate IDENTICE cu plan_elements x,y
    rooms: List[dict] = []  # OPTIONAL (V4): camere Vision {name, area_m2, bbox} -> room_geoms (geom_bbox per camera)


@app.post("/extract-geometry")
def extract_geometry_endpoint(request: ExtractGeometryRequest):
    """P1: extrage peretii GLOBALI (segmente H/V) din PDF-ul curat, in PUNCTE PDF (acelasi spatiu ca
    plan_elements). Pt. snap prize pe perete (viitor). _collect = auto-detect layere (5/5 arhitecti).
    V4 (aditiv): daca request.rooms e nenul -> intoarce si room_geoms (geom_bbox per camera, cu
    fallback-ul ancora-eticheta din geometry.extract_room_geometry) -> perimetru corect la plasarea
    prizelor in editor (camerele fara pereti completi: holuri/terase/open-space).
    Defensiv: fara layere de pereti -> walls:[]; orice eroare -> success:false + walls:[] (nu strica editorul)."""
    try:
        raw = request.pdf_base64 or ""
        if "," in raw:
            raw = raw.split(",", 1)[1]
        if not raw:
            return {"success": False, "error": "pdf_base64 lipseste", "walls": [], "doors": []}
        import fitz
        import geometry
        pdf_bytes = base64.b64decode(raw)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            page = doc[0]
            W, H = page.rect.width, page.rect.height
            h_segs, v_segs, doors = geometry._collect(page)
        finally:
            doc.close()
        walls = ([{"x1": round(x0, 1), "y1": round(y, 1), "x2": round(x1, 1), "y2": round(y, 1), "orientation": "h"}
                  for (x0, x1, y) in h_segs]
                 + [{"x1": round(x, 1), "y1": round(y0, 1), "x2": round(x, 1), "y2": round(y1, 1), "orientation": "v"}
                    for (y0, y1, x) in v_segs])
        doors_out = [{"x": round(cx, 1), "y": round(cy, 1), "r": round(r, 1)} for (cx, cy, r) in doors]
        # V4 (aditiv): geom_bbox per camera Vision (wall SAU label_anchor) — paralel cu request.rooms.
        # Orice eroare -> room_geoms=[] (editorul cade pe bbox-ul Vision, comportamentul de azi).
        room_geoms = []
        if request.rooms:
            try:
                geoms = geometry.extract_room_geometry(pdf_bytes, request.rooms, W, H)
                room_geoms = [{"name": g.get("name"), "geom_bbox": g.get("geom_bbox"),
                               "geom_source": g.get("geom_source")} for g in geoms]
            except Exception:
                room_geoms = []
        return {"success": True, "walls": walls, "doors": doors_out,
                "pdf_width_pt": W, "pdf_height_pt": H, "room_geoms": room_geoms}
    except Exception as e:
        return {"success": False, "error": str(e), "walls": [], "doors": []}


# -------------------------------------------------
#  CROP TO BUILDING (V3b: decupare la cladire pt. Vision)  —  POST /crop-to-building
# -------------------------------------------------

class CropToBuildingRequest(BaseModel):
    pdf_base64: str = ""        # planul brut (parter/etaj) -> se decupeaza la conturul cladirii
    dpi: int = 200             # rezolutie raster pt. imaginea decupata trimisa la Vision
    margin_frac: float = 0.11  # V3b: margine 11% in jurul peretilor -> NU taie terasele deschise


@app.post("/crop-to-building")
def crop_to_building_endpoint(request: CropToBuildingRequest):
    """V3b: decupeaza pagina 1 la bounding-box-ul cladirii (din pereti) -> Vision vede cladirea mare
    -> bbox-uri camere corecte; intoarce crop_box pt. re-maparea bbox-urilor la pagina intreaga.
    Wrapper subtire peste geometry.crop_image_to_building (care isi extrage singura peretii via _collect).
    Fara pereti (plan scanat/fara vectori) -> cropped:false -> caller-ul trimite PDF-ul brut (zero regresie).
    Defensiv: ORICE eroare -> cropped:false (caller-ul are fallback la PDF brut)."""
    try:
        raw = request.pdf_base64 or ""
        if "," in raw:
            raw = raw.split(",", 1)[1]
        if not raw:
            return {"cropped": False, "error": "pdf_base64 lipseste"}
        import geometry
        pdf_bytes = base64.b64decode(raw)
        res = geometry.crop_image_to_building(
            pdf_bytes, dpi=request.dpi, margin_frac=request.margin_frac)
        if not res:
            logger.info("[crop-to-building] fara pereti -> cropped:false (fallback PDF brut)")
            return {"cropped": False}
        cb = res.get("crop_box") or {}
        logger.info("[crop-to-building] cropped:true crop_box=%s dpi=%s margin=%s",
                    cb, res.get("dpi"), request.margin_frac)
        return {
            "cropped": True,
            "image_base64": res["image_base64"],
            "media_type": res.get("media_type", "image/png"),
            "crop_box": cb,
            "dpi": res.get("dpi", request.dpi),
        }
    except Exception as e:
        logger.error("[crop-to-building] eroare -> cropped:false: %r", e)
        return {"cropped": False, "error": str(e)}


# -------------------------------------------------
#  POARTA DE VALIDARE PLAN  —  POST /validate-plan
# -------------------------------------------------

class ValidatePlanRequest(BaseModel):
    pdf_base64: str = ""


@app.post("/validate-plan")
def validate_plan_endpoint(request: ValidatePlanRequest):
    """POARTA de validare DETERMINISTA (fara AI, <1s) — ruleaza INAINTE de Vision/credite.
    Discriminanti dovediti empiric (schema reala: 0 pereti + 0 etichete arie; planuri reale:
    sute de pereti + etichete = exact nr. camerelor; raster: 0 text):
      - raster (words==0)                  -> rejected (blocare HARD in frontend)
      - 0 etichete arie SI < 20 pereti     -> warning  (override in frontend, faza 1)
      - altfel                             -> ok
    Refoloseste geometry._collect (pereti) + draw_elements.AREA_RE (etichete "A: NN.N mp").
    DEFENSIV: orice eroare INTERNA a portii -> ok cu nota (poarta nu blocheaza useri pe bug-ul ei)."""
    doc = None
    try:
        import fitz   # main.py nu are fitz global (pattern-ul local, ca la /regenerate-plan)
        raw = request.pdf_base64 or ""
        if "," in raw:
            raw = raw.split(",", 1)[1]
        if not raw:
            return {"status": "ok", "note": "pdf_base64 lipseste — permis defensiv"}
        pdf_bytes = base64.b64decode(raw)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        words = page.get_text("words")
        if len(words) == 0:
            return {"status": "rejected", "reason": "raster",
                    "message": "PDF scanat (imagine, fără strat vectorial). Încarcă exportul PDF vectorial din programul CAD."}
        import geometry
        try:
            h_segs, v_segs, _dd = geometry._collect(page)
        except Exception:
            h_segs, v_segs = [], []
        n_walls = len(h_segs) + len(v_segs)
        text = page.get_text("text") or ""
        n_area = len(draw_elements.AREA_RE.findall(text))
        detected = {"walls": n_walls, "area_labels": n_area, "words": len(words)}
        if n_area == 0 and n_walls < 20:
            return {"status": "warning", "reason": "not_a_plan", "detected": detected,
                    "message": "Fișierul nu pare un plan de arhitectură (nicio cameră cu suprafață, aproape niciun perete detectat). Poate fi o schemă sau alt document."}
        return {"status": "ok", "detected": detected}
    except Exception as e:
        logger.error("[validate-plan] eroare interna -> permis defensiv: %r", e)
        return {"status": "ok", "note": f"validare esuata, permis defensiv: {e}"}
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


# -------------------------------------------------
#  SERVIRE FRONTEND STATIC
# -------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
