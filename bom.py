# bom.py — LISTA DE CANTITATI (antemasuratori) din sursa UNIFICATA (enrich circuits + plan_elements).
# PUR (fara DB/PDF/HTTP): endpoint-ul /bom (main.py) face glue-ul (citeste DB, deschide PDF pt. W/H,
# ruleaza enrich_circuits + compute_cables) si cheama build_bom(). Consistent cu schema/memoriu:
# ACELEASI circuite (enrich) -> aceleasi numere.
#
# 7 categorii: 1) Sigurante (breaker), 2) Cabluri (tip+metri), 3) Prize, 4) Becuri, 5) Tablouri,
# 6) Receptoare, 7) Tuburi (diametru+metri). Metri: scala per-proiect din area_m2 (fallback fix ~1:71).
import math
import re

import draw_elements
from draw_elements import _PX_TO_M, _cable_l_path

# ── kind (compute_cables) -> sectiune cablu. iluminat=1.5 fix, prize=2.5 fix (ca enrich). ──
_ILUM_KINDS  = {"bec_lant", "bec_paralel", "cap_scara", "senzor_teg", "sw_tablou"}
_PRIZA_KINDS = {"priza_lant", "priza_tablou"}
_ILUM_CABLE  = "CYY-F 3x1.5"
_PRIZA_CABLE = "CYY-F 3x2.5"

_BULB_TYPES  = {"lustra_led", "aplica_tavan", "aplica_perete", "aplica_senzor", "banda_led"}
_PRIZA_TYPES = {"priza_simpla", "priza_dubla", "priza_16a", "priza_exterior_ip44"}
_PANEL_TYPES = {"tablou_teg", "tablou_tes", "tablou_te_ct"}

_NAMES = {
    "priza_simpla": "Priza simpla", "priza_dubla": "Priza dubla", "priza_16a": "Priza 16A",
    "priza_exterior_ip44": "Priza exterioara IP44",
    "lustra_led": "Lustra LED", "aplica_tavan": "Aplica/plafoniera tavan",
    "aplica_perete": "Aplica perete", "aplica_senzor": "Aplica cu senzor", "banda_led": "Banda LED",
    "tablou_teg": "Tablou general TEG", "tablou_tes": "Tablou secundar TES",
    "tablou_te_ct": "Tablou TE-CT (camera tehnica)",
}


# ── SCALA px -> m ────────────────────────────────────────────────────────────
def derive_scale(rooms, W, H):
    """Scala reala px->m PER-PROIECT din area_m2 (suprafata cunoscuta) vs aria bbox-urilor in px².
    sum(area_m2) / sum(bbox_w*bbox_h*W*H) = m²/px² -> sqrt = m/px. Fallback: _PX_TO_M fix (~1:71)
    daca lipseste area_m2 / dimensiuni. Intoarce (scale_m_per_px, sursa)."""
    try:
        W = float(W); H = float(H)
    except (TypeError, ValueError):
        W = H = 0.0
    sum_m2, sum_px2 = 0.0, 0.0
    for r in (rooms or []):
        try:
            a = float((r or {}).get("area_m2") or 0)
            bb = (r or {}).get("bbox") or {}
            w = float(bb.get("w") or 0); h = float(bb.get("h") or 0)
        except (TypeError, ValueError):
            continue
        if a > 0 and w > 0 and h > 0 and W > 0 and H > 0:
            sum_m2 += a
            sum_px2 += (w * W) * (h * H)
    if sum_m2 > 0 and sum_px2 > 0:
        return (sum_m2 / sum_px2) ** 0.5, "area_m2 (per-proiect)"
    return _PX_TO_M, "fix (~1:71, aproximativ)"


# ── cable_type: normalizare + sectiune + pozare ─────────────────────────────
def _norm_cable(s):
    """Normalizeaza formatele variate ('CYY-F 3x1.5', '5x2.5 mm2 CYYF', 'CYY-F 5x4mmp') ->
    'CYY-F NxM' canonic (pt. agregare consistenta enrich + base + kind-assigned)."""
    s = str(s or "")
    m = re.search(r"(\d+)\s*[xX]\s*([\d.]+)", s)
    if not m:
        return s.strip() or "necunoscut"
    nxm = "%sx%s" % (m.group(1), m.group(2).rstrip(".") or m.group(2))
    fam = "CYY-F" if "cyy" in s.lower() else (s.split()[0] if s.split() else "CYY-F")
    return "%s %s" % (fam, nxm)


def _section_of(cable_type):
    """Sectiunea (mm², = M din NxM) dintr-un cable_type. 0 daca nu se poate parsa."""
    m = re.search(r"\d+\s*[xX]\s*([\d.]+)", str(cable_type or ""))
    try:
        return float(m.group(1)) if m else 0.0
    except (TypeError, ValueError):
        return 0.0


def _pozare(section):
    """Diametru tub (IPEY) din sectiune — oglinda enrich_circuits.pozare_for."""
    if section <= 1.5: return "IPEY 16mm"
    if section <= 2.5: return "IPEY 18mm"
    if section <= 6.0: return "IPEY 25mm"
    return "IPEY 32mm"


# ── LUNGIMI: iluminat/prize (compute_cables) + dedicate/coloana (element->tablou) ─────────
def _path_len(path):
    return sum(math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
               for i in range(len(path) - 1))


def _cable_meters_by_type(cables, scale):
    """Metri per cable_type din cablurile desenate (compute_cables): iluminat->3x1.5, prize->3x2.5."""
    px = {}
    for c in (cables or []):
        kind = c.get("kind")
        L = c.get("length")
        if L is None:
            L = _path_len(c.get("path") or [])
        if kind in _ILUM_KINDS:
            px[_ILUM_CABLE] = px.get(_ILUM_CABLE, 0.0) + L
        elif kind in _PRIZA_KINDS:
            px[_PRIZA_CABLE] = px.get(_PRIZA_CABLE, 0.0) + L
    return {ct: v * scale for ct, v in px.items()}


def _panel_xy(plan_elements):
    p = {}
    for el in (plan_elements or []):
        et = (el or {}).get("element_type") or ""
        if et in _PANEL_TYPES:
            try:
                p[et] = (float(el["x"]), float(el["y"]))
            except (TypeError, ValueError, KeyError):
                pass
    return p


def _match_receptor(desc, pool):
    """Potriveste un circuit dedicat (description) cu un element receptor din pool (consumat).
    'Alimentare retea/date' -> receptor_internet; 'Alimentare X' -> alimentare_receptor cu label X."""
    d = (desc or "").strip().lower()
    if "retea/date" in d or "retea" in d or "date" in d:
        for i, el in enumerate(pool):
            if (el.get("element_type") or "") == "receptor_internet":
                return pool.pop(i)
        return None
    lbl = d.replace("alimentare", "", 1).strip()
    for i, el in enumerate(pool):
        if (el.get("element_type") or "") == "alimentare_receptor" and lbl and lbl in (el.get("label") or "").lower():
            return pool.pop(i)
    # fallback: primul alimentare_receptor ramas
    for i, el in enumerate(pool):
        if (el.get("element_type") or "") == "alimentare_receptor":
            return pool.pop(i)
    return None


_TES_FEED_FALLBACK = "CYY-F 5x6"   # sectiunea coloanei TEG->TES cand feed-ul lipseste din breviar
                                   # (CONSISTENT cu fallback-ul legendei din /regenerate-plan)


def _extra_meters_by_type(plan_elements, circuits, scale):
    """Metri pt. cablurile care NU sunt in compute_cables: DEDICATE (receptor->tablou) + COLOANA
    (TEG->TE-CT) + COLOANA TEG->TES (cross-plansa, P0-4; o data, scara parterului).
    Lungime = L-path element->tablou (ca celelalte cabluri). Bucket pe cable_type."""
    panels = _panel_xy(plan_elements)
    teg  = panels.get("tablou_teg") or panels.get("tablou_tes")
    tect = panels.get("tablou_te_ct")
    tes  = panels.get("tablou_tes")
    # coloana TEG->TES exista DOAR cross-floor (TEG si TES pe etaje diferite) — ca desenul de pe plan
    _fl = {}
    for el in (plan_elements or []):
        et = (el or {}).get("element_type") or ""
        if et in ("tablou_teg", "tablou_tes") and et not in _fl:
            _fl[et] = str(el.get("floor") or "parter")
    tes_cross = ("tablou_teg" in _fl and "tablou_tes" in _fl and _fl["tablou_teg"] != _fl["tablou_tes"])
    tes_counted = False
    out = {}
    pool = [el for el in (plan_elements or [])
            if (el.get("element_type") or "") in ("alimentare_receptor", "receptor_internet")]
    for c in (circuits or []):
        ctype = c.get("type")
        ct = _norm_cable(c.get("cable_type"))
        if ctype == "dedicat":
            # DOAR receptoarele PLANULUI (descriere "Alimentare X") au geometrie (element pe plan).
            # Echipamentele de incalzire din baza (PDC/Boiler ACM/Pompa...) NU sunt elemente de plan
            # -> fara geometrie -> doar tip+count (metri = doar coloana feed). Le sarim aici.
            if not str(c.get("description") or "").strip().lower().startswith("alimentare"):
                continue
            el = _match_receptor(c.get("description"), pool)
            if not el:
                continue
            is_tech = "tehnic" in (el.get("room") or "").lower()
            target = (tect if (is_tech and tect) else teg)
            if not target:
                continue
            try:
                a = (float(el["x"]), float(el["y"]))
            except (TypeError, ValueError, KeyError):
                continue
            out[ct] = out.get(ct, 0.0) + _path_len(_cable_l_path(a, target)) * scale
        elif ctype == "sub_tablou" and c.get("feeds_panel") == "TE-CT":
            if teg and tect:
                out[ct] = out.get(ct, 0.0) + _path_len(_cable_l_path(tect, teg)) * scale
        elif ctype == "sub_tablou" and str(c.get("feeds_panel") or "").startswith("TES"):
            # P0-4: feed-ul TEG->TES (coloana cross-plansa) — numarat O DATA, pe pozitiile de plan
            # (proiectia TES pe parter ≈ pozitia TES bruta; plansele-s suprapuse, eroare ~3pt = ~5cm).
            if teg and tes and tes_cross:
                out[ct] = out.get(ct, 0.0) + _path_len(_cable_l_path(tes, teg)) * scale
                tes_counted = True
    # feed TES ABSENT din circuits (breviarul actual nu-l emite — follow-up cunoscut) dar tablourile-s
    # cross-floor -> coloana desenata pe plan exista; numaram cu fallback-ul CONSISTENT cu legenda (5x6).
    if teg and tes and tes_cross and not tes_counted:
        ct = _norm_cable(_TES_FEED_FALLBACK)
        out[ct] = out.get(ct, 0.0) + _path_len(_cable_l_path(tes, teg)) * scale
    return out


# ── P0-4: ORIZONTALE PER-ETAJ (multi-etaj) ───────────────────────────────────
# /bom rula compute_cables pe TOATE elementele amestecate (fara rooms, scara fixa) -> +75% pe P+M
# (masurat pe 9926: 320m vs 182m) + 8 cabluri fizic imposibile (intrerupatoarele parterului "coborau"
# spre TES-ul etajului). Fix: fiecare etaj se calculeaza IZOLAT (elementele+camerele+scara plansei lui),
# ca la desen (/regenerate-plan) — sursa unica. Mono-etaj: identic cu totalul (un singur etaj).
_FLOOR_IDX = {"parter": 0, "etaj": 1, "mansarda": 2}


def per_floor_horizontals(plan_elements, rooms, floor_wh):
    """Metrii ORIZONTALI per cable_type, calculati PER ETAJ (floor filter + rooms filtrate pe
    rooms[].floor + W/H + scara plansei etajului) si insumati. `floor_wh` = {floor_name: (W, H)}
    (din png_meta per plansa; lipsa/0 -> derive_scale cade pe scara fixa pt. acel etaj).
    Returneaza (m_by_type, cables_all, per_floor_info) — per_floor_info[fl] = {scale, scale_source,
    n_elements, n_rooms} pt. raportare/teste."""
    out, cables_all, info = {}, [], {}
    els = plan_elements or []
    floors = sorted({str((r or {}).get("floor") or "parter") for r in els},
                    key=lambda f: _FLOOR_IDX.get(f, 9))
    for fl in floors:
        rows_fl = [r for r in els if str((r or {}).get("floor") or "parter") == fl]
        rooms_fl = [r for r in (rooms or []) if int((r or {}).get("floor") or 0) == _FLOOR_IDX.get(fl, 0)]
        W, H = (floor_wh or {}).get(fl) or (0.0, 0.0)
        cen = draw_elements._room_centroids(rows_fl)
        cab_fl, _st = draw_elements.compute_cables(rows_fl, rooms=rooms_fl, W=(W or None), H=(H or None),
                                                   room_centroids=cen)
        sc_fl, ssrc_fl = derive_scale(rooms_fl, W, H)
        for ct, m in _cable_meters_by_type(cab_fl, sc_fl).items():
            out[ct] = out.get(ct, 0.0) + m
        cables_all += cab_fl
        info[fl] = {"scale": sc_fl, "scale_source": ssrc_fl,
                    "n_elements": len(rows_fl), "n_rooms": len(rooms_fl)}
    return out, cables_all, info


# ── COBORARI VERTICALE (H camera − h montaj) — metri REALI, nu px ───────────
_H_FALLBACK = 2.7    # H camera lipsa (rooms fara height_m / element fara camera)
_H_GENERIC  = 0.6    # default-ul UI nespecific al mount_height_m (nu inseamna "editat")
_H_SWITCH   = 1.1    # intrerupator (decizia Dan; datele au 0.6 generic)
_H_PANEL    = 1.4    # tablou (plecarile circuitelor urca la tavan de la 1.4)
# Coloana TEG->TES (cross-floor, corectii Dan): verticala REALA intre etaje. NOTA: 1.5 (capetele
# coloanei la tablouri) e distinct de _H_PANEL=1.4 (plecarile circuitelor spre tavan) — reguli separate.
_PLANSEU_M = 0.5          # grosimea planseului traversat per nivel
_TABLOU_HEIGHT_M = 1.5    # inaltimea de montaj a tablourilor (capetele coloanei TEG/TES)
_PDC_MIN_M = 10.0         # cablul PDC (unitate exterioara, nu pe plan): minim 10 m FIX


def _floor_heights(rooms):
    """{floor_idx: H reprezentativ (mediana height_m a camerelor nivelului)}; lipsa -> 2.7."""
    by_fl = {}
    for r in (rooms or []):
        try:
            h = float((r or {}).get("height_m") or 0)
        except (TypeError, ValueError):
            h = 0.0
        if h > 0:
            by_fl.setdefault(int((r or {}).get("floor") or 0), []).append(h)
    out = {}
    for fl, hs in by_fl.items():
        hs.sort()
        out[fl] = hs[len(hs) // 2]
    return out


def _tes_feed_ct(circuits):
    """cable_type-ul coloanei TEG->TES: feed-ul sub_tablou TES din breviar; absent -> fallback 5x6
    (CONSISTENT cu legenda + orizontala din _extra_meters)."""
    for c in (circuits or []):
        if isinstance(c, dict) and c.get("type") == "sub_tablou" and str(c.get("feeds_panel") or "").startswith("TES"):
            return _norm_cable(c.get("cable_type"))
    return _norm_cable(_TES_FEED_FALLBACK)


def _tes_column_vertical(plan_elements, rooms):
    """VERTICALA coloanei TEG->TES (Dan): per nivel traversat H_nivel + 0.5 (planseu), + 1.5 la
    fiecare capat (tablourile-s montate la 1.5, nu in podea). P+E: (H_parter+0.5)+1.5+1.5 ≈ 6.2 m.
    0 daca tablourile nu-s cross-floor."""
    fl = {}
    for el in (plan_elements or []):
        et = (el or {}).get("element_type") or ""
        if et in ("tablou_teg", "tablou_tes") and et not in fl:
            fl[et] = _FLOOR_IDX.get(str(el.get("floor") or "parter"), 0)
    if "tablou_teg" not in fl or "tablou_tes" not in fl or fl["tablou_teg"] == fl["tablou_tes"]:
        return 0.0
    lo, hi = min(fl["tablou_teg"], fl["tablou_tes"]), max(fl["tablou_teg"], fl["tablou_tes"])
    hs = _floor_heights(rooms)
    v = 2.0 * _TABLOU_HEIGHT_M                                  # capetele (TEG + TES)
    for lvl in range(lo, hi):                                   # fiecare nivel dintre ele
        v += hs.get(lvl, _H_FALLBACK) + _PLANSEU_M
    return v
# H4 (Regula 10): inaltimea de montaj DEFAULT pt. grupatele fara mount_height_m persistat (fallback
# defensiv; UI-ul o seteaza mereu la plasare). Radiator la parapet 0.3, VCV sus pe perete 2.2.
_GROUPED_HEATING_DEFAULT_H = {"radiator": 0.3, "vcv": 2.2}


def _room_heights(rooms):
    """{nume: H (m)} din result_data.rooms[].height_m (Vision, ex. 2.7 / 3.0). Lipsa -> fallback 2.7."""
    out = {}
    for r in (rooms or []):
        nm = str((r or {}).get("name") or "").strip()
        try:
            h = float((r or {}).get("height_m") or 0)
        except (TypeError, ValueError):
            h = 0.0
        if nm:
            out[nm] = h if h > 0 else _H_FALLBACK
    return out


def _vertical_drops(plan_elements, circuits, rooms, W=None, H=None):
    """Metri VERTICALI per cable_type: per element racordat max(0, H_camera − h_efectiv) + plecarile
    din tablou (H_tablou − 1.4) per circuit. h_efectiv = mount_height_m EDITAT (≠ 0.6 generic la
    tipurile cu alt default natural), altfel default per tip: priza 0.6, intrerupator 1.1, becuri de
    TAVAN 0 (fara coborare), aplice de perete/senzor = h-ul lor, receptoare = mount_height_m.
    Bucket pe cable_type-ul circuitului elementului. W/H (px pagina) optionale -> room geometric
    pt. elementele fara room (ex. tablouri: TE-CT in Spatiu tehnic H=3.0)."""
    hs = _room_heights(rooms)

    def room_of(el):
        r = ((el or {}).get("room") or "").strip()
        if r:
            return r
        if W and H and rooms:                            # fallback geometric (tablourile au room null)
            try:
                return (draw_elements._room_of_point(float(el["x"]), float(el["y"]), rooms, W, H) or "").strip()
            except (TypeError, ValueError, KeyError):
                return ""
        return ""

    def Hc(el):
        return hs.get(room_of(el), _H_FALLBACK)

    out = {}

    def put(ct, m):
        if m > 0:
            out[ct] = out.get(ct, 0.0) + m

    # cablul circuitului elementului (id-urile per-tablou din enrich = plan_elements.circuit_id)
    cab = {str(c.get("id") or ""): _norm_cable(c.get("cable_type")) for c in (circuits or [])}

    # DEDICATELE de plan (receptoare): coborarea la element, pe cablul circuitului dedicat.
    # H4: EXCLUDE grupatele (VCV/radiatoare) -> au ramura proprie (jos), NU pot fi inghitite de fallback-ul
    # _match_receptor al unui dedicat nepotrivit (evita dubla-numarare + mis-match). Distribuitorul zona
    # (dedicat, kind=None) RAMANE in pool -> prins normal aici prin "Alimentare Distribuitor zona".
    pool = [el for el in (plan_elements or [])
            if (el.get("element_type") or "") in ("alimentare_receptor", "receptor_internet")
            and not draw_elements._grouped_heating_kind(el.get("label"))]
    for c in (circuits or []):
        if c.get("type") != "dedicat":
            continue
        if not str(c.get("description") or "").strip().lower().startswith("alimentare"):
            continue                                     # incalzirea din baza nu are element pe plan
        el = _match_receptor(c.get("description"), pool)
        if not el:
            continue
        hm = el.get("mount_height_m")
        h = float(hm) if hm is not None else 1.0
        put(_norm_cable(c.get("cable_type")), max(0.0, Hc(el) - h))

    _SW = draw_elements._SWITCH_TYPES
    _WALL_BULBS = {"aplica_perete", "aplica_senzor"}     # pe perete -> coboara; tavanul NU coboara
    for el in (plan_elements or []):
        et = (el.get("element_type") or "")
        hm = el.get("mount_height_m")
        try:
            hm = None if hm is None else float(hm)
        except (TypeError, ValueError):
            hm = None
        if et in _PRIZA_TYPES:
            h = hm if hm is not None else 0.6            # 0.6 = default-ul CORECT al prizei
            put(cab.get(str(el.get("circuit_id") or ""), _PRIZA_CABLE), max(0.0, Hc(el) - h))
        elif et in _SW:
            h = hm if (hm is not None and abs(hm - _H_GENERIC) > 1e-9) else _H_SWITCH
            put(_ILUM_CABLE, max(0.0, Hc(el) - h))
        elif et in _WALL_BULBS:
            h = hm if hm is not None else _H_GENERIC
            put(_ILUM_CABLE, max(0.0, Hc(el) - h))
        elif et == "alimentare_receptor" and draw_elements._grouped_heating_kind(el.get("label")):
            # Regula 10 / H4: VCV/radiatoare GRUPATE -> coborarea la element (H_camera − h_montaj), pe cablul
            # circuitului GRUPAT (via circuit_id, NU descriere). Boilerul/cuptorul/distribuitorul (dedicate,
            # kind=None) NU intra aici -> prinse de bucla dedicatelor de sus.
            kind = draw_elements._grouped_heating_kind(el.get("label"))
            h = hm if hm is not None else _GROUPED_HEATING_DEFAULT_H.get(kind, 1.0)
            put(cab.get(str(el.get("circuit_id") or ""), _PRIZA_CABLE), max(0.0, Hc(el) - h))
        # aplica_tavan / lustra_led / banda_led: racord la tavan -> coborare 0

    # PLECARILE DIN TABLOU: fiecare circuit urca din tabloul lui la tavan (H_tablou − 1.4),
    # pe cablul circuitului (inclusiv dedicatele de incalzire + feed-ul coloanei).
    ppos = {}
    for el in (plan_elements or []):
        if (el.get("element_type") or "") in _PANEL_TYPES:
            ppos[(el.get("element_type") or "")] = el
    for c in (circuits or []):
        if _section_of(c.get("cable_type")) <= 0:
            continue                                     # fara sectiune parsabila (ex. rezerva "—")
        if c.get("type") == "sub_tablou" and str(c.get("feeds_panel") or "").startswith("TES"):
            continue                                     # coloana TEG->TES: verticala ei COMPLETA mai jos (nu +1.3 dublat)
        panel = str(c.get("panel") or "TEG")
        key = ("tablou_te_ct" if panel == "TE-CT" else
               ("tablou_tes" if panel.startswith("TES") else "tablou_teg"))
        el = ppos.get(key) or ppos.get("tablou_teg")
        if el is None:
            continue
        put(_norm_cable(c.get("cable_type")), max(0.0, Hc(el) - _H_PANEL))
    # COLOANA TEG->TES (cross-floor): verticala REALA intre etaje (Dan) = per nivel traversat
    # H_nivel + 0.5 planseu, + 1.5 la fiecare capat. Pe cablul feed-ului TES (fallback 5x6).
    put(_tes_feed_ct(circuits), _tes_column_vertical(plan_elements, rooms))
    return out


# ── [2] PDC minim 10 m (unitate exterioara — cablul real e mereu mai lung decat planul) ──
def _pdc_min_topup(plan_elements, circuits, rooms, scale, W=None, H=None):
    """Pentru fiecare circuit dedicat PDC (_equip_key == 'pdc'): lungimea CALCULABILA din plan =
    plecarea din tablou (H_tablou − 1.4) + orizontala (doar daca exista element pe plan cu label
    pdc/aer-apa — de regula NU exista, unitatea e exterioara) -> max(calculat, 10 m) => top-up-ul
    diferentei pe cable_type-ul circuitului. PRE-waste (aliniat cu restul orizontale+verticale;
    doar bransamentul 20 m ramane explicit fara waste)."""
    try:
        from enrich_circuits import _equip_key
    except Exception:
        return {}
    pdcs = [c for c in (circuits or [])
            if isinstance(c, dict) and c.get("type") == "dedicat" and _equip_key(c.get("description")) == "pdc"]
    if not pdcs:
        return {}
    hs = _room_heights(rooms)
    panels = {}
    for el in (plan_elements or []):
        et = (el.get("element_type") or "")
        if et in _PANEL_TYPES and et not in panels:
            panels[et] = el

    def _panel_H(el):
        r = ((el or {}).get("room") or "").strip()
        if not r and W and H and rooms:
            try:
                r = (draw_elements._room_of_point(float(el["x"]), float(el["y"]), rooms, W, H) or "").strip()
            except (TypeError, ValueError, KeyError):
                r = ""
        return hs.get(r, _H_FALLBACK)

    out = {}
    for c in pdcs:
        key = "tablou_te_ct" if str(c.get("panel") or "") == "TE-CT" else "tablou_teg"
        pel = panels.get(key) or panels.get("tablou_teg")
        calc = max(0.0, (_panel_H(pel) if pel is not None else _H_FALLBACK) - _H_PANEL)   # plecarea din tablou
        pdc_el = next((el for el in (plan_elements or [])
                       if (el.get("element_type") or "") == "alimentare_receptor"
                       and any(k in (el.get("label") or "").lower() for k in ("pdc", "aer-apa", "sol-apa"))), None)
        if pdc_el is not None and pel is not None:
            try:
                a = (float(pdc_el["x"]), float(pdc_el["y"]))
                b = (float(pel["x"]), float(pel["y"]))
                calc += _path_len(_cable_l_path(a, b)) * scale
            except (TypeError, ValueError, KeyError):
                pass
        if calc < _PDC_MIN_M:
            ct = _norm_cable(c.get("cable_type"))
            out[ct] = out.get(ct, 0.0) + (_PDC_MIN_M - calc)
    return out


# ── BRANSAMENT TEG (coloana generala, dimensionata ca in monofilara) ─────────
def _bransament_cable(power_summary):
    """Tipul cablului de bransament din power_summary (schema monofilara): sectiunea din current_a
    (aceeasi mapare normativa ca feeder-ele TEG->TES din main.py), 5x trifazat / 3x monofazat.
    None daca nu exista power_summary (randul se omite)."""
    ps = power_summary or {}
    try:
        ia = float(ps.get("current_a") or 0)
    except (TypeError, ValueError):
        ia = 0.0
    if ia <= 0:
        return None
    size = "35"
    for max_a, s in ((16, "2.5"), (25, "4"), (35, "6"), (50, "10"), (63, "16"), (80, "25")):
        if ia <= max_a:
            size = s
            break
    tri = "trifazat" in str(ps.get("connection") or "").lower() or "3P" in str(ps.get("main_breaker_type") or "")
    return "CYY-F %sx%s" % ("5" if tri else "3", size)


_BRANSAMENT_M = 20.0   # marja fixa Dan (deja acopera; NU se aplica waste peste)


# ── BOM ──────────────────────────────────────────────────────────────────────
def _row(cat, den, spec, qty, um):
    return {"categorie": cat, "denumire": den, "specificatie": spec, "cantitate": qty, "um": um}


def build_bom(plan_elements, circuits, cables, scale, waste=1.1, rooms=None, power_summary=None,
              W=None, H=None, horizontal_m=None):
    """Lista de cantitati (7 categorii) din circuitele UNIFICATE + plan_elements. `cables` =
    compute_cables(plan_elements)[0] (cu length/kind). `scale` = m/px (derive_scale). `waste` =
    adaos aplicat LA FINAL pe orizontale+verticale (default 1.1 = +10%, decizia Dan; acopera si
    mustatile). `rooms` (height_m) -> COBORARILE VERTICALE per element + plecarile din tablou.
    `power_summary` -> randul de BRANSAMENT TEG (tip din monofilara, 20 m FIX, fara waste).
    W/H (px pagina) optionale -> H-ul camerei tabloului determinat geometric.
    P0-4: `horizontal_m` (dict cable_type->metri, din per_floor_horizontals) dat -> orizontalele
    PRE-AGREGATE per etaj (scara fiecarei planse) inlocuiesc _cable_meters_by_type(cables, scale);
    `scale` ramane folosit la dedicate/coloane (_extra_meters, pozitii pe parter)."""
    plan_elements = plan_elements or []
    circuits = circuits or []
    rows = []

    # 2+7 metri cablu (per cable_type normalizat): iluminat/prize (desenate) + dedicate/coloana
    # (ORIZONTALE, px*scale) + COBORARILE VERTICALE (H camera − h montaj + plecarile din tablou,
    # metri reali). Waste-ul se aplica LA FINAL pe suma.
    m_by_type = dict(horizontal_m) if horizontal_m is not None else _cable_meters_by_type(cables, scale)
    for ct, m in _extra_meters_by_type(plan_elements, circuits, scale).items():
        m_by_type[ct] = m_by_type.get(ct, 0.0) + m
    vertical_m = _vertical_drops(plan_elements, circuits, rooms, W=W, H=H)
    for ct, m in vertical_m.items():
        m_by_type[ct] = m_by_type.get(ct, 0.0) + m
    # [2] PDC minim 10 m: top-up-ul pana la 10 m pe cablul PDC-ului (PRE-waste, ca restul)
    for ct, m in _pdc_min_topup(plan_elements, circuits, rooms, scale, W=W, H=H).items():
        m_by_type[ct] = m_by_type.get(ct, 0.0) + m
    m_by_type = {ct: v * waste for ct, v in m_by_type.items()}

    # nr. circuite per cable_type (din TOATE circuitele enrich)
    circ_by_cable = {}
    for c in circuits:
        ct = _norm_cable(c.get("cable_type"))
        circ_by_cable[ct] = circ_by_cable.get(ct, 0) + 1

    # ── 1. SIGURANTE (MCB pe amperaj+poli; RCCB pe mA) ──
    mcb, rccb = {}, {}
    for c in circuits:
        amp = c.get("breaker_a")
        bt = str(c.get("breaker_type") or "")
        if amp:
            poles = "3P" if "3P" in bt else "1P"
            mcb[(amp, poles)] = mcb.get((amp, poles), 0) + 1
        ma = None
        if "10mA" in bt or "10 mA" in bt:
            ma = 10
        elif c.get("rccb_ma") or c.get("has_rccb_individual"):
            ma = int(c.get("rccb_ma") or 30)
        if ma:
            rccb[ma] = rccb.get(ma, 0) + 1
    for (amp, poles), n in sorted(mcb.items()):
        rows.append(_row("Sigurante", "MCB %dA %s curba C" % (amp, poles), "", n, "buc"))
    for ma, n in sorted(rccb.items()):
        rows.append(_row("Sigurante", "Protectie diferentiala RCCB %dmA" % ma, "", n, "buc"))

    # ── 2. CABLURI (tip + metri: orizontale + verticale, × waste) ──
    for ct in sorted(set(list(m_by_type.keys()) + list(circ_by_cable.keys()))):
        m = m_by_type.get(ct, 0.0)
        n = circ_by_cable.get(ct, 0)
        spec = "%d circuite" % n if n else "coloana/feed"
        rows.append(_row("Cabluri", ct, spec, (round(m, 1) if m else 0), "m"))
    # BRANSAMENT TEG (coloana generala): tip dimensionat ca in monofilara (power_summary),
    # 20 m FIX (marja Dan — deja acopera, NU intra sub waste; nici la tuburi: pozare separata).
    bransament_ct = _bransament_cable(power_summary)
    bransament_m = _BRANSAMENT_M if bransament_ct else 0.0
    if bransament_ct:
        rows.append(_row("Cabluri", bransament_ct, "bransament TEG (fix)", round(bransament_m, 1), "m"))

    # ── 3. PRIZE (plan_elements, pe tip) ──
    prz = {}
    for el in plan_elements:
        et = (el.get("element_type") or "")
        if et in _PRIZA_TYPES:
            prz[et] = prz.get(et, 0) + 1
    for et, n in sorted(prz.items()):
        rows.append(_row("Prize", _NAMES.get(et, et), "", n, "buc"))

    # ── 4. BECURI (plan_elements, pe tip + putere) ──
    bec = {}
    for el in plan_elements:
        et = (el.get("element_type") or "")
        if et in _BULB_TYPES:
            try:
                pw = int(el.get("power_w")) if el.get("power_w") not in (None, "") else 0
            except (TypeError, ValueError):
                pw = 0
            bec[(et, pw)] = bec.get((et, pw), 0) + 1
    for (et, pw), n in sorted(bec.items()):
        rows.append(_row("Becuri", _NAMES.get(et, et), ("%dW" % pw if pw else ""), n, "buc"))

    # ── 5. TABLOURI (plan_elements) ──
    tab = {}
    for el in plan_elements:
        et = (el.get("element_type") or "")
        if et in _PANEL_TYPES:
            tab[et] = tab.get(et, 0) + 1
    for et, n in sorted(tab.items()):
        rows.append(_row("Tablouri", _NAMES.get(et, et), "", n, "buc"))

    # ── 6. RECEPTOARE (plan_elements: alimentare pe label + retea) ──
    rec = {}
    for el in plan_elements:
        et = (el.get("element_type") or "")
        if et == "alimentare_receptor":
            lbl = (el.get("label") or "receptor").strip()
            rec[lbl] = rec.get(lbl, 0) + 1
        elif et == "receptor_internet":
            rec["Retea date / Internet (RJ45)"] = rec.get("Retea date / Internet (RJ45)", 0) + 1
    for lbl, n in sorted(rec.items()):
        den = lbl[:1].upper() + lbl[1:] if lbl else lbl
        rows.append(_row("Receptoare", den, "", n, "buc"))

    # ── 7. TUBURI (diametru din sectiune; metri = metri cablu, re-bucketat) ──
    tub = {}
    for ct, m in m_by_type.items():
        tub.setdefault(_pozare(_section_of(ct)), 0.0)
        tub[_pozare(_section_of(ct))] += m
    for d, m in sorted(tub.items()):
        rows.append(_row("Tuburi", d, "", round(m, 1), "m"))

    total_m = round(sum(m_by_type.values()) + bransament_m, 1)
    summary = {"circuite": len(circuits), "metri_cablu_total": total_m,
               "metri_verticali": round(sum(vertical_m.values()), 1), "waste": waste,
               "randuri": len(rows), "categorii": len(set(r["categorie"] for r in rows))}
    return {"rows": rows, "summary": summary}
