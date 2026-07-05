# enrich_circuits.py — FAZA 1 (IZOLAT, neconectat la finalize/n8n/frontend).
# Imbogateste circuitele derivate din PLAN (plan_elements) la formatul cerut de documente
# (result_data.circuits: ~15 campuri). Gruparea vine din draw_elements.compute_circuits (plan);
# aici adaugam power_w/breaker/cablu/faza/panel/... dupa cele 8 reguli validate de inginer (Dan).
#
# Sursa = PLANUL. Puterile: iluminat=suma becuri (plan are power_w); prize=2kW normativ (plan
# n-are power_w pe prize); receptoare=din formular extra_equipment (plan are doar label).
import math
from draw_elements import compute_circuits, _BULB_DEFAULT_W

_RECEPTOR_TYPES = {"alimentare_receptor"}          # receptor_internet = date (skip in faza 1)

# ── Regula 3: scara breaker + Ia ─────────────────────────────────────────────
_BREAKER_LADDER = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200]

def _std_breaker(amps):
    for b in _BREAKER_LADDER:
        if b >= amps:
            return b
    return 200

def breaker_and_ia(power_w, tri=False, minimum=0):
    """Ia = P/230 (mono) sau P/636.4 (tri = sqrt3*400*0.92); breaker = prima treapta >= ceil(Ia*1.25).
    minimum = pragul minim pe tip (prize 16A, iluminat 10A)."""
    u = 636.4 if tri else 230.0
    ia = (power_w or 0) / u
    b = max(_std_breaker(math.ceil(ia * 1.25)), minimum or 0)
    return b, round(ia, 1)

# ── Regula 4: cablu ──────────────────────────────────────────────────────────
def _dedicate_section(breaker_a):
    """Sectiune (mm²) care SUPORTA breaker_a — cablul dedicatelor SCALEAZA cu siguranta (nu fix pe tip).
    Ladder normativ (ca feed-urile main): <=16->2.5, 20->4, 25/32->6, 40->10, 50/63->16, >63->25."""
    if breaker_a >= 63: return 25.0
    if breaker_a >= 50: return 16.0
    if breaker_a >= 40: return 10.0
    if breaker_a >= 25: return 6.0
    if breaker_a >= 20: return 4.0
    return 2.5

def cable_type(kind, breaker_a=0, is_exterior=False, tri=False):
    """iluminat->1.5 FIX; prize->2.5 FIX (+IP44 exterior); dedicat->sectiune SCALEAZA cu breaker
    (siguranta). '3x'=mono (F+N+PE), '5x'=trifazat (3F+N+PE)."""
    n = "5x" if tri else "3x"
    if kind == "iluminat":
        sec = 1.5
    elif kind == "priza":
        sec = 2.5
    else:  # dedicat -> sectiune din breaker (siguranta)
        sec = _dedicate_section(breaker_a)
    txt = "CYY-F %s%s" % (n, ("%.1f" % sec).rstrip("0").rstrip("."))
    if kind == "priza" and is_exterior:
        txt += " IP44"
    return txt, sec

def pozare_for(section):
    if section <= 1.5: return "IPEY 16mm"
    if section <= 2.5: return "IPEY 18mm"
    if section <= 6.0: return "IPEY 25mm"
    return "IPEY 32mm"

# ── Regula 8: zone cu RCCB 10mA obligatoriu (I7-2011): BAI + TERASE/BALCOANE ──
_BATH_KW = ("baie", "bath", "wc", "g.s", "grup sanitar", "gs")
_TERRACE_KW = ("terasa", "terasă", "balcon", "loggia", "logie")
def rccb_zone(room):
    """Categoria zonei cu RCCB 10mA (sau None). Bai -> 'baie'; terase/balcoane -> 'terasa'."""
    r = (room or "").strip().lower()
    if any(k in r for k in _BATH_KW): return "baie"
    if any(k in r for k in _TERRACE_KW): return "terasa"
    return None

# ── Regula 2: putere receptor din formular (join pe label) ───────────────────
# Puteri default (W) — oglinda EXTRA_EQUIPMENT_DEFAULTS (constants.ts); fallback daca lipseste din formular.
_RECEPTOR_DEFAULT_W = {"boiler": 2000, "cuptor_electric": 2000, "ac": 2500, "hrv": 200,
                       "ev_charger": 7400, "internet": 0, "solar": 5000}
# label plan (poate fi display "Cuptor electric" sau tip "boiler") -> tip formular
_RECEPTOR_LABEL_MAP = [("boiler", "boiler"), ("cuptor", "cuptor_electric"), ("aer", "ac"),
                       ("condi", "ac"), (" ac", "ac"), ("hrv", "hrv"), ("recuper", "hrv"),
                       ("incarcare", "ev_charger"), ("statie", "ev_charger"), ("masina", "ev_charger"),
                       ("ev_charger", "ev_charger"), ("internet", "internet"), ("retea", "internet")]

def receptor_type_of(label):
    l = " " + (label or "").strip().lower()
    for kw, t in _RECEPTOR_LABEL_MAP:
        if kw in l:
            return t
    return None

def receptor_power(label, form):
    """(power_w, tip, faza, sursa). Formular extra_equipment[tip] -> altfel DEFAULT presetat din UI
    (puterile sunt mereu presetate). Nu exista 'flag lipsa': fara valoare explicita -> default UI."""
    t = receptor_type_of(label)
    for eq in (form or {}).get("extra_equipment") or []:
        if (eq.get("type") or "") == t:
            kw = eq.get("power_kw")
            ph = (eq.get("phase") or "mono")
            if kw not in (None, ""):
                return int(round(float(kw) * 1000)), t, ph, "formular"
    if t in _RECEPTOR_DEFAULT_W:
        return _RECEPTOR_DEFAULT_W[t], t, "mono", "default UI"
    return 0, t, "mono", "tip necunoscut"     # label nemapabil (rar; receptoarele vin din butoane UI)

# ── Regula 6: panel din floor ────────────────────────────────────────────────
def _floor_panel(floor):
    f = str(floor if floor is not None else "parter").strip().lower()
    if "mansard" in f or f == "2": return "TES2", 2
    if "etaj" in f or f == "1":    return "TES1", 1
    return "TEG", 0

def _bulb_w(el):
    pw = el.get("power_w")
    try:
        return int(pw) if pw not in (None, "") else _BULB_DEFAULT_W
    except (TypeError, ValueError):
        return _BULB_DEFAULT_W

_ROOM_TYPE = None  # room_type pe plan = neutru (Vision-only); pastram nume brut

def _enrich_group(c, els, panel, floor_idx):
    """Circuit iluminat/priza din compute_circuits -> ~15 campuri (fara fasa, atribuita ulterior)."""
    kind = c["kind"]                                   # iluminat | priza
    idxs = c.get("indices") or []
    if kind == "iluminat":
        power_w = sum(_bulb_w(els[i]) for i in idxs) or _BULB_DEFAULT_W
        ctype, minimum, pi_norm, reason = "iluminat", 10, False, None
    else:                                              # priza -> 2kW normativ (Regula 1)
        power_w, ctype, minimum = 2000, "prize", 16
        pi_norm, reason = True, "Pi standardizat 2kW per circuit conform reguli Zynapse"
    breaker_a, ia = breaker_and_ia(power_w, tri=False, minimum=minimum)
    is_ext = any((els[i].get("element_type") or "") == "priza_exterior_ip44" for i in idxs)
    cbl, sec = cable_type(kind, breaker_a, is_ext, tri=False)
    _FLOOR_NAME = {0: "parter", 1: "etaj", 2: "mansarda"}
    if kind == "iluminat":
        room = None                                    # iluminatul e pe etaj, nu pe o camera anume
        zone = None
        outlets = 0
        desc = "Iluminat " + _FLOOR_NAME.get(floor_idx, panel)
    else:
        room = c.get("room") or (els[idxs[0]].get("room") if idxs else None)   # VERBATIM (nume plan neschimbat)
        zone = rccb_zone(room)                         # "baie"/"terasa"/None -> RCCB 10mA la ambele
        outlets = sum(1 for i in idxs if (els[i].get("element_type") or "").startswith("priza"))
        desc = "Prize " + (str(room) if room else _FLOOR_NAME.get(floor_idx, panel))
    rccb = zone is not None
    bt = "MCB-1P-C" + (" + RCCB 10mA" if rccb else "")
    return {
        "id": c["id"], "fasa": None, "room": room, "type": ctype, "floor": floor_idx,
        "panel": panel, "pozare": pozare_for(sec), "outlets": outlets, "power_w": power_w,
        "breaker_a": breaker_a, "room_type": zone, "cable_type": cbl, "description": desc,
        "is_bathroom": bool(rccb), "is_exterior": bool(is_ext), "breaker_type": bt,
        "pi_normalized": pi_norm, "ia_calculated_a": ia, "normalize_reason": reason,
        "name": c["id"],
    }

def _enrich_receptor(el, cid, panel, floor_idx, form):
    """alimentare_receptor -> circuit DEDICAT (compute_circuits nu-l grupeaza). Putere din formular."""
    power_w, tip, ph, src = receptor_power(el.get("label"), form)
    tri = str(ph).lower() in ("tri", "trifazat", "3")
    breaker_a, ia = breaker_and_ia(power_w, tri=tri, minimum=16)
    cbl, sec = cable_type("dedicat", breaker_a, False, tri=tri)
    room = el.get("room")
    bt = ("MCB-3P-C" if tri else "MCB-1P-C")
    return {
        "id": cid, "fasa": None, "room": room, "type": "dedicat", "floor": floor_idx,
        "panel": panel, "pozare": pozare_for(sec), "outlets": 0, "power_w": power_w,
        "breaker_a": breaker_a, "room_type": None, "cable_type": cbl,
        "description": "Alimentare " + (el.get("label") or tip or "receptor"),
        "is_bathroom": False, "is_exterior": False, "breaker_type": bt,
        "pi_normalized": False, "ia_calculated_a": ia,
        "normalize_reason": ("Putere din formular" if src == "formular" else
                             "Putere default UI (%s)" % tip if src == "default UI" else "Tip receptor necunoscut"),
        "name": cid, "_receptor_src": src,
    }

# ── Regula 5: faza round-robin ciclic PER TABLOU ─────────────────────────────
def assign_phases(circuits):
    seq = ["R", "S", "T"]
    counters = {}
    for c in circuits:
        if c.get("fasa"):                             # PRESERVAT (TE-CT/feed) -> pastreaza faza normativa
            continue
        panel = c.get("panel")
        if str(c.get("cable_type") or "").find("5x") >= 0 or str(c.get("breaker_type") or "").find("3P") >= 0:
            c["fasa"] = "RST"                          # trifazat -> nu consuma pas
            continue
        k = counters.get(panel, 0)
        c["fasa"] = seq[k % 3]
        counters[panel] = k + 1

def enrich_circuits(plan_elements, form=None, base_circuits=None):
    """PLAN -> circuite (TEG/TES) in formatul result_data.circuits. TE-CT = PRESERVAT din
    base_circuits (heating-driven, ORTOGONAL de plan; dimensionarea normativa din norme_alimentari
    ramane INTACTA) + feed-ul coloanei (sub_tablou feeds_panel='TE-CT'). Renumerotare flat C1..CN
    (ordine TEG -> TES -> TE-CT). base_circuits lipsa/fara TE-CT (heating 'existing') -> doar TEG/TES."""
    form = form or {}
    plan_elements = plan_elements or []
    by_panel = {}                                      # panel -> (elements, floor_idx)
    for el in plan_elements:
        panel, fidx = _floor_panel(el.get("floor"))
        by_panel.setdefault(panel, ([], fidx))[0].append(el)
    plan_out = []
    for panel in sorted(by_panel.keys()):
        els, fidx = by_panel[panel]
        general = panel                                # gsuf -> id-uri C1 / C1-TES1 / C1-TES2
        cc = compute_circuits(els, tech_room=None, general=general)   # tech_room=None -> TE-CT nu din plan
        for c in cc["circuits"]:
            plan_out.append(_enrich_group(c, els, panel, fidx))
        nextn = cc["n_circuits"] + 1
        gsuf = "" if general == "TEG" else "-%s" % general
        for el in els:
            if (el.get("element_type") or "") in _RECEPTOR_TYPES:
                if receptor_type_of(el.get("label")) == "ev_charger":
                    continue                           # EV = separat (ca fotovoltaicele)
                plan_out.append(_enrich_receptor(el, "C%d%s" % (nextn, gsuf), panel, fidx, form))
                nextn += 1

    # PRESERVARE din base_circuits: circuitele TE-CT (heating) + feed-ul coloanei TEG->TE-CT.
    # NU recalculam (dimensionarea din norme_alimentari e deja normativa); doar copiem + renumerotam.
    tect_circuits, feed_circuits = [], []
    for c in (base_circuits or []):
        if not isinstance(c, dict):
            continue
        if c.get("panel") == "TE-CT":
            tect_circuits.append(dict(c))
        elif c.get("type") == "sub_tablou" and c.get("feeds_panel") == "TE-CT":
            feed_circuits.append(dict(c))              # coloana TEG->TE-CT (sectiunea = cable_type)

    # ordine finala: TEG(plan) + feed(TEG->TE-CT) + TES(plan) + TE-CT(preservat)
    teg = [c for c in plan_out if c.get("panel") == "TEG"]
    tes = [c for c in plan_out if str(c.get("panel") or "").startswith("TES")]
    out = teg + feed_circuits + tes + tect_circuits

    # renumerotare flat C1..CN (id+name); panel/feeds_panel/dimensionarea raman
    for i, c in enumerate(out):
        cid = "C%d" % (i + 1)
        c["id"] = cid
        c["name"] = cid

    assign_phases(out)                                 # doar circuitele PLANULUI (TE-CT/feed pastreaza faza)
    return out
