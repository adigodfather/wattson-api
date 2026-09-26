# -*- coding: utf-8 -*-
"""
ZYNAPSE · Schema de distributie RETEA DE INTERFON (P7b)
======================================================
Schema VERTICALA a videointerfonului pe doua fire: intrarea blocului jos (panoul de apel, cititorul
de control acces, yala usii de acces si sursa), magistrala care urca prin cladire, iar pe fiecare
nivel posturile interioare, pe apartamente. Se genereaza din elementele PLASATE — nu dintr-un sablon
si nu din formular: campul „apartamente pe etaj" nu-l citeste nimeni, deci nu se construieste pe el.

Pe tiparul `schema_cs.py`: PyMuPDF, simbolurile LITERAL din `draw_elements._draw_cs`, legenda din
`build_legend_rows`, cartusul prin `schema_cs._cartus_final`. Etichetele (PA, PI 2) vin din aceleasi
functii care eticheteaza planşa (`cs_index_map`), iar apartamentele (P1_2) din aceeasi apartenenta
la contur ca circuitele (`apartament_al_elementului`) — schema, planşa si tablourile nu pot spune
lucruri diferite despre acelasi post.

Gate: `interfon.are_interfon`, ACEEASI conditie pe care o citeste numerotarea. Fara elemente de
interfon -> None, iar planşa nici nu se anunta.
"""

import re

import fitz

import apartments as _ap
import draw_elements as DE
import floors as _fl
import interfon as _ifn
from plansa_numbering import plansa_nume, _nivel_label
from schema_cs import (_A3, _PAD_MM, MMPT, _NEGRU, _GRI, _CARTUS_W_MM, _CARTUS_H_MM,
                       _text, _cartus_final, _legenda_dim)

# = numele din numerotare si din borderou: titlul planşei are o singura sursa
TITLU = plansa_nume("schema_distributie_interfon")

_COL = DE._CS_INTERFON
_SPEC_BUS = DE._CS_CABLE[_ifn.CABLU]
_GRI_TEXT = (0.35, 0.35, 0.35)


def _tip(el):
    return str((el or {}).get("element_type") or "")


def _cheie_apartament(eticheta):
    """P1_2 -> (1, 2); SP1 -> (1, 0); necunoscut / None -> la coada, alfabetic."""
    m = re.match(r"^(?:SP|P)(\d+)(?:_(\d+))?$", str(eticheta or ""))
    if m:
        return (0, int(m.group(1)), int(m.group(2) or 0), "")
    return (1, 0, 0, str(eticheta or ""))


def date_schema(elements):
    """CE deseneaza schema, fara desen (testabil): intrarea, posturile pe niveluri si apartamente,
    sursele, traseele de magistrala. None daca proiectul n-are interfon."""
    els = [e for e in (elements or []) if isinstance(e, dict)]
    if not _ifn.are_interfon(els):
        return None
    ifn = [e for e in els if _tip(e) in _ifn.TIPURI]
    idx = DE.cs_index_map(ifn)          # numerotarea planşei: pe (nivel, abreviere)

    def _eticheta(e):
        ab = DE._cs_abbr_for(e)
        i = idx.get(e.get("id"))
        return "%s %d" % (ab, i) if (ab and i) else ab

    def _poz(e):
        return (float(e.get("y") or 0), float(e.get("x") or 0))

    intrare = {t: [(e, _eticheta(e)) for e in sorted(ifn, key=_poz) if _tip(e) == t]
               for t in (_ifn.PANOU, _ifn.CITITOR, _ifn.YALA)}
    posturi = [e for e in ifn if _tip(e) == _ifn.POST]
    niveluri = sorted({_fl.floor_canonic(e.get("floor")) for e in posturi}, key=_fl.floor_index)
    per_nivel = []
    for fk in niveluri:
        conturi = _ap.conturi_nivel(els, fk, _fl.floor_canonic)
        lst = []
        for p in posturi:
            if _fl.floor_canonic(p.get("floor")) != fk:
                continue
            ap = _ap.apartament_al_elementului(p, conturi) if conturi else None
            lst.append({"el": p, "eticheta": _eticheta(p), "apartament": ap})
        lst.sort(key=lambda d: (_cheie_apartament(d["apartament"]), float(d["el"].get("x") or 0)))
        per_nivel.append({"nivel": fk, "posturi": lst})
    return {
        "intrare": intrare,
        "niveluri": per_nivel,
        "surse": [e for e in els if _ifn.este_sursa(e)],
        "trasee": [e for e in els if _tip(e) == "traseu_cs"
                   and DE._cs_cable_kind(e) == _ifn.CABLU],
        "elemente": ifn,
        "n_posturi": len(posturi),
    }


def _linie(page, x0, y0, x1, y1, col=_COL, width=1.0, dashes=None):
    sh = page.new_shape()
    sh.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1))
    sh.finish(color=col, width=width, dashes=dashes)
    sh.commit()


def _magistrala(page, x0, y0, x1, y1):
    """Segment de magistrala: EXACT culoarea si stilul cablului de pe planşa (linie-punct)."""
    _linie(page, x0, y0, x1, y1, col=_SPEC_BUS["col"], width=1.3, dashes=_SPEC_BUS["dash"])


def build_interfon_schema(elements, cartus_firma=None, cartus_proiect=None, plansa_nr=None):
    """Schema de distributie a retelei de interfon -> bytes PDF (o pagina, A3 orizontal), sau None
    daca proiectul n-are interfon (gate pe PREZENTA — aceeasi functie ca numerotarea)."""
    d = date_schema(elements)
    if d is None:
        return None

    W, H = _A3[0] * MMPT, _A3[1] * MMPT
    PAD = _PAD_MM * MMPT
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    page.draw_rect(fitz.Rect(PAD, PAD, W - PAD, H - PAD), color=_NEGRU, width=1.2)

    _text(page, W / 2.0, PAD + 26, TITLU, fs=13.0, bold=True, anchor="center")
    _n_niv = len(d["niveluri"])
    _n_pa = len(d["intrare"][_ifn.PANOU])
    _sub = ("videointerfon pe 2 fire, magistrală nepolarizată — schemă funcțională · "
            "%d %s pe %d %s · %d %s"
            % (d["n_posturi"], "post interior" if d["n_posturi"] == 1 else "posturi interioare",
               _n_niv, "nivel" if _n_niv == 1 else "niveluri",
               _n_pa, "panou de apel" if _n_pa == 1 else "panouri de apel"))
    _text(page, W / 2.0, PAD + 38, _sub, fs=7.5, col=_GRI_TEXT, anchor="center")

    # ── LEGENDA: JOS-STANGA, ca la schema de curenti slabi; cartusul sta in dreapta-jos ─────────
    rows = DE.build_legend_rows(d["elemente"] + d["trasee"], "curenti_slabi")
    _lw, _lh = _legenda_dim(rows)
    X_LEG = PAD + 12.0
    Y_LEG = H - PAD - 12.0 - _lh
    if rows:
        DE._draw_legend(page, X_LEG, Y_LEG, rows)
    _text(page, X_LEG, Y_LEG - 8.0,
          "Numerele de pe schemă sunt cele de pe planșa de curenți slabi; apartamentele, "
          "cele conturate pe planșe.", fs=6.2, col=_GRI_TEXT)

    # ── ZONA DESENULUI: deasupra legendei si a cartusului ───────────────────────────────────────
    Y_SUS = PAD + 64.0
    y_cartus = H - PAD - _CARTUS_H_MM * MMPT
    Y_JOS = min(Y_LEG - 26.0, y_cartus - 18.0)
    X_LAB = PAD + 18.0                        # coloana cu numele nivelurilor
    X_COL = PAD + 118.0                       # MAGISTRALA verticala
    X_MAX = W - PAD - 24.0
    X_POST0 = X_COL + 46.0                    # primul post de pe un nivel

    # ── INTRAREA (jos): panou(ri) pe magistrala, cititor + yala, sursa sub ele ───────────────────
    H_INTRARE = 96.0
    y_in = Y_JOS - H_INTRARE + 26.0           # randul aparatelor de la usa
    y_src = Y_JOS - 16.0                      # caseta sursei
    _text(page, X_LAB, y_in + 3.0, "INTRARE BLOC", fs=8.0, bold=True)

    x = X_COL
    poz = {}                                  # tip -> [(x, eticheta)]
    for t, pas in ((_ifn.PANOU, 58.0), (_ifn.CITITOR, 74.0), (_ifn.YALA, 74.0)):
        if t == _ifn.CITITOR:
            # locul primului panou ramane REZERVAT si cand panoul lipseste: altfel cititorul s-ar fi
            # desenat chiar pe magistrala, ca si cum el ar fi capul coloanei
            x = max(x, X_COL + 58.0) + 26.0
        for el, et in d["intrare"][t]:
            DE._draw_cs(page, x, y_in, t)
            if et:
                # panoul de pe COLOANA isi pune eticheta in dreapta ei: centrata, ar fi taiat-o magistrala
                if x == X_COL:
                    _text(page, x + 9.0, y_in - 11.0, et, fs=6.8, bold=True, col=_COL)
                else:
                    _text(page, x, y_in - 13.5, et, fs=6.8, bold=True, col=_COL, anchor="center")
            poz.setdefault(t, []).append((x, et))
            x += pas
    # magistrala porneste de la PRIMUL panou (sau, fara panou, de la baza coloanei)
    y_baza = y_in - 9.5 if poz.get(_ifn.PANOU) else y_in
    for (xp, _e) in poz.get(_ifn.PANOU, [])[1:]:
        _magistrala(page, X_COL, y_in + 12.0, xp, y_in + 12.0)       # panourile suplimentare
        _linie(page, xp, y_in + 9.5, xp, y_in + 12.0, col=_SPEC_BUS["col"], width=1.0)
    if len(poz.get(_ifn.PANOU, [])) > 1:
        _linie(page, X_COL, y_in + 9.5, X_COL, y_in + 12.0, col=_SPEC_BUS["col"], width=1.0)

    # comanda de deschidere: cititor -> yala (releul cititorului actioneaza yala)
    _cit, _yal = poz.get(_ifn.CITITOR, []), poz.get(_ifn.YALA, [])
    if _cit and _yal:
        _linie(page, _cit[0][0] + 11.0, y_in, _yal[0][0] - 9.5, y_in, col=_COL, width=0.8,
               dashes="[3 2] 0")
        _text(page, (_cit[0][0] + _yal[0][0]) / 2.0, y_in - 3.0, "comandă deschidere", fs=5.6,
              col=_COL, anchor="center")

    # SURSA: receptor pe TCC. Alimenteaza magistrala, yala si cititorul (decizia lui Dan).
    _usa = [xx for xx, _e in _cit + _yal]
    x_src0 = (min(_usa) - 20.0) if _usa else X_COL + 60.0
    x_src1 = max(x_src0 + 190.0, (max(_usa) + 20.0) if _usa else 0.0)
    if d["surse"]:
        r = fitz.Rect(x_src0, y_src - 14.0, x_src1, y_src + 14.0)
        page.draw_rect(r, color=_COL, fill=(1, 1, 1), width=1.1)
        _n_s = len(d["surse"])
        _text(page, r.x0 + 7, r.y0 + 11.5, "SURSĂ VIDEOINTERFON%s" % (" × %d" % _n_s if _n_s > 1 else ""),
              fs=7.4, bold=True, col=_COL)
        _text(page, r.x0 + 7, r.y0 + 22.5, "circuit dedicat 230 V din TCC (tabloul consumatorilor comuni)",
              fs=6.0, col=_GRI_TEXT)
        # alimentarea magistralei: sursa -> baza coloanei. Eticheta sta pe tronsonul orizontal, in
        # golul dintre coloana si caseta (pe coloana ar fi calcat numele nivelurilor). SCURTA: cablul
        # complet e in legenda, iar numele lung intra peste titlul casetei.
        _magistrala(page, r.x0, y_src, X_COL, y_src)
        # pana la baza panoului; fara panou, pana la baza coloanei (altfel ramane o gaura in linie)
        _magistrala(page, X_COL, y_src, X_COL,
                    (y_in + (12.0 if len(poz[_ifn.PANOU]) > 1 else 9.5)) if poz.get(_ifn.PANOU) else y_baza)
        _text(page, X_COL + 6.0, y_src - 3.5, "magistrală 2 fire", fs=5.6, col=_SPEC_BUS["col"])
        # alimentarea yalei si a cititorului: cate o legatura verticala, din caseta
        for xx in _usa:
            _linie(page, xx, r.y0, xx, y_in + 9.5, col=_COL, width=0.8)
        if _usa:
            _text(page, _usa[0] + 4.0, (r.y0 + y_in + 9.5) / 2.0 + 2.0, "alimentare", fs=5.6, col=_COL)
    else:
        # ABSENTA SE VEDE: o yala fara sursa e o schema incompleta, iar verificatorul trebuie s-o prinda
        _text(page, x_src0, y_src + 2.0,
              "Sursa videointerfonului nu e plasată pe planul de forță (spațiul comun, alimentare din TCC).",
              fs=6.4, col=_GRI_TEXT)

    # ── NIVELURILE: de jos in sus, posturile pe apartamente ────────────────────────────────────
    # cate posturi incap pe un rand; peste, nivelul primeste inca un rand (pieptene pe magistrala).
    # Pasul se LARGESTE cand sunt putine posturi (pana la 130 pt), ca schema sa nu stea ingramadita
    # in stanga foii; minimul de 66 pt tine eticheta „P10_12" departe de a vecinului.
    _max_niv = max([len(n["posturi"]) for n in d["niveluri"]] + [1])
    _SLOT = min(130.0, max(66.0, (X_MAX - X_POST0) / _max_niv))
    _per_rand = max(1, int((X_MAX - X_POST0) // _SLOT) + 1)
    randuri = []                              # (nivel, [posturi], primul_rand_al_nivelului)
    for niv in d["niveluri"]:
        ps = niv["posturi"]
        for k in range(0, max(1, len(ps)), _per_rand):
            randuri.append((niv["nivel"], ps[k:k + _per_rand], k == 0))
    y_niv_jos = y_in - 34.0                   # primul rand de posturi, deasupra intrarii
    h_disp = max(40.0, y_niv_jos - Y_SUS)
    row_h = min(78.0, h_disp / max(1, len(randuri)))
    sc = max(0.55, min(1.0, row_h / 60.0))    # nivelurile multe se strang, nu ies din foaie
    y_top = y_baza
    for i, (fk, ps, primul) in enumerate(randuri):
        y_f = y_niv_jos - i * row_h           # linia de magistrala a randului
        if primul:
            _text(page, X_LAB, y_f + 3.0, _nivel_label(fk), fs=8.0 if sc > 0.8 else 7.0, bold=True)
        page.draw_circle(fitz.Point(X_COL, y_f), 2.0, color=_SPEC_BUS["col"], fill=_SPEC_BUS["col"])
        x_ult = X_POST0 + (len(ps) - 1) * _SLOT if ps else X_POST0
        _magistrala(page, X_COL, y_f, x_ult, y_f)
        for j, p in enumerate(ps):
            xp = X_POST0 + j * _SLOT
            ys = y_f - 16.0 * sc               # simbolul sta deasupra liniei, pe un picior scurt
            DE._draw_cs(page, xp, ys, _ifn.POST, scale=sc)
            _linie(page, xp, ys + 6.5 * sc, xp, y_f, col=_SPEC_BUS["col"], width=0.9)
            if p["eticheta"]:
                _text(page, xp, ys - 8.5 * sc, p["eticheta"], fs=6.4 * max(sc, 0.8), bold=True,
                      col=_COL, anchor="center")
            _text(page, xp, y_f + 8.5, p["apartament"] or "fără apartament", fs=6.4 * max(sc, 0.8),
                  col=_NEGRU if p["apartament"] else _GRI_TEXT, anchor="center")
        y_top = y_f
    # MAGISTRALA VERTICALA: de la baza (primul panou) pana la cel mai de sus nivel
    _magistrala(page, X_COL, y_baza, X_COL, min(y_top, y_baza))

    raw = doc.tobytes(deflate=True)
    doc.close()
    return _cartus_final(raw, W, H, cartus_firma, cartus_proiect, plansa_nr, TITLU)
