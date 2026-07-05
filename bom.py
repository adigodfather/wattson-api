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


def _extra_meters_by_type(plan_elements, circuits, scale):
    """Metri pt. cablurile care NU sunt in compute_cables: DEDICATE (receptor->tablou) + COLOANA
    (TEG->TE-CT). Lungime = L-path element->tablou (ca celelalte cabluri). Bucket pe cable_type."""
    panels = _panel_xy(plan_elements)
    teg  = panels.get("tablou_teg") or panels.get("tablou_tes")
    tect = panels.get("tablou_te_ct")
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
    return out


# ── BOM ──────────────────────────────────────────────────────────────────────
def _row(cat, den, spec, qty, um):
    return {"categorie": cat, "denumire": den, "specificatie": spec, "cantitate": qty, "um": um}


def build_bom(plan_elements, circuits, cables, scale, waste=1.0):
    """Lista de cantitati (7 categorii) din circuitele UNIFICATE + plan_elements. `cables` =
    compute_cables(plan_elements)[0] (cu length/kind). `scale` = m/px (derive_scale). `waste` =
    factor adaos capete (1.0 = fara; 1.10 = +10%). Intoarce {rows:[...], summary, meters_source}."""
    plan_elements = plan_elements or []
    circuits = circuits or []
    rows = []

    # 2+7 metri cablu (per cable_type normalizat): iluminat/prize (desenate) + dedicate/coloana
    m_by_type = _cable_meters_by_type(cables, scale)
    for ct, m in _extra_meters_by_type(plan_elements, circuits, scale).items():
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

    # ── 2. CABLURI (tip + metri) ──
    for ct in sorted(set(list(m_by_type.keys()) + list(circ_by_cable.keys()))):
        m = m_by_type.get(ct, 0.0)
        n = circ_by_cable.get(ct, 0)
        spec = "%d circuite" % n if n else "coloana/feed"
        rows.append(_row("Cabluri", ct, spec, (round(m, 1) if m else 0), "m"))

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

    total_m = round(sum(m_by_type.values()), 1)
    summary = {"circuite": len(circuits), "metri_cablu_total": total_m,
               "randuri": len(rows), "categorii": len(set(r["categorie"] for r in rows))}
    return {"rows": rows, "summary": summary}
