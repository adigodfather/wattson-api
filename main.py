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
# `memoriu_generator` trage python-docx: 12,4 MB la pornire, pentru DOUA locuri din tot
# serverul. Se importa in corpul lor — al doilea apel il ia din cache-ul de module.
from cartus_swap import swap_cartus_plan
import draw_elements
# PASUL 2 din trei: campul nedeclarat se LOGHEAZA, cererea TRECE. Trei incidente de acelasi fel
# (14 iul, P7, P9) au costat ore, fiindca Pydantic arunca in tacere si endpointul raspunde 200.
import strict_models
from strict_models import ZynModel
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


# ── PROTECTIA INSTANTEI (etapa 1, 22.09.2026) ────────────────────────────────────────────────
# Instanta are 512 MB si `get_drawings()` cere ~1,85 KB per primitiva de desen. Un plan de bloc de
# rola a urcat la 1772 MB si a omorat procesul: 502/503 pentru TOTI utilizatorii pana la repornire.
# Nici casele nu stau departe — `santandrei` cere 240 MB, deci doua incarcari deodata trec de
# limita. Decoratorul pune amandoua pazele din `capacitate.py` peste endpointurile care
# materializeaza desenul sau randeaza: o singura cerere grea odata, si nimic peste prag.
# NU schimba niciun rezultat — ce trecea, trece byte-identic.
import functools                                                          # noqa: E402
import capacitate                                                         # noqa: E402

_CAMPURI_PDF = ("pdf_base64", "base_pdf_base64", "plan_base64")


def _protejat(fn):
    """Semafor + poarta pe complexitate. Se pune SUB `@app.post(...)`.

    `functools.wraps` pastreaza `__wrapped__`, deci `inspect.signature` — si prin ea FastAPI —
    vede semnatura reala si validarea Pydantic ramane neatinsa.
    """
    @functools.wraps(fn)
    def invelis(*args, **kwargs):
        cerere = args[0] if args else next(iter(kwargs.values()), None)
        try:
            with capacitate.poarta_grea():
                _verifica_prag(cerere)
                return fn(*args, **kwargs)
        except capacitate.Ocupat:
            logger.warning("[capacitate] coada plina la %s — 503", fn.__name__)
            return JSONResponse(status_code=503, content=capacitate.mesaj_ocupat(),
                                headers={"Retry-After": "5"})
        except capacitate.PreaComplex as e:
            logger.warning("[capacitate] %s refuzat: %d primitive (limita %d)",
                           fn.__name__, e.n, capacitate.PRAG_PRIMITIVE)
            return JSONResponse(status_code=413, content=capacitate.mesaj_prea_complex(e.n))
    return invelis


def _verifica_prag(cerere):
    """Numara primitivele planului din cerere, daca cererea aduce unul.

    Fara PDF in corp (ex. /regenerate-plan, care-l ia din baza) ramane doar semaforul — tot
    protejeaza, fiindca varfurile nu se mai aduna. Orice eroare de citire lasa cererea sa treaca:
    poarta nu are voie sa blocheze utilizatori pe un bug al ei (acelasi principiu ca /validate-plan).
    """
    b64 = next((getattr(cerere, c, None) for c in _CAMPURI_PDF if getattr(cerere, c, None)), None)
    if not isinstance(b64, str) or len(b64) < 1000:
        return
    doc = None
    try:
        import fitz
        raw = b64.split(",", 1)[1] if "," in b64 else b64
        doc = fitz.open(stream=base64.b64decode(raw), filetype="pdf")
        if doc.page_count < 1:
            return
        capacitate.verifica(doc)
    except capacitate.PreaComplex:
        raise
    except Exception:
        return
    finally:
        if doc is not None:
            doc.close()


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


# Calea cererii, pusa la dispozitia validarii Pydantic (PASUL 2). Se citeste DOAR `url.path` —
# corpul nu se atinge, deci fluxul HTTP ramane exact cel de azi. Fara asta, un camp necunoscut pe
# un model IMBRICAT (Circuit, CartusFirma) n-ar avea cum sa spuna pe ce endpoint a intrat.
@app.middleware("http")
async def _marcheaza_ruta(request, call_next):
    jeton = strict_models.ruta_curenta.set(request.url.path)
    try:
        return await call_next(request)
    finally:
        strict_models.ruta_curenta.reset(jeton)


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


class MotorData(ZynModel):
    name: str
    power_kw: float
    phase: str = "tri"  # mono / tri
    count: int = 1


class ExtraEquipment(ZynModel):
    type: str   # boiler/ac/hrv/internet/solar/ev_charger/custom
    name: str
    power_kw: float = 0.0
    phase: str = "mono"  # mono / tri / none
    # FV (G2): pachetul discret + solul prizei de pamant — pydantic ar TAIA campurile nedeclarate,
    # deci le declaram explicit (optional, backward-compat: payload-urile vechi merg neschimbate)
    package_kw: Optional[float] = None
    soil_type: Optional[str] = None


class Building(ZynModel):
    type: str
    levels: str
    climate_zone: Optional[str] = None
    climate_source: Optional[str] = None  # e.g. "jud. Bihor" — auto-detected by Vision
    insulation_level: Literal["slaba", "medie", "buna", "foarte_buna"]
    main_entrance: Optional[str] = None
    total_area_m2: float
    total_volume_m3: float


class Heating(ZynModel):
    type: str  # pdc_air_water/pdc_air_air/pdc_ground_water/gas_boiler/electric_boiler/geothermal/district_heating/existing/none
    has_acm_boiler: bool = False
    has_ventilation: bool = False
    has_hrv: bool = False
    pdc_phase: Optional[Literal["mono", "tri"]] = "tri"
    distribution: Optional[str] = None  # floor_heating/fan_coil/electric_radiator/radiant_ceiling/existing


class Room(ZynModel):
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


class ProjectData(ZynModel):
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












# -------------------------------------------------
#  UTILITARE – PDC / TE-CT
# -------------------------------------------------














# -------------------------------------------------
#  CAMERE – PRIZE + ILUMINAT (rezidential)
# -------------------------------------------------




# -------------------------------------------------
#  CIRCUITE REZIDENTIAL – TE-CT + TEG
# -------------------------------------------------








# -------------------------------------------------
#  CLADIRI PUBLICE
# -------------------------------------------------




# -------------------------------------------------
#  HALE INDUSTRIALE
# -------------------------------------------------




# -------------------------------------------------
#  BLOCURI DE LOCUINTE
# -------------------------------------------------




# -------------------------------------------------
#  COMERCIAL
# -------------------------------------------------




# -------------------------------------------------
#  MEMORIU TEHNIC ADAPTAT
# -------------------------------------------------


def _memoriu_fv_sections(extra_equipment, faza=None):
    """G2: capitolele FV pentru memoriul text — [9] descrierea sistemului (identica pe faze) +
    [10] priza de pamant DEDICATA, RAMIFICATA pe faza (fix Dan): PT -> breviarul complet (ipoteze
    + formule + rezultat per pachet x sol); DTAC / faza absenta -> DOAR fraza de propunere (fara
    cifre de dimensionare). [] daca FV nu e selectat. Functie PURA (testabila izolat); accepta
    obiecte pydantic SAU dict-uri. Fail-safe: orice eroare -> [] (memoriul nu crapa)."""
    def _get(e, k, default=None):
        return e.get(k, default) if isinstance(e, dict) else getattr(e, k, default)
    try:
        solar = next((e for e in (extra_equipment or []) if _get(e, "type") == "solar"), None)
        if solar is None:
            return []
        import math as _m
        from schema_fv import FV_PACKAGES, FV_FIXED, snap_fv_package, fv_grounding
        kw = snap_fv_package(_get(solar, "package_kw") or _get(solar, "power_kw"))
        pkg = FV_PACKAGES[kw]
        g = fv_grounding(kw, _get(solar, "soil_type"))
        soil_lbl = {"mlastinos": "sol mlastinos", "argila": "argila umeda", "agricol": "sol agricol",
                    "nisip_umed": "nisip umed", "nisip_uscat": "nisip uscat", "pietris": "pietris"}[g["soil_type"]]
        lines = []

        # [B] 9. + 9.1 descrierea sistemului (montajul invertorului nu e mentionat specific:
        # memoriul se genereaza INAINTE de plasarea tablourilor FV -> "conform planului").
        # Structura-oglinda cu DOCX-ul (2.8 + 2.8.1/2.8.2): capitol UNIC cu subsectiuni.
        lines.append("9. SISTEM FOTOVOLTAIC")
        lines.append("9.1. Descrierea sistemului")
        nstr = "%d string-uri" % pkg["nr_stringuri"] if pkg["nr_stringuri"] != 1 else "1 string"
        lines.append(
            "Obiectivul este echipat cu un sistem fotovoltaic format din %d panouri fotovoltaice "
            "monocristaline de %d Wp fiecare, cu o putere instalata totala de %.2f kWp, dispuse in %s. "
            "Conversia se realizeaza printr-un invertor solar trifazat de %d kW, montat pe fatada sau "
            "in spatiul tehnic, conform planului de forta. Sistemul se racordeaza la tabloul electric "
            "general (TEG) prin tablourile de interfata si protectie T.CC (curent continuu) si T.CA "
            "(curent alternativ). Productia este contorizata separat prin contor de productie 400V."
            % (pkg["nr_panouri"], FV_FIXED["wp"], pkg["pi_kw"], nstr, pkg["invertor_ca_kw"]))
        lines.append("")

        # [C] 9.2. priza de pamant dedicata — RAMURA PE FAZA: DTAC = fraza de propunere;
        # PT = breviarul complet (ipoteze + formule + rezultat per pachet x sol)
        lines.append("9.2. Priza de pamant a sistemului fotovoltaic")
        lines.append("Sistemul fotovoltaic se leaga la o priza de pamant DEDICATA, separata de priza "
                     "de pamant a instalatiei generale.")
        from memoriu_generator import _is_pt
        if not _is_pt(faza):
            lines.append("Pentru sistemul fotovoltaic se va propune o priza de pamant dedicata, "
                         "dimensionata la faza PT (Rp <= 4 ohm).")
            lines.append("")
            return lines
        lines.append("Ipoteze de calcul:")
        lines.append("  - Rezistivitatea solului: ro = %d ohm*m (%s)." % (g["rho"], soil_lbl))
        lines.append("  - Rezistenta tinta: Rp <= 4 ohm (I7-2011).")
        lines.append("  - Tarusi OL-Zn Ø18 mm, L = 1.5 m, distanta intre tarusi a = 3 m (a/L = 2).")
        lines.append("  - Priza de contur: tarusi legati cu platbanda OL-Zn 40x4 mm, ingropata la 0.8 m.")
        r1 = g["rho"] / (2 * _m.pi * 1.5) * (_m.log(4 * 1.5 / 0.018) - 1.0)
        lines.append("Rezistenta de dispersie a unui tarus: R1 = ro/(2*pi*L)*[ln(4L/d)-1] = %.1f ohm." % r1)
        lines.append("Rezistenta grupului de n tarusi: Rn = R1/(n*eta), cu eta ~ 0.7 (coeficientul de "
                     "utilizare la a/L = 2), in paralel cu platbanda de contur.")
        lines.append("Dimensionare pentru %s, sistem de %d kW: %d tarusi de 1.5 m + %d m platbanda "
                     "OL-Zn 40x4." % (soil_lbl, kw, g["tarusi"], g["platbanda_m"]))
        if g["soil_type"] == "pietris":
            # nota SPECIALA pietris: inlocuieste linia de Rp (tarusii de 1.5 m nu ating tinta)
            lines.append("NOTA: In sol pietros (ro = 500 ohm*m), tarusii de 1.5 m nu asigura Rp <= 4 ohm. "
                         "Se recomanda tarusi de 2-3 m, electrozi forati sau tratarea solului (bentonita). "
                         "Rp se masoara la receptie.")
        else:
            rp = float(g["rp"])
            lines.append("Rezistenta de dispersie estimata: Rp = %s ohm%s." % (g["rp"], " <= 4 ohm" if rp <= 4.0 else ""))
            if rp > 4.0:
                lines.append("NOTA: Rp estimat depaseste 4 ohm; se vor adauga tarusi suplimentari sau se "
                             "prelungeste conturul pana la atingerea valorii <= 4 ohm. Rp se masoara la receptie.")
        lines.append("Rezistenta se masoara la receptie (metoda Wenner). Valorile sunt estimate de calcul.")
        lines.append("")
        return lines
    except Exception:
        return []




# -------------------------------------------------
#  ENDPOINT PRINCIPAL
# -------------------------------------------------




# -------------------------------------------------
#  ADNOTARE PLAN
# -------------------------------------------------

class RoomWithCircuits(ZynModel):
    name: str
    function: str
    bbox: Optional[dict] = None  # {x, y, w, h} in pixels
    sockets: Optional[List[dict]] = None
    lights: Optional[List[dict]] = None


class AnnotatePlanRequest(ZynModel):
    plan_base64: str   # raw base64 (no data: prefix) OR data:image/...;base64,...
    plan_type: str = "image/png"
    rooms_with_circuits: List[RoomWithCircuits]
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None


@app.post("/annotate-plan")
@_protejat
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

class CircuitSchema(ZynModel):
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


class TablouInfo(ZynModel):
    name: str
    Pi: float = 0.0
    Pa: float = 0.0
    Ia: float = 0.0
    alimentare_kv: str = "0.4"
    protectie_generala: str = ""


class ProjectInfoSchema(ZynModel):
    beneficiar: str = ""
    titlu_proiect: str = ""
    adresa: str = ""
    proiect_nr: str = ""
    data: str = ""
    faza: str = "DTAC"


class GenerateSchemaRequest(ZynModel):
    project_info: Optional[ProjectInfoSchema] = None
    tablou: TablouInfo
    circuits: List[CircuitSchema]




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

class CircuitInputNew(ZynModel):
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
    kit_panica: int = 0              # nr. becuri cu kit de emergenta pe circuit (gate-ul Notei 5)


class PowerSummaryNew(ZynModel):
    installed_kw: float = 0
    absorbed_kw: float = 0
    current_a: float = 0
    main_breaker_a: int = 63
    connection: str = "Monofazat 230V+N+PE"
    simultaneity_ks: float = 0.7
    main_breaker_type: Optional[str] = None


class PanelInfoNew(ZynModel):
    rccb_groups: List[dict] = []
    has_spd: bool = True
    name: Optional[str] = None


class EquipmentInfoNew(ZynModel):
    boiler_acm: bool = False
    aer_conditionat: bool = False
    pdc: bool = False
    pompe_circulatie: bool = False
    ventilatie_hrv: bool = False


class GenerateSchemaMultiRequest(ZynModel):
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










# ── Page format registry ─────────────────────────────────────────────────────
# max_circuits: how many branches fit on one page of this format
_PAGE_FMT_INFO: dict = {
    "A4": {"max_circuits": 8},
    "A3": {"max_circuits": 14},
    "A2": {"max_circuits": 22},
    "A1": {"max_circuits": 35},
    "A0": {"max_circuits": 55},
}












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


# -------------------------------------------------
#  SCHEMA FV (POST /generate-schema-fv-b64) — planșa IE finală, șablon fix pe pachete 5/10/15/20 kW
# -------------------------------------------------

class FvSchemaRequest(ZynModel):
    package_kw: Optional[float] = None   # pachetul explicit (5/10/15/20)
    power_kw: Optional[float] = None     # SAU puterea liberă din formular -> snap la pachet
    cartus_firma: Optional[dict] = None
    cartus_proiect: Optional[dict] = None


@app.post("/generate-schema-fv-b64")
def generate_schema_fv_b64(request: FvSchemaRequest):
    """Schema monofilară a sistemului fotovoltaic (base64, pentru n8n). Pachetul = package_kw
    sau snap-ul lui power_kw pe 5/10/15/20; cartus_firma/proiect ca la /generate-schema-b64."""
    try:
        from schema_fv import build_fv_schema, snap_fv_package
        from schema_generator import CartusFirma, CartusProiect
        kw = snap_fv_package(request.package_kw or request.power_kw or 5)
        firma = CartusFirma(**(request.cartus_firma or {}))
        proiect = CartusProiect(**(request.cartus_proiect or {}))
        pdf_bytes = build_fv_schema(kw, firma, proiect)
        return {
            "success": True,
            "package_kw": kw,
            "pdf_base64": base64.b64encode(pdf_bytes).decode('utf-8'),
            "filename": f"schema_fv_{kw}kw.pdf",
            "size_bytes": len(pdf_bytes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  SCHEMA CURENTI SLABI (POST /generate-schema-cs-b64) — schema FUNCTIONALA a sistemului de
#  efractie + supraveghere video, generata din elementele EFECTIV plasate pe planşa.
# -------------------------------------------------

class CsSchemaRequest(ZynModel):
    project_id: str = ""              # elementele se citesc din DB (ca la /bom) — sursa UNICA
    plan_elements: List[dict] = []    # SAU explicit (teste / apelanti care le au deja)
    cartus_firma: Optional[dict] = None
    cartus_proiect: Optional[dict] = None
    plansa_nr: str = ""               # numarul REAL din numerotare (n8n il trimite)
    comercial_subtip: str = ""        # gol -> se citeste din DB (doar numele RACK-ului depinde de el)


@app.post("/generate-schema-cs-b64")
def generate_schema_cs_b64(request: CsSchemaRequest):
    """Schema sistemului de curenti slabi (base64, pentru n8n).

    ELEMENTELE: din `plan_elements` daca-s trimise, altfel din DB pe `project_id` — acelasi tipar ca
    /bom. Asa etichetele (PIR 1, CV-INT 2) ies din ACELEASI randuri pe care le deseneaza planşa.
    GATE pe PREZENTA: fara echipamente de curenti slabi -> success cu skipped=True si FARA pdf, ca
    apelantul sa treaca mai departe (exact ca gate-ul de faza al caietului de sarcini)."""
    try:
        from schema_cs import build_cs_schema
        rows = list(request.plan_elements or [])
        subtip = (request.comercial_subtip or "").strip()
        if not rows and request.project_id:
            from supabase_client import supabase as _supa
            rows = (_supa.table("plan_elements").select("*")
                    .eq("project_id", request.project_id).execute().data) or []
            if not subtip:
                try:
                    _p = (_supa.table("projects").select("input_data")
                          .eq("id", request.project_id).single().execute().data) or {}
                    subtip = ((_p.get("input_data") or {}).get("comercial_subtip") or "")
                except Exception:
                    subtip = ""
        pdf_bytes = build_cs_schema(rows, request.cartus_firma or {}, request.cartus_proiect or {},
                                    request.plansa_nr or None, subtip or None)
        if not pdf_bytes:
            return {"success": True, "skipped": True,
                    "reason": "fara echipamente de curenti slabi pe plan"}
        return {
            "success": True,
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": "schema_curenti_slabi.pdf",
            "size_bytes": len(pdf_bytes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  SCHEMA DETECTIE INCENDIU (POST /generate-schema-det-b64) — schema MONOBLOC a sistemului de
#  detectie + desfumare, generata din elementele EFECTIV plasate pe planşa. Tiparul e IDENTIC cu
#  al schemei de curenti slabi (elementele din DB pe project_id, gate pe prezenta, base64 pentru
#  n8n) — schema n-are sub-tip comercial, singura diferenta fata de `CsSchemaRequest`.
# -------------------------------------------------

class DetSchemaRequest(ZynModel):
    project_id: str = ""              # elementele se citesc din DB (ca la /bom) — sursa UNICA
    plan_elements: List[dict] = []    # SAU explicit (teste / apelanti care le au deja)
    cartus_firma: Optional[dict] = None
    cartus_proiect: Optional[dict] = None
    plansa_nr: str = ""               # numarul REAL din numerotare (n8n il trimite)


@app.post("/generate-schema-det-b64")
def generate_schema_det_b64(request: DetSchemaRequest):
    """Schema monobloc a sistemului de detectie incendiu si desfumare (base64, pentru n8n).

    ELEMENTELE: din `plan_elements` daca-s trimise, altfel din DB pe `project_id` — acelasi tipar ca
    /bom si ca /generate-schema-cs-b64. Asa etichetele de bucla (D1/1, DM1/4) ies din ACELEASI
    randuri pe care le deseneaza planşa, prin `draw_elements.det_eticheta`.
    GATE pe PREZENTA: fara echipamente de detectie (sau doar cu centrala, fara nimic pe ramuri)
    `build_det_schema` intoarce None -> success cu skipped=True si FARA pdf, ca apelantul sa treaca
    mai departe. Autentificarea e cea globala (`x-zynapse-key`, middleware) — nimic in plus aici."""
    try:
        from schema_det import build_det_schema
        rows = list(request.plan_elements or [])
        if not rows and request.project_id:
            from supabase_client import supabase as _supa
            rows = (_supa.table("plan_elements").select("*")
                    .eq("project_id", request.project_id).execute().data) or []
        pdf_bytes = build_det_schema(rows, request.cartus_firma or {}, request.cartus_proiect or {},
                                     request.plansa_nr or None)
        if not pdf_bytes:
            return {"success": True, "skipped": True,
                    "reason": "fara echipamente de detectie incendiu pe plan"}
        return {
            "success": True,
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": "schema_detectie_incendiu.pdf",
            "size_bytes": len(pdf_bytes),
        }
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


def _umbra_stare():
    """Contoarele umbrei parserului; orice esec -> None, `/health` nu are voie sa cada pe asta."""
    try:
        import geometry
        return dict(geometry._umbra_stare, ultimele_diferente=geometry._umbra_log[-5:])
    except Exception:
        return None


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

    # Memoria procesului, ca sa se poata VEDEA cat de aproape de limita de 512 MB e instanta —
    # pana acum se afla doar din „Ran out of memory", adica dupa ce cadea. `/proc` exista pe
    # Linux (Render); pe Windows lipseste si campurile raman None, fara sa strice nimic.
    rss = varf = None
    try:
        with open("/proc/self/status") as f:
            for ln in f:
                if ln.startswith("VmRSS:"):
                    rss = round(int(ln.split()[1]) / 1024.0, 1)
                elif ln.startswith("VmHWM:"):          # varful atins de la pornire
                    varf = round(int(ln.split()[1]) / 1024.0, 1)
    except Exception:
        pass

    return {
        "status": "ok",
        "version": "4.0.0",
        "supabase": sb_ok,
        "supabase_error": sb_err,
        "env_url": bool(url),
        "env_key": bool(key),
        "rss_mb": rss,
        "rss_varf_mb": varf,
        "prag_primitive": capacitate.PRAG_PRIMITIVE,
        "concurenta_grea": capacitate.CONCURENTA,
        # starea UMBREI parserului: pana acum traia doar in liniile de log ale instantei, deci ca
        # sa stii daca s-a strans vreo diferenta trebuia sa derulezi logul Render. Aici se vede.
        # (`geometry` se importa local — in main nu e la nivel de modul, ca pornirea sa ramana usoara)
        "umbra": _umbra_stare(),
    }


# -------------------------------------------------
#  MEMORIU TEHNIC (.docx)  —  POST /generate-memoriu
# -------------------------------------------------

class MemoriuCartusProiect(ZynModel):
    beneficiar: str = ""
    titlu_proiect: str = ""
    amplasament: str = ""
    numar_proiect: str = ""
    faza: str = ""


class MemoriuCartusFirma(ZynModel):
    firma_nume: str = ""
    firma_reg_com: str = ""
    firma_cui: str = ""
    firma_tel: str = ""
    firma_email: str = ""
    firma_atestat: str = ""
    firma_logo_url: str = ""
    sef_proiect: str = ""
    proiectant_nume: str = ""


class MemoriuPlansa(ZynModel):
    nr: str = ""
    titlu: str = ""


class GenerateMemoriuRequest(ZynModel):
    cartus_proiect: MemoriuCartusProiect = MemoriuCartusProiect()
    cartus_firma: MemoriuCartusFirma = MemoriuCartusFirma()
    planse: List[MemoriuPlansa] = []
    # M5 (brevier de calcul) — date REALE pt. brevier. Optional (default gol -> backward-compat:
    # cererile vechi/fara aceste campuri merg normal; brevierul B le foloseste cand exista).
    circuits: List[dict] = []        # circuite (type/power_w/cable_type) -> putere iluminat reala
    power_summary: dict = {}         # current_a (Ic TEG), main_breaker_a, installed_kw, ...
    # G3: pachetul FV + solul prizei de pamant ({package_kw, soil_type} din extra_equipment.solar;
    # n8n il completeaza in body — partea n8n, separat). Gol -> memoriul FARA capitolele FV.
    solar: dict = {}
    # 2026-07-24: randurile-cablu din /bom ({item, sectiune}), trimise de finalize prin n8n ->
    # fraza 2.6 + lista TEG dinamice. Gol/absent -> texte statice byte-identice (MAIN neatins).
    bom_cables: List[dict] = []
    # ALIMENTAREA: "din_firida" (spatiu intr-un imobil existent) sau "bransament_propriu" / gol.
    # Absent = proiectele de dinainte -> bransament propriu, memoriu byte-identic.
    alimentare: str = ""
    # SURSA DE CALDURA (valorile din HEATING_GENERATION) -> capitolul 2.2 „Sistemul termoenergetic".
    # Absent/necunoscut -> capitolul LIPSESTE, memoriu byte-identic. Declararea AICI e obligatorie:
    # `model_dump()` arunca tacit orice camp nedeclarat — exact defectul din 5d3e770, unde nodul n8n
    # trimitea din iulie campuri pe care modelul nu le avea, iar generatorul nu le vedea niciodata.
    heating_type: str = ""
    # NUMEROTAREA PLANSELOR (borderoul de la PT). Cele patru campuri erau CITITE de
    # `build_memoriu_docx` (`data.get("has_tect")` etc.) dar NEDECLARATE aici — iar `model_dump()`
    # arunca tacut ce nu-i in model. Consecinta, masurata pe Render: `has_tect=False` trimis cu un
    # circuit TE-CT prezent, si `extra_floors=["etaj"]`, nu schimbau NIMIC in borderou; nodul n8n
    # le trimitea din iulie degeaba, iar memoriul cadea mereu pe derivarea din circuite. La o casa
    # cu etaj borderoul anunta doar planşele de parter, fara TES. Caietul de sarcini le declara —
    # de-aia asimetria a trecut neobservata.
    # LISTA AUTORITATII, intreaga (P9): cand vine, borderoul o foloseste ca atare in loc s-o
    # recalculeze. Declarata AICI din acelasi motiv ca celelalte — si nu teoretic: am trimis-o
    # inainte s-o declar, `model_dump()` a aruncat-o tacit, si borderoul a tiparit in continuare
    # lista lui recalculata. Avertismentul de mai sus era scris; l-am citit dupa ce-am pierdut
    # zece minute asteptand un deploy care n-avea ce sa schimbe.
    plansa_numbering: Optional[list] = None
    extra_floors: Optional[list] = None
    has_tect: Optional[bool] = None
    has_cs: Optional[bool] = None
    has_det: Optional[bool] = None
    coborare_floors: Optional[list] = None   # nivelurile fara tablou secundar -> fara schema TES


class GenerateCaietSarciniRequest(ZynModel):
    """Caiet de sarcini (2026-07-24) — livrabil DISTINCT de memoriu (CUM se execută).
    Payload aproape identic cu memoriul; emis DOAR la fazele cu PT (gate _is_pt)."""
    cartus_proiect: MemoriuCartusProiect = MemoriuCartusProiect()
    cartus_firma: MemoriuCartusFirma = MemoriuCartusFirma()
    planse: List[MemoriuPlansa] = []     # nominalizări planşe (1.4) + referinţa cap. 4
    circuits: List[dict] = []            # specificaţia tablourilor (cap. 7)
    solar: dict = {}                     # menţiunea FV + normele FV (gol -> fără)
    extra_floors: Optional[list] = None  # numerotarea planşelor (aceeaşi autoritate ca memoriul)
    has_tect: Optional[bool] = None
    has_cs: Optional[bool] = None        # curenti slabi + detectie: aceeasi lista ca la memoriu —
    has_det: Optional[bool] = None       # nominalizarea planselor (1.4) trebuie sa fie ACEEASI
    coborare_floors: Optional[list] = None   # idem: nivelurile fara tablou secundar
    alimentare: str = ""                 # "din_firida" -> racordul din firida; gol -> ca azi


@app.post("/generate-caiet-sarcini")
def generate_caiet_sarcini(request: GenerateCaietSarciniRequest):
    """Genereaza caietul de sarcini .docx (base64). DOAR la DTAC+PT / PT — la DTAC simplu
    raspunde success cu skipped=True (fara docx), ca apelantul (n8n) sa treaca mai departe."""
    try:
        from memoriu_generator import _is_pt as _cs_is_pt
        if not _cs_is_pt(request.cartus_proiect.faza):
            return {"success": True, "skipped": True,
                    "reason": "faza fara PT — caietul de sarcini se emite doar la DTAC+PT / PT"}
        from caiet_sarcini_generator import build_caiet_docx
        docx_bytes = build_caiet_docx(request.model_dump())
        numar = (request.cartus_proiect.numar_proiect or "proiect").strip()
        safe_numar = numar.replace("/", "-").replace(" ", "_") or "proiect"
        return {
            "success": True,
            "docx_base64": base64.b64encode(docx_bytes).decode("utf-8"),
            "filename": f"Caiet_Sarcini_{safe_numar}.docx",
            "size_bytes": len(docx_bytes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/generate-memoriu")
def generate_memoriu(request: GenerateMemoriuRequest):
    """Genereaza memoriul tehnic instalatii electrice ca .docx, returnat base64.
    Acelasi pattern ca /generate-schema-b64 (erori cu status 200 pentru n8n)."""
    try:
        from memoriu_generator import build_memoriu_docx
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

class SwapCartusFirma(ZynModel):
    firma_nume: str = ""
    firma_reg_com: str = ""
    firma_cui: str = ""
    firma_tel: str = ""
    firma_email: str = ""
    firma_logo_url: str = ""
    sef_proiect: str = ""
    proiectant_nume: str = ""


class SwapCartusProiect(ZynModel):
    beneficiar: str = ""
    titlu_proiect: str = ""
    amplasament: str = ""
    numar_proiect: str = ""
    faza: str = ""
    sef_proiect: str = ""     # confirmat in modalul cartusului (Vision propune, inginerul confirma)


class SwapCartusRequest(ZynModel):
    pdf_base64: str = ""
    cartus_firma: SwapCartusFirma = SwapCartusFirma()
    cartus_proiect: SwapCartusProiect = SwapCartusProiect()
    plansa_nr: str = ""
    plansa_titlu: str = ""
    rooms: Optional[list] = None   # bbox-uri Vision (fracții 0-1, {x,y,w,h}) -> mascare margini. Lipsă -> fără mascare.


@app.post("/swap-cartus-plan")
@_protejat
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

class DrawPlanElementsRequest(ZynModel):
    pdf_base64: str = ""
    plansa_nr: str = ""
    plan_type: str = "iluminat"  # deocamdată doar iluminat (becuri)
    rooms: Optional[list] = None  # camere cu bbox Vision (fracții 0-1); lipsă -> fallback regex
    apply_geometry: bool = False  # True DOAR pe faza PT (din n8n) -> centroid geometric din pereți
    project_id: str = ""          # uuid Supabase (din save_project) -> persistă elementele în plan_elements (OPȚIONAL)
    floor: str = "parter"         # eticheta etaj pt. plan_elements (idempotență per project_id+floor)
    comercial_subtip: str = ""    # sub-tipul spațiului comercial; gol -> se citește din DB (vezi mai jos)


@app.post("/draw-plan-elements")
@_protejat
def draw_plan_elements_endpoint(request: DrawPlanElementsRequest):
    try:
        payload = request.model_dump()
        # Sub-tipul comercial NU vine prin n8n (contractul lui nu se schimbă): se citește din
        # projects.input_data, pe baza lui project_id, care e deja în payload. Cine îl trimite
        # explicit are prioritate. Orice eșec -> fără sub-tip = exact comportamentul de dinainte.
        if not payload.get("comercial_subtip") and request.project_id:
            try:
                from supabase_client import supabase as _supa
                _p = (_supa.table("projects").select("input_data")
                      .eq("id", request.project_id).single().execute().data) or {}
                payload["comercial_subtip"] = ((_p.get("input_data") or {}).get("comercial_subtip") or "")
            except Exception:
                pass
        return draw_elements.draw_plan_elements(payload)
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  ENRICH CIRCUITS (Faza 2)  —  POST /enrich-circuits
#  Circuite IMBOGATITE din PLAN (plan_elements) -> format result_data.circuits, ca schema+memoriu
#  (Finalize) sa fie consistente cu PLANUL, nu cu Vision. Fail-safe: eroare -> success:False +
#  circuits:[] (caller-ul /api/finalize cade pe circuitele vechi Vision -> nu blocheaza finalizarea).
# -------------------------------------------------

class EnrichCircuitsRequest(ZynModel):
    plan_elements: list = []
    form: dict = {}
    base_circuits: list = []   # result_data.circuits — TE-CT + feed coloana se PRESERVA de aici


class ApartamenteCopiazaRequest(ZynModel):
    """P4: ce continut ar trebui sa primeasca apartamentele de pe un nivel, de la cele identice de
    dedesubt. Toate campurile declarate — `model_dump()` arunca TACIT ce nu-i in model (defectul
    din 5d3e770, unde generatorul citea campuri pe care modelul nu le avea)."""
    plan_elements: list = []
    floor: str = "parter"           # nivelul TINTA (cel deschis in editor)
    project_id: str = ""


@app.post("/apartamente-copiaza")
def apartamente_copiaza(request: ApartamenteCopiazaRequest):
    """PROPUNE ce sa se copieze; NU scrie nimic. Scrierea ramane la CLIENT, ca la restul
    elementelor de plan (`save_plan_elements` e efectiv mort — nodul n8n nu-i paseaza project_id).
    Acelasi tipar ca la kitul de panica: regula traieste aici, insertul acolo.

    Fail-safe: orice eroare -> success:False cu liste goale, ca deschiderea etajului sa nu se
    blocheze niciodata din cauza unei copieri."""
    try:
        import apartments as _ap
        import floors as _fl
        r = _ap.copieri_pentru_nivel(request.plan_elements or [], request.floor,
                                     request.project_id, _fl.floor_canonic, _fl.floor_index)
        return {"success": True, **r}
    except Exception as e:
        return {"success": False, "error": str(e), "copieri": [], "sarite": []}


@app.post("/enrich-circuits")
def enrich_circuits_endpoint(request: EnrichCircuitsRequest):
    try:
        import enrich_circuits as _ec
        circuits = _ec.enrich_circuits(request.plan_elements or [], request.form or {},
                                       base_circuits=request.base_circuits or [])
        # GRAFUL DE TABLOURI (P1) — ADITIV: `circuits` iese exact ca pana acum, iar `panels` e un
        # camp NOU pe care azi nu-l citeste nimeni. Calculul lui sta AICI, nu in n8n, pentru ca e o
        # sumare peste circuitele pe care tot backendul le produce: pus dincolo, ar deveni a doua
        # sursa de adevar pentru aceleasi cifre (exact divergenta plan/schema reparata cu enrich).
        # Esecul lui nu are voie sa strice raspunsul: circuitele sunt livrabilul.
        try:
            import panels as _pnl
            _graf = _pnl.panel_graph(circuits)
        except Exception as _eg:
            print("[enrich-circuits] panel_graph skip:", _eg)
            _graf = {}
        return {"success": True, "circuits": circuits, "count": len(circuits), "panels": _graf}
    except Exception as e:
        return {"success": False, "error": str(e), "circuits": []}


# -------------------------------------------------
#  BOM / LISTA DE CANTITATI (antemasuratori)  —  POST /bom
#  7 categorii (sigurante/cabluri/prize/becuri/tablouri/receptoare/tuburi) din SURSA UNIFICATA
#  (enrich_circuits + plan_elements) -> CONSISTENT cu schema/memoriu (aceleasi numere). Metri:
#  scala per-proiect din area_m2 (fallback fix ~1:71). Self-contained: citeste DB pe project_id.
# -------------------------------------------------

class BomRequest(ZynModel):
    project_id: str = ""
    base_pdf_base64: str = ""   # pt. W/H (scala per-proiect); OPTIONAL -> fallback scala fixa
    form: dict = {}             # extra_equipment (puteri receptoare), ca la enrich
    waste: float = 1.1          # adaos (decizia Dan: +10% pe orizontale+verticale; acopera mustatile)


@app.post("/bom")
@_protejat
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
        proj = (_supa.table("projects").select("result_data, input_data")
                .eq("id", request.project_id).single().execute().data) or {}
        rd = (proj.get("result_data") or {})
        _rooms = rd.get("rooms") or []
        base_circuits = rd.get("circuits") or []
        # G1: priza de pamant FV — pachetul + solul din extra_equipment.solar (input_data contine
        # DOAR echipamentele BIFATE -> prezenta solar = FV selectat). Sol absent -> agricol (default
        # pana la selectorul UI). Esec parsare -> fara categoria FV (fail-safe).
        _fvg = None
        try:
            _inp = (proj.get("input_data") or {})
            _solar = next((e for e in (_inp.get("extra_equipment") or [])
                           if isinstance(e, dict) and e.get("type") == "solar"), None)
            if _solar:
                from schema_fv import fv_grounding as _fv_grounding
                _fvg = _fv_grounding(_solar.get("package_kw") or _solar.get("power_kw"),
                                     _solar.get("soil_type"))
        except Exception:
            _fvg = None
        # W/H din base_pdf (fallback); lipsa -> png_meta per plansa (mai jos) -> scala fixa.
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
        # P0-4: W/H PER ETAJ din png_meta-ul plansei lui (planse_iluminat sortate pe source_plansa_nr =
        # ordinea etajelor: IE.1=parter, IE.2=etaj, ...). Self-contained (fara base_pdf param). Fallback:
        # W/H din base_pdf (toate etajele) -> altfel (0,0) -> derive_scale cade pe scala fixa.
        _floor_wh = {}
        try:
            _order = ["parter", "etaj", "mansarda"]
            _pls = sorted((rd.get("planse_iluminat") or []),
                          key=lambda p: str((p or {}).get("source_plansa_nr") or ""))
            for _i, _p in enumerate(_pls):
                if _i >= len(_order):
                    break
                _pm = (_p or {}).get("png_meta") or {}
                _pw, _ph = float(_pm.get("pdf_width_pt") or 0), float(_pm.get("pdf_height_pt") or 0)
                if _pw > 0 and _ph > 0:
                    _floor_wh[_order[_i]] = (_pw, _ph)
        except Exception:
            _floor_wh = {}
        if _W and _H:
            for _fl in ("parter", "etaj", "mansarda"):
                _floor_wh.setdefault(_fl, (_W, _H))
        # ACELEASI circuite ca schema/memoriu (enrich; pe TOATE elementele — per proiect, nu per etaj).
        # sub-tipul comercial (zonele umede proprii comertului) din DB, ca la /draw-plan-elements:
        # callerul nu-l trimite, dar project_id e deja aici -> BOM-ul vede aceleasi circuite ca schema
        _formb = dict(request.form or {})
        _formb.setdefault("comercial_subtip", (proj.get("input_data") or {}).get("comercial_subtip") or "")
        # ALIMENTAREA (bransament propriu / din firida): tot din DB, ca sub-tipul — contractul
        # endpoint-ului NU se schimba. Absenta (proiecte vechi) -> bransament propriu, ca azi.
        _formb.setdefault("alimentare", (proj.get("input_data") or {}).get("alimentare") or "")
        circuits = _ec.enrich_circuits(rows, _formb, base_circuits=base_circuits)
        # FOLLOW-UP FIX-C1: geometria camerelor (pereti reali) PER ETAJ din bazele curate
        # (rd.planuri[i].pdf_base64, aceeasi sursa ca redraw; ordinea = parter/etaj/mansarda) ->
        # compute_cables din BOM ruteaza EXACT ca desenul (gate geom_bbox->Vision) -> metrii =
        # traseul de pe plan (pe pereti), nu L-urile scurte. Defensiv: ORICE esec / etaj fara
        # geometrie -> etajul lipseste din dict -> rutarea veche pt. el, byte-identica.
        _floor_geoms = {}
        try:
            import fitz
            import geometry as _geo2
            _order2 = ["parter", "etaj", "mansarda"]
            for _i, _p in enumerate(rd.get("planuri") or []):
                if _i >= len(_order2):
                    break
                try:
                    # plansa vine din rand SAU din Storage (vezi supabase_client.plansa_bytes).
                    # Inainte se citea numai `pdf_base64`, iar mutarea in Storage l-a golit: ramura
                    # asta a incetat sa se mai execute la TOATE proiectele, fara nicio eroare, si
                    # metrii de cablu au cazut tacut pe rutarea veche.
                    from supabase_client import plansa_bytes as _plb
                    _pdf2 = _plb(_p or {})
                    if not _pdf2:
                        continue
                    _doc2 = fitz.open(stream=_pdf2, filetype="pdf")
                    _w2, _h2 = _doc2[0].rect.width, _doc2[0].rect.height
                    _doc2.close()
                    _fi = _bom._FLOOR_IDX.get(_order2[_i], 0)
                    _rooms_fl2 = [r for r in _rooms if int((r or {}).get("floor") or 0) == _fi]
                    _geos2 = _geo2.extract_room_geometry(_pdf2, _rooms_fl2, _w2, _h2)
                    _gm2 = {}
                    for _g in (_geos2 or []):
                        _gb = (_g or {}).get("geom_bbox")
                        _nm = str((_g or {}).get("name") or "").strip()
                        if _gb and _nm:
                            _gm2[_nm] = (float(_gb["x"]) * _w2, float(_gb["y"]) * _h2,
                                         (float(_gb["x"]) + float(_gb["w"])) * _w2,
                                         (float(_gb["y"]) + float(_gb["h"])) * _h2)
                    if _gm2:   # ca la redraw: doar cu geometrie reala gasita (gol -> rutarea veche)
                        _floor_geoms[_order2[_i]] = _gm2
                except Exception:
                    continue
        except Exception:
            _floor_geoms = {}
        # P0-4: orizontalele PER ETAJ (floor filter + rooms filtrate + scara plansei etajului) —
        # inainte: compute_cables pe elementele AMESTECATE (+75% pe P+M + cabluri fizic imposibile).
        horiz_m, cables, _flinfo = _bom.per_floor_horizontals(rows, _rooms, _floor_wh,
                                                              floor_geoms=_floor_geoms or None)
        # scara "principala" (parter) — pt. dedicate/coloane (_extra_meters, pozitii parter) + verticale
        _p_wh = _floor_wh.get("parter") or (_W, _H)
        _rooms_p = [r for r in _rooms if int((r or {}).get("floor") or 0) == 0]
        scale, ssrc = _bom.derive_scale(_rooms_p or _rooms, _p_wh[0], _p_wh[1])
        # rooms (height_m) -> COBORARILE VERTICALE; power_summary -> randul de BRANSAMENT TEG;
        # W/H -> H-ul camerei tabloului (geometric, tablourile au room null).
        out = _bom.build_bom(rows, circuits, cables, scale, waste=float(request.waste or 1.1),
                             subtip=(_formb.get("comercial_subtip") or None),
                             alimentare=(_formb.get("alimentare") or None),
                             rooms=_rooms, power_summary=rd.get("power_summary") or {},
                             W=(_p_wh[0] or None), H=(_p_wh[1] or None), horizontal_m=horiz_m,
                             fv_grounding=_fvg)
        # `geom_rooms` face RAMURA GEOMETRICA vizibila din afara: cate camere au intrat in rutare
        # cu conturul lor real, per etaj. Pana acum nimic nu o pazea — cand mutarea in Storage a
        # golit campul din care se citea plansa, ramura a incetat sa se execute, raspunsul a ramas
        # 200, iar metrii au cazut tacut pe rutarea veche. Un test poate cere acum > 0.
        return {"success": True, "scale_m_per_px": round(scale, 6), "scale_source": ssrc,
                "geom_rooms": {k: len(v) for k, v in (_floor_geoms or {}).items()},
                "floors": {k: {"scale": round(v["scale"], 6), "scale_source": v["scale_source"],
                               "n_elements": v["n_elements"], "n_rooms": v["n_rooms"]}
                           for k, v in _flinfo.items()},
                "rows": out["rows"], "summary": out["summary"]}
    except Exception as e:
        return {"success": False, "error": str(e), "rows": []}


# -------------------------------------------------
#  NUMEROTARE PLANSE (IE.1..IE.N)  —  POST /plansa-numbering
#  SINGURA sursa de adevar pt. numerotarea secventiala (fara goluri, ordinea fixa) din ce EXISTA.
#  Wrapper subtire peste plansa_numbering.compute_plansa_numbering (pura, testata izolat). n8n (Faza 2B)
#  o cheama, apoi restampeaza fiecare PDF cu /restamp-plansa. Sub x-zynapse-key (middleware global).
# -------------------------------------------------

class PlansaNumberingRequest(ZynModel):
    """CONTRACTUL endpointului = EXACT parametrii functiei pure.

    Avea patru campuri cand functia citea deja douazeci: un camp nedeclarat pe un model Pydantic
    NU da eroare, se ARUNCA in tacere. E aceeasi clasa de defect ca `model_dump()` din 14 iulie,
    unde `extra_floors` si `has_tect` plecau din n8n si nu ajungeau niciodata — saptamani in care
    totul raspundea 200. De-aia campurile de aici se tin sincronizate cu semnatura functiei, si
    de-aia testul lor trece PRIN ENDPOINT: un test care cheama functia direct ar fi verde si cand
    modelul arunca tot."""
    extra_floors: List[str] = []   # niveluri peste parter, in ordine (ex. ["etaj"] / ["etaj","mansarda"])
    has_tect: bool = False         # exista tablou centrala termica -> schema TE-CT
    has_tes: Optional[bool] = None # override; implicit = exista cel putin un nivel peste parter
    has_fv: bool = False           # sistem fotovoltaic selectat (solar.enabled) -> schema FV = ULTIMA IE
    # curenti slabi + detectie (pachetul de curenti slabi) — planşele CHIAR generate, nu derivate
    has_cs: bool = False
    has_schema_cs: Optional[bool] = None
    has_det: bool = False
    has_schema_det: Optional[bool] = None
    coborare_floors: Optional[List[str]] = None
    # ── BLOC (P5). Toate implicit ABSENT: o casa nu trimite niciunul si lista iese ca pana acum.
    has_situatie: bool = False
    has_camera_pompe: bool = False
    has_schema_camera_pompe: Optional[bool] = None
    has_teg: bool = True           # un bloc il trece pe False (tabloul general e BMPT/TEGD)
    has_distributie: bool = False
    has_bmpt_fdcp: bool = False
    fdcp: Optional[List[str]] = None          # cate o schema per firida de palier
    apartamente: Optional[List[str]] = None   # tipurile de apartament (AP-1, AP-2...)
    spatii: Optional[List[str]] = None        # spatiile comerciale (SP1, SP2...)
    has_tcc: bool = False
    has_tecv: bool = False
    has_tv: bool = False
    has_date: bool = False
    has_interfon: bool = False
    detalii: Optional[List[str]] = None       # planşele de detaliu care exista


@app.post("/plansa-numbering")
def plansa_numbering_endpoint(request: PlansaNumberingRequest):
    """Lista ORDONATA a planselor EXISTENTE, IE.1..IE.N fara goluri. Erori status 200 (n8n)."""
    try:
        from plansa_numbering import compute_plansa_numbering
        planse = compute_plansa_numbering(
            request.extra_floors or [], bool(request.has_tect), request.has_tes,
            bool(request.has_fv),
            has_cs=bool(request.has_cs), has_schema_cs=request.has_schema_cs,
            has_det=bool(request.has_det), has_schema_det=request.has_schema_det,
            coborare_floors=request.coborare_floors,
            has_situatie=bool(request.has_situatie),
            has_camera_pompe=bool(request.has_camera_pompe),
            has_schema_camera_pompe=request.has_schema_camera_pompe,
            has_teg=bool(request.has_teg),
            has_distributie=bool(request.has_distributie),
            has_bmpt_fdcp=bool(request.has_bmpt_fdcp),
            fdcp=request.fdcp, apartamente=request.apartamente, spatii=request.spatii,
            has_tcc=bool(request.has_tcc), has_tecv=bool(request.has_tecv),
            has_tv=bool(request.has_tv), has_date=bool(request.has_date),
            has_interfon=bool(request.has_interfon), detalii=request.detalii)
        return {"success": True, "planse": planse, "count": len(planse)}
    except Exception as e:
        return {"success": False, "error": str(e), "planse": []}


# -------------------------------------------------
#  SARCINILE SCHEMELOR  —  POST /schema-payloads
#  Lista ANUNTATA de /plansa-numbering -> cate o sarcina gata de trimis la /generate-schema-b64,
#  cu numarul ei de planşa. n8n doar itereaza: nu mai decide EL ce scheme exista.
#  Inlocuieste lista alba prin regex din nodul „Generate Schemas TES" (/^TES\d+$/), care lasa pe
#  dinafara 15 din cele 16 tablouri ale unui bloc si, invers, genera scheme neanuntate.
# -------------------------------------------------

class SchemaPayloadsRequest(ZynModel):
    planse: List[dict] = []            # iesirea /plansa-numbering (autoritatea)
    circuits: List[dict] = []
    cartus_firma: dict = {}
    cartus_proiect: dict = {}
    tipuri_apartament: List[dict] = []  # din /tipuri-apartament; gol = fara scheme de tip


@app.post("/schema-payloads")
def schema_payloads_endpoint(request: SchemaPayloadsRequest):
    """{sarcini, lipsa, count}. `lipsa` = planse anuntate fara tablou — se VAD, nu dispar."""
    try:
        from schema_payloads import sarcini_scheme
        r = sarcini_scheme(request.planse or [], request.circuits or [],
                           cartus_firma=request.cartus_firma or {},
                           cartus_proiect=request.cartus_proiect or {},
                           tipuri_ap=request.tipuri_apartament or [])
        return {"success": True, "sarcini": r["sarcini"], "lipsa": r["lipsa"],
                "count": len(r["sarcini"])}
    except Exception as e:
        return {"success": False, "error": str(e), "sarcini": [], "lipsa": []}


# -------------------------------------------------
#  GRUPARILE DE BLOC  —  POST /tipuri-apartament
#  Doua grupari, amandoua „mai multe obiecte, o singura planşa":
#    `tipuri` — tipul de apartament = RADACINA lantului `copiat_din` (decizia Dan). Pe blocul lui:
#               2 tipuri pentru 27 de apartamente.
#    `fdcp`   — firidele de palier identice. Cere si `circuits`; fara ele iese lista goala.
#  Numele caii ramane `/tipuri-apartament` DELIBERAT: Render si Vercel se deployeaza separat, iar o
#  redenumire ar fi deschis o fereastra in care frontendul vechi cheama o cale care nu mai exista si
#  isi pierde TACUT tipurile de apartament (try/catch -> lista goala). Campul nou e aditiv.
# -------------------------------------------------

class TipuriApartamentRequest(ZynModel):
    plan_elements: List[dict] = []
    circuits: List[dict] = []          # doar pentru gruparea FDCP; gol = `fdcp` gol


@app.post("/tipuri-apartament")
def tipuri_apartament_endpoint(request: TipuriApartamentRequest):
    try:
        import apartments as _ap
        import floors as _fl
        from schema_payloads import grupuri_fdcp
        t = _ap.tipuri_apartament(request.plan_elements or [], _fl.floor_canonic, _fl.floor_index)
        # ACEEASI functie pe care o cheama /schema-payloads cand rezolva o planşa `schema_fdcp`.
        # Daca cele doua ar grupa diferit, numerotarea ar anunta planşe pe care generatorul nu le
        # poate produce — exact dezechilibrul inchis la P9.
        g = grupuri_fdcp(request.circuits or [], t)
        return {"success": True, "tipuri": t, "count": len(t), "fdcp": g}
    except Exception as e:
        return {"success": False, "error": str(e), "tipuri": [], "fdcp": []}


# -------------------------------------------------
#  RESTAMP PLANSA (nr + titlu final pe cartus)  —  POST /restamp-plansa
#  Re-stampeaza numarul FINAL (IE.N) + numele pe cartusul unui PDF gata (cartus_swap.restamp_plansa,
#  reutilizeaza metadata zy_cartus_plansa/zy_cartus_title). Asa numarul TIPARIT = numarul din documente.
# -------------------------------------------------

class RestampPlansaRequest(ZynModel):
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

class RegeneratePlanRequest(ZynModel):
    project_id: str = ""
    floor: str = "parter"
    base_pdf_base64: str = ""   # BAZA CURATA = planuri[].pdf_base64 (cartus+mask, FARA becuri)
    plan_type: str = "iluminat"   # F4: ce DESENAM (iluminat=becuri/...; forta=prize). default backward-compat


@app.post("/regenerate-plan")
@_protejat
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
        # ETICHETE CIRCUITE pe alimentari (decizia Dan, 2026-07-17): codul enrich (C14 / C3-TECT)
        # injectat IN-MEMORY pe elemente (_cid_label — NU se persista; circuit_id in DB ramane None
        # pt. dedicate, by design). Enrich = ACEEASI functie + ACELEASI inputuri ca finalize
        # (plan_elements TOATE + base_circuits=result_data.circuits + form derivat identic) ->
        # numerotare CONSECVENTA cu schema/memoriul prin constructie. Mapare circuit->element:
        # (1) pozitia _plan_x/_plan_y (dedup-ul base_covered o seteaza pe circuitele din breviar);
        # (2) cheia _equip_key_fine + room, apoi doar cheia, in ordinea elementelor (= ordinea in
        # care enrich creeaza dedicatele 1:1) — acopera 2x AC etc. Defensiv: ORICE esec -> fara
        # coduri -> draw cade pe eticheta VECHE (fallback in draw_elements).
        # DETECTIE INCENDIU: aceeasi injectie de coduri — echipamentele de desfumare si centrala
        # au circuit dedicat, iar eticheta lor de pe planşa il poarta (tiparul fortei).
        if request.plan_type in ("forta", "detectie_incendiu"):
            try:
                import enrich_circuits as _ecm
                import draw_elements as _dem
                from supabase_client import supabase as _supa5
                _prj5 = (_supa5.table("projects").select("result_data, input_data")
                         .eq("id", request.project_id).single().execute().data) or {}
                _rd5 = (_prj5.get("result_data") or {})
                _in5 = (_prj5.get("input_data") or {})
                _allrows = (_supa5.table("plan_elements").select("*")
                            .eq("project_id", request.project_id).execute().data) or []
                _conn5 = str((_rd5.get("power_summary") or {}).get("connection") or "").lower()
                _form5 = {"power_phase": ("tri" if ("trif" in _conn5 or "400" in _conn5) else "mono"),
                          "has_tech_room": _in5.get("has_tech_room", True),
                          "heating_type": _in5.get("heating_type"),
                          "comercial_subtip": _in5.get("comercial_subtip") or "",
                          "extra_equipment": _in5.get("extra_equipment") or []}
                _ecirc = _ecm.enrich_circuits(_allrows, _form5, base_circuits=_rd5.get("circuits") or [])
                _ded = [c for c in _ecirc if isinstance(c, dict) and c.get("type") == "dedicat" and c.get("id")]
                # tipurile care pot primi cod: receptoarele de forta + cele de detectie cu circuit
                # (centrala + desfumarea alimentata). Lista vine din registrul familiei, nu
                # rescrisa aici — un tip nou de desfumare intra automat.
                _RTYPES = ("alimentare_receptor", "receptor_internet") + tuple(
                    _dem._DET_TYPES if request.plan_type == "detectie_incendiu" else ())

                def _k_el(_el):
                    if (_el.get("element_type") or "") == "receptor_internet":
                        return "internet"
                    return _ecm._equip_key_fine(_el.get("label"))

                _codes, _ded_left = {}, []
                # (0) TEXT EXACT (label == description, normalizat, cu/fara prefixul "alimentare") —
                # INAINTEA pozitiei: pozitiile _plan_x/_plan_y din baza pot fi INCRUCISATE pe chei
                # comune (ex. cele 2 pompe, cheia 'pompa' — dedup-ul de la generare a legat pozitiile
                # in ordinea intalnirii). Textul identic garanteaza cod = circuitul REAL al elementului
                # (eticheta planului consecventa cu schema: C4 = tur si pe plan, si in schema).
                def _norm_t(_s):
                    return (_s or "").strip().lower().replace("ă", "a").replace("â", "a").replace("î", "i").replace("ș", "s").replace("ț", "t")
                _ded_pool = list(_ded)
                for _el in _allrows:
                    if (_el.get("element_type") or "") not in _RTYPES or not _el.get("id"):
                        continue
                    _lt = _norm_t(_el.get("label"))
                    if not _lt:
                        continue
                    for _c in _ded_pool:
                        _dt = _norm_t(_c.get("description") or _c.get("usage"))
                        if _dt == _lt or _dt == ("alimentare " + _lt):
                            _codes[_el["id"]] = str(_c["id"])
                            _ded_pool.remove(_c)
                            break
                _ded = _ded_pool                                   # ramasii intra pe pozitie/cheie
                for _c in _ded:                                    # (1) pozitie exacta (dedup a scris-o)
                    _px, _py = _c.get("_plan_x"), _c.get("_plan_y")
                    _hit = None
                    if _px is not None and _py is not None:
                        for _el in _allrows:
                            if ((_el.get("element_type") or "") in _RTYPES and _el.get("id")
                                    and _el["id"] not in _codes
                                    and abs(float(_el.get("x") or 0) - float(_px)) < 0.01
                                    and abs(float(_el.get("y") or 0) - float(_py)) < 0.01):
                                _hit = _el
                                break
                    if _hit is not None:
                        _codes[_hit["id"]] = str(_c["id"])
                    else:
                        _ded_left.append(_c)
                for _el in _allrows:                               # (2) cheie + room, apoi cheie (in ordine)
                    if (_el.get("element_type") or "") not in _RTYPES or not _el.get("id") or _el["id"] in _codes:
                        continue
                    _ke = _k_el(_el)
                    if not _ke:
                        continue                                   # custom nemapabil -> fara cod (eticheta veche + nume)
                    _pick = None
                    for _c in _ded_left:
                        if (_ecm._equip_key_fine(_c.get("description") or _c.get("usage")) == _ke
                                and str(_c.get("room") or "") == str(_el.get("room") or "")):
                            _pick = _c
                            break
                    if _pick is None:
                        for _c in _ded_left:
                            if _ecm._equip_key_fine(_c.get("description") or _c.get("usage")) == _ke:
                                _pick = _c
                                break
                    if _pick is not None:
                        _codes[_el["id"]] = str(_pick["id"])
                        _ded_left.remove(_pick)
                # NIVEL FARA TABLOU SECUNDAR: planşa a persistat id-ul LOCAL (C1-SUS), dar circuitul
                # sta pe TEG si poarta acolo numarul din numerotarea TEG (C5). Fara puntea asta,
                # eticheta de pe planşa si numarul din schema ar arata doua lucruri diferite pentru
                # acelasi circuit — exact divergenta plan/schema pe care numerotarea per-tablou a
                # rezolvat-o la restul. `_plan_cid` e id-ul de planşa, pastrat de enrich inainte de
                # renumerotare. Marcajul "-SUS" ramane pe cod: `_cid_display` il ascunde, iar
                # `_cid_coboara` aprinde sageata vectoriala.
                _pc_map = {str(_c.get("_plan_cid")): str(_c.get("id"))
                           for _c in _ecirc
                           if isinstance(_c, dict) and str(_c.get("_plan_cid") or "").endswith("-SUS")}
                for _el in rows:
                    _pc = str(_el.get("circuit_id") or "")
                    if _pc in _pc_map:
                        _el["_cid_label"] = _pc_map[_pc] + "-SUS"
                for _el in rows:                                   # injectare pe subsetul etajului (alt fetch, acelasi id)
                    if _el.get("id") in _codes:
                        _el["_cid_label"] = _codes[_el["id"]]
            except Exception as _e5:
                print("[regenerate-plan] etichete circuite skip:", _e5)   # defensiv: eticheta veche
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
        # TRAVERSARE INTRE NIVELURI (cross-plansa, varianta A — decizia Dan): cand TEG si TES sunt pe
        # ETAJE DIFERITE, plansa cu TEG primeste coloana TEG->proiectia TES (pe trasee) + simbol "URCA",
        # iar plansa cu TES primeste simbolul "VINE DE JOS". Proiectia = pozitia TES transformata cu
        # floor_offset (cascada: axe CAD -> pereti -> identitate; plansele-s suprapuse, R&D 2026-07-10).
        # Doar pe planul de FORTA. Defensiv: ORICE esec -> fara traversare, planul ramane intact.
        _cross = None
        try:
            if request.plan_type == "forta":
                from supabase_client import supabase as _supa4
                _pans = (_supa4.table("plan_elements").select("element_type,x,y,floor")
                         .eq("project_id", request.project_id)
                         .in_("element_type", ["tablou_teg", "tablou_tes", "coborare_cabluri"])
                         .execute().data) or []
                _tegr = next((r for r in _pans if r.get("element_type") == "tablou_teg"), None)
                # CAPATUL DE SUS al coloanei: tabloul secundar SAU, pe nivelul fara tablou, punctul
                # de coborare. Traversarea e ACEEASI (o coloana intre doua niveluri) — se schimba
                # doar ce sta in capatul de sus si textul sagetilor. Mecanismul se REFOLOSESTE.
                _cobr = next((r for r in _pans if r.get("element_type") == "coborare_cabluri"), None)
                _tesr = next((r for r in _pans if r.get("element_type") == "tablou_tes"), None) or _cobr
                _e_cob = (_tesr is not None and _cobr is not None
                          and _tesr.get("element_type") == "coborare_cabluri")
                _f_teg = str((_tegr or {}).get("floor") or "parter")
                _f_tes = str((_tesr or {}).get("floor") or "parter")
                if _tegr and _tesr and _f_teg != _f_tes and request.floor in (_f_teg, _f_tes):
                    try:
                        _rdX = _rd2 if isinstance(_rd2, dict) and _rd2 else {}
                    except NameError:
                        _rdX = {}                      # blocurile feeds/numerotare au picat -> refetch mai jos
                    if not _rdX:
                        _rdX = (((_supa4.table("projects").select("result_data")
                                  .eq("id", request.project_id).single().execute().data) or {})
                                .get("result_data")) or {}
                    # plansa etajului N = planuri[N] sortate pe plansa_nr (IE.1=parter, IE.2=etaj, ...)
                    _order = ["parter", "etaj", "mansarda"]
                    _pls = sorted((_rdX.get("planuri") or []), key=lambda p: str((p or {}).get("plansa_nr") or ""))
                    # AL DOILEA cititor de calcul ramas pe campul golit de mutarea in Storage:
                    # fara plansele celor doua niveluri, `floor_offset` cade pe „identity", adica
                    # proiectia TES-ului pe plansa TEG-ului ateriza netranslatata. Tacut, ca si la
                    # /bom. `floor_offset` cere base64, deci octetii se reimbraca aici.
                    from supabase_client import plansa_bytes as _plb2
                    _pdf_of = {}
                    for _i2, _p2 in enumerate(_pls):
                        if _i2 >= len(_order):
                            break
                        _raw2 = _plb2(_p2 or {})
                        _pdf_of[_order[_i2]] = base64.b64encode(_raw2).decode() if _raw2 else ""
                    if request.floor == _f_teg:
                        # plansa cu TEG: proiecteaza TES aici -> coloana + simbol URCA
                        _dx, _dy, _osrc = draw_elements.floor_offset(_pdf_of.get(_f_tes, ""), _pdf_of.get(_f_teg, ""))
                        _px, _py = float(_tesr["x"]) + _dx, float(_tesr["y"]) + _dy
                        # clamp pe amprenta plansei curente (etaj in consola -> proiectia nu iese din cladire)
                        try:
                            import fitz as _fz
                            import geometry as _geo
                            _rawX = request.base_pdf_base64.split(",", 1)[-1]
                            _dX = _fz.open(stream=base64.b64decode(_rawX), filetype="pdf")
                            _hs, _vs, _ = _geo._collect(_dX[0])
                            _dX.close()
                            _xs = [s for (x0, x1, _y) in _hs for s in (x0, x1)] + [x for (_y0, _y1, x) in _vs]
                            _ys = [y for (_x0, _x1, y) in _hs] + [s for (y0, y1, _x) in _vs for s in (y0, y1)]
                            if _xs and _ys:
                                _px = min(max(_px, min(_xs) + 6.0), max(_xs) - 6.0)
                                _py = min(max(_py, min(_ys) + 6.0), max(_ys) - 6.0)
                        except Exception:
                            pass
                        _cross = {"mode": "up", "xy": (_px, _py),
                                  "label": ("Alimentare circuite %s (vine de sus)" % _f_tes if _e_cob
                                            else "Coloana spre TES (%s)" % _f_tes),
                                  "offset_source": _osrc}
                        print("[regenerate-plan] cross-floor UP: offset=(%.2f, %.2f) src=%s -> TES proiectat (%.1f, %.1f)"
                              % (_dx, _dy, _osrc, _px, _py))
                    else:
                        # plansa cu TES: simbolul "vine de jos" LANGA tablou (24pt deasupra —
                        # exact pe pozitia TES ar acoperi simbolul tabloului)
                        # pe planşa de SUS simbolul il deseneaza chiar elementul (COBOARA LA TEG),
                        # deci aici nu se mai adauga unul al doilea peste el
                        _cross = (None if _e_cob else
                                  {"mode": "down", "xy": (float(_tesr["x"]), float(_tesr["y"]) - 24.0),
                                   "label": "Alimentare din TEG (%s)" % _f_teg})
                    # sectiunea coloanei TES in legenda: feed-ul TES REAL din schema (enrich il genereaza
                    # acum: feeds_panel="TES1"/"TES2"); fallback normativ DOAR daca lipseste cu totul
                    # (proiecte nefinalizate pre-enrich) — cu prefixul FAZEI bransamentului (mono: 3 fire)
                    if not any(isinstance(f, dict) and str(f.get("feeds_panel") or "").startswith("TES") for f in _feeds):
                        _conn = str(((_rdX.get("power_summary") or {}).get("connection")) or "").lower()
                        _pref = "3x" if "monofazat" in _conn else "5x"
                        _feeds.append({"type": "sub_tablou", "feeds_panel": "TES", "cable_type": "CYY-F %s6mmp" % _pref})
        except Exception as _e4:
            print("[regenerate-plan] cross-floor skip:", _e4)
        # Sub-tipul comercial: DOAR pentru numele DDCS -> RACK pe eticheta si in legenda. Se citeste
        # din projects.input_data pe baza lui project_id (deja aici), ca la /draw-plan-elements —
        # contractul /regenerate-plan nu se schimba. Esec -> None = rezidential, ca inainte.
        _subtip = None
        try:
            from supabase_client import supabase as _supaS
            _pS = (_supaS.table("projects").select("input_data")
                   .eq("id", request.project_id).single().execute().data) or {}
            _subtip = ((_pS.get("input_data") or {}).get("comercial_subtip") or "").strip() or None
        except Exception:
            _subtip = None
        return draw_elements.redraw_from_plan_elements(
            request.base_pdf_base64, rows, draw_plan_type=request.plan_type, feeds=_feeds, rooms=_rooms,
            plansa_nr=_pl_nr, plansa_titlu=_pl_titlu, circuits=_circs, cross_floor=_cross,
            subtip=_subtip)
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
#  RENDER BASE PNG (fundal editor forta)  —  POST /render-base-png
#  Randare PURA a paginii PDF -> PNG + png_meta (mapare coordonate), FARA a desena elemente.
#  Fundalul editorului de FORTA = baza CURATA (planuri[].pdf_base64), nu iluminatul (becuri invechite).
#  Acelasi DPI/meta ca draw_plan_elements -> editorul mapeaza IDENTIC. Sub x-zynapse-key (middleware).
# -------------------------------------------------

class RenderBasePngRequest(ZynModel):
    pdf_base64: str = ""
    dpi: int = 120          # identic cu draw_plan_elements (png_meta.scale = dpi/72)


@app.post("/render-base-png")
@_protejat
def render_base_png_endpoint(request: RenderBasePngRequest):
    """PDF (baza curata) -> {png_base64, png_meta}. NU deseneaza nimic. Erori status 200 (frontend)."""
    doc = None
    try:
        import fitz
        raw = request.pdf_base64.split(",", 1)[1] if "," in request.pdf_base64 else request.pdf_base64
        if not raw:
            return {"success": False, "error": "pdf_base64 lipseste"}
        doc = fitz.open(stream=base64.b64decode(raw), filetype="pdf")
        if doc.page_count < 1:
            return {"success": False, "error": "PDF fara pagini"}
        page = doc[0]
        W, H = page.rect.width, page.rect.height
        dpi = int(request.dpi or 120)
        scale = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        png_b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
        meta = {"dpi": dpi, "scale": scale, "pdf_width_pt": W, "pdf_height_pt": H,
                "png_width_px": pix.width, "png_height_px": pix.height}
        pix = None
        return {"success": True, "png_base64": png_b64, "png_meta": meta}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


# -------------------------------------------------
#  EXTRACT GEOMETRY (pereti din cleanBasePdf, P1)  —  POST /extract-geometry
# -------------------------------------------------

class ExtractGeometryRequest(ZynModel):
    pdf_base64: str = ""   # cleanBasePdf (planuri[].pdf_base64) -> coordonate IDENTICE cu plan_elements x,y
    rooms: List[dict] = []  # OPTIONAL (V4): camere Vision {name, area_m2, bbox} -> room_geoms (geom_bbox per camera)


@app.post("/extract-geometry")
@_protejat
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

class CropToBuildingRequest(ZynModel):
    pdf_base64: str = ""        # planul brut (parter/etaj) -> se decupeaza la conturul cladirii
    dpi: int = 200             # rezolutie raster pt. imaginea decupata trimisa la Vision
    margin_frac: float = 0.11  # V3b: margine 11% in jurul peretilor -> NU taie terasele deschise


@app.post("/crop-to-building")
@_protejat
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
#  SUPRAFATA CONSTRUITA DETERMINISTA (text vectorial) — POST /extract-surface
# -------------------------------------------------
# FIX BILLING faza 1: suprafata de facturare = CONSTRUITA (amprenta la sol), extrasa DETERMINIST din
# stratul de text vectorial al planului (zero Vision, zero flakiness). Inlocuieste citirea probabilistica
# de catre Claude Vision (temperature 1.0, + crop-to-building care taia bilantul) care dadea NULL ->
# billing pe declarat. Precedent: extract_room_labels (text vectorial ancorat, 16/16 + 7/7).
# Dovedit pe planurile reale: 6cc18f12 (Vision->null) -> 80 (parter/amprenta, NU 240 desfasurata);
# ef83000c -> 245.73 (corp principal C1, NU totalul 448.48).
import re                    # main.py nu-l are la top (restul foloseste import re LOCAL) — necesar pt. compile-urile de mai jos
import unicodedata as _ud

def _surf_deacc(s):
    return "".join(c for c in _ud.normalize("NFKD", s or "") if not _ud.combining(c))

_SURF_LEVELS = ("demisol", "subsol", "parter", "mansarda", "etaj")
_SURF_EXCLUDE = ("utila", "locuib", "teren", "alei", "pavat", "verzi", "vitrat", "vistrat")
# ancora CONSTRUITA (deaccentuat/lower): "Suprafata construita" (+ constr.), "S. construita", sau abreviere
# STRANSA "Sc="/"Ac=" DIRECT inainte de separator. NU prinde "S c a r a 1:50" (scara scrisa rasfirat).
_SURF_ANCHOR = re.compile(
    r"^\s*(?:supraf\w*\s+construit\w*|supraf\w*\s+constr\.?|s\.?\s*construit\w*|(?:sc|ac)\.?\s*[=:]"
    # 2026-07-28: formulari uzuale la ALTE birouri (cele de sus — "Sc=", "Ac=", "S construita" — erau
    # deja acoperite). Ancora ramane STRANSA: fiecare varianta cere cuvantul intreg, nu prefix liber.
    r"|s\.\s*c\.\s*[=:]|aria\s+construit\w*|amprenta\s+la\s+sol|supraf\w*\s+la\s+sol)")
_SURF_NUM = re.compile(r"[=:]\s*([\d]+(?:[.,]\d+)?)\s*(?:mp|m2|m²|mc)?", re.I)

# Ariile PER CAMERA ("A: 13.48 m²" — Jurjea ; "S=4.72 m2" — alte birouri). Ancore EXPLICITE pe
# litera + separator: un regex generic ("orice numar urmat de m2") ar inghiti si valorile din
# bilant si ar DUBLA suma (masurat: 2429 mp in loc de 208 pe un plan real). "Sc=" / "Ac=" NU se
# potrivesc aici (dupa S/A urmeaza o litera, nu separatorul) -> bilantul nu contamineaza suma.
# "SU=" (suprafata utila) adaugat dupa masurarea ancorelor REALE pe 9 planuri distincte: A (58
# aparitii), S (42), SU (4). Restul gasite — AC / ACD / S.C / SOL / TRS — sunt ancore de BILANT si
# raman EXCLUSE intentionat; adaugarea lor ar dubla suma. Ancorele stau ENUMERATE (su|a|s), nu
# generalizate: "su" INAINTE de [as], altfel "s" ar consuma litera si "u" ar rupe potrivirea.
_ROOM_AREA_RX = re.compile(r"^\s*(?:su|[as])\s*[:=]\s*([0-9]{1,4}(?:[.,][0-9]{1,2})?)\s*(?:m2|mp|m²)\b")
# Coeficient CONSERVATOR pereti: construita = Σ utila x k. Masurat pe plan real cu bilant:
# 245.73 / 208.04 = 1.181. Folosim 1.15 -> ramanem SUB realitate (nu putem supra-factura).
_ROOM_SUM_COEF = 1.15

def extract_surface(pdf_bytes):
    """Suprafata CONSTRUITA (amprenta la sol) DETERMINIST din textul vectorial. Ancora obligatorie
    "construita"; SARE peste "desfasurata" (suma nivelurilor -> plasa multi-etaj) si "TOTALA" (multi-corp).
    Prioritate: parter (amprenta) -> primul corp plain (principal C1) -> nivel maxim.
    Return {construita_mp, desfasurata_mp, levels, source, note, flag}; source=None la raster/corupt/gol
    (-> apelantul cade pe fallback Vision)."""
    import fitz
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return {"construita_mp": None, "desfasurata_mp": None, "levels": [], "source": None, "note": "pdf invalid", "flag": None}
    try:
        lines = []
        for page in doc:
            for b in page.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    raw = "".join(s["text"] for s in l.get("spans", [])).strip()
                    if raw:
                        lines.append((l["bbox"][1], _surf_deacc(raw).lower()))
    except Exception as e:
        return {"construita_mp": None, "desfasurata_mp": None, "levels": [], "source": None, "note": f"citire esuata: {e}", "flag": None}
    finally:
        try:
            doc.close()
        except Exception:
            pass

    constr = []       # (y, val, level|None, is_plain)
    desf_vals = []    # (y, val) — desfasurata pe corp (non-total), doar referinta/coerenta
    levels = set()
    room_areas = []   # ariile PER CAMERA (prag minim cand lipseste bilantul)
    for y, n in lines:
        mroom = _ROOM_AREA_RX.match(n)
        if mroom:
            try:
                rv = float(mroom.group(1).replace(",", "."))
                if 0.5 <= rv <= 2000:              # plaja sanatoasa pt. o incapere (filtreaza cotele)
                    room_areas.append(rv)
            except ValueError:
                pass
        if not _SURF_ANCHOR.match(n):
            continue
        mval = _SURF_NUM.search(n)
        if not mval:
            continue
        try:
            val = float(mval.group(1).replace(",", "."))
        except ValueError:
            continue
        if val <= 0:
            continue
        head = re.split(r"[=:]", n, 1)[0]          # calificatorul (inainte de separator)
        is_desf = ("desfasur" in head) or bool(re.search(r"\bdesf\.?\b", head)) or ("scd" in head)
        is_total = "total" in head
        if is_desf:
            if not is_total:
                desf_vals.append((y, val))
            continue                                # NU o luam ca CONSTRUITA (plasa multi-etaj)
        if is_total:
            continue                                # multi-corp: nu facturam TOTALUL
        if any(x in head for x in _SURF_EXCLUDE):
            continue                                # utila/teren/alei/etc.
        lvl = next((L for L in _SURF_LEVELS if L in head), None)
        if lvl:
            levels.add(lvl)
        constr.append((y, val, lvl, lvl is None))

    construita = None
    note = ""
    parter = sorted([(y, v) for (y, v, lvl, pl) in constr if lvl == "parter"])
    plain = sorted([(y, v) for (y, v, lvl, pl) in constr if pl])
    per_level = [v for (y, v, lvl, pl) in constr if lvl]
    if parter:
        construita = parter[0][1]; note = "construita parter (amprenta la sol)"
    elif plain:
        construita = plain[0][1]; note = "construita corp principal (prima aparitie, top)"
    elif per_level:
        construita = max(per_level); note = "construita nivel maxim (fara parter explicit)"
    elif constr:
        construita = sorted(constr)[0][1]; note = "construita (prima gasita)"

    desf_main = sorted(desf_vals)[0][1] if desf_vals else None
    flag = None
    if construita is not None and desf_main is not None and len(levels) > 1 and abs(construita - desf_main) < 0.5:
        flag = "construita==desfasurata la multi-nivel (verifica: posibil desfasurata luata gresit)"

    # PRAG MINIM din ariile camerelor (2026-07-28): construita >= Σ utila MEREU (peretii doar adauga),
    # deci Σ x 1.15 e o limita inferioara FIZICA, nu o estimare. Rol dublu:
    #  (a) planurile FARA bilant (primul client din afara conventiei Jurjea) nu mai cad pe 422;
    #  (b) inchide exploatul "declar 10 mp pentru o casa de 160" (billing-ul ia greatest).
    # Bilantul are PRIORITATE: cand exista, `construita_mp` ramane EXACT valoarea lui (non-regresie).
    rooms_sum = round(sum(room_areas), 2) if room_areas else None
    construita_min = round(rooms_sum * _ROOM_SUM_COEF, 2) if rooms_sum else None
    source = "text_vectorial" if construita is not None else None
    if construita is None and construita_min:
        construita = construita_min
        source = "suma_camere"
        note = "prag din Σ arii camere (%d camere x %.2f = %.2f mp); planul nu are bilant" % (
            len(room_areas), _ROOM_SUM_COEF, construita_min)
    return {"construita_mp": construita, "desfasurata_mp": desf_main,
            "levels": sorted(levels), "source": source,
            "note": note, "flag": flag,
            "rooms_sum_mp": rooms_sum, "rooms_count": len(room_areas),
            "construita_min_mp": construita_min}


def _extract_surface_b64(b64):
    """base64 (cu/fara prefix data-uri) -> extract_surface. Gol/invalid -> source None."""
    raw = b64 or ""
    if "," in raw:
        raw = raw.split(",", 1)[1]
    if not raw:
        return {"construita_mp": None, "desfasurata_mp": None, "levels": [], "source": None, "note": "gol", "flag": None}
    try:
        pdf_bytes = base64.b64decode(raw)
    except Exception:
        return {"construita_mp": None, "desfasurata_mp": None, "levels": [], "source": None, "note": "base64 invalid", "flag": None}
    return extract_surface(pdf_bytes)


def extract_surface_from_plans(plan_floors_base64=None, plan_base64=""):
    """Combina mai multe planuri (multi-etaj): bilantul e pe PARTER si e autoritar.

    ALEGEREA PLANULUI SE FACE PE ETICHETA NIVELULUI, nu pe pozitie. Pana aici se lua PRIMUL plan
    care da o valoare, pe presupunerea „parterul = primul". Pe un bloc cu subsol, primul plan e
    SUBSOLUL — o parcare cu putine etichete de camera, din care una e hala de ~1000 mp. Masurat pe
    proiectul real al lui Dan: aceleasi cinci planuri, doar alta ordine, dau 1153,14 mp (subsol
    primul) vs 696,69 mp (parter primul). 456 mp diferenta pe calea care decide FACTURA.
    E a treia aparitie a aceleiasi presupuneri pozitionale, dupa `pick_plan_entry` si `route.ts`.

    CUM SE AFLA ETICHETA: apelantul o poate trimite pe fiecare intrare (`nivel` / `floor` / `type`).
    Cand N-O TRIMITE NIMENI, se pastreaza ordinea primita — si asta nu-i lene, ci singurul
    comportament corect: fara etichete nu exista alta informatie decat pozitia, iar contractul de azi
    al interfetei chiar garanteaza slotul 0 = parter. Asa cele 10 proiecte cu `plan_generic` din baza
    raman byte-identice, iar blocul primeste alegerea determinista de indata ce trimite etichete.
    """
    import floors as _fl
    brute = []
    for p in (plan_floors_base64 or []):
        if isinstance(p, str):
            brute.append((p, None))
        elif isinstance(p, dict):
            b = p.get("base64") or p.get("plan_base64") or p.get("pdf_base64") or ""
            # `plan_type` NU e eticheta de nivel — in payload-ul de azi e tipul MIME al fisierului.
            et = p.get("nivel") or p.get("floor") or p.get("type") or p.get("eticheta")
            brute.append((b, str(et) if et else None))
    if plan_base64:
        brute.append((plan_base64, None))

    if any(et for _b, et in brute):
        # Ordonare pe AXA nivelurilor (P0): parterul primul, apoi in sus; subsolul/demisolul dupa,
        # fiindca bilantul nu-i al lor. Fara eticheta -> la coada, in ordinea primita.
        def cheie(i_p):
            i, (_b, et) = i_p
            if not et:
                return (2, i)
            idx = _fl.floor_index(_fl.floor_canonic(et))
            return (0, idx, i) if idx >= 0 else (1, -idx, i)
        brute = [q for _i, q in sorted(enumerate(brute), key=cheie)]

    plans = [b for b, _et in brute]
    for b64 in plans:
        r = _extract_surface_b64(b64)
        if r.get("construita_mp") is not None:
            return r
    return {"construita_mp": None, "desfasurata_mp": None, "levels": [], "source": None,
            "note": ("niciun plan cu suprafata in text" if plans else "niciun plan"), "flag": None}


class ExtractSurfaceRequest(ZynModel):
    plan_base64: str = ""
    plan_floors_base64: list = []   # multi-etaj: list de base64 SAU de {base64}


@app.post("/extract-surface")
@_protejat
def extract_surface_endpoint(request: ExtractSurfaceRequest):
    """Suprafata construita DETERMINISTA din planuri (base64) — pt. billing server-side (route.ts o
    re-extrage la generare, fara sa se increada in client). source='text_vectorial' daca s-a gasit;
    None -> apelantul cade pe Vision. Zero Anthropic, <1s."""
    try:
        return extract_surface_from_plans(request.plan_floors_base64, request.plan_base64)
    except Exception as e:
        logger.error("[extract-surface] eroare -> source None: %r", e)
        return {"construita_mp": None, "desfasurata_mp": None, "levels": [], "source": None, "note": f"eroare: {e}", "flag": None}


# -------------------------------------------------
#  POARTA DE VALIDARE PLAN  —  POST /validate-plan
# -------------------------------------------------

class ValidatePlanRequest(ZynModel):
    pdf_base64: str = ""


# Sub atatea segmente de perete, plansa nu poarta informatie de pereti utilizabila.
#
# MASURAT pe cele 11 planse distincte din baza (27 de perechi plan-proiect):
#     0, 0, 0 · 120, 151, 217, 229, 235, 559, 575, 779
# Intre 0 si 120 nu exista nimic — cel mai lat gol din distributie. Iar cele trei planse cu ZERO
# pereti sunt exact cele in care NICIO camera nu primeste contur (0% din camere), pe cand toate
# celelalte dau cel putin 27%. Deci pragul nu desparte „mai bine" de „mai rau", ci „exista
# informatie de pereti" de „nu exista deloc". 20 e numarul pe care poarta il folosea deja pentru
# cealalta conditie; se pastreaza unul singur, ca sa nu existe doua praguri care spun acelasi lucru.
PRAG_PERETI = 20


@app.post("/validate-plan")
@_protejat
def validate_plan_endpoint(request: ValidatePlanRequest):
    """POARTA de validare DETERMINISTA (fara AI, <1s) — ruleaza INAINTE de Vision/credite.
    Discriminanti dovediti empiric (schema reala: 0 pereti + 0 etichete arie; planuri reale:
    sute de pereti + etichete = exact nr. camerelor; raster: 0 text):
      - raster (words==0)                  -> rejected (blocare HARD in frontend)
      - 0 etichete arie SI < 20 pereti     -> warning „not_a_plan" (schema sau alt document)
      - < 20 pereti, DAR are etichete      -> warning „fara_pereti" (e plan, dar exportat aplatizat)
      - altfel                             -> ok
    Cele doua avertismente sunt despre lucruri diferite si nu se suprapun: primul spune „poate nu-i
    un plan", al doilea „e un plan, dar fara informatie de pereti". Inainte, al doilea caz trecea
    `ok` daca plansa avea etichete de arie — masurat, o plansa din unsprezece — si userul platea
    fara sa stie ca prizele vor fi aproximative.
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
        # FIX BILLING faza 1: suprafata CONSTRUITA determinista din text vectorial (planul e deja deschis).
        # Modalul o afiseaza; /api/generate o RE-extrage server-side (nu se increde in client) -> billing.
        surface = extract_surface(pdf_bytes)
        if n_area == 0 and n_walls < PRAG_PERETI:
            return {"status": "warning", "reason": "not_a_plan", "detected": detected, "surface": surface,
                    "message": "Fișierul nu pare un plan de arhitectură (nicio cameră cu suprafață, "
                               "aproape niciun perete detectat). Poate fi o schemă sau alt document. "
                               "Dacă totuși este un plan, a fost exportat fără layere: prizele și "
                               "traseele vor fi puse pe conturul aproximativ al camerei, nu pe pereții "
                               "reali."}
        # Plansa ESTE un plan (are camere cu suprafata scrisa), dar nu poarta pereti. Se intampla la
        # exportul aplatizat, in care toate liniile ajung pe un singur layer fara nume: liniile sunt
        # in fisier, dar nu se pot deosebi de mobilier si de cote, deci nu se colecteaza.
        # MASURAT: pe planse fara pereti, ZERO camere primesc contur — prizele ajung pe laturile
        # dreptunghiului aproximativ, iar traseele merg in linie dreapta prin camere. Avertismentul
        # sta AICI fiindca `/validate-plan` e ultima poarta dinaintea consumului: dupa ea urmeaza
        # Vision (Anthropic), lock-ul si debitarea. Frontendul il arata deja, cu „Continua oricum?".
        if n_walls < PRAG_PERETI:
            camere = ("%d camere cu suprafață scrisă" % n_area) if n_area else "camere"
            return {"status": "warning", "reason": "fara_pereti", "detected": detected, "surface": surface,
                    "message": "Planul are %s, dar nu am găsit pereți în el (%d detectați). "
                               "Prizele și traseele se vor pune pe conturul aproximativ al camerei, "
                               "nu pe pereții reali. Planul pare exportat aplatizat, fără layere — "
                               "pentru poziții exacte, cereți arhitectului exportul PDF cu layere."
                               % (camere, n_walls)}
        return {"status": "ok", "detected": detected, "surface": surface}
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
#  SCHEMA DE DISTRIBUTIE  —  POST /schema-distributie-b64
#  Arborele tuturor tablourilor, cu Pi/Pa/Ia/protectie/cablu pe fiecare nod. Datele vin din
#  `panels.panel_graph` — NU se recalculeaza nimic aici.
# -------------------------------------------------

class SchemaDistributieRequest(ZynModel):
    circuits: List[dict] = []
    cartus_firma: dict = {}
    cartus_proiect: dict = {}
    plansa_nr: str = ""


@app.post("/schema-distributie-b64")
def schema_distributie_b64(request: SchemaDistributieRequest):
    try:
        from schema_distributie import build_schema_distributie
        pdf = build_schema_distributie(request.circuits or [],
                                       cartus_firma=request.cartus_firma or {},
                                       cartus_proiect=request.cartus_proiect or {},
                                       plansa_nr=request.plansa_nr or None)
        if not pdf:
            # Gate pe PREZENTA: un singur tablou nu e o schema de distributie. Nu-i eroare.
            return {"success": True, "pdf_base64": None, "motiv": "fara arbore de tablouri"}
        return {"success": True, "pdf_base64": base64.b64encode(pdf).decode("utf-8"),
                "filename": "schema_distributie.pdf", "size_bytes": len(pdf)}
    except Exception as e:
        logger.error("[schema-distributie] %r", e)
        return {"success": False, "error": str(e), "pdf_base64": None}


# -------------------------------------------------
#  PLANSELE DE DETALIU  —  POST /detaliu-b64
#  Doua detalii TIPIZATE, desenate vectorial la noi (vezi `detalii.py` pentru de ce nu se
#  incorporeaza PDF-ul de referinta). Sectiunea benzii prizei de pamant se cere de la
#  `bloc.sectiune_banda`, aceeasi sursa ca BOM-ul — apelantul nu trimite nimic pentru ea.
#
#  `plan_elements` a existat aici cat timp sectiunea depindea de tipul proiectului. A fost scos
#  odata cu diferentierea: un camp declarat pe care nu-l citeste nimeni e exact ce va refuza pasul 3
#  (`extra="forbid"`) fara sa aduca nimic acum. Niciun apelant nu-l trimitea inca.
# -------------------------------------------------

class DetaliuRequest(ZynModel):
    tip: str = ""
    cartus_firma: dict = {}
    cartus_proiect: dict = {}
    plansa_nr: str = ""


@app.post("/detaliu-b64")
def detaliu_b64(request: DetaliuRequest):
    try:
        from detalii import build_detaliu
        pdf = build_detaliu(request.tip or "", cartus_firma=request.cartus_firma or {},
                            cartus_proiect=request.cartus_proiect or {},
                            plansa_nr=request.plansa_nr or None)
        if not pdf:
            return {"success": False, "error": "tip de detaliu necunoscut: %r" % request.tip,
                    "pdf_base64": None}
        return {"success": True, "pdf_base64": base64.b64encode(pdf).decode("utf-8"),
                "filename": "%s.pdf" % (request.tip or "detaliu"), "size_bytes": len(pdf)}
    except Exception as e:
        logger.error("[detaliu] %r", e)
        return {"success": False, "error": str(e), "pdf_base64": None}


# -------------------------------------------------
#  CAMPURILE NECUNOSCUTE  —  GET /campuri-necunoscute  (PASUL 2)
#  Dovada ca se poate trece la pasul 3 (`extra="forbid"`). Se citeste de aici, nu din logurile
#  Render: acolo un avertisment se pierde intre mii de linii, si tocmai asta a lasat cele trei
#  incidente sa treaca neobservate.
#
#  `curat: true` cere DOUA lucruri deodata:
#    campuri_necunoscute gol  — niciun apelant nu trimite ceva ce modelul arunca;
#    modele_neatinse gol      — fiecare model a fost CHEMAT macar o data de trafic real.
#  Al doilea e cel usor de uitat: un model netestat da si el lista goala, dar nu inseamna „curat",
#  inseamna „nu stiu". Numaratoarea `atingeri` face diferenta vizibila.
#
#  Se inregistreaza AICI, dupa ce toate rutele sunt montate: harta model -> cale se citeste din
#  `app.routes`, nu dintr-o lista scrisa de mana care ar ramane in urma si ar minti in log.
# -------------------------------------------------

_N_RUTE_INREGISTRATE = strict_models.inregistreaza_rute(app)
logger.info("[campuri] harta model -> ruta: %d modele inregistrate (politica extra=%s)",
            _N_RUTE_INREGISTRATE, strict_models.POLITICA_EXTRA)


@app.get("/campuri-necunoscute")
def campuri_necunoscute():
    return strict_models.raport()


@app.post("/campuri-necunoscute/reset")
def campuri_necunoscute_reset():
    """Reporneste fereastra de masurare. De chemat dupa ce s-a curatat un apelant — altfel raportul
    poarta la nesfarsit un camp care nu se mai trimite si `curat` nu devine verde din motive moarte.
    Nu atinge nimic din generare: sterge doar contoare din memoria instantei."""
    return {"success": True, "sterse": strict_models.reseteaza(), "raport": strict_models.raport()}


# -------------------------------------------------
#  SERVIRE FRONTEND STATIC
# -------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
