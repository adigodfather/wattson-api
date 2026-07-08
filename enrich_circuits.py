# enrich_circuits.py — FAZA 1 (IZOLAT, neconectat la finalize/n8n/frontend).
# Imbogateste circuitele derivate din PLAN (plan_elements) la formatul cerut de documente
# (result_data.circuits: ~15 campuri). Gruparea vine din draw_elements.compute_circuits (plan);
# aici adaugam power_w/breaker/cablu/faza/panel/... dupa cele 8 reguli validate de inginer (Dan).
#
# Sursa = PLANUL. Puterile: iluminat=suma becuri (plan are power_w); prize=2kW normativ (plan
# n-are power_w pe prize); receptoare=din formular extra_equipment (plan are doar label).
import math
from draw_elements import compute_circuits, tech_room_from_elements, _BULB_DEFAULT_W

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

def _enrich_receptor(el, cid, panel, floor_idx, form):
    """alimentare_receptor / receptor_internet -> circuit DEDICAT (compute_circuits nu-l grupeaza).
    Putere din formular/default UI (regula #2). Reteaua (receptor_internet) = 0W (date low-voltage)
    -> circuit minimal (breaker minim 16A), reprezinta alimentarea echipamentului de retea."""
    is_net = (el.get("element_type") or "") == "receptor_internet"
    power_w, tip, ph, src = receptor_power(el.get("label"), form)
    tri = str(ph).lower() in ("tri", "trifazat", "3")
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


_KS_TECT = 0.8   # simultaneitate coloana TE-CT (ca n8n) — cand resumam din circuitele TE-CT

def _resize_column_feed(feed, tect_circuits, force_resum=False):
    """FIX coloana: n8n lasa breaker=16 PLACEHOLDER (nu se re-deriva din putere) -> recalculam
    breaker+cablu din puterea ABSORBITA. Pi_total = feed.power_w (deja = suma × ks); fallback (sau
    force_resum cand planul a MODIFICAT TE-CT): resumam din TE-CT MERGED × ks -> coloana reflecta
    adaugarile din plan. Coloana trifazata (5x). Suprascrie DOAR feed-ul (nu circuitele TE-CT)."""
    try:
        pw = int(feed.get("power_w"))
    except (TypeError, ValueError):
        pw = 0
    if force_resum or not pw:                           # re-suma din TE-CT MERGED × ks (plan a atins TE-CT)
        pw = int(round(sum((c.get("power_w") or 0) for c in (tect_circuits or [])) * _KS_TECT))
        feed["power_w"] = pw
    tri = str(feed.get("phases")) == "3" or "5x" in str(feed.get("cable_type") or "")
    breaker, ia = breaker_and_ia(pw, tri=tri, minimum=16)   # min 16A (coloana principala)
    sec = _dedicate_section(breaker)                        # scara: 16->2.5, 20->4, 25/32->6, 40->10...
    n = "5x" if tri else "3x"
    feed["breaker_a"] = breaker
    feed["cable_type"] = "CYY-F %s%smmp" % (n, ("%.1f" % sec).rstrip("0").rstrip("."))
    feed["ia_calculated_a"] = ia
    feed["pozare"] = pozare_for(sec)


def enrich_circuits(plan_elements, form=None, base_circuits=None):
    """PLAN -> circuite (TEG/TES) in formatul result_data.circuits. TE-CT = PRESERVAT din
    base_circuits (heating-driven, ORTOGONAL de plan; dimensionarea normativa din norme_alimentari
    ramane INTACTA) + feed-ul coloanei (sub_tablou feeds_panel='TE-CT'). Numerotare PER TABLOU =
    sistemul PLANULUI: TEG C1..CN, etaj C1-TES..CN-TES, TE-CT C1-TECT..CN-TECT (identice cu
    plan_elements.circuit_id). base_circuits lipsa/fara TE-CT (heating 'existing') -> doar TEG/TES."""
    form = form or {}
    plan_elements = plan_elements or []

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
    # TE-CT e HEATING-DRIVEN: rutam tech-ul planului pe TE-CT DOAR daca baza are deja un context
    # TE-CT (circuite TE-CT sau feed coloana). 'existing' (fara incalzire) -> tech ramane pe TEG (ca inainte).
    has_base_tect = bool(tect_circuits) or bool(feed_circuits)

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
            plan_out.append(_enrich_group(c, els, panel, fidx))
        nextn = cc["n_circuits"] + 1
        gsuf = "" if general == "TEG" else "-%s" % general
        tech_l = (tech_room or "").strip().lower()     # NIVEL 2: receptor cu room==camera tehnica -> TE-CT
        for el in els:
            et = (el.get("element_type") or "")
            if et not in ("alimentare_receptor", "receptor_internet"):
                continue
            is_tech = bool(tech_l) and (el.get("room") or "").strip().lower() == tech_l
            if et == "receptor_internet" and not is_tech:
                continue                               # net in afara camerei tehnice = date low-voltage, NU circuit de putere (ca inainte)
            if et == "alimentare_receptor" and receptor_type_of(el.get("label")) == "ev_charger":
                continue                               # EV = separat (ca fotovoltaicele)
            rec_panel = "TE-CT" if is_tech else panel  # NIVEL 2: receptor din camera tehnica -> TE-CT
            rec_id = ("C%d-TECT" % nextn) if is_tech else ("C%d%s" % (nextn, gsuf))
            plan_out.append(_enrich_receptor(el, rec_id, rec_panel, fidx, form))
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
        _resize_column_feed(f, merged_tect, force_resum=plan_touched_tect)

    # ordine finala: TEG(plan, EXCL. tech) + feed(TEG->TE-CT) + TES(plan) + TE-CT(incalzire + tech plan)
    teg = [c for c in plan_out if c.get("panel") == "TEG"]
    tes = [c for c in plan_out if str(c.get("panel") or "").startswith("TES")]
    out = teg + feed_circuits + tes + merged_tect

    # renumerotare PER TABLOU = sistemul PLANULUI (id+name; panel/feeds_panel/dimensionarea raman).
    # Pastreaza ORDINEA compute_circuits (deci id-uri IDENTICE cu plan_elements.circuit_id: TEG C1..,
    # etaj C1-TES.., TE-CT C1-TECT..) si integreaza circuitele din baza (feed pe TEG, incalzire pe
    # TE-CT) in numerotarea tabloului lor. NU mai flat C1..CN (care arunca sufixele).
    def _renumber_panel(circuits, suffix):
        for i, c in enumerate(circuits):
            cid = "C%d%s" % (i + 1, suffix)
            c["id"] = cid
            c["name"] = cid
    _renumber_panel(teg + feed_circuits, "")       # TEG + coloana TE-CT -> C1..CN (fara sufix, ca planul)
    _renumber_panel(tes, "-TES")                   # etaj -> C1-TES..CN-TES (ca planul; nu -TES1, nu flat)
    _renumber_panel(merged_tect, "-TECT")          # TE-CT -> C1-TECT..CN-TECT (tech plan intai = ca planul)

    assign_phases(out)                                 # doar circuitele PLANULUI (TE-CT/feed pastreaza faza)
    return out
