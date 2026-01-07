from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Literal
import math

app = FastAPI(
    title="WATTSON Core API",
    description="Motor inteligent de calcul pentru proiecte electrice rezidențiale – WATTSON",
    version="1.0.0",
)

# -------------------------------------------------
#  CONSTANTE
# -------------------------------------------------

# COP tipic pentru PDC – se poate ajusta ulterior
COP_BY_TYPE = {
    "PDC aer-apa": 4.0,
    "PDC aer-aer": 3.5,
    "geotermala": 4.5,
}

# Mapare aproximativa JUDET -> zona climatica (conform hartilor uzuale)
# NOTA: este o aproximare la nivel de judet, pentru proiecte serioase
# se poate rafina pe localitati / altitudine.
COUNTY_TO_ZONE = {
    # Zona I (-12 °C)
    "TM": "zona I",
    "CS": "zona I",
    "CT": "zona I",
    "TL": "zona I",

    # Zona II (-15 °C)
    "MH": "zona II",
    "GJ": "zona II",
    "DJ": "zona II",
    "OT": "zona II",
    "TR": "zona II",
    "GR": "zona II",
    "CL": "zona II",
    "IL": "zona II",
    "AG": "zona II",
    "DB": "zona II",
    "PH": "zona II",
    "BZ": "zona II",
    "BR": "zona II",
    "BH": "zona II",
    "AR": "zona II",

    # Zona III (-18 °C)
    "CJ": "zona III",
    "SJ": "zona III",
    "SM": "zona III",
    "AB": "zona III",
    "HD": "zona III",
    "VL": "zona III",
    "VN": "zona III",
    "GL": "zona III",
    "VS": "zona III",
    "IS": "zona III",
    "NT": "zona III",
    "BC": "zona III",
    "BT": "zona III",
    "SV": "zona III",
    "RM": "zona III",  # Rep. Moldova – aproximativ

    # Zona IV (-21 °C)
    "BN": "zona IV",
    "MS": "zona IV",
    "SB": "zona IV",
    "BV": "zona IV",

    # Zona V (-25 °C) – zone foarte reci (pungi de frig)
    "HR": "zona V",
    "CV": "zona V",
}

# -------------------------------------------------
#  MODELE DE INTRARE
# -------------------------------------------------


class Building(BaseModel):
    type: str
    levels: str
    floor_area: float
    volume: float
    # poate fi dat direct ("zona I", "zona II"...),
    # sau poate lipsi, caz in care incercam sa o deducem din judet
    climate_zone: Optional[str] = None
    insulation: Literal["sub_normativ", "minim_normativ", "peste_normativ"]
    # amplasament – pentru deducerea zonei climatice
    county: Optional[str] = None  # ex: "BV", "CJ", "TM"
    locality: Optional[str] = None  # ex: "Brasov", "Cluj-Napoca"


class Heating(BaseModel):
    type: Literal[
        "PDC aer-apa",
        "PDC aer-aer",
        "centrala_gaz",
        "centrala_electrica",
        "geotermala",
        "fara_incalzire",
    ]
    acm: Optional[str] = None
    ventilation: Optional[str] = None
    has_ventilation: bool = False
    has_hrv: bool = False
    # PDC monofazata sau trifazata (daca e cazul)
    pdc_phase: Optional[Literal["monofazat", "trifazat"]] = "trifazat"


class Room(BaseModel):
    name: str
    area: float
    height: float
    function: Literal["zi", "noapte", "circulatie", "baie", "bucatarie"]
    has_tv: bool = False
    tv_mount: Optional[Literal["suspendat", "pe_comoda"]] = None
    has_nightstands: bool = False
    is_bathroom: bool = False


class ProjectData(BaseModel):
    project_id: str
    building: Building
    heating: Heating
    rooms: List[Room]
    has_floor_heating: bool = False


# -------------------------------------------------
#  FUNCTII UTILITARE – ZONA CLIMATICA
# -------------------------------------------------


def auto_climate_zone(building: Building) -> str:
    """
    Daca building.climate_zone este setat, folosim valoarea aceea.
    Altfel, incercam sa deducem zona din judet (county).
    Daca nu reusim, default 'zona II'.
    """
    if building.climate_zone and building.climate_zone.strip():
        return building.climate_zone

    if building.county:
        code = building.county.strip().upper()
        zone = COUNTY_TO_ZONE.get(code)
        if zone:
            return zone

    # fallback rezonabil
    return "zona II"


# -------------------------------------------------
#  FUNCTII UTILITARE – PDC / TE-CT
# -------------------------------------------------


def calc_pdc_power_kw(building: Building, heating: Heating, climate_zone: str) -> float:
    """
    Calcul simplificat pentru puterea termica a PDC (kW), dupa suprafata, izolatie si zona climatica.
    """
    if not heating.type.startswith("PDC"):
        return 0.0

    # baza W/m² in functie de izolatie
    if building.insulation == "peste_normativ":
        w_per_m2 = 40.0
    elif building.insulation == "minim_normativ":
        w_per_m2 = 50.0
    else:
        w_per_m2 = 70.0

    zone_norm = climate_zone.replace(" ", "").lower()

    # ajustari dupa zona climatica (mai rece -> mai multi W/m²)
    if "zonai" in zone_norm:
        w_per_m2 -= 5.0
    elif "zonaiii" in zone_norm:
        # zona III – baza
        pass
    elif "zonaiv" in zone_norm:
        w_per_m2 += 5.0
    elif "zonav" in zone_norm:
        w_per_m2 += 8.0
    # zona II – implicit, fara modificare

    # regula ta: case < 250 m² cu izolatie ok -> fix 10 kW
    if building.floor_area <= 250 and building.insulation in ["minim_normativ", "peste_normativ"]:
        return 10.0

    q_kw = building.floor_area * w_per_m2 / 1000.0
    return round(q_kw, 1)


def choose_pdc_circuit(
    power_kw: float,
    phase: str = "trifazat",
    pdc_type: str = "PDC aer-apa",
) -> Optional[dict]:
    """
    Dimensioneaza circuitul PDC mono/tri plecand de la:
      - puterea termica (kW),
      - COP (in functie de tip PDC),
      - formulele date de tine:

        Pi_el (kW) = P_termica / COP

        Ia_trifazat = Pi_el / (0.4 * 0.92 * 1.73)
        Ia_monofazat = Pi_el / 0.23
    """
    if power_kw <= 0:
        return None

    # COP din tabel; daca nu gasim, presupunem 4.0
    cop = COP_BY_TYPE.get(pdc_type, 4.0)

    # puterea electrica absorbita (kW si W)
    p_el_kw = power_kw / cop
    # p_el_w = p_el_kw * 1000.0  # nu e neaparat nevoie, las asa comentat

    if phase == "trifazat":
        ia = p_el_kw / (0.4 * 0.92 * 1.73)
        ia = math.ceil(ia)

        if power_kw <= 10:
            breaker = 16
            cable = "5x2.5 mm² CYYF"
        elif power_kw <= 14:
            breaker = 20
            cable = "5x4 mm² CYYF"
        else:
            breaker = 25
            cable = "5x6 mm² CYYF"

        return {
            "device": "PDC",
            "phase": "trifazat",
            "poles": "3P+N",
            "power_kw_thermal": power_kw,
            "power_kw_electric": round(p_el_kw, 2),
            "current_a_calc": ia,
            "breaker_a": breaker,
            "cable": cable,
            "notes": f"Circuit trifazat PDC, COP ~{cop}. Ia = Pi_el / (0.4×0.92×1.73).",
        }

    # monofazat
    ia = p_el_kw / 0.23
    ia = math.ceil(ia)

    if power_kw <= 10:
        breaker = 20
        cable = "3x4 mm² CYYF"
    else:
        breaker = 25
        cable = "3x6 mm² CYYF"

    return {
        "device": "PDC",
        "phase": "monofazat",
        "poles": "1P+N",
        "power_kw_thermal": power_kw,
        "power_kw_electric": round(p_el_kw, 2),
        "current_a_calc": ia,
        "breaker_a": breaker,
        "cable": cable,
        "notes": f"Circuit monofazat PDC, COP ~{cop}. Ia = Pi_el / 0.23.",
    }


def choose_boiler_circuit(building: Building, heating: Heating) -> Optional[dict]:
    if not heating.acm or "boiler" not in (heating.acm or ""):
        return None

    if building.floor_area <= 200:
        p_kw = 2.0
    else:
        p_kw = 3.0

    if p_kw <= 2.5:
        breaker = 16
    else:
        breaker = 20

    cable = "3x2.5 mm² CYYF"
    return {
        "device": "Boiler ACM",
        "power_kw": p_kw,
        "breaker_a": breaker,
        "cable": cable,
        "notes": "Circuit monofazat dedicat pentru boiler ACM.",
    }


def choose_pump_circuit() -> dict:
    return {
        "device": "Pompa circulatie",
        "power_kw": 0.3,
        "breaker_a": 10,
        "cable": "3x1.5 mm² CYYF",
        "notes": "Circuit monofazat pentru pompa de circulatie.",
    }


def choose_ventilation_circuit(heating: Heating) -> Optional[dict]:
    if not heating.has_ventilation and not heating.has_hrv:
        return None

    return {
        "device": "Ventilatie / recuperare",
        "power_kw": 0.2,
        "breaker_a": 10,
        "cable": "3x1.5 mm² CYYF",
        "notes": "Circuit monofazat pentru unitate de ventilatie / recuperare.",
    }


# -------------------------------------------------
#  FUNCTII PE CAMERE (PRIZE + ILUMINAT)
# -------------------------------------------------


def calc_room_electrics(room: Room) -> dict:
    sockets = []
    lights = []

    # prize noptiere
    if room.has_nightstands:
        sockets.append({
            "type": "priza_noptiera",
            "count": 2,
            "height_m": 0.6,
            "notes": "Prize la 0,6 m la fiecare noptiera.",
        })

    # prize TV
    if room.has_tv:
        if room.tv_mount == "suspendat":
            sockets.append({
                "type": "priza_TV",
                "count": 1,
                "height_m": 1.8,
                "notes": "TV suspendat, priza la ~1,8–2,0 m.",
            })
        elif room.tv_mount == "pe_comoda":
            sockets.append({
                "type": "priza_TV",
                "count": 1,
                "height_m": 0.6,
                "notes": "TV pe comoda, priza la ~0,6 m.",
            })

    # iluminat in functie de tip camera
    if room.function in ["zi", "noapte"]:
        lights.append({
            "type": "candelabru_central",
            "count": 1,
            "notes": "Corp plafon central in incapere (lustra LED / pendul).",
        })
    elif room.function == "baie" or room.is_bathroom:
        lights.append({
            "type": "aplica_IP44",
            "count": 1,
            "notes": "Corp cu IP44 sau mai mare in zona de baie.",
        })
    elif room.function == "bucatarie":
        lights.append({
            "type": "plafoniera_LED",
            "count": 1,
            "notes": "Plafoniera LED centrala; se pot adauga benzi LED deasupra blatului.",
        })
    else:
        lights.append({
            "type": "plafoniera",
            "count": 1,
            "notes": "Iluminat general pentru circulatii / spatii tehnice.",
        })

    return {
        "name": room.name,
        "function": room.function,
        "area_m2": room.area,
        "sockets": sockets,
        "lights": lights,
    }


# -------------------------------------------------
#  LISTA DE CIRCUITE TE-CT + TEG (simplificat)
# -------------------------------------------------


def build_circuits_te_ct(
    pdc_circuit: Optional[dict],
    boiler_circuit: Optional[dict],
    pump_circuit: Optional[dict],
    ventilation_circuit: Optional[dict],
    has_floor_heating: bool,
) -> List[dict]:
    """
    Genereaza lista de circuite pentru TE-CT (camera tehnica).
    Schema simplificata:
      1 - PDC
      2 - Boiler ACM
      3 - Automatizare (fara detaliu acum)
      4 - Pompa circulatie
      5 - Circuit de rezerva
      6 - Distribuitor IP (daca exista incalzire in pardoseala)
    """
    circuits = []
    idx = 1

    def add(device_dict: Optional[dict], usage_name: str):
        nonlocal idx
        if not device_dict:
            return
        circuits.append({
            "id": f"TECT_{idx}",
            "panel": "TE-CT",
            "usage": usage_name,
            **device_dict,
        })
        idx += 1

    add(pdc_circuit, "Alimentare PDC")
    add(boiler_circuit, "Boiler ACM")
    add(pump_circuit, "Pompa circulatie")
    add(ventilation_circuit, "Ventilatie / recuperare")

    # Automatizare (fara calcul detaliat acum)
    circuits.append({
        "id": f"TECT_{idx}",
        "panel": "TE-CT",
        "usage": "Automatizare CT",
        "device": "Automatizare",
        "breaker_a": 10,
        "cable": "3x1.5 mm² CYYF",
        "notes": "Alimentare automatizare centrala / PDC.",
    })
    idx += 1

    # Circuit de rezerva
    circuits.append({
        "id": f"TECT_{idx}",
        "panel": "TE-CT",
        "usage": "Circuit rezerva",
        "device": "Rezerva",
        "breaker_a": 16,
        "cable": "3x2.5 mm² CYYF",
        "notes": "Circuit de rezerva pentru echipamente viitoare.",
    })
    idx += 1

    # Distribuitor IP (daca exista incalzire in pardoseala)
    if has_floor_heating:
        circuits.append({
            "id": f"TECT_{idx}",
            "panel": "TE-CT",
            "usage": "Distribuitor incalzire in pardoseala",
            "device": "Distribuitor IP",
            "power_kw": 0.5,
            "breaker_a": 16,
            "cable": "3x2.5 mm² CYYF",
            "notes": "Alimentare distribuitor IP (pompe / actuatoare).",
        })

    return circuits


def build_circuits_teg(data: ProjectData, room_results: List[dict]) -> List[dict]:
    """
    Lista simplificata de circuite pentru TEG:
      - iluminat general (2 circuite daca suprafata e mare)
      - iluminat exterior
      - prize generale
      - prize bucatarie
      - masina spalat rufe (daca exista baie)
    """
    circuits = []
    idx = 1

    total_area = sum(r.area for r in data.rooms)
    has_kitchen = any(r.function == "bucatarie" for r in data.rooms)
    has_bathroom = any(r.is_bathroom or r.function == "baie" for r in data.rooms)

    # Iluminat interior: minim 1, altfel ~1 circuit / 60 m2
    num_light_circuits = max(1, math.ceil(total_area / 60.0))
    for i in range(num_light_circuits):
        circuits.append({
            "id": f"TEG_L{i+1}",
            "panel": "TEG",
            "usage": "Iluminat interior",
            "type": "iluminat",
            "breaker_a": 10,
            "cable": "3x1.5 mm² CYYF",
            "notes": "Circuit iluminat general pentru niveluri / zone.",
        })

    # Iluminat exterior
    circuits.append({
        "id": "TEG_EX1",
        "panel": "TEG",
        "usage": "Iluminat exterior",
        "type": "iluminat",
        "breaker_a": 10,
        "cable": "3x1.5 mm² CYYF",
        "notes": "Aplice LED cu senzor crepuscular la intrari / terase.",
    })

    # Prize generale: ~1 circuit / 40 m2
    num_socket_circuits = max(1, math.ceil(total_area / 40.0))
    for i in range(num_socket_circuits):
        circuits.append({
            "id": f"TEG_P{i+1}",
            "panel": "TEG",
            "usage": "Prize generale",
            "type": "prize",
            "breaker_a": 16,
            "cable": "3x2.5 mm² CYYF",
            "rcd_30ma": True,
            "afdd": True,
            "notes": "Prize generale in camere de zi / dormitoare (max ~5 prize / circuit).",
        })

    # Bucatarie - prize dedicate
    if has_kitchen:
        circuits.append({
            "id": "TEG_PB1",
            "panel": "TEG",
            "usage": "Prize blaturi bucatarie",
            "type": "prize",
            "breaker_a": 20,
            "cable": "3x2.5 mm² CYYF",
            "rcd_30ma": True,
            "afdd": True,
            "notes": "Prize blaturi bucatarie, multe consumatoare mici.",
        })
        circuits.append({
            "id": "TEG_PB2",
            "panel": "TEG",
            "usage": "Electrocasnice bucatarie",
            "type": "prize",
            "breaker_a": 20,
            "cable": "3x2.5 mm² CYYF",
            "rcd_30ma": True,
            "afdd": True,
            "notes": "Cuptor electric / masina spalat vase / alte aparate dedicate.",
        })

    # Masina de spalat rufe (daca avem baie)
    if has_bathroom:
        circuits.append({
            "id": "TEG_MSR1",
            "panel": "TEG",
            "usage": "Masina spalat rufe",
            "type": "prize",
            "breaker_a": 16,
            "cable": "3x2.5 mm² CYYF",
            "rcd_30ma": True,
            "afdd": True,
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

    lines.append(f"Proiect: {data.project_id}")
    lines.append(
        f"Cladire: {data.building.type}, regim {data.building.levels}, "
        f"Supr. utila {data.building.floor_area} m², volum {data.building.volume} m³."
    )
    lines.append(
        f"Zona climatica: {climate_zone}, izolatie: {data.building.insulation}."
    )
    if data.building.county or data.building.locality:
        loc = f"{data.building.locality or ''}, jud. {data.building.county or ''}".strip(", ")
        lines.append(f"Amplasament: {loc}.")
    lines.append("")
    lines.append(
        f"Sistem de incalzire: {data.heating.type}. "
        f"ACM: {data.heating.acm or 'nespecificat'}."
    )
    lines.append("")

    if pdc_circuit:
        lines.append("Circuit pompa de caldura (PDC):")
        lines.append(
            f"  - Putere termica: {pdc_circuit['power_kw_thermal']} kW, "
            f"putere electrica estimata: {pdc_circuit['power_kw_electric']} kW."
        )
        lines.append(
            f"  - Curent calculat: ~{pdc_circuit['current_a_calc']} A, "
            f"protectie: siguranta automata {pdc_circuit['breaker_a']} A ({pdc_circuit['poles']})."
        )
        lines.append(f"  - Cablu: {pdc_circuit['cable']}.")
        lines.append("")
    else:
        lines.append("Nu a fost generat circuit de PDC (tip incalzire diferit sau date insuficiente).")
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
        lines.append(
            f"  - Protectie: {ventilation_circuit['breaker_a']} A, cablu {ventilation_circuit['cable']}."
        )
        lines.append("")

    lines.append("Rezumat camera cu camera (prize si iluminat):")
    for r in room_results:
        lines.append(f"- {r['name']} ({r['area_m2']} m²):")
        for s in r["sockets"]:
            lines.append(
                f"    · {s['type']} x{s['count']} la h ≈ {s['height_m']} m ({s['notes']})"
            )
        for l in r["lights"]:
            lines.append(
                f"    · Iluminat: {l['type']} x{l['count']} ({l['notes']})"
            )
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

    lines.append(
        "Toate circuitele vor fi verificate si dimensionate conform normativelor in vigoare."
    )
    return "\n".join(lines)


# -------------------------------------------------
#  ENDPOINT PRINCIPAL
# -------------------------------------------------


@app.post("/calc-electric")
def calc_electric(data: ProjectData):
    # 1. Stabilim zona climatica (auto din judet, daca nu e data explicit)
    climate_zone = auto_climate_zone(data.building)

    # 2. Incalzire / PDC / TE-CT
    pdc_power_kw = calc_pdc_power_kw(data.building, data.heating, climate_zone)
    pdc_phase = data.heating.pdc_phase or "trifazat"
    pdc_circuit = (
        choose_pdc_circuit(
            power_kw=pdc_power_kw,
            phase=pdc_phase,
            pdc_type=data.heating.type,
        )
        if pdc_power_kw > 0
        else None
    )

    boiler_circuit = choose_boiler_circuit(data.building, data.heating)

    pump_circuit = None
    if data.heating.type in ["PDC aer-apa", "centrala_gaz", "centrala_electrica", "geotermala"]:
        pump_circuit = choose_pump_circuit()

    ventilation_circuit = choose_ventilation_circuit(data.heating)

    # 3. Camere
    room_results = [calc_room_electrics(r) for r in data.rooms]

    # 4. Liste de circuite
    circuits_te_ct = build_circuits_te_ct(
        pdc_circuit=pdc_circuit,
        boiler_circuit=boiler_circuit,
        pump_circuit=pump_circuit,
        ventilation_circuit=ventilation_circuit,
        has_floor_heating=data.has_floor_heating,
    )
    circuits_teg = build_circuits_teg(data, room_results)
    circuits_all = circuits_te_ct + circuits_teg

    # 5. Memoriu tehnic
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
