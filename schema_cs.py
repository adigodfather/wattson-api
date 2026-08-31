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
# A TREIA ramura: distributia de date si TV. Prizele sunt PASIVE (nu consuma), dar converg la acelasi
# punct de distributie — rack-ul — deci intra pe schema ca o coloana proprie, nu doar in legenda.
_DATE_TV = ("priza_date", "priza_tv", "priza_mixta")

# Textele scurte de pe ramuri (cele lungi raman in legenda, verbatim din planurile de referinta).
_SCURT = {
    "detector_pir": "detector de mișcare",
    "contact_magnetic": "contact magnetic",
    "buton_panica": "buton de panică",
    "tastatura_efractie": "tastatură",
    "sirena_interioara": "sirenă interioară",
    "sirena_exterioara": "sirenă exterioară",
    "centrala_efractie": "centrală de efracție",
    # fara „(NVR)" in text: eticheta de planşa scrie deja NVR chiar in fata randului, iar latimea
    # castigata tine treapta de canale pe acelasi rand („64 canale (fără PoE)" se rupea altfel)
    "nvr": "înregistrator video",
    "rack_9u": "rack 9U 600×600",
    "sursa_alimentare_cs": "sursă cu acumulator",
    "priza_date": "priză de date RJ45 cat. 5e/6",
    "priza_tv": "priză TV coaxială 75 ohm",     # „ohm" scris, nu Ω: fontul base14 n-are simbolul
    "priza_mixta": "priză mixtă date + TV",
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
        "date_tv": _grup(_DATE_TV),
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


def _peste_coloane(page, x_bus, y_bus, x_cutie, y_cutie, y_sus, kind, eticheta):
    """Legatura coloanei DIN STANGA spre cutie, rutata PE DEASUPRA celeilalte coloane: sus din
    magistrala, orizontal peste capul coloanei vecine, apoi jos in cutie. Ruta directa ar fi trecut
    ORIZONTAL prin randurile coloanei din dreapta, taind prin etichete."""
    x_mij = x_cutie - 22.0
    _cablu(page, x_bus, y_bus, x_bus, y_sus, kind)
    _cablu(page, x_bus, y_sus, x_mij, y_sus, kind)
    _cablu(page, x_mij, y_sus, x_mij, y_cutie, kind)
    _cablu(page, x_mij, y_cutie, x_cutie, y_cutie, kind)
    spec = _CS_CABLE.get(kind) or _CS_CABLE[DE._CS_CABLE_DEFAULT]
    _text(page, x_bus + 8, y_sus - 3.5, eticheta, fs=5.6, col=spec["col"])


def _incape_in_cutie(linii, lat):
    """Rupe randurile mai late decat cutia. Latimea se MASOARA cu fontul real, nu se estimeaza —
    prima varianta a randului de cascada („splittere TV pasive in cascada: 2 iesiri, 2 x 8 iesiri")
    iesea pur si simplu peste chenarul cutiei. Randurile care incap raman NEATINSE, deci cutiile de
    pana acum arata identic; garda pazeste si randurile care s-ar adauga de acum inainte."""
    out = []
    for ln in linii:
        cur = ""
        for cuv in _ascii(ln).split(" "):
            _t = ("%s %s" % (cur, cuv)).strip()
            if cur and fitz.get_text_length(_t, fontname="helv", fontsize=6.8) > lat:
                out.append(cur)
                cur = "   %s" % cuv          # continuarea, indentata sub randul ei
            else:
                cur = _t
        if cur:
            out.append(cur)
    return out


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


def _legenda_split(rows):
    """Imparte randurile de legenda in DOUA coloane, pe inaltime egala. CONTINUTUL nu se atinge —
    se cheama `_draw_legend` de doua ori, cu jumatati. Treapta asta se foloseste DOAR cand
    echipamentele nu incap deasupra unei legende pe o singura coloana."""
    def _h(r):
        return _LEG_ROW_H + (len(r.get("lines") or [r.get("text") or ""]) - 1) * _LEG_LINE_H
    total = sum(_h(r) for r in rows)
    acc, taie = 0.0, len(rows)
    for i, r in enumerate(rows):
        acc += _h(r)
        if acc >= total / 2.0:
            taie = i + 1
            break
    return rows[:taie], rows[taie:]


def _gap_hub():
    """Spatiul dintre magistrala si cutii: cat sa incapa CEA MAI LATA eticheta de cablu, plus
    marginile. Calculat, nu o constanta ghicita — altfel textul intra peste cutie exact cand
    numele cablului e lung (cazul UTP/semnal/coaxial)."""
    w = max(fitz.get_text_length(_ascii(_CS_CABLE[k]["bom"]), fontname="helv", fontsize=5.6)
            for k in ("utp", "semnal", "coax_tv"))
    return max(_COL_GAP, w + 34.0)


def _lat_linie(eticheta, descriere):
    return (fitz.get_text_length(_ascii(eticheta), fontname="hebo", fontsize=7.2) + 5.0
            + fitz.get_text_length(_ascii(descriere), fontname="helv", fontsize=6.4))


def _lat_grup(randuri):
    """Cea mai lata linie dintr-un grup: eticheta (bold) + descrierea (normal)."""
    return max([_lat_linie(et, d) for _el, et, d in randuri] + [0.0])


def _grupuri(g):
    """Coloanele schemei, in ordinea de citit. Fiecare grup: cheie, titlu, culoare, tipul de cablu
    cu care se leaga si randurile (element, eticheta, descriere). Grupurile GOALE nu apar.

    Generalizat la N coloane (nu doua hardcodate): a treia ramura — distributia de date si TV — s-a
    adaugat fara cazuri speciale, iar a patra s-ar adauga la fel."""
    out = []
    if g["video"]:
        out.append({"cheie": "video", "titlu": "SUPRAVEGHERE VIDEO", "col": DE._CS_VIDEO,
                    "kind": "utp", "cutie": "rack",
                    "randuri": [(el, et, "%s · %d° · %d m" % (
                        _CAM_TIPURI[_cam_tip(el)]["nume"], _CAM_TIPURI[_cam_tip(el)]["unghi"],
                        _CAM_TIPURI[_cam_tip(el)]["raza_m"])) for el, et in g["video"]]})
    if g["intrari"] or g["comanda"] or g["iesiri"]:
        r = ([(el, et, "%s — zonă" % _SCURT.get(el.get("element_type") or "", ""))
              for el, et in g["intrari"]]
             + [(el, et, "%s — comandă (armare/dezarmare)"
                 % _SCURT.get(el.get("element_type") or "", "")) for el, et in g["comanda"]]
             + [(el, et, "%s — ieșire de alarmă" % _SCURT.get(el.get("element_type") or "", ""))
                for el, et in g["iesiri"]])
        out.append({"cheie": "efractie", "titlu": "DETECȚIE EFRACȚIE", "col": DE._CS_EFRACTIE,
                    "kind": "semnal", "cutie": "centrala", "randuri": r})
    if g["date_tv"]:
        # cablul ramurii: coax daca sunt DOAR prize TV; altfel UTP (datele si mixtele merg pe UTP)
        _doar_tv = all((el.get("element_type") or "") == "priza_tv" for el, _ in g["date_tv"])
        out.append({"cheie": "date_tv", "titlu": "DISTRIBUȚIE DATE ȘI TV", "col": DE._CS_DATE_TV,
                    "kind": "coax_tv" if _doar_tv else "utp", "cutie": "rack",
                    "randuri": [(el, et, _SCURT.get(el.get("element_type") or "", ""))
                                for el, et in g["date_tv"]]})
    return out


def _masoara(g):
    """Masuratorile pe care se aseaza layout-ul.

    LEGENDA sta JOS-STANGA (decizia Dan), ca zona de sus sa ramana libera pentru echipamente. Latimea
    castigata se investeste in COLOANE ALATURATE (una per grup): inaltimea devine cea a coloanei celei
    mai lungi, nu suma lor. Trei trepte, in ordine: (1) coloane alaturate, (2) legenda pe doua
    coloane, (3) sub-coloane in grupul prea inalt."""
    rows = build_legend_rows(g["toate"], "curenti_slabi")
    leg_w, leg_h = _legenda_dim(rows)
    grupuri = _grupuri(g)
    for gr in grupuri:
        gr["lat"] = 29.0 + _lat_grup(gr["randuri"]) + 18.0
        gr["n"] = len(gr["randuri"])

    _H = 297.0 * MMPT
    _LAT_MAX = 420.0 * MMPT - 2 * _PAD_MM * MMPT - 24.0
    _buget = (_H - _PAD_MM * MMPT - 12.0) - (_PAD_MM * MMPT + 62.0) - 20.0 - 28.0

    def _sub(n, buget):
        """Cate sub-coloane trebuie ca grupul de `n` randuri sa incapa in `buget` pe inaltime."""
        if n <= 0:
            return 1
        for k in (1, 2, 3):
            if math.ceil(n / float(k)) * _ROW_H <= buget:
                return k
        return 3               # peste 3 se strica latimea; apelantul semnaleaza ca nu incape

    def _asaza(bug):
        for gr in grupuri:
            gr["s"] = _sub(gr["n"], bug)
        h = 14.0 + max([math.ceil(gr["n"] / float(gr["s"])) for gr in grupuri] or [0]) * _ROW_H + 14.0
        w = sum(gr["lat"] * gr["s"] + _COL_GAP * (gr["s"] - 1) for gr in grupuri)             + _COL_GAP * max(0, len(grupuri) - 1) + _gap_hub() + _HUB_W
        return h, w

    cont_h, cont_w = _asaza(_buget - leg_h)
    # TREAPTA 2: legenda pe doua coloane, daca echipamentele nu incap deasupra ei
    leg2 = None
    if cont_h > _buget - leg_h:
        a_, b_ = _legenda_split(rows)
        if a_ and b_:
            w1, h1 = _legenda_dim(a_)
            w2, h2 = _legenda_dim(b_)
            leg2 = {"a": a_, "b": b_, "w1": w1, "w": w1 + 14.0 + w2, "h": max(h1, h2)}
            leg_h, leg_w = leg2["h"], leg2["w"]
            cont_h, cont_w = _asaza(_buget - leg_h)
    return {"rows": rows, "leg_w": leg_w, "leg_h": leg_h, "leg2": leg2, "grupuri": grupuri,
            # Semnaleaza daca nu incape — pe INALTIME (nici cu 3 sub-coloane) SAU pe LATIME.
            # Apelantul scrie o nota vizibila pe planşa; nu se lasa niciodata suprapunere tacuta.
            "incape": cont_h <= _buget - leg_h and cont_w <= _LAT_MAX,
            "w": cont_w, "h": cont_h}


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
    # subtitlul spune ce contine CHIAR proiectul: la o casa cu doar prize de date n-are ce cauta
    # „efractie si supraveghere video"
    _parti = [x for x in (("efracție" if any(gr["cheie"] == "efractie" for gr in m["grupuri"]) else None),
                          ("supraveghere video" if any(gr["cheie"] == "video" for gr in m["grupuri"]) else None),
                          ("distribuție date și TV" if any(gr["cheie"] == "date_tv" for gr in m["grupuri"]) else None))
              if x]
    _sub_t = (" și ".join([", ".join(_parti[:-1]), _parti[-1]]) if len(_parti) > 1 else
              (_parti[0] if _parti else "curenți slabi"))
    _text(page, W / 2.0, PAD + 38, "%s — schemă funcțională" % _sub_t,
          fs=7.5, col=(0.35, 0.35, 0.35), anchor="center")

    # ── LEGENDA: JOS-STANGA (decizia Dan) ────────────────────────────────────────────────────
    # Sta la STANGA cartusului (care-i ancorat dreapta-jos), deci nu se bat pe acelasi loc. Zona de
    # sus ramane in intregime a echipamentelor.
    X_LEG = PAD + 12.0
    Y_LEG = H - PAD - 12.0 - m["leg_h"]
    if m["leg2"]:
        _draw_legend(page, X_LEG, Y_LEG, m["leg2"]["a"])
        _draw_legend(page, X_LEG + m["leg2"]["w1"] + 14.0, Y_LEG, m["leg2"]["b"])
    else:
        _draw_legend(page, X_LEG, Y_LEG, m["rows"])
    # Fraza de 12 V c.c. e ADEVARATA doar cand exista echipamente alimentate. Prizele de date si TV
    # sunt PASIVE: pe o schema numai cu ele n-ar exista nici sursa cu acumulator, nici consum — deci
    # nota s-ar contrazice cu propriul desen. Acelasi gate ca in memoriu si in caietul de sarcini.
    _efr = any(gr["cheie"] == "efractie" for gr in m["grupuri"])
    _vid = any(gr["cheie"] == "video" for gr in m["grupuri"])
    # De cand camerele merg pe PoE din inregistrator, „echipamentele" nu mai stau toate pe 12 V:
    # doar efractia. Cu AMBELE sisteme pe foaie fraza trebuie sa le desparta, altfel schema ar
    # sustine ca si camerele sunt alimentate din sursele cu acumulator — ceea ce contrazice
    # magistrala UTP desenata deasupra ei. Cu DOAR efractie, textul ramane cel dinainte, cuvant cu
    # cuvant: acolo „echipamentele" inseamna fara echivoc echipamentele de efractie.
    if _efr and _vid:
        _nota = ("Echipamentele de efracție sunt alimentate în joasă tensiune, 12 V c.c., din "
                 "sursele cu acumulator montate în rack, iar camerele prin PoE, din înregistrator. ")
    elif _efr:
        _nota = ("Echipamentele sunt alimentate în joasă tensiune, 12 V c.c., din sursele cu "
                 "acumulator montate în rack. ")
    elif _vid:
        _nota = "Camerele sunt alimentate prin PoE, din înregistratorul montat în rack. "
    else:
        _nota = ""
    _text(page, X_LEG, Y_LEG - 8.0,
          _nota + "Numerele de pe schemă sunt cele de pe planșa de curenți slabi.",
          fs=6.2, col=(0.35, 0.35, 0.35))

    # ── ECHIPAMENTELE: sus, pe toata latimea, in COLOANE ALATURATE (una per grup) ────────────
    _SUS = PAD + 62.0                       # sub titlu + subtitlu
    _JOS = Y_LEG - 20.0                     # deasupra notei si a legendei
    X0 = max(PAD + 12.0, (W - m["w"]) / 2.0)
    Y0 = max(_SUS, _SUS + ((_JOS - _SUS) - m["h"]) / 2.0)
    if not m["incape"]:
        # nu se ascunde o suprapunere: se scrie pe planşa ca sistemul depaseste ce incape pe A3
        _text(page, X0, Y0 - 14.0,
              "ATENȚIE: sistemul depășește ce încape pe o planșă A3 — se recomandă împărțirea pe "
              "planșe separate (efracție / video / date).", fs=6.6, col=(0.80, 0.15, 0.15))

    def _coloana(x, gr, y_start):
        """Un grup, in `gr['s']` sub-coloane alaturate. Fiecare sub-coloana are magistrala ei;
        magistralele se unesc pe o linie orizontala la mijloc, de unde pleaca legatura spre cutie.
        Intoarce (x_magistrala_dreapta, y_prim, y_ultim)."""
        _text(page, x, y_start, gr["titlu"], fs=8.0, bold=True, col=gr["col"])
        per = int(math.ceil(gr["n"] / float(gr["s"])))
        y_prim = y_start + 14.0
        y_ultim = y_prim
        buses = []
        for k in range(gr["s"]):
            felie = gr["randuri"][k * per:(k + 1) * per]
            if not felie:
                continue
            xk = x + k * (gr["lat"] + _COL_GAP)
            x_bus = xk + gr["lat"] - 18.0
            y = y_prim
            for el, et, descriere in felie:
                _draw_cs(page, xk + 8, y + 4, (el.get("element_type") or "doza_cs"), scale=0.62)
                w1 = _text(page, xk + 23, y + 6.5, et, fs=7.2, bold=True)
                w2 = _text(page, xk + 23 + w1 + 5, y + 6.5, descriere, fs=6.4,
                           col=(0.35, 0.35, 0.35))
                _cablu(page, xk + 23 + w1 + 5 + w2 + 6.0, y + 4, x_bus, y + 4, gr["kind"])
                y += _ROW_H
            _cablu(page, x_bus, y_prim + 4, x_bus, y - _ROW_H + 4, gr["kind"])
            buses.append(x_bus)
            y_ultim = max(y_ultim, y - _ROW_H)
        if len(buses) > 1:      # colector orizontal intre magistralele sub-coloanelor
            _cablu(page, buses[0], (y_prim + y_ultim) / 2.0 + 4, buses[-1],
                   (y_prim + y_ultim) / 2.0 + 4, gr["kind"])
        return buses[-1], y_prim, y_ultim

    x = X0
    for gr in m["grupuri"]:
        gr["geom"] = _coloana(x, gr, Y0)
        x += gr["lat"] * gr["s"] + _COL_GAP * (gr["s"] - 1) + _COL_GAP
    X_HUB = min(x - _COL_GAP + _gap_hub(), W - PAD - 12.0 - _HUB_W)

    _spre_rack = [gr for gr in m["grupuri"] if gr["cutie"] == "rack"]
    _spre_centrala = [gr for gr in m["grupuri"] if gr["cutie"] == "centrala"]

    # ── RACK (dreapta), in dreptul primului grup care se leaga la el ─────────────────────────
    rack_lin = []
    for el, et in g["rack"]:
        _t = el.get("element_type") or ""
        nume = _SCURT.get(_t, _t)
        if _t == "nvr":
            # dimensionat pe camerele plasate — aceeasi sursa ca legenda si ca lista de cantitati.
            # Forma SCURTA: in cutie incap ~40 de caractere, iar textul lung al legendei ar fi rupt
            # randul in doua fara sa adauge nimic (detaliile stau oricum in legenda).
            _tn = DE.cs_nvr(len(g["video"]))
            nume += ", %d canale%s" % (_tn["canale"], " PoE" if _tn["poe"] else " (fără PoE)")
        # eticheta de pe planşa (NVR, RACK, SA) sta PRIMA, ca pe planşa: acelasi obiect, acelasi
        # nume in ambele documente — cine citeste schema regaseste elementul pe desen dupa eticheta
        rack_lin.append("%s — %s" % (et, nume) if et else nume)
    if not rack_lin:
        rack_lin = ["punct de distribuție (rack / patch panel)"]
    # ECHIPAMENTUL DE DISTRIBUTIE derivat din prize (switch + splitter): nu-s elemente de plan, dar
    # stau FIZIC in rack — deci se citesc din cutia lui, acolo unde inginerul ii cauta. Fara eticheta
    # de planşa in fata (n-au una: nu-s desenate pe plan).
    _comp = {}
    for _e in g["toate"]:
        _t = (_e or {}).get("element_type") or ""
        _comp[_t] = _comp.get(_t, 0) + 1
    _n_date, _n_tv = DE.cs_prize_dtv(_comp)
    _porturi = DE.cs_switch_porturi(_n_date)
    if _porturi:
        rack_lin.append("switch %d porturi — distribuție date" % _porturi)
    _spl = DE.cs_splitter_bom(_n_tv)
    if _spl:
        if sum(n for _, n in _spl) == 1:
            rack_lin.append("splitter TV pasiv %d ieșiri" % _spl[0][0])
        else:
            # cascada (peste 12 prize) pe DOUA randuri, nu pe unul singur: intr-unul singur textul
            # depasea chenarul cu ~4 pt. `_spl` vine sortat crescator -> primul e capul de cascada.
            _cap, _ram = _spl[0], _spl[-1]
            rack_lin.append("splittere TV pasive, în cascadă:")
            rack_lin.append("   %d ieșiri (cap) + %d × %d ieșiri (ramuri)"
                            % (_cap[0], _ram[1], _ram[0]))
    rack_lin = _incape_in_cutie(rack_lin, _HUB_W - 12.0)
    rack_h = 24.0 + 10.0 * len(rack_lin)
    _g0 = _spre_rack[0] if _spre_rack else None
    y_rack = ((_g0["geom"][1] + _g0["geom"][2]) / 2.0 - rack_h / 2.0 + 4) if _g0 else Y0 + 14.0
    r_rack = fitz.Rect(X_HUB, y_rack, X_HUB + _HUB_W, y_rack + rack_h)
    _bloc(page, r_rack, DE._DDCS_NAME_COM if DE._e_comercial(subtip) else DE._DDCS_NAME_REZ,
          rack_lin, col=DE._CS_VIDEO)
    for gr in _spre_rack:
        _bx, _y1, _y2 = gr["geom"]
        _ultim = gr is m["grupuri"][-1]
        _f = _spre_cutie if _ultim else _peste_coloane
        if _ultim:
            _f(page, _bx, (_y1 + _y2) / 2.0 + 4, X_HUB, r_rack.y0 + rack_h / 2.0,
               gr["kind"], _CS_CABLE[gr["kind"]]["bom"])
        else:
            _f(page, _bx, (_y1 + _y2) / 2.0 + 4, X_HUB, r_rack.y0 + rack_h / 2.0, Y0 - 8.0,
               gr["kind"], _CS_CABLE[gr["kind"]]["bom"])

    # ── CENTRALA DE EFRACTIE (sub rack) ──────────────────────────────────────────────────────
    r_c = None
    if _spre_centrala or g["centrala"]:
        def _nr(n, sg, pl):
            return None if not n else ("%d %s" % (n, sg if n == 1 else pl))
        c_lin = [x_ for x_ in (_nr(len(g["intrari"]), "zonă de detecție", "zone de detecție"),
                               _nr(len(g["iesiri"]), "ieșire de alarmă", "ieșiri de alarmă"),
                               _nr(len(g["comanda"]), "organ de comandă", "organe de comandă"),
                               "acumulator de rezervă") if x_]
        c_lin = _incape_in_cutie(c_lin, _HUB_W - 12.0)
        c_h = 24.0 + 10.0 * len(c_lin)
        _ge = _spre_centrala[0]["geom"] if _spre_centrala else None
        y_c = max(r_rack.y1 + 30.0,
                  ((_ge[1] + _ge[2]) / 2.0 - c_h / 2.0 + 4) if _ge else r_rack.y1 + 30.0)
        r_c = fitz.Rect(X_HUB, y_c, X_HUB + _HUB_W, y_c + c_h)
        _et_ce = (g["centrala"][0][1] if g["centrala"] else "CE") or "CE"
        _bloc(page, r_c, "%s — CENTRALĂ EFRACȚIE" % _et_ce, c_lin, col=DE._CS_EFRACTIE)
        for gr in _spre_centrala:
            _bx, _y1, _y2 = gr["geom"]
            _ultim = gr is m["grupuri"][-1]
            if _ultim:
                _spre_cutie(page, _bx, (_y1 + _y2) / 2.0 + 4, X_HUB, r_c.y0 + c_h / 2.0,
                            gr["kind"], _CS_CABLE[gr["kind"]]["bom"])
            else:
                _peste_coloane(page, _bx, (_y1 + _y2) / 2.0 + 4, X_HUB, r_c.y0 + c_h / 2.0,
                               Y0 - 8.0, gr["kind"], _CS_CABLE[gr["kind"]]["bom"])
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
