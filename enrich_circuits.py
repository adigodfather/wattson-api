# enrich_circuits.py — FAZA 1 (IZOLAT, neconectat la finalize/n8n/frontend).
# Imbogateste circuitele derivate din PLAN (plan_elements) la formatul cerut de documente
# (result_data.circuits: ~15 campuri). Gruparea vine din draw_elements.compute_circuits (plan);
# aici adaugam power_w/breaker/cablu/faza/panel/... dupa cele 8 reguli validate de inginer (Dan).
#
# Sursa = PLANUL. Puterile: iluminat=suma becuri (plan are power_w); prize=2kW normativ (plan
# n-are power_w pe prize); receptoare=din formular extra_equipment (plan are doar label).
import math
import re
from draw_elements import compute_circuits, tech_room_from_elements, _BULB_DEFAULT_W, _grouped_heating_kind

_RECEPTOR_TYPES = {"alimentare_receptor"}          # receptor_internet = date (skip in faza 1)

# ── Regula 3: scara breaker + Ia ─────────────────────────────────────────────
_BREAKER_LADDER = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200]

def _std_breaker(amps):
    for b in _BREAKER_LADDER:
        if b >= amps:
            return b
    return 200

def _next_breaker(b):
    """Treapta imediat SUPERIOARA lui b din ladder (pt. SELECTIVITATE feed>circuit). Max -> ultima."""
    for x in _BREAKER_LADDER:
        if x > b:
            return x
    return _BREAKER_LADDER[-1]

def _section_of(cable_type):
    """Sectiunea (mm², = M din NxM) dintr-un cable_type variat ('5x4 mm2 CYYF', 'CYY-F 3x2.5',
    'CYY-F 5x2.5mmp'). 0 daca nu se poate parsa."""
    m = re.search(r"\d+\s*[xX]\s*([\d.]+)", str(cable_type or ""))
    try:
        return float(m.group(1)) if m else 0.0
    except (TypeError, ValueError):
        return 0.0

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
                       "ev_charger": 7400, "internet": 0, "solar": 5000, "distribuitor_zona": 300,
                       # FIX 3: centrala plasata pe plan = 2 kW FIX (pompa/automatizare/aprindere) —
                       # era nemapata -> 0W "tip necunoscut". Centrala ELECTRICA e neatinsa:
                       # puterea ei vine din base/formular (dedup-ul base_covered castiga).
                       "centrala": 2000}
# label plan (poate fi display "Cuptor electric" sau tip "boiler") -> tip formular. Regula 10:
# "distribuitor" (zona/nivel) INAINTE de "aer"/etc. — distribuitorul de zona = receptor dedicat 300W.
_RECEPTOR_LABEL_MAP = [("boiler", "boiler"), ("cuptor", "cuptor_electric"),
                       ("distribuitor", "distribuitor_zona"), ("aer", "ac"),
                       ("condi", "ac"), (" ac", "ac"), ("hrv", "hrv"), ("recuper", "hrv"),
                       ("incarcare", "ev_charger"), ("statie", "ev_charger"), ("masina", "ev_charger"),
                       ("ev_charger", "ev_charger"), ("internet", "internet"), ("retea", "internet"),
                       ("centrala", "centrala")]   # FIX 3: "Centrala pe gaz" -> default 2 kW

def receptor_type_of(label):
    l = " " + (label or "").strip().lower()
    for kw, t in _RECEPTOR_LABEL_MAP:
        if kw in l:
            return t
    return None

_NET_RECEPTOR_W = 150   # alimentare echipament de retea (router/switch/rack) — circuit dedicat (nu date low-voltage)

# TIP NORMALIZAT pt. DEDUP receptor plan <-> circuit formular (ordine SPECIFIC->generic; robust la
# variatii de descriere: 'PDC aer-apa 20kW' -> pdc, NU ac). Substring lowercase. None = nemapabil.
_EQUIP_KEYS = [
    ("boiler", "boiler"), ("cuptor", "cuptor"),
    ("pdc", "pdc"), ("pompa de caldura", "pdc"), ("pompa caldura", "pdc"), ("aer-apa", "pdc"),
    ("sol-apa", "pdc"), ("pompa circulatie", "pompa"), ("pompa recirculare", "pompa"),
    ("automatizare", "bms"), ("bms", "bms"),
    # T3 anti-dublare: "Centrala electrica 12kW" / "Centrala pe gaz" nu mapau pe nicio cheie ->
    # elementul auto-plasat nu se lega prin dedup si _enrich_receptor crea circuit DUPLICAT (0W).
    ("centrala", "centrala"),
    # Regula 10 / CAPCANA 1: distribuitorul de ZONA/NIVEL -> cheie DISTINCTA (nu se contopeste prin
    # dedup cu "Distribuitor principal incalzire" din baza TE-CT). Ordine SPECIFIC->generic.
    ("distribuitor de zona", "distribuitor_zona"), ("distribuitor zona", "distribuitor_zona"),
    ("distribuitor de nivel", "distribuitor_zona"), ("distribuitor nivel", "distribuitor_zona"),
    ("distribuitor", "distribuitor"),
    ("recuperare", "hrv"), ("hrv", "hrv"), ("aer conditionat", "ac"), ("conditionat", "ac"),
    ("internet", "internet"), ("retea", "internet"),
    ("incarcare", "ev"), ("statie incarcare", "ev"), ("masina electrica", "ev"), ("ev_charger", "ev"),
]

def _equip_key(s):
    """Tip normalizat de echipament din label/descriere (pt. dedup plan<->formular). None = nemapabil."""
    t = (s or "").strip().lower().replace("ă", "a").replace("â", "a").replace("î", "i").replace("ș", "s").replace("ț", "t")
    for kw, k in _EQUIP_KEYS:
        if kw in t:
            return k
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
    """Circuit iluminat/priza din compute_circuits -> ~15 campuri (fara fasa, atribuita ulterior).
    NIVEL 1: circuitele cu id '-TECT' (becuri/prize din camera tehnica) -> panel='TE-CT' (nu TEG)."""
    kind = c["kind"]                                   # iluminat | priza
    idxs = c.get("indices") or []
    is_tect = "-TECT" in str(c.get("id") or "")        # NIVEL 1: grup din camera tehnica -> TE-CT
    panel_out = "TE-CT" if is_tect else panel
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
        room = c.get("room") if is_tect else None      # TECT: iluminatul e pe camera tehnica (nume)
        zone = None
        outlets = 0
        desc = ("Iluminat " + str(room)) if (is_tect and room) else ("Iluminat " + _FLOOR_NAME.get(floor_idx, panel))
    else:
        room = c.get("room") or (els[idxs[0]].get("room") if idxs else None)   # VERBATIM (nume plan neschimbat)
        zone = rccb_zone(room)                         # "baie"/"terasa"/None -> RCCB 10mA la ambele
        outlets = sum(1 for i in idxs if (els[i].get("element_type") or "").startswith("priza"))
        desc = "Prize " + (str(room) if room else _FLOOR_NAME.get(floor_idx, panel))
    rccb = zone is not None
    bt = "MCB-1P-C" + (" + RCCB 10mA" if rccb else "")
    return {
        "id": c["id"], "fasa": None, "room": room, "type": ctype, "floor": floor_idx,
        "panel": panel_out, "pozare": pozare_for(sec), "outlets": outlets, "power_w": power_w,
        "breaker_a": breaker_a, "room_type": zone, "cable_type": cbl, "description": desc,
        "is_bathroom": bool(rccb), "is_exterior": bool(is_ext), "breaker_type": bt,
        "pi_normalized": pi_norm, "ia_calculated_a": ia, "normalize_reason": reason,
        "name": c["id"],
    }

def _enrich_receptor(el, cid, panel, floor_idx, form, is_mono=False):
    """alimentare_receptor / receptor_internet -> circuit DEDICAT (compute_circuits nu-l grupeaza).
    Putere din formular/default UI (regula #2). Reteaua (receptor_internet) = 0W (date low-voltage)
    -> circuit minimal (breaker minim 16A), reprezinta alimentarea echipamentului de retea.
    is_mono (bransament MONOFAZAT): forteaza mono — nu exista receptor trifazat pe o singura faza."""
    is_net = (el.get("element_type") or "") == "receptor_internet"
    power_w, tip, ph, src = receptor_power(el.get("label"), form)
    if is_net:                                            # alimentare router/switch/rack = 150W (decizia Dan),
        power_w, tip, src = _NET_RECEPTOR_W, "internet", "default UI"   # NU 0 (era 'date low-voltage')
    tri = str(ph).lower() in ("tri", "trifazat", "3") and not is_mono
    breaker_a, ia = breaker_and_ia(power_w, tri=tri, minimum=16)
    cbl, sec = cable_type("dedicat", breaker_a, False, tri=tri)
    room = el.get("room")
    bt = ("MCB-3P-C" if tri else "MCB-1P-C")
    desc = "Alimentare retea/date" if is_net else ("Alimentare " + (el.get("label") or tip or "receptor"))
    return {
        "id": cid, "fasa": None, "room": room, "type": "dedicat", "floor": floor_idx,
        "panel": panel, "pozare": pozare_for(sec), "outlets": 0, "power_w": power_w,
        "breaker_a": breaker_a, "room_type": None, "cable_type": cbl,
        "description": desc,
        "is_bathroom": False, "is_exterior": False, "breaker_type": bt,
        "pi_normalized": False, "ia_calculated_a": ia,
        "normalize_reason": ("Putere din formular" if src == "formular" else
                             "Putere default UI (%s)" % tip if src == "default UI" else "Tip receptor necunoscut"),
        "name": cid, "_receptor_src": src,
    }

def _enrich_heating_group(c, panel, floor_idx, is_mono=False):
    """REGULA 10: circuit de INCALZIRE ELECTRICA grupat (VCV + radiatoare). SURSA UNICA — gruparea +
    puterea REALA insumata vin din compute_circuits (c['power_w'], c['tri']); enrich NU regrupeaza,
    doar dimensioneaza: breaker MINIM 16A (peste = Ia*1.25), cablu scaleaza cu breaker (regula 4),
    mono '3x' / tri '5x'. Panel = general (TEG/TES), NU TE-CT. Faza: None (assign_phases o pune —
    mono round-robin, tri 'RST')."""
    power_w = int(c.get("power_w") or 0)
    # is_mono: bransament monofazat -> elementele marcate 'tri' se dimensioneaza MONO (regula fizica;
    # binuirea din compute_circuits ramane pe el.phase — 2 elem 'tri' pe mono = 2 circuite mono, corect)
    tri = bool(c.get("tri")) and not is_mono
    breaker_a, ia = breaker_and_ia(power_w, tri=tri, minimum=16)
    cbl, sec = cable_type("dedicat", breaker_a, False, tri=tri)
    _FLOOR_NAME = {0: "parter", 1: "etaj", 2: "mansarda"}
    desc = "Incalzire electrica " + _FLOOR_NAME.get(floor_idx, str(panel))
    return {
        "id": c["id"], "fasa": None, "room": None, "type": "dedicat", "floor": floor_idx,
        "panel": panel, "pozare": pozare_for(sec), "outlets": 0, "power_w": power_w,
        "breaker_a": breaker_a, "room_type": None, "cable_type": cbl, "description": desc,
        "is_bathroom": False, "is_exterior": False, "breaker_type": ("MCB-3P-C" if tri else "MCB-1P-C"),
        "pi_normalized": False, "ia_calculated_a": ia,
        "normalize_reason": "Incalzire electrica grupata (putere reala insumata, plafon 2kW, FFD)",
        "name": c["id"], "_heating_group": True,
    }

# ── Regula 5: faza round-robin ciclic PER TABLOU ─────────────────────────────
def assign_phases(circuits, is_mono=False):
    # BRANSAMENT MONOFAZAT: exista O SINGURA faza reala -> TOATE circuitele "R" (round-robin-ul R/S/T
    # ar documenta faze inexistente — bug vizibil pe proiectele mono din productie). Suprascrie si
    # fazele preservate (RST-ul din base nu are sens fizic pe mono).
    if is_mono:
        for c in circuits:
            c["fasa"] = "R"
        return
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

# ── NIVEL 1: detectie camera tehnica in enrich (fara geometrie) ──────────────
# enrich NU are rooms bbox + W/H -> nu poate reface point-in-bbox (ca _detect_tech_room la desen).
# Dar becurile/prizele din camera tehnica AU deja room setat la desen (assign_circuits) = numele
# camerei tehnice. Detectam pe NUME ('tehnic'), GATED de prezenta unui tablou_te_ct pe plan (ca
# _detect_tech_room care porneste de la tablou_te_ct) -> fara TE-CT panel plasat => NU rutam pe TE-CT
# (protejeaza cazul 'existing' fara incalzire).
_TECH_ROOM_KW = ("tehnic",)   # "spatiu tehnic" / "camera tehnica" / "tehnică" (substring lowercase)

def _detect_tech_room_name(elements):
    """Numele camerei tehnice (sau None) — SURSA UNICA plan<->enrich (Faza 1 TE-CT):
    room-ul PERSISTAT al elementului tablou_te_ct (tech_room_from_elements — scris de
    assign_circuits cu detectia geometrica stricta pe POZITIA tabloului: in bbox / <=60pt
    candidat unic / None). Plan si enrich = ACEEASI camera, prin constructie.
    FALLBACK LEGACY (doar proiecte vechi, cu room-ul tabloului nepersistat): camera al carei
    nume contine 'tehnic' — detectia istorica, pastrata pentru compatibilitate.
    Gate: fara tablou_te_ct pe plan -> None (comportament vechi, tech pe TEG)."""
    els = elements or []
    if not any(((el or {}).get("element_type") or "") == "tablou_te_ct" for el in els):
        return None                                     # fara panou TE-CT pe plan -> fara rutare tech
    r = tech_room_from_elements(els)                    # sursa unica (room persistat pe tablou)
    if r:
        return r
    for el in els:                                      # LEGACY: dupa nume (proiecte neregenerate)
        rr = ((el or {}).get("room") or "").strip()
        if rr and any(k in rr.lower() for k in _TECH_ROOM_KW):
            return rr
    return None


_KS_COLUMN = 0.8   # simultaneitate coloana de sub-tablou (TE-CT + TES, ca n8n) — la re-suma din circuite

def _resize_column_feed(feed, tect_circuits, force_resum=False, force_mono=False):
    """FIX coloana: n8n lasa breaker=16 PLACEHOLDER (nu se re-deriva din putere) -> recalculam
    breaker+cablu din puterea ABSORBITA. Pi_total = feed.power_w (deja = suma × ks); fallback (sau
    force_resum cand planul a MODIFICAT TE-CT): resumam din TE-CT MERGED × ks -> coloana reflecta
    adaugarile din plan. Suprascrie DOAR feed-ul (nu circuitele TE-CT).
    force_mono (bransament MONOFAZAT): guard defensiv — chiar daca breviarul a emis feed trifazat
    (phases=3/5x), coloana se redimensioneaza MONO (Ia=P/230, 3 fire, MCB-1P)."""
    try:
        pw = int(feed.get("power_w"))
    except (TypeError, ValueError):
        pw = 0
    if force_resum or not pw:                           # re-suma din TE-CT MERGED × ks (plan a atins TE-CT)
        pw = int(round(sum((c.get("power_w") or 0) for c in (tect_circuits or [])) * _KS_COLUMN))
        feed["power_w"] = pw
    tri = (str(feed.get("phases")) == "3" or "5x" in str(feed.get("cable_type") or "")) and not force_mono
    if force_mono:
        feed["phases"] = 1
        feed["breaker_type"] = "MCB-1P-C"
        feed["fasa"] = None                             # assign_phases (mono) o pune "R"
    breaker, ia = breaker_and_ia(pw, tri=tri, minimum=16)   # min 16A (coloana principala)
    # SELECTIVITATE + podea normativa (decizia Dan): coloana unui tablou NU poate fi mai mica decat
    # circuitele lui. breaker feed >= o TREAPTA peste max breaker intern; sectiune >= max sectiune
    # interna. Regula generala pt. ORICE feed de sub-tablou (ff42: max intern 20A/5x4 -> feed 25A/5x6).
    max_brk = max([int(c.get("breaker_a") or 0) for c in (tect_circuits or [])] or [0])
    if max_brk:
        breaker = max(breaker, _next_breaker(max_brk))
    sec = _dedicate_section(breaker)                        # scara: 16->2.5, 20->4, 25/32->6, 40->10...
    max_sec = max([_section_of(c.get("cable_type")) for c in (tect_circuits or [])] or [0.0])
    sec = max(sec, max_sec)                                 # >= cel mai gros cablu din tablou
    n = "5x" if tri else "3x"
    feed["breaker_a"] = breaker
    feed["cable_type"] = "CYY-F %s%smmp" % (n, ("%.1f" % sec).rstrip("0").rstrip("."))
    feed["ia_calculated_a"] = ia
    feed["pozare"] = pozare_for(sec)


def _synth_gas_tect(form, is_mono, has_distributor_on_plan=True):
    """FAZA 2 TE-CT / GAZ: breviarul n8n nu emite circuite TE-CT pe gas_boiler. Setul minim (Dan):
    DISTRIBUITOR principal incalzire (FIX 2: DOAR daca e PLASAT pe plan — casele mici fara
    distribuitor nu-l mai primesc "fantoma" in schema; dimensionat ca C21 din breviarul PDC:
    200W/10A/3x1.5, RCCB 30mA) + BOILER ACM (OPTIONAL: doar daca bifat in echipamente — centrala
    pe gaz face si ACM; puterea/faza din formular, default 2kW mono). Panel TE-CT; redirectul
    (nebifat) le muta pe TEG."""
    out = [{
        "id": None, "name": None, "fasa": None, "room": None, "type": "dedicat", "panel": "TE-CT",
        "usage": "Distribuitor principal incalzire", "description": "Distribuitor principal incalzire",
        "power_w": 200, "breaker_a": 10, "cable_type": "3x1.5 mm2 CYYF", "pozare": pozare_for(1.5),
        "breaker_type": "MCB-1P-C", "ia_calculated_a": round(200 / 230.0, 2), "rccb_ma": 30,
        "has_rccb_individual": True, "is_main_distributor": True, "phases": 1, "outlets": 0,
        "notes": "Distribuitor incalzire (pompe/actuatoare) — centrala pe gaz",
    }]
    if not has_distributor_on_plan:
        out = []                       # FIX 2: fara distribuitor plasat -> fara circuit (boilerul ramane pe bifa lui)
    for eq in (form or {}).get("extra_equipment") or []:
        if (eq.get("type") or "") != "boiler":
            continue
        try:
            pw = int(round(float(eq.get("power_kw") or 2.0) * 1000))
        except (TypeError, ValueError):
            pw = 2000
        tri = str(eq.get("phase") or "mono").lower() in ("tri", "trifazat", "3") and not is_mono
        breaker_a, ia = breaker_and_ia(pw, tri=tri, minimum=16)
        cbl, sec = cable_type("dedicat", breaker_a, False, tri=tri)
        out.append({
            "id": None, "name": None, "fasa": None, "room": None, "type": "dedicat", "panel": "TE-CT",
            "usage": "Boiler ACM", "description": "Alimentare boiler", "power_w": pw,
            "breaker_a": breaker_a, "cable_type": cbl, "pozare": pozare_for(sec),
            "breaker_type": ("MCB-3P-C" if tri else "MCB-1P-C"), "ia_calculated_a": ia,
            "rccb_ma": 30, "has_rccb_individual": True, "phases": (3 if tri else 1), "outlets": 0,
        })
        break                                          # un singur boiler
    return out


def enrich_circuits(plan_elements, form=None, base_circuits=None):
    """PLAN -> circuite (TEG/TES) in formatul result_data.circuits. TE-CT = PRESERVAT din
    base_circuits (heating-driven, ORTOGONAL de plan; dimensionarea normativa din norme_alimentari
    ramane INTACTA) + feed-ul coloanei (sub_tablou feeds_panel='TE-CT'). Numerotare PER TABLOU =
    sistemul PLANULUI: TEG C1..CN, etaj C1-TES..CN-TES, TE-CT C1-TECT..CN-TECT (identice cu
    plan_elements.circuit_id). base_circuits lipsa/fara TE-CT (heating 'existing') -> doar TEG/TES."""
    form = form or {}
    plan_elements = plan_elements or []
    # COERENTA MONOFAZATA (regula fizica): bransament mono -> TOT mono (feed-uri, receptoare, grupate,
    # faze). Sursa: form.power_phase — finalize il deriva din power_summary.connection (route.ts:85).
    # UN punct de decizie; absent -> "tri" (conservator, identic cu comportamentul de azi).
    is_mono = str(form.get("power_phase") or "tri").strip().lower() != "tri"

    # FAZA 2 TE-CT: camera tehnica e OPTIONALA — checkbox-ul (form.has_tech_room) decide DOAR destinatia
    # echipamentelor de incalzire: bifat -> TE-CT (ca azi); nebifat -> TEG (alta incapere). Absent -> True
    # (non-regresie totala pe proiectele existente).
    is_tech_room = form.get("has_tech_room", True) is not False

    # PRESERVARE din base_circuits (parsat INTAI): circuitele TE-CT (heating) + feed-ul coloanei.
    # NU recalculam (dimensionarea din norme_alimentari e deja normativa); doar copiem + renumerotam.
    tect_circuits, feed_circuits = [], []
    for c in (base_circuits or []):
        if not isinstance(c, dict):
            continue
        if c.get("panel") == "TE-CT":
            tect_circuits.append(dict(c))
        elif c.get("type") == "sub_tablou" and c.get("feeds_panel") == "TE-CT":
            feed_circuits.append(dict(c))              # coloana TEG->TE-CT (sectiunea = cable_type)

    # SINTEZA GAZ (functionalitate NOUA, ca feed-ul TES — "daca base nu emite, enrich creeaza"):
    # breviarul n8n NU emite TE-CT pe gas_boiler (doar circuit dedicat centrala pe TEG). Setul minim
    # (decizia Dan): DISTRIBUITOR principal (FIX 2: DOAR daca e plasat pe plan) + BOILER ACM
    # (optional, daca bifat in echipamente — gazul face si ACM). Sintetizat pe TE-CT; redirectul
    # de mai jos il muta pe TEG daca nebifat.
    if str(form.get("heating_type") or "") == "gas_boiler" and not tect_circuits:
        # distribuitorul PRINCIPAL plasat pe plan? (cheia "distribuitor"; distribuitor_zona = Regula 10,
        # cheie DISTINCTA -> neatins de gate)
        _has_dist = any((el.get("element_type") or "") == "alimentare_receptor"
                        and _equip_key(el.get("label")) == "distribuitor"
                        for el in (plan_elements or []))
        tect_circuits.extend(_synth_gas_tect(form, is_mono, has_distributor_on_plan=_has_dist))

    # REDIRECT TE-CT -> TEG (nebifat): dedicatele (echipamentele sursei, ORICARE set — mutam circuitele
    # existente, nu re-derivam) -> panel TEG (numerotare/faza/schema/BOM TEG natural); genericele legate
    # de camera ("Iluminat/Priza rezerva camera tehnica") -> DROP (camera nu exista); feed -> DROP (fara
    # coloana orfana). Fizic: PDC afara fara puffer, boiler mascat in debara, pompele acolo.
    redirected_teg = []
    if not is_tech_room:
        for c in tect_circuits:
            if c.get("type") == "dedicat":
                c["panel"] = "TEG"
                redirected_teg.append(c)
        tect_circuits = []                             # genericele raman aici -> dropate
        feed_circuits = []
    # TE-CT e HEATING-DRIVEN: rutam tech-ul planului pe TE-CT DOAR daca baza are deja un context
    # TE-CT (circuite TE-CT sau feed coloana). 'existing' (fara incalzire) -> tech ramane pe TEG (ca inainte).
    has_base_tect = bool(tect_circuits) or bool(feed_circuits)

    # DEDUP receptor plan <-> circuit formular: tipurile de echipament DEJA acoperite de baza
    # (breviar incalzire: boiler/pdc/pompa/bms/distribuitor). Un element de plan cu acelasi tip NU
    # creeaza circuit nou -> circuitul base (dimensionat normativ) primeste POZITIA elementului.
    # + redirectatele pe TEG (nebifat): elementul de plan tot pe circuitul base se leaga (pozitia).
    base_covered = {}
    for c in tect_circuits + redirected_teg:
        if c.get("type") == "dedicat":
            k = _equip_key(c.get("description") or c.get("usage"))
            if k and k not in base_covered:
                base_covered[k] = c

    by_panel = {}                                      # panel -> (elements, floor_idx)
    for el in plan_elements:
        panel, fidx = _floor_panel(el.get("floor"))
        by_panel.setdefault(panel, ([], fidx))[0].append(el)
    plan_out = []
    for panel in sorted(by_panel.keys()):
        els, fidx = by_panel[panel]
        # SUFIX id = conventia PLANULUI: compute_circuits via _detect_general_panel foloseste "TES"
        # (nu "TES1") -> id-uri C1-TES (identice cu plan_elements.circuit_id). panel ramane "TES1"/"TES2"
        # (grupare pe pagini de schema, setat in _enrich_group); DOAR sufixul id-ului se aliniaza.
        general = "TEG" if panel == "TEG" else "TES"   # gsuf -> C1 (TEG) / C1-TES (etaj+)
        tech_room = _detect_tech_room_name(els) if has_base_tect else None   # NIVEL 1: gated tablou_te_ct + base TE-CT
        cc = compute_circuits(els, tech_room=tech_room, general=general)   # tech_room -> becuri/prize tech = -TECT
        for c in cc["circuits"]:
            if c.get("kind") == "incalzire":                               # Regula 10: VCV/radiatoare grupate
                plan_out.append(_enrich_heating_group(c, panel, fidx, is_mono=is_mono))
            else:
                plan_out.append(_enrich_group(c, els, panel, fidx))
        nextn = cc["n_circuits"] + 1
        gsuf = "" if general == "TEG" else "-%s" % general
        tech_l = (tech_room or "").strip().lower()     # NIVEL 2: receptor cu room==camera tehnica -> TE-CT
        for el in els:
            et = (el.get("element_type") or "")
            if et not in ("alimentare_receptor", "receptor_internet"):
                continue
            if _grouped_heating_kind(el.get("label")) is not None:
                continue                               # Regula 10: VCV/radiatoare -> circuit grupat (compute_circuits), NU 1:1
            is_tech = bool(tech_l) and (el.get("room") or "").strip().lower() == tech_l
            if et == "alimentare_receptor" and receptor_type_of(el.get("label")) == "ev_charger":
                continue                               # EV = separat (ca fotovoltaicele)
            # DEDUP plan<->formular pe TIP NORMALIZAT: receptorul de plan care se potriveste cu un
            # echipament din breviar (base) NU creeaza circuit nou -> circuitul base primeste POZITIA
            # elementului (pt. Faza B: desenul cablului). Nu pierde receptoare multiple legitime
            # (AC/cuptor NU-s in base -> raman circuite separate per element).
            _ek = _equip_key(el.get("label") if et == "alimentare_receptor" else "internet")
            if _ek and _ek in base_covered:
                _bc = base_covered[_ek]
                _bc["_plan_x"], _bc["_plan_y"], _bc["_plan_room"] = el.get("x"), el.get("y"), el.get("room")
                continue                               # UN singur circuit (base), elementul da pozitia
            # receptor_internet: MEREU circuit dedicat (150W, alimentare router/rack) — oriunde plasat
            # (skip-ul vechi 'net in afara camerei tehnice -> ignorat' e ELIMINAT).
            rec_panel = "TE-CT" if is_tech else panel  # NIVEL 2: receptor din camera tehnica -> TE-CT
            rec_id = ("C%d-TECT" % nextn) if is_tech else ("C%d%s" % (nextn, gsuf))
            plan_out.append(_enrich_receptor(el, rec_id, rec_panel, fidx, form, is_mono=is_mono))
            nextn += 1

    # NIVEL 1: becurile/prizele din camera tehnica (plan) -> panel TE-CT (setat in _enrich_group)
    plan_tect = [c for c in plan_out if c.get("panel") == "TE-CT"]
    plan_has_ilum  = any(c.get("type") == "iluminat" for c in plan_tect)
    plan_has_priza = any(c.get("type") in ("prize", "priza") for c in plan_tect)

    # REGULA DE INLOCUIRE (evita DUBLAREA): din baza TE-CT preservata PASTRAM echipamentele de
    # incalzire (type='dedicat': PDC/pompa/boiler/automatizare/distribuitor) SI generice NEACOPERITE
    # de plan; INLOCUIM genericele (type iluminat/prize = "Iluminat/Priza rezerva camera tehnica")
    # DOAR daca planul a produs iluminat/prize tech REALE (altfel le pastram = non-regresie 'ca inainte').
    kept_base_tect = []
    for c in tect_circuits:
        t = c.get("type")
        if t == "iluminat" and plan_has_ilum:
            continue                                   # inlocuit de becurile REALE din plan
        if t in ("prize", "priza") and plan_has_priza:
            continue                                   # inlocuit de prizele REALE din plan
        kept_base_tect.append(c)                       # echipamente incalzire (dedicat) + generice fara inlocuitor
    # ordine TE-CT = becuri/prize PLAN INTAI (C1-TECT.. = identic cu plan_elements.circuit_id, si
    # ordinea I7: iluminat/prize inainte de 'dedicat') + incalzirea(baza) numerotata DUPA.
    merged_tect = plan_tect + kept_base_tect

    # FIX coloana: recalculeaza breaker+cablu din puterea absorbita (n8n lasa 16A placeholder).
    # force_resum cand planul a atins TE-CT -> power_w = suma MERGED × ks (coloana creste corect,
    # fara dubla-numarare: genericele inlocuite NU mai sunt in merged_tect).
    plan_touched_tect = bool(plan_tect)
    for f in feed_circuits:
        _resize_column_feed(f, merged_tect, force_resum=plan_touched_tect, force_mono=is_mono)

    # ordine finala: TEG(plan, EXCL. tech) + feed(TEG->TE-CT) + TES(plan) + TE-CT(incalzire + tech plan)
    teg = [c for c in plan_out if c.get("panel") == "TEG"]
    tes = [c for c in plan_out if str(c.get("panel") or "").startswith("TES")]

    # FEED TES (coloana TEG->TES) — mecanism GENERAL pt. ORICE tablou secundar (TES1, TES2/mansarda...):
    # breviarul n8n NU emite feed TES, iar filtrul de preservare pastreaza doar TE-CT -> il cream AICI,
    # dimensionat cu ACEEASI regula ca TE-CT (_resize_column_feed: re-suma x ks 0.8 + SELECTIVITATE
    # breaker = treapta peste max intern + sectiune >= max interna, trifazat 5 fire). Coloana desenata
    # (cross-floor) + BOM (_tes_feed_ct/_extra_meters) + legenda citesc feed-ul REAL din circuits ->
    # fallback-ul 5x6 nu se mai activeaza. 9926: TES1 (240W ilum + 6x2000W prize) -> 20A / CYY-F 5x4.
    _TES_FLOOR_DESC = {"TES1": "etaj", "TES2": "mansarda"}
    for _pn in sorted({str(c.get("panel") or "") for c in tes}):
        if any(str(f.get("feeds_panel") or "") == _pn for f in feed_circuits):
            continue                                   # breviarul l-a emis deja (viitor) -> preservat, nu dublam
        _tes_grp = [c for c in tes if str(c.get("panel") or "") == _pn]
        # faza coloanei = faza BRANSAMENTULUI (pe mono nu exista coloana trifazata): phases/breaker/fasa
        # conditionate -> _resize_column_feed dimensioneaza corect (mono: Ia=P/230, 3 fire).
        _fd = {"id": None, "name": None, "fasa": (None if is_mono else "RST"), "type": "sub_tablou",
               "panel": "TEG", "feeds_panel": _pn, "phases": (1 if is_mono else 3),
               "breaker_type": ("MCB-1P-C" if is_mono else "MCB-3P-C"), "is_sub_tablou": True,
               "description": "Alimentare %s (%s)" % (_pn, _TES_FLOOR_DESC.get(_pn, "nivel superior")),
               "usage": "Alimentare %s (%s)" % (_pn, _TES_FLOOR_DESC.get(_pn, "nivel superior")),
               # culorile simbolului de sub-tablou in schema monofilara (alb/albastru = simbolul TES din editor)
               "sub_tablou_color1": "#F0F0F0", "sub_tablou_color2": "#1565C0"}
        _resize_column_feed(_fd, _tes_grp, force_resum=True)
        _fd["cable"] = _fd.get("cable_type")           # alias-ul legacy `cable` (schema il afiseaza la feed-uri)
        feed_circuits.append(_fd)

    # FEED TE-CT SINTETIZAT (gaz bifat): base-ul de gaz nu are feed (breviarul nu emite TE-CT pe gaz) —
    # daca exista circuite TE-CT (sintetizate) si niciun feed TE-CT, il cream ca la TES (acelasi mecanism,
    # dimensionat pe merged_tect cu selectivitate). Pe proiectele existente feed-ul vine din breviar -> skip.
    if is_tech_room and merged_tect and not any(str(f.get("feeds_panel") or "") == "TE-CT" for f in feed_circuits):
        _fd = {"id": None, "name": None, "fasa": (None if is_mono else "RST"), "type": "sub_tablou",
               "panel": "TEG", "feeds_panel": "TE-CT", "phases": (1 if is_mono else 3),
               "breaker_type": ("MCB-1P-C" if is_mono else "MCB-3P-C"), "is_sub_tablou": True,
               "description": "Alimentare TE-CT (camera tehnica)",
               "usage": "Alimentare TE-CT (camera tehnica)",
               "sub_tablou_color1": "#e74c3c", "sub_tablou_color2": "#3498db"}
        _resize_column_feed(_fd, merged_tect, force_resum=True, force_mono=is_mono)
        _fd["cable"] = _fd.get("cable_type")
        feed_circuits.append(_fd)

    # FAZA 2 TE-CT (nebifat): dedicatele redirectate intra in fluxul TEG (dupa circuitele planului),
    # numerotate C{n} fara sufix — exact ca feed-urile.
    out = teg + redirected_teg + feed_circuits + tes + merged_tect

    # renumerotare PER TABLOU = sistemul PLANULUI (id+name; panel/feeds_panel/dimensionarea raman).
    # Pastreaza ORDINEA compute_circuits (deci id-uri IDENTICE cu plan_elements.circuit_id: TEG C1..,
    # etaj C1-TES.., TE-CT C1-TECT..) si integreaza circuitele din baza (feed pe TEG, incalzire pe
    # TE-CT) in numerotarea tabloului lor. NU mai flat C1..CN (care arunca sufixele).
    def _renumber_panel(circuits, suffix):
        for i, c in enumerate(circuits):
            cid = "C%d%s" % (i + 1, suffix)
            c["id"] = cid
            c["name"] = cid
    _renumber_panel(teg + redirected_teg + feed_circuits, "")   # TEG + redirectate + coloane -> C1..CN
    _renumber_panel(tes, "-TES")                   # etaj -> C1-TES..CN-TES (ca planul; nu -TES1, nu flat)
    _renumber_panel(merged_tect, "-TECT")          # TE-CT -> C1-TECT..CN-TECT (tech plan intai = ca planul)

    # tri: doar circuitele planului (TE-CT/feed pastreaza faza normativa); MONO: TOATE "R" (o faza reala)
    assign_phases(out, is_mono=is_mono)
    return out
