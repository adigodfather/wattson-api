from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Literal
import math
import os

app = FastAPI(
    title="ZYNAPSE Core API",
    description="Motor inteligent de calcul pentru proiecte electrice rezidențiale – ZYNAPSE",
    version="2.0.0",
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

# Temperatura exterioara de calcul pe zone climatice (°C)
ZONE_TEMP = {
    "I": -12,
    "II": -15,
    "III": -18,
    "IV": -21,
    "V": -25,
}

# W/m² de baza in functie de nivelul de izolatie
INSULATION_W_M2 = {
    "slaba": 70.0,
    "medie": 60.0,
    "buna": 50.0,
    "foarte_buna": 40.0,
}

# -------------------------------------------------
#  MODELE DE INTRARE  (schema noua v2)
# -------------------------------------------------


class Building(BaseModel):
    type: str
    levels: str
    climate_zone: Optional[str] = None       # "I" / "II" / "III" / "IV" / "V"
    insulation_level: Literal["slaba", "medie", "buna", "foarte_buna"]
    main_entrance: Optional[str] = None
    total_area_m2: float
    total_volume_m3: float


class Heating(BaseModel):
    type: Literal[
        "pdc_air_water",
        "pdc_air_air",
        "gas_boiler",
        "electric_boiler",
        "geothermal",
        "none",
    ]
    has_acm_boiler: bool = False
    has_ventilation: bool = False
    has_hrv: bool = False
    pdc_phase: Optional[Literal["mono", "tri"]] = "tri"


class Room(BaseModel):
    name: str
    level: Optional[str] = None
    area_m2: float
    height_m: float
    window_sill_height_m: Optional[float] = None
    function: Literal["day", "night", "circulation", "bathroom", "kitchen", "technical/storage", "other"]
    has_tv: bool = False
    has_nightstands: bool = False


class ProjectData(BaseModel):
    project_id: str
    building: Building
    heating: Heating
    rooms: List[Room]
    has_floor_heating: bool = False
    notes: Optional[str] = None


# -------------------------------------------------
#  UTILITARE – ZONA CLIMATICA
# -------------------------------------------------


def resolve_climate_zone(building: Building) -> str:
    if building.climate_zone:
        z = building.climate_zone.strip().upper().replace("ZONA", "").strip()
        if z in ZONE_TEMP:
            return z
    return "II"


# -------------------------------------------------
#  UTILITARE – PDC / TE-CT
# -------------------------------------------------


def calc_pdc_power_kw(building: Building, heating: Heating, climate_zone: str) -> float:
    if not heating.type.startswith("pdc") and heating.type != "geothermal":
        return 0.0

    w_per_m2 = INSULATION_W_M2.get(building.insulation_level, 50.0)

    # Ajustare dupa zona climatica fata de zona II (referinta)
    zone_delta = {
        "I": -5.0,
        "II": 0.0,
        "III": 3.0,
        "IV": 5.0,
        "V": 8.0,
    }
    w_per_m2 += zone_delta.get(climate_zone, 0.0)

    # Regula practica: casa ≤ 250 m², izolatie buna/foarte_buna → 10 kW fix
    if building.total_area_m2 <= 250 and building.insulation_level in ["buna", "foarte_buna"]:
        return 10.0

    q_kw = building.total_area_m2 * w_per_m2 / 1000.0
    return round(q_kw, 1)


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
            breaker, cable = 16, "5×2,5 mm² CYYF"
        elif power_kw <= 14:
            breaker, cable = 20, "5×4 mm² CYYF"
        else:
            breaker, cable = 25, "5×6 mm² CYYF"

        return {
            "device": "PDC",
            "phase": "trifazat",
            "poles": "3P+N",
            "power_kw_thermal": power_kw,
            "power_kw_electric": round(p_el_kw, 2),
            "current_a_calc": ia,
            "breaker_a": breaker,
            "cable": cable,
            "notes": f"Circuit trifazat PDC, COP ~{cop}.",
        }

    # monofazat
    ia = math.ceil(p_el_kw / 0.23)

    if power_kw <= 10:
        breaker, cable = 20, "3×4 mm² CYYF"
    else:
        breaker, cable = 25, "3×6 mm² CYYF"

    return {
        "device": "PDC",
        "phase": "monofazat",
        "poles": "1P+N",
        "power_kw_thermal": power_kw,
        "power_kw_electric": round(p_el_kw, 2),
        "current_a_calc": ia,
        "breaker_a": breaker,
        "cable": cable,
        "notes": f"Circuit monofazat PDC, COP ~{cop}.",
    }


def choose_boiler_circuit(building: Building, heating: Heating) -> Optional[dict]:
    if not heating.has_acm_boiler:
        return None

    p_kw = 2.0 if building.total_area_m2 <= 200 else 3.0
    breaker = 16 if p_kw <= 2.5 else 20

    return {
        "device": "Boiler ACM",
        "power_kw": p_kw,
        "breaker_a": breaker,
        "cable": "3×2,5 mm² CYYF",
        "notes": "Circuit monofazat dedicat pentru boiler ACM.",
    }


def choose_pump_circuit() -> dict:
    return {
        "device": "Pompa circulatie",
        "power_kw": 0.3,
        "breaker_a": 10,
        "cable": "3×1,5 mm² CYYF",
        "notes": "Circuit monofazat pentru pompa de circulatie.",
    }


def choose_ventilation_circuit(heating: Heating) -> Optional[dict]:
    if not heating.has_ventilation and not heating.has_hrv:
        return None

    return {
        "device": "Ventilatie / recuperare",
        "power_kw": 0.2,
        "breaker_a": 10,
        "cable": "3×1,5 mm² CYYF",
        "notes": "Circuit monofazat pentru unitate de ventilatie / HRV.",
    }


# -------------------------------------------------
#  CAMERE – PRIZE + ILUMINAT
# -------------------------------------------------


def calc_room_electrics(room: Room) -> dict:
    sockets = []
    lights = []

    # Prize noptiere
    if room.has_nightstands:
        sockets.append({
            "type": "priza_noptiera",
            "count": 2,
            "height_m": 0.6,
            "notes": "Prize la 0,6 m la fiecare noptiera.",
        })

    # Prize TV
    if room.has_tv:
        h_tv = 1.8 if room.function in ["day"] else 0.6
        sockets.append({
            "type": "priza_TV",
            "count": 1,
            "height_m": h_tv,
            "notes": f"TV – priza la ~{h_tv} m.",
        })

    # Iluminat dupa functie
    func = room.function
    if func in ["day", "night"]:
        lights.append({
            "type": "candelabru_central",
            "count": 1,
            "notes": "Corp plafon central (lustra LED / pendul).",
        })
        if room.area_m2 > 20:
            lights.append({
                "type": "spoturi_sau_benzi",
                "count": math.ceil(room.area_m2 / 5),
                "notes": "Iluminat accent / ambiental pentru camera mare.",
            })
    elif func == "bathroom":
        lights.append({
            "type": "aplica_IP44",
            "count": 1,
            "notes": "Corp cu IP44 sau mai mare (zona umeda).",
        })
    elif func == "kitchen":
        lights.append({
            "type": "plafoniera_LED",
            "count": 1,
            "notes": "Plafoniera LED centrala; benzi LED deasupra blatului.",
        })
    elif func == "circulation":
        lights.append({
            "type": "plafoniera_slim",
            "count": max(1, math.ceil(room.area_m2 / 8)),
            "notes": "Iluminat general circulatie.",
        })
    else:
        lights.append({
            "type": "plafoniera",
            "count": 1,
            "notes": "Iluminat general.",
        })

    return {
        "name": room.name,
        "level": room.level,
        "function": room.function,
        "area_m2": room.area_m2,
        "sockets": sockets,
        "lights": lights,
    }


# -------------------------------------------------
#  CIRCUITE TE-CT + TEG
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
        "device": "Automatizare", "breaker_a": 10, "cable": "3×1,5 mm² CYYF",
        "notes": "Alimentare automatizare centrala / PDC.",
    })
    idx += 1

    circuits.append({
        "id": f"TECT_{idx}", "panel": "TE-CT", "usage": "Circuit rezerva",
        "device": "Rezerva", "breaker_a": 16, "cable": "3×2,5 mm² CYYF",
        "notes": "Circuit de rezerva pentru echipamente viitoare.",
    })
    idx += 1

    if has_floor_heating:
        circuits.append({
            "id": f"TECT_{idx}", "panel": "TE-CT", "usage": "Distribuitor incalzire in pardoseala",
            "device": "Distribuitor IP", "power_kw": 0.5, "breaker_a": 16,
            "cable": "3×2,5 mm² CYYF", "notes": "Alimentare distribuitor IP (pompe / actuatoare).",
        })

    return circuits


def build_circuits_teg(data: ProjectData) -> List[dict]:
    circuits = []
    total_area = sum(r.area_m2 for r in data.rooms)
    has_kitchen = any(r.function == "kitchen" for r in data.rooms)
    has_bathroom = any(r.function == "bathroom" for r in data.rooms)

    # Iluminat interior
    num_light = max(1, math.ceil(total_area / 60.0))
    for i in range(num_light):
        circuits.append({
            "id": f"TEG_L{i+1}", "panel": "TEG", "usage": "Iluminat interior",
            "type": "iluminat", "breaker_a": 10, "cable": "3×1,5 mm² CYYF",
            "notes": "Circuit iluminat general.",
        })

    circuits.append({
        "id": "TEG_EX1", "panel": "TEG", "usage": "Iluminat exterior",
        "type": "iluminat", "breaker_a": 10, "cable": "3×1,5 mm² CYYF",
        "notes": "Aplice LED cu senzor crepuscular la intrari / terase.",
    })

    # Prize generale
    num_sockets = max(1, math.ceil(total_area / 40.0))
    for i in range(num_sockets):
        circuits.append({
            "id": f"TEG_P{i+1}", "panel": "TEG", "usage": "Prize generale",
            "type": "prize", "breaker_a": 16, "cable": "3×2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Prize generale camere zi / dormitoare (max ~5 prize / circuit).",
        })

    if has_kitchen:
        circuits.append({
            "id": "TEG_PB1", "panel": "TEG", "usage": "Prize blaturi bucatarie",
            "type": "prize", "breaker_a": 20, "cable": "3×2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Prize blaturi bucatarie – consumatoare mici.",
        })
        circuits.append({
            "id": "TEG_PB2", "panel": "TEG", "usage": "Electrocasnice bucatarie",
            "type": "prize", "breaker_a": 20, "cable": "3×2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Cuptor / masina spalat vase / aparate dedicate.",
        })

    if has_bathroom:
        circuits.append({
            "id": "TEG_MSR1", "panel": "TEG", "usage": "Masina spalat rufe",
            "type": "prize", "breaker_a": 16, "cable": "3×2,5 mm² CYYF",
            "rcd_30ma": True, "afdd": True,
            "notes": "Circuit dedicat masina de spalat rufe.",
        })

    return circuits


# -------------------------------------------------
#  MEMORIU TEHNIC
# -------------------------------------------------


def build_memoriu(
    data: ProjectData,
    climate_zone: str,
    pdc_circuit: Optional[dict],
    boiler_circuit: Optional[dict],
    pump_circuit: Optional[dict],
    ventilation_circuit: Optional[dict],
    room_results: List[dict],
    circuits_te_ct: List[dict],
    circuits_teg: List[dict],
) -> str:
    lines = []
    b = data.building
    h = data.heating

    lines.append(f"MEMORIU TEHNIC INSTALATIE ELECTRICA")
    lines.append(f"=====================================")
    lines.append(f"Proiect: {data.project_id}")
    lines.append(
        f"Cladire: {b.type}, regim {b.levels}, "
        f"Supr. utila {b.total_area_m2} m², volum {b.total_volume_m3} m³."
    )
    lines.append(f"Zona climatica: {climate_zone}, izolatie: {b.insulation_level}.")
    if b.main_entrance:
        lines.append(f"Intrare principala: {b.main_entrance}.")
    lines.append("")

    heating_labels = {
        "pdc_air_water": "PDC aer-apa",
        "pdc_air_air": "PDC aer-aer",
        "gas_boiler": "Centrala gaz",
        "electric_boiler": "Centrala electrica",
        "geothermal": "Geotermala",
        "none": "Fara incalzire centralizata",
    }
    lines.append(f"Sistem de incalzire: {heating_labels.get(h.type, h.type)}.")
    lines.append(f"Boiler ACM: {'Da' if h.has_acm_boiler else 'Nu'}.")
    lines.append(f"Ventilatie mecanica: {'Da' if h.has_ventilation else 'Nu'}.")
    lines.append(f"Recuperator caldura (HRV): {'Da' if h.has_hrv else 'Nu'}.")
    lines.append(f"Incalzire in pardoseala: {'Da' if data.has_floor_heating else 'Nu'}.")
    lines.append("")

    if pdc_circuit:
        lines.append("Circuit pompa de caldura (PDC):")
        lines.append(
            f"  - Putere termica: {pdc_circuit['power_kw_thermal']} kW, "
            f"putere electrica estimata: {pdc_circuit['power_kw_electric']} kW."
        )
        lines.append(
            f"  - Curent calculat: ~{pdc_circuit['current_a_calc']} A, "
            f"protectie: {pdc_circuit['breaker_a']} A ({pdc_circuit['poles']})."
        )
        lines.append(f"  - Cablu: {pdc_circuit['cable']}.")
        lines.append("")

    if boiler_circuit:
        lines.append("Circuit boiler ACM:")
        lines.append(f"  - Putere: {boiler_circuit['power_kw']} kW.")
        lines.append(f"  - Protectie: {boiler_circuit['breaker_a']} A, cablu {boiler_circuit['cable']}.")
        lines.append("")

    if pump_circuit:
        lines.append("Circuit pompa de circulatie:")
        lines.append(f"  - Protectie: {pump_circuit['breaker_a']} A, cablu {pump_circuit['cable']}.")
        lines.append("")

    if ventilation_circuit:
        lines.append("Circuit ventilatie / recuperare:")
        lines.append(f"  - Protectie: {ventilation_circuit['breaker_a']} A, cablu {ventilation_circuit['cable']}.")
        lines.append("")

    lines.append("Rezumat camera cu camera (prize si iluminat):")
    for r in room_results:
        lines.append(f"- {r['name']} ({r['area_m2']} m²):")
        for s in r.get("sockets", []):
            lines.append(f"    · {s['type']} ×{s['count']} la h ≈ {s['height_m']} m ({s['notes']})")
        for lgt in r.get("lights", []):
            lines.append(f"    · Iluminat: {lgt['type']} ×{lgt['count']} ({lgt['notes']})")
        lines.append("")

    if circuits_te_ct:
        lines.append("Lista circuite TE-CT (camera tehnica):")
        for c in circuits_te_ct:
            lines.append(
                f"  - {c['id']}: {c['usage']} – {c.get('breaker_a', '?')} A, "
                f"cablu {c.get('cable', '?')}."
            )
        lines.append("")

    if circuits_teg:
        lines.append("Lista circuite TEG (tabloul general):")
        for c in circuits_teg:
            lines.append(
                f"  - {c['id']}: {c['usage']} – {c['breaker_a']} A, cablu {c['cable']}."
            )
        lines.append("")

    lines.append("Toate circuitele vor fi verificate si dimensionate conform normativelor in vigoare.")
    return "\n".join(lines)


# -------------------------------------------------
#  ENDPOINT PRINCIPAL
# -------------------------------------------------


@app.post("/calc-electric")
def calc_electric(data: ProjectData):
    climate_zone = resolve_climate_zone(data.building)

    pdc_power_kw = calc_pdc_power_kw(data.building, data.heating, climate_zone)
    pdc_phase = data.heating.pdc_phase or "tri"
    pdc_circuit = (
        choose_pdc_circuit(power_kw=pdc_power_kw, phase=pdc_phase, pdc_type=data.heating.type)
        if pdc_power_kw > 0
        else None
    )

    boiler_circuit = choose_boiler_circuit(data.building, data.heating)

    pump_circuit = None
    if data.heating.type in ["pdc_air_water", "gas_boiler", "electric_boiler", "geothermal"]:
        pump_circuit = choose_pump_circuit()

    ventilation_circuit = choose_ventilation_circuit(data.heating)

    room_results = [calc_room_electrics(r) for r in data.rooms]

    circuits_te_ct = build_circuits_te_ct(
        pdc_circuit=pdc_circuit,
        boiler_circuit=boiler_circuit,
        pump_circuit=pump_circuit,
        ventilation_circuit=ventilation_circuit,
        has_floor_heating=data.has_floor_heating,
    )
    circuits_teg = build_circuits_teg(data)
    circuits_all = circuits_te_ct + circuits_teg

    memoriu = build_memoriu(
        data=data,
        climate_zone=climate_zone,
        pdc_circuit=pdc_circuit,
        boiler_circuit=boiler_circuit,
        pump_circuit=pump_circuit,
        ventilation_circuit=ventilation_circuit,
        room_results=room_results,
        circuits_te_ct=circuits_te_ct,
        circuits_teg=circuits_teg,
    )

    return {
        "project_id": data.project_id,
        "status": "success",
        "climate_zone": climate_zone,
        "heating_circuits": {
            "pdc": pdc_circuit,
            "boiler": boiler_circuit,
            "pump": pump_circuit,
            "ventilation": ventilation_circuit,
        },
        "rooms": room_results,
        "circuits_te_ct": circuits_te_ct,
        "circuits_teg": circuits_teg,
        "circuits_all": circuits_all,
        "memoriu_tehnic": memoriu,
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


# -------------------------------------------------
#  SERVIRE FRONTEND STATIC
# -------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
