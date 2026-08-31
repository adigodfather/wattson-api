# -*- coding: utf-8 -*-
"""
ZYNAPSE · Schema sistemului de CURENTI SLABI (efractie + supraveghere video)
===========================================================================
O schema FUNCTIONALA, nu monofilara: arata ce echipament e legat la ce si cu ce cablu. Se genereaza
din elementele EFECTIV plasate pe plansa de curenti slabi — nu dintr-un sablon.

DE CE PyMuPDF si nu ReportLab (ca schemele de tablou si cea FV): simbolurile celor 13 tipuri exista
deja, desenate cu fitz in `draw_elements._draw_cs`, iar caseta de legenda in `_draw_legend`. Cu fitz
le refolosesc LITERAL — acelasi cod, nu o oglinda care poate ramane in urma. Cartusul se aplica tot
cu fitz (`cartus_swap._draw_cartus`), exact ca la schema FV, deci nu pierdem nimic din lantul comun.

ETICHETELE (PIR 1, CV-INT 2, ...) vin din `cs_index_map` + `_cs_abbr_for` — ACELEASI functii care
eticheteaza planşa. Consecventa plan <-> schema e structurala, nu verificata pe cuvant de onoare.

Gate: fara elemente de curenti slabi -> None (schema nu se genereaza), ca la FV.
"""

import math

import fitz

import draw_elements as DE
from draw_elements import (
    _CS_CABLE, _CS_LEGEND, _CAM_TIPURI, _CS_HEIGHT,
    _cam_tip, _cs_abbr_for, cs_index_map, build_legend_rows, _draw_cs, _draw_legend,
)

MMPT = 72.0 / 25.4

try:
    from cartus_swap import _txt as _ascii        # transpunerea diacriticelor, ca la cartus/planşa
except Exception:                                  # pragma: no cover
    def _ascii(s):
        return str(s or "")

# FORMAT FIX A3 orizontal (decizia Dan): uniformitate cu celelalte planşe. Inainte se alegea cel
# mai mic format in care incapea continutul (A4 la sisteme mici) — a iesit un set cu planşe de doua
# marimi. Continutul se CENTREAZA pe foaie, ca la sistemele mici sa nu ramana ingramadit intr-un colt.
_A3 = (420.0, 297.0)
_CARTUS_W_MM, _CARTUS_H_MM = 182.5, 42.5      # cartusul UNIFICAT, ca la planşe si la FV
_PAD_MM = 6.0

TITLU = "SCHEMA SISTEM CURENȚI SLABI"

_NEGRU = (0.10, 0.10, 0.10)
_GRI = (0.62, 0.62, 0.62)

# Ce intra pe fiecare ramura a schemei. Ordinea = cea de citit, nu cea din baza.
_VIDEO = ("camera_video",)
# ZONELE de detectie ale centralei: ce declanseaza alarma. Tastatura NU e zona — e organ de
# COMANDA (armare/dezarmare cu cod), deci sta pe ramura ei si nu intra la numaratoarea de zone.
_EFRACTIE_INTRARI = ("detector_pir", "contact_magnetic", "buton_panica")
_EFRACTIE_COMANDA = ("tastatura_efractie",)
_EFRACTIE_IESIRI = ("sirena_interioara", "sirena_exterioara")
_RACK = ("nvr", "rack_9u", "sursa_alimentare_cs")

# Textele scurte de pe ramuri (cele lungi raman in legenda, verbatim din planurile de referinta).
_SCURT = {
    "detector_pir": "detector de mișcare",
    "contact_magnetic": "contact magnetic",
    "buton_panica": "buton de panică",
    "tastatura_efractie": "tastatură",
    "sirena_interioara": "sirenă interioară",
    "sirena_exterioara": "sirenă exterioară",
    "centrala_efractie": "centrală de efracție",
    "nvr": "înregistrator video (NVR)",
    "rack_9u": "rack 9U 600×600",
    "sursa_alimentare_cs": "sursă cu acumulator",
}


def _eticheta(el, idx):
    """Eticheta EXACTA de pe planşa: abrevierea + indexul secvential (lipsa la tipurile unice)."""
    ab = _cs_abbr_for(el)
    if not ab:
        return ""
    i = idx.get((el or {}).get("id"))
    return "%s %d" % (ab, i) if i else ab


def _cs_elemente(elements):
    """Elementele de curenti slabi, grupate pe rol, cu eticheta de pe planşa deja calculata."""
    els = [e for e in (elements or [])
           if ((e or {}).get("element_type") or "") in DE._CS_TYPES
           and (e or {}).get("element_type") != "traseu_cs"]
    idx = cs_index_map(els)
    # sortare identica cu numerotarea (sus->jos, apoi stanga->dreapta) -> ordinea de pe schema
    # urmeaza ordinea de pe planşa, deci "PIR 1" e primul si pe hartie
    els.sort(key=lambda d: (float(d.get("y") or 0), float(d.get("x") or 0)))
    def _grup(tipuri):
        return [(e, _eticheta(e, idx)) for e in els if (e.get("element_type") or "") in tipuri]
    return {
        "video": _grup(_VIDEO),
        "intrari": _grup(_EFRACTIE_INTRARI),
        "comanda": _grup(_EFRACTIE_COMANDA),
        "iesiri": _grup(_EFRACTIE_IESIRI),
        "rack": _grup(_RACK),
        "centrala": _grup(("centrala_efractie",)),
        "toate": els,
    }


def _text(page, x, y, s, fs=7.0, bold=False, col=_NEGRU, anchor="left"):
    """Text pe pagina. Diacriticele se transpun la ASCII cu ACELASI helper ca la cartus si la
    planşa (`cartus_swap._txt`): fonturile base-14 (helv/hebo) n-au ă/î/ș/ț, iar fara transpunere
    ies puncte. Asa arata si numele planselor tiparite pe cartus."""
    fn = "hebo" if bold else "helv"
    s = _ascii(s)
    w = fitz.get_text_length(s, fontname=fn, fontsize=fs)
    if anchor == "center":
        x -= w / 2.0
    elif anchor == "right":
        x -= w
    page.insert_text(fitz.Point(x, y), s, fontname=fn, fontsize=fs, color=col)
    return w


def _cablu(page, x0, y0, x1, y1, kind, eticheta=None, fs=5.6):
    """Legatura dintre doua echipamente, in culoarea si stilul cablului REAL de pe planşa."""
    spec = _CS_CABLE.get(kind) or _CS_CABLE[DE._CS_CABLE_DEFAULT]
    sh = page.new_shape()
    sh.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1))
    sh.finish(color=spec["col"], width=1.0, dashes=spec["dash"])
    sh.commit()
    if eticheta:
        _text(page, (x0 + x1) / 2.0, min(y0, y1) - 2.4, eticheta, fs=fs, col=spec["col"],
              anchor="center")


def _spre_cutie(page, x_bus, y_bus, x_cutie, y_cutie, kind, eticheta):
    """Legatura magistrala -> cutie, in L (orizontal, apoi vertical, apoi scurt in cutie).
    Eticheta sta pe segmentul ORIZONTAL, ancorata la stanga langa magistrala — asa nu mai intra
    peste cutie, cum se intampla cand era centrata pe o diagonala."""
    x_mij = x_cutie - 22.0
    _cablu(page, x_bus, y_bus, x_mij, y_bus, kind)
    _cablu(page, x_mij, y_bus, x_mij, y_cutie, kind)
    _cablu(page, x_mij, y_cutie, x_cutie, y_cutie, kind)
    spec = _CS_CABLE.get(kind) or _CS_CABLE[DE._CS_CABLE_DEFAULT]
    _text(page, x_bus + 8, y_bus - 3.5, eticheta, fs=5.6, col=spec["col"])


def _bloc(page, r, titlu, linii, col=_NEGRU):
    """Cutie cu titlu bold + linii de text (RACK, centrala)."""
    page.draw_rect(r, color=col, fill=(1, 1, 1), width=1.1)
    y = r.y0 + 11.0
    _text(page, r.x0 + 6, y, titlu, fs=8.0, bold=True, col=col)
    y += 3.0
    page.draw_line(fitz.Point(r.x0 + 5, y), fitz.Point(r.x1 - 5, y), color=_GRI, width=0.5)
    for ln in linii:
        y += 10.0
        _text(page, r.x0 + 6, y, ln, fs=6.8)


# Constantele casetei de legenda — IDENTICE cu `_draw_legend` (draw_elements.py). Le am nevoie ca sa
# stiu CAT DE LATA iese caseta INAINTE s-o desenez, ca sa asez coloanele la dreapta ei. Un test
# compara latimea calculata aici cu dreptunghiul chiar desenat: daca cineva schimba _draw_legend,
# testul pica, nu schema.
_LEG_PAD, _LEG_TITLE_H, _LEG_ROW_H, _LEG_SYM_W, _LEG_ROW_FS, _LEG_GAP, _LEG_LINE_H =     7.0, 15.0, 17.0, 30.0, 8.0, 5.0, 9.5


def _legenda_dim(rows):
    """(latime, inaltime) casetei de legenda, cu formula din `_draw_legend`."""
    if not rows:
        return 0.0, 0.0
    def _linii(r):
        return r.get("lines") or [r.get("text") or ""]
    txt_w = max([fitz.get_text_length(ln, fontname="helv", fontsize=_LEG_ROW_FS)
                 for r in rows for ln in _linii(r)] + [0.0])
    title_w = fitz.get_text_length("LEGENDA", fontname="hebo", fontsize=9.5)
    w = max(_LEG_PAD + _LEG_SYM_W + _LEG_GAP + txt_w + _LEG_PAD, _LEG_PAD + title_w + _LEG_PAD)
    h = _LEG_PAD + _LEG_TITLE_H + sum(_LEG_ROW_H + (len(_linii(r)) - 1) * _LEG_LINE_H
                                      for r in rows) + _LEG_PAD
    return w, h


_ROW_H = 17.0          # inaltimea unei linii de echipament
_HUB_W = 155.0         # latimea cutiilor RACK / centrala
_COL_GAP = 26.0        # spatiu intre coloane


def _masoara(g):
    """Latimea/inaltimea de care are nevoie desenul, INAINTE de a alege formatul."""
    rows = build_legend_rows(g["toate"], "curenti_slabi")
    leg_w, leg_h = _legenda_dim(rows)
    # cea mai lata linie de echipament: eticheta (bold) + descrierea
    lat = 0.0
    for el, et in g["video"]:
        sp = _CAM_TIPURI[_cam_tip(el)]
        lat = max(lat, _lat_linie(et, "%s · %d° · %d m" % (sp["nume"], sp["unghi"], sp["raza_m"])))
    for el, et in g["intrari"] + g["comanda"] + g["iesiri"]:
        _t = (el.get("element_type") or "")
        lat = max(lat, _lat_linie(et, "%s — ieșire de alarmă" % _SCURT.get(_t, _t)))
    ech_w = 16.0 + lat + 18.0            # simbol + text + spatiu pana la magistrala
    n = len(g["video"]) + len(g["intrari"]) + len(g["comanda"]) + len(g["iesiri"])
    cont_h = 34.0 + n * _ROW_H + (14.0 if g["video"] else 0) + (14.0 if n > len(g["video"]) else 0)
    return {"rows": rows, "leg_w": leg_w, "leg_h": leg_h, "ech_w": ech_w,
            "w": leg_w + _COL_GAP + ech_w + _gap_hub() + _HUB_W,
            "h": max(leg_h, cont_h)}


def _gap_hub():
    """Spatiul dintre magistrala si cutii: cat sa incapa CEA MAI LATA eticheta de cablu, plus
    marginile. Calculat, nu o constanta ghicita — altfel textul intra peste cutie exact cand
    numele cablului e lung (cazul UTP/semnal)."""
    w = max(fitz.get_text_length(_ascii(_CS_CABLE[k]["bom"]), fontname="helv", fontsize=5.6)
            for k in ("utp", "semnal"))
    return max(_COL_GAP, w + 34.0)


def _lat_linie(eticheta, descriere):
    return (fitz.get_text_length(_ascii(eticheta), fontname="hebo", fontsize=7.2) + 5.0
            + fitz.get_text_length(_ascii(descriere), fontname="helv", fontsize=6.4))


def _format(g):
    """FORMAT FIX: A3 orizontal, mereu. Masuratorile raman (ele aseaza coloanele si centreaza
    continutul), dar nu mai decid marimea foii."""
    return ("A3",) + _A3


def build_cs_schema(elements, cartus_firma=None, cartus_proiect=None, plansa_nr=None,
                    subtip=None):
    """Schema sistemului de curenti slabi -> bytes PDF (o pagina), sau None daca proiectul n-are
    echipamente de curenti slabi (gate pe PREZENTA, ca la FV).

    `elements` = plan_elements ale proiectului. Etichetele, simbolurile si randurile de legenda ies
    din ACELEASI functii ca planşa (`cs_index_map`, `_draw_cs`, `build_legend_rows`), deci nu pot
    diverge. `subtip` = sub-tipul comercial: doar numele RACK-ului depinde de el (DDCS / RACK)."""
    g = _cs_elemente(elements)
    if not g["toate"]:
        return None                       # gate: fara echipamente -> fara schema

    m = _masoara(g)
    _fmt, W_MM, H_MM = _format(g)
    W, H = W_MM * MMPT, H_MM * MMPT
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    PAD = _PAD_MM * MMPT
    page.draw_rect(fitz.Rect(PAD, PAD, W - PAD, H - PAD), color=_NEGRU, width=1.2)

    _text(page, W / 2.0, PAD + 26, TITLU, fs=13.0, bold=True, anchor="center")
    _text(page, W / 2.0, PAD + 38, "efracție și supraveghere video — schemă funcțională",
          fs=7.5, col=(0.35, 0.35, 0.35), anchor="center")

    # ── COLOANELE, asezate pe latimile MASURATE (legenda nu mai calca peste echipamente) ──────
    # Pe A3 fix, un sistem mic ar lasa desenul ingramadit sus-stanga -> blocul se CENTREAZA pe
    # spatiul liber: orizontal pe latimea masurata, vertical intre titlu si banda cartusului.
    _SUS = PAD + 50.0                                   # sub titlu + subtitlu
    _JOS = H - PAD - _CARTUS_H_MM * MMPT - 18.0         # deasupra notei si a cartusului
    X_LEG = max(PAD + 12.0, (W - m["w"]) / 2.0)
    Y0 = max(_SUS, _SUS + ((_JOS - _SUS) - m["h"]) / 2.0)
    _draw_legend(page, X_LEG, Y0, m["rows"])
    X_ECH = X_LEG + m["leg_w"] + _COL_GAP          # coloana echipamentelor
    X_BUS = X_ECH + m["ech_w"]                     # magistrala verticala, DUPA text
    X_HUB = min(X_BUS + _gap_hub(), W - PAD - 12.0 - _HUB_W)

    def _linie(el, et, descriere, y):
        """Un echipament: simbol, eticheta de pe planşa, descriere scurta. Intoarce x-ul unde se
        TERMINA textul — ramura de cablu porneste de-acolo, ca sa nu taie prin litere."""
        _draw_cs(page, X_ECH, y + 4, (el.get("element_type") or "doza_cs"), scale=0.62)
        w = _text(page, X_ECH + 15, y + 6.5, et, fs=7.2, bold=True)
        w2 = _text(page, X_ECH + 15 + w + 5, y + 6.5, descriere, fs=6.4, col=(0.35, 0.35, 0.35))
        return X_ECH + 15 + w + 5 + w2 + 6.0

    y = Y0 + 8.0

    # ── SUPRAVEGHERE VIDEO ───────────────────────────────────────────────────────────────────
    y_cam0 = y_cam1 = None
    if g["video"]:
        _text(page, X_ECH - 14, y, "SUPRAVEGHERE VIDEO", fs=8.0, bold=True, col=DE._CS_VIDEO)
        y += 14.0
        y_cam0 = y
        for el, et in g["video"]:
            sp = _CAM_TIPURI[_cam_tip(el)]
            _xe = _linie(el, et, "%s · %d° · %d m" % (sp["nume"], sp["unghi"], sp["raza_m"]), y)
            _cablu(page, _xe, y + 4, X_BUS, y + 4, "utp")            # ramura, DUPA text
            y += _ROW_H
        y_cam1 = y - _ROW_H
        _cablu(page, X_BUS, y_cam0 + 4, X_BUS, y_cam1 + 4, "utp")    # magistrala verticala
        y += 12.0

    # ── DETECTIE EFRACTIE ────────────────────────────────────────────────────────────────────
    y_z0 = y_z1 = None
    n_efr = len(g["intrari"]) + len(g["comanda"]) + len(g["iesiri"])
    if n_efr:
        _text(page, X_ECH - 14, y, "DETECȚIE EFRACȚIE", fs=8.0, bold=True, col=DE._CS_EFRACTIE)
        y += 14.0
        y_z0 = y
        for el, et in g["intrari"]:
            _t = el.get("element_type") or ""
            _xe = _linie(el, et, "%s — zonă" % _SCURT.get(_t, _t), y)
            _cablu(page, _xe, y + 4, X_BUS, y + 4, "semnal")
            y += _ROW_H
        for el, et in g["comanda"]:
            _t = el.get("element_type") or ""
            _xe = _linie(el, et, "%s — comandă (armare/dezarmare)" % _SCURT.get(_t, _t), y)
            _cablu(page, _xe, y + 4, X_BUS, y + 4, "semnal")
            y += _ROW_H
        for el, et in g["iesiri"]:
            _t = el.get("element_type") or ""
            _xe = _linie(el, et, "%s — ieșire de alarmă" % _SCURT.get(_t, _t), y)
            _cablu(page, _xe, y + 4, X_BUS, y + 4, "semnal")
            y += _ROW_H
        y_z1 = y - _ROW_H
        _cablu(page, X_BUS, y_z0 + 4, X_BUS, y_z1 + 4, "semnal")

    # ── RACK (dreapta), in dreptul camerelor ─────────────────────────────────────────────────
    rack_lin = []
    for el, et in g["rack"]:
        _t = el.get("element_type") or ""
        nume = _SCURT.get(_t, _t)
        if _t == "nvr":
            nume += ", 24 canale"
        # eticheta de pe planşa (NVR, RACK, SA) sta PRIMA, ca pe planşa: acelasi obiect, acelasi
        # nume in ambele documente — cine citeste schema regaseste elementul pe desen dupa eticheta
        rack_lin.append("%s — %s" % (et, nume) if et else nume)
    if not rack_lin:
        rack_lin = ["• echipamentele de rețea"]
    rack_h = 24.0 + 10.0 * len(rack_lin)
    y_rack = ((y_cam0 + y_cam1) / 2.0 - rack_h / 2.0 + 4) if g["video"] else Y0 + 22.0
    r_rack = fitz.Rect(X_HUB, y_rack, X_HUB + _HUB_W, y_rack + rack_h)
    _bloc(page, r_rack, DE._DDCS_NAME_COM if DE._e_comercial(subtip) else DE._DDCS_NAME_REZ,
          rack_lin, col=DE._CS_VIDEO)
    if g["video"]:
        _spre_cutie(page, X_BUS, (y_cam0 + y_cam1) / 2.0 + 4, X_HUB, r_rack.y0 + rack_h / 2.0,
                    "utp", _CS_CABLE["utp"]["bom"])

    # ── CENTRALA DE EFRACTIE (sub rack), in dreptul zonelor ──────────────────────────────────
    r_c = None
    if n_efr or g["centrala"]:
        # randurile cu ZERO nu se tiparesc: "0 organe de comandă" nu spune nimic despre proiect
        def _nr(n, sg, pl):
            return None if not n else ("%d %s" % (n, sg if n == 1 else pl))
        c_lin = [x for x in (_nr(len(g["intrari"]), "zonă de detecție", "zone de detecție"),
                             _nr(len(g["iesiri"]), "ieșire de alarmă", "ieșiri de alarmă"),
                             _nr(len(g["comanda"]), "organ de comandă", "organe de comandă"),
                             "acumulator de rezervă") if x]
        c_h = 24.0 + 10.0 * len(c_lin)
        y_c = max(r_rack.y1 + 30.0,
                  ((y_z0 + y_z1) / 2.0 - c_h / 2.0 + 4) if n_efr else r_rack.y1 + 30.0)
        r_c = fitz.Rect(X_HUB, y_c, X_HUB + _HUB_W, y_c + c_h)
        # titlul poarta eticheta de pe planşa (CE), ca sa se regaseasca elementul pe desen
        _et_ce = (g["centrala"][0][1] if g["centrala"] else "CE") or "CE"
        _bloc(page, r_c, "%s — CENTRALĂ EFRACȚIE" % _et_ce, c_lin, col=DE._CS_EFRACTIE)
        if n_efr:
            _spre_cutie(page, X_BUS, (y_z0 + y_z1) / 2.0 + 4, X_HUB, r_c.y0 + c_h / 2.0,
                        "semnal", _CS_CABLE["semnal"]["bom"])
        # 12 V c.c. din sursa din rack -> centrala
        _cablu(page, r_rack.x0 + _HUB_W / 2.0, r_rack.y1, r_c.x0 + _HUB_W / 2.0, r_c.y0,
               "alimentare")
        _text(page, r_rack.x0 + _HUB_W / 2.0 + 6, (r_rack.y1 + r_c.y0) / 2.0,
              "%s · 12 V c.c." % _CS_CABLE["alimentare"]["bom"], fs=5.6,
              col=_CS_CABLE["alimentare"]["col"])

    # ── ALIMENTAREA 230 V: circuitul dedicat din tabloul electric ────────────────────────────
    y_al = r_rack.y0 - 24.0
    _text(page, X_HUB + _HUB_W / 2.0, y_al - 4.0, "circuit dedicat 230 V din tabloul electric",
          fs=6.4, col=(0.35, 0.35, 0.35), anchor="center")
    sh = page.new_shape()
    sh.draw_line(fitz.Point(X_HUB + _HUB_W / 2.0, y_al),
                 fitz.Point(X_HUB + _HUB_W / 2.0, r_rack.y0))
    sh.finish(color=_NEGRU, width=1.2)
    sh.commit()

    # ── NOTA de subsol (deasupra cartusului) ─────────────────────────────────────────────────
    _text(page, PAD + 12, H - PAD - _CARTUS_H_MM * MMPT - 10,
          "Echipamentele sunt alimentate în joasă tensiune, 12 V c.c., din sursele cu acumulator "
          "montate în rack. Numerele de pe schemă sunt cele de pe planșa de curenți slabi.",
          fs=6.2, col=(0.35, 0.35, 0.35))

    # ── CARTUS UNIFICAT + numarul REAL al planşei (acelasi lant ca schema FV) ────────────────
    raw = doc.tobytes(deflate=True)
    doc.close()
    try:
        import cartus_swap as _cs
        d2 = fitz.open(stream=raw, filetype="pdf")
        pg = d2[0]
        x1 = W - _PAD_MM * MMPT
        y1 = H - _PAD_MM * MMPT
        bbox = fitz.Rect(x1 - _CARTUS_W_MM * MMPT, y1 - _CARTUS_H_MM * MMPT, x1, y1)
        cf = dict(cartus_firma or {})
        cp = dict(cartus_proiect or {})
        nr = plansa_nr or cp.get("plansa_nr") or ""
        title_rect, title_base, plansa_box = _cs._draw_cartus(pg, bbox, cf, cp, nr, None, "-")
        try:
            d2.set_metadata({**(d2.metadata or {}),
                             "keywords": "zy_cartus_plansa=%.1f,%.1f,%.1f,%.1f|"
                                         "zy_cartus_title=%.1f,%.1f,%.1f,%.1f|%s"
                                         % (plansa_box[0], plansa_box[1], plansa_box[2], plansa_box[3],
                                            title_rect[0], title_rect[1], title_rect[2], title_rect[3],
                                            title_base)})
        except Exception:
            pass
        out = d2.tobytes(deflate=True)
        d2.close()
        rs = _cs.restamp_plansa(out, nr, TITLU)
        if rs.get("success") and rs.get("pdf_base64"):
            import base64 as _b64
            return _b64.b64decode(rs["pdf_base64"])
        return out
    except Exception:
        return raw      # fail-safe: schema FARA cartus e mai buna decat lipsa schemei
