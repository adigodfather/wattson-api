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


_PAS_STEA = 2.6        # distanta intre liniile paralele ale unei stele (linia are 1,0 pt)
# Spatiul dintre benzile a doua fascicule vecine. Nu-i ornament: acolo se scrie eticheta „N x Cablu
# ...", asa ca trebuie sa incapa un rand de 5,6 pt plus aer — la 6 pt eticheta unui fascicul ajungea
# peste banda celui de deasupra.
_GAP_FASC = 13.0
_PAS_STEA_MIN = 1.5    # sub atat liniile se lipesc si banda nu se mai citeste ca fire distincte


def _pas_stea(n, spatiu):
    """Pasul dintre liniile stelei: cel nominal, stramtat daca N linii n-ar incapea in `spatiu`."""
    if n <= 1:
        return _PAS_STEA
    return max(_PAS_STEA_MIN, min(_PAS_STEA, spatiu / float(n - 1)))


def _rezerva_fascicule(benzi):
    """Inaltimea ceruta DEASUPRA coloanelor de benzile fasciculelor care trec peste vecini.
    Se calculeaza intr-un singur loc fiindca intra si in bugetul de inaltime, si in asezare: cand
    lipsea din buget, banda de jos coborea peste caseta de legenda si taia randuri de text."""
    _t = 0.0
    for _banda in benzi:
        _tot_f = sum(gr["s"] for gr in _banda)
        _k = 0
        for gr in _banda:
            _nf = int(math.ceil(gr["n"] / float(gr["s"])))
            for _ in range(gr["s"]):
                _k += 1
                if _k < _tot_f:            # ultimul fascicul al benzii pleaca direct la dreapta
                    _t += _pas_stea(_nf, 46.0) * _nf + _GAP_FASC
    return _t


def _intrari_cutie(r, n, ocupate=0, total=None):
    """Punctele de intrare in cutie, cate unul per cablu — asa arata un patch panel: N porturi, nu
    o singura bornă. Se imparte inaltimea utila a cutiei; `ocupate`/`total` permit doua grupuri
    (video + date) sa intre in ACEEASI cutie fara sa se calce."""
    _t = total or n
    _h = r.height - 10.0
    return [r.y0 + 5.0 + _h * (ocupate + i + 1) / float(_t + 1) for i in range(n)]


def _stea(page, puncte, x_cutie, intrari, kind, eticheta, y_sus=None, x_lane=None,
          off=0):
    """CABLARE IN STEA: cate o linie PROPRIE de la fiecare element pana in cutie.

    `puncte` = [(x_capat_text, y)] de sus in jos; `intrari` = ordonatele de intrare in cutie.
    Ordinea lanelor nu-i cosmetica — e ALEASA ca liniile sa nu se taie intre ele:
      · coborarea spre cutie: randul de SUS pica cel mai APROAPE de cutie (x_mij scade cu indexul),
        asa orizontala fiecarui rand se opreste inainte de verticalele randurilor de deasupra;
      · ruta PE DEASUPRA coloanelor vecine (grupurile care nu-s ultimul): randul de sus ia laneul
        cel mai din interior si banda cea mai de sus, iar cele de sub el ies pe rand spre exterior.
    Verificat pe desen, nu pe rationament: un test numara intersectiile segmentelor."""
    n = len(puncte)
    if not n:
        return
    _sp = _pas_stea(n, 46.0)
    if y_sus is None:
        # ORDINEA COBORARILOR, aleasa ca liniile sa nu se taie: cine are de mers cel mai mult pe
        # verticala pica cel mai APROAPE de cutie. Randurile de deasupra cutiei coboara, cele de sub
        # ea urca, iar orizontala unui rand trece PESTE toate laneurile din stanga ei — de-aia nu
        # merge o ordine simpla dupa indice (prima varianta avea 68 de incrucisari la 20 de camere).
        _ord = sorted(range(n), key=lambda i: -abs(puncte[i][1] - intrari[i]))
        _x_mij = [0.0] * n
        for _r, _i in enumerate(_ord):
            _x_mij[_i] = x_cutie - 14.0 - (off + _r) * _sp
    else:
        # ruta peste coloane: toate liniile vin de sus, din banda, deci coboara toate — ordinea
        # simpla dupa indice e cea corecta aici
        _x_mij = [x_cutie - 14.0 - (off + i) * _sp for i in range(n)]
    if y_sus is None:
        for i, ((xe, y), y_in) in enumerate(zip(puncte, intrari)):
            _cablu(page, xe, y, _x_mij[i], y, kind)
            _cablu(page, _x_mij[i], y, _x_mij[i], y_in, kind)
            _cablu(page, _x_mij[i], y_in, x_cutie, y_in, kind)
    else:
        _lane = [(x_lane or puncte[0][0]) + i * _sp for i in range(n)]
        _band = [y_sus - (n - 1 - i) * _sp for i in range(n)]
        for i, ((xe, y), y_in) in enumerate(zip(puncte, intrari)):
            _cablu(page, xe, y, _lane[i], y, kind)
            _cablu(page, _lane[i], y, _lane[i], _band[i], kind)
            _cablu(page, _lane[i], _band[i], _x_mij[i], _band[i], kind)
            _cablu(page, _x_mij[i], _band[i], _x_mij[i], y_in, kind)
            _cablu(page, _x_mij[i], y_in, x_cutie, y_in, kind)
    if eticheta:
        spec = _CS_CABLE.get(kind) or _CS_CABLE[DE._CS_CABLE_DEFAULT]
        _y = (y_sus - (n - 1) * _sp - 4.0) if y_sus is not None else (puncte[0][1] - 5.0)
        _text(page, puncte[0][0] + 8, _y, "%d × %s" % (n, eticheta), fs=5.6, col=spec["col"])


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
    # DOUA BENZI, dupa cutia in care intra grupul: sus cele care merg la rack (video, date/TV), jos
    # efractia, care isi duce fasciculul pe sub celelalte pana la centrala. Asa fiecare fascicul
    # ajunge la cutia lui fara sa traverseze alt grup — inainte, toate stateau pe acelasi rand si
    # liniile treceau peste textul vecinilor.
    for gr in grupuri:
        gr["n"] = len(gr["randuri"])
    _sus, _jos = [], []

    def _benzi(doua):
        """Imparte grupurile pe benzi si recalculeaza latimile (laneurile depind de rutare)."""
        del _sus[:], _jos[:]
        if doua:
            _sus.extend(gr for gr in grupuri if gr["cutie"] == "rack")
            _jos.extend(gr for gr in grupuri if gr["cutie"] != "rack")
        else:
            _sus.extend(grupuri)            # o singura banda: toate coloanele pe acelasi rand
        for _b in (_sus, _jos):
            for gr in _b:
                gr["banda"] = "sus" if _b is _sus else "jos"
                # ULTIMUL grup din banda pleaca direct la dreapta, spre cutia lui; cele dinaintea
                # lui se ruteaza pe deasupra si au nevoie de laneuri in marginea coloanei.
                gr["direct"] = gr is _b[-1]
                _lane = 0.0 if gr["direct"] else _pas_stea(gr["n"], 46.0) * gr["n"]
                gr["lat"] = 29.0 + _lat_grup(gr["randuri"]) + 18.0 + _lane

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

    _GAP_BENZI = 30.0                   # minimul dintre banda de sus si cea de jos

    _pas = [_ROW_H]                     # pasul pe verticala, adaptiv (vezi mai jos)

    def _rb(_banda):
        return max([math.ceil(gr["n"] / float(gr["s"])) for gr in _banda]) if _banda else 0

    def _hb(_banda):
        return 28.0 + _rb(_banda) * _pas[0] if _banda else 0.0

    def _wb():
        # `default=0` nu-i decorativ: un plan care are DOAR rack si NVR (fara camere, prize sau
        # detectoare) n-are niciun grup, deci ambele benzi sunt goale — si atunci max() crapa.
        return max([sum(gr["lat"] * gr["s"] + _COL_GAP * (gr["s"] - 1) for gr in _banda)
                    + _COL_GAP * max(0, len(_banda) - 1) for _banda in (_sus, _jos) if _banda],
                   default=0.0)

    def _asaza(bug):
        """Inaltimea si latimea continutului, pe cele doua benzi.

        SUB-COLOANELE sunt ULTIMA solutie, nu prima: se pornea de la un buget impartit intre benzi,
        iar asta le declansa degeaba — o coloana de 20 de camere ajungea pe doua sub-coloane desi
        incapea intreaga, si atunci banda depasea latimea foii. Acum se incearca intai o singura
        sub-coloana peste tot, iar daca inaltimea nu ajunge se sparge DOAR grupul cel mai inalt, si
        numai cat timp latimea o permite."""
        _gap = _GAP_BENZI if (_sus and _jos) else 0.0
        _lat_col = _LAT_MAX - _gap_hub() - _HUB_W
        for gr in grupuri:
            gr["s"] = 1
        while _hb(_sus) + _hb(_jos) + _gap > bug:
            _cand = max([gr for gr in grupuri if gr["s"] < 3],
                        key=lambda z: math.ceil(z["n"] / float(z["s"])), default=None)
            if _cand is None:
                break
            _cand["s"] += 1
            if _wb() > _lat_col:            # nu incape pe latime -> se revine si se semnaleaza
                _cand["s"] -= 1
                break
        # RASFIRAREA: daca a ramas loc pe inaltime, randurile se departeaza intre ele in loc sa
        # lase foaia goala la mijloc. Plafonat la 1,55x — peste atat eticheta si simbolul raman
        # mici intr-un rand prea inalt si desenul se rareste fara sa castige nimic.
        _pas[0] = _ROW_H
        _r = _rb(_sus) + _rb(_jos)
        if _r:
            _sp = bug - (_hb(_sus) + _hb(_jos) + _gap + _rezerva_fascicule((_sus, _jos)))
            _pas[0] = max(_ROW_H, min(_ROW_H * 1.55, _ROW_H + _sp * 0.55 / _r))
        h_sus, h_jos = _hb(_sus), _hb(_jos)
        return (h_sus + h_jos + _gap + _rezerva_fascicule((_sus, _jos)),
                _wb() + _gap_hub() + _HUB_W, h_sus, h_jos)

    def _incearca(bug):
        """DOUA benzi daca incap; altfel toate coloanele pe UN rand, ca inainte. Doua benzi asaza
        mai frumos (fiecare fascicul are culoarul lui), dar cer mai multa inaltime — la un sistem de
        peste 40 de elemente inaltimea e exact ce lipseste, si atunci un rand e alegerea corecta."""
        _benzi(True)
        _r = _asaza(bug)
        if _r[0] > bug:
            _benzi(False)
            _r = _asaza(bug)
        return _r

    cont_h, cont_w, h_sus, h_jos = _incearca(_buget - leg_h)
    # TREAPTA 2: legenda pe doua coloane, daca echipamentele nu incap deasupra ei
    leg2 = None
    if cont_h > _buget - leg_h:
        a_, b_ = _legenda_split(rows)
        if a_ and b_:
            w1, h1 = _legenda_dim(a_)
            w2, h2 = _legenda_dim(b_)
            leg2 = {"a": a_, "b": b_, "w1": w1, "w": w1 + 14.0 + w2, "h": max(h1, h2)}
            leg_h, leg_w = leg2["h"], leg2["w"]
            cont_h, cont_w, h_sus, h_jos = _incearca(_buget - leg_h)
    return {"rows": rows, "leg_w": leg_w, "leg_h": leg_h, "leg2": leg2, "grupuri": grupuri,
            "sus": _sus, "jos": _jos, "h_sus": h_sus, "h_jos": h_jos, "gap_benzi": _GAP_BENZI,
            "pas": _pas[0],
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

    # ── ECHIPAMENTELE: pe TOATA foaia, in doua benzi ────────────────────────────────────────
    # Continutul nu se mai inghesuie centrat: cutiile stau lipite de marginea din dreapta, coloanele
    # pleaca de la marginea din stanga, iar spatiul ramas se imparte in golurile dintre ele. Banda de
    # SUS duce la rack (video, date/TV), cea de JOS la centrala (efractia) — asa fasciculele nu se
    # mai intalnesc, fiindca fiecare are propriul culoar pe verticala.
    _SUS = PAD + 62.0                       # sub titlu + subtitlu
    _JOS = Y_LEG - 20.0                     # deasupra notei si a legendei
    X0 = PAD + 12.0
    X_HUB = W - PAD - 12.0 - _HUB_W
    _LAT_DISP = X_HUB - _gap_hub() - X0
    # rezerva pe verticala pentru fasciculele care trec PE DEASUPRA coloanelor vecine (doar in banda
    # in care exista mai multe grupuri); fiecare grup are banda LUI, stivuita peste a celui dinainte
    _rez = _rezerva_fascicule((m["sus"], m["jos"]))
    _liber = max(0.0, (_JOS - _SUS) - _rez - m["h_sus"] - m["h_jos"])
    if m["sus"] and m["jos"]:
        # Doua benzi: golul dintre ele ia jumatate din spatiul ramas, dar PLAFONAT — la un sistem
        # mic un gol proportional ar fi devenit o prapastie de jumatate de foaie intre trei camere
        # sus si trei detectoare jos. Restul se imparte egal sus si jos, deci ansamblul ramane
        # echilibrat pe inaltime.
        _g = min(_liber * 0.5, 150.0)
        Y_SUS = _SUS + _rez + (_liber - _g) / 2.0
        Y_JOS = Y_SUS + m["h_sus"] + _g
    else:
        # o singura banda: se CENTREAZA pe inaltime, ca la sistemele mici sa nu ramana un gol ciudat
        Y_SUS = Y_JOS = _SUS + _rez + _liber / 2.0
    Y0 = Y_SUS
    if not m["incape"]:
        # nu se ascunde o suprapunere: se scrie pe planşa ca sistemul depaseste ce incape pe A3
        _text(page, X0, _SUS - 6.0,
              "ATENȚIE: sistemul depășește ce încape pe o planșă A3 — se recomandă împărțirea pe "
              "planșe separate (efracție / video / date).", fs=6.6, col=(0.80, 0.15, 0.15))

    def _coloana(x, gr, y_start):
        """Un grup, in `gr['s']` sub-coloane alaturate. NU mai deseneaza nicio magistrala: cablarea
        structurata e in STEA, deci fiecare element pleaca cu linia LUI (desenata de `_stea`).
        Intoarce (fascicule, x_dreapta, y_prim, y_ultim), unde `fascicule` are cate o intrare per
        SUB-COLOANA. Sub-coloanele trebuie rutate separat: liniile primei sub-coloane treceau peste
        textul celei de-a doua (10 etichete taiate la o coloana de 20 de camere)."""
        _text(page, x, y_start, gr["titlu"], fs=8.0, bold=True, col=gr["col"])
        per = int(math.ceil(gr["n"] / float(gr["s"])))
        y_prim = y_start + 14.0
        y_ultim = y_prim
        fasc, x_dr = [], x
        for k in range(gr["s"]):
            felie = gr["randuri"][k * per:(k + 1) * per]
            if not felie:
                continue
            _sub = []
            xk = x + k * (gr["lat"] + _COL_GAP)
            y = y_prim
            for el, et, descriere in felie:
                _draw_cs(page, xk + 8, y + 4, (el.get("element_type") or "doza_cs"), scale=0.62)
                w1 = _text(page, xk + 23, y + 6.5, et, fs=7.2, bold=True)
                w2 = _text(page, xk + 23 + w1 + 5, y + 6.5, descriere, fs=6.4,
                           col=(0.35, 0.35, 0.35))
                _sub.append((xk + 23 + w1 + 5 + w2 + 6.0, y + 4))
                y += m["pas"]
            fasc.append({"gr": gr, "pct": _sub, "x_dr": xk + gr["lat"]})
            x_dr = max(x_dr, xk + gr["lat"])
            y_ultim = max(y_ultim, y - m["pas"])
        return fasc, x_dr, y_prim, y_ultim

    _banda_fasc = []
    for _banda, _y_banda_top in ((m["sus"], Y_SUS), (m["jos"], Y_JOS)):
        if not _banda:
            _banda_fasc.append([])
            continue
        # SPATIUL RAMAS se imparte in golurile dintre coloane si in cel dinaintea cutiei: coloanele
        # se intind pe toata latimea, in loc sa stea lipite una de alta in mijlocul foii.
        _ocupat = sum(gr["lat"] * gr["s"] + _COL_GAP * (gr["s"] - 1) for gr in _banda)
        _gol = max(_COL_GAP, _COL_GAP + (_LAT_DISP - _ocupat) / float(len(_banda)))
        x = X0
        for gr in _banda:
            gr["geom"] = _coloana(x, gr, _y_banda_top)
            x += gr["lat"] * gr["s"] + _COL_GAP * (gr["s"] - 1) + _gol
        # FASCICULELE benzii, de la stanga la dreapta: ultimul pleaca direct spre cutie, restul se
        # ruteaza pe deasupra, fiecare cu banda LUI stivuita peste a celui dinainte
        _f = [fa for gr in _banda for fa in gr["geom"][0]]
        for _idx, fa in enumerate(_f):
            fa["direct"] = _idx == len(_f) - 1
        # Banda cea mai de SUS ii revine fasciculului cel mai din STANGA, si tot asa coborand spre
        # dreapta. Invers (cum era intai) fasciculul din stanga trecea pe sub benzile vecinilor si
        # le taia laneurile verticale — 200 de incrucisari la o schema cu trei fascicule.
        _acc = 0.0
        for fa in reversed([x for x in _f if not x["direct"]]):
            fa["y_sus"] = _y_banda_top - 8.0 - _acc
            _acc += _pas_stea(len(fa["pct"]), 46.0) * len(fa["pct"]) + _GAP_FASC
        _banda_fasc.append(_f)

    _spre_rack = list(m["sus"])
    _spre_centrala = list(m["jos"])

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
    # PATCH PANEL: toate cablurile UTP (camere + prize de date) se termina pe el — e chiar punctul
    # central al stelei, deci apare inaintea switch-ului, in ordinea in care circula semnalul
    for _pp, _bp in DE.cs_patch_bom(DE.cs_utp_cabluri(_comp)):
        rack_lin.append("%spatch panel %d porturi cat. 5e/6"
                        % ("%d × " % _bp if _bp > 1 else "", _pp))
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
    # cutia trebuie sa fie destul de INALTA cat sa primeasca fiecare cablu pe intrarea lui: cu N
    # cabluri si o cutie de 60 pt, intrarile s-ar lipi. Se creste, nu se ingramadesc.
    _n_rack = sum(len(fa["pct"]) for fa in _banda_fasc[0])
    rack_h = max(rack_h, 20.0 + _n_rack * 3.2)
    # cutia se CENTREAZA pe banda ei, nu pe primul grup: asa fasciculul intra drept, iar cutia nu
    # ajunge in dreptul altei benzi. Ramane loc deasupra pentru sageata de 230 V.
    y_rack = max(_SUS + 26.0, Y_SUS + m["h_sus"] / 2.0 - rack_h / 2.0)
    r_rack = fitz.Rect(X_HUB, y_rack, X_HUB + _HUB_W, y_rack + rack_h)
    _bloc(page, r_rack, DE._DDCS_NAME_COM if DE._e_comercial(subtip) else DE._DDCS_NAME_REZ,
          rack_lin, col=DE._CS_VIDEO)
    _ocupate = 0
    for fa in _banda_fasc[0]:
        gr, _pct, _bx = fa["gr"], fa["pct"], fa["x_dr"]
        _intr = _intrari_cutie(r_rack, len(_pct), _ocupate, _n_rack)
        # DOUA grupuri in aceeasi cutie (video + date) trebuie sa aiba laneuri de coborare DISJUNCTE
        # — cu acelasi interval, coborarile unuia taiau orizontalele celuilalt (278 incrucisari).
        if fa["direct"]:
            _stea(page, _pct, X_HUB, _intr, gr["kind"], _CS_CABLE[gr["kind"]]["bom"],
                  off=_ocupate)
        else:
            _stea(page, _pct, X_HUB, _intr, gr["kind"], _CS_CABLE[gr["kind"]]["bom"],
                  y_sus=fa["y_sus"], x_lane=_bx - 14.0, off=_ocupate)
        _ocupate += len(_pct)

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
        # fiecare detector/contact/buton intra pe ZONA LUI, deci si aici cutia trebuie sa aiba loc
        # de cate o intrare per element — exact ce spune si randul „N zone de detectie" din ea
        _n_ce = sum(len(fa["pct"]) for fa in _banda_fasc[1])
        c_h = max(24.0 + 10.0 * len(c_lin), 20.0 + _n_ce * 3.2)
        # centrala se centreaza pe banda de JOS (unde sta efractia); fara banda proprie (centrala
        # plasata dar fara detectoare) ramane sub rack, ca pana acum
        y_c = (max(r_rack.y1 + 20.0, Y_JOS + m["h_jos"] / 2.0 - c_h / 2.0) if _spre_centrala
               else r_rack.y1 + 30.0)
        r_c = fitz.Rect(X_HUB, y_c, X_HUB + _HUB_W, y_c + c_h)
        _et_ce = (g["centrala"][0][1] if g["centrala"] else "CE") or "CE"
        _bloc(page, r_c, "%s — CENTRALĂ EFRACȚIE" % _et_ce, c_lin, col=DE._CS_EFRACTIE)
        _ocup_c = 0
        for fa in _banda_fasc[1]:
            gr, _pct, _bx = fa["gr"], fa["pct"], fa["x_dr"]
            _intr = _intrari_cutie(r_c, len(_pct), _ocup_c, _n_ce)
            if fa["direct"]:
                _stea(page, _pct, X_HUB, _intr, gr["kind"], _CS_CABLE[gr["kind"]]["bom"],
                      off=_ocup_c)
            else:
                _stea(page, _pct, X_HUB, _intr, gr["kind"], _CS_CABLE[gr["kind"]]["bom"],
                      y_sus=fa["y_sus"], x_lane=_bx - 14.0, off=_ocup_c)
            _ocup_c += len(_pct)
        _cablu(page, r_rack.x0 + _HUB_W / 2.0, r_rack.y1, r_c.x0 + _HUB_W / 2.0, r_c.y0,
               "alimentare")
        # eticheta sta la STANGA firului, aliniata la dreapta: cutiile sunt acum lipite de marginea
        # din dreapta a foii, iar in dreapta firului textul iesea din chenar
        _text(page, r_rack.x0 + _HUB_W / 2.0 - 6, (r_rack.y1 + r_c.y0) / 2.0,
              "%s · 12 V c.c." % _CS_CABLE["alimentare"]["bom"], fs=5.6,
              col=_CS_CABLE["alimentare"]["col"], anchor="right")

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
