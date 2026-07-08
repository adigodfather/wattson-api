# -*- coding: utf-8 -*-
"""
Swap cartus arhitect -> cartus firma (Zynapse) pe un plan PDF vectorial.

Detecteaza automat cartusul arhitectului prin text-ancora, il acopera cu alb si
deseneaza in loc cartusul firmei — overlay direct pe vectorial (NU reconverteste in
imagine), pastrand formatul si scara PDF-ului original.

Returneaza un dict cu rezultatul (success/error). Encodarea base64 finala se face aici.
"""

import base64
import io
import re
from datetime import datetime

import fitz  # PyMuPDF
import requests

# Formate standard (mm), short x long
_FORMATS_MM = {
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189),
}
_TOL_MM = 15.0

# Ancore-text de cartus (arhitect + generice cartus romanesc). Comparate normalizat
# (fara diacritice, lowercase). Tokenii multi-cuvant nu prind cuvinte simple, dar sunt
# inofensivi — detectia se sprijina pe tokenii simpli puternici.
ANCORE = [
    "jurjea", "c.i.f", "c.i.f.", "beneficiar", "amplasament", "sef proiect",
    "proiectat", "desenat", "verif", "specificatie", "referat", "expertiza",
    "semnatura", "intocmit", "sef de proiect",
    # generice cartus romanesc
    "faza", "proiect nr", "proiectant",
]

# Ancore tabele arhitect (bilant teritorial, suprafete, retrageri, categorii pericol) —
# comparate normalizat (fara diacritice). Tokenii multi-cuvant sunt inofensivi (nu prind
# cuvinte simple); detectia se sprijina pe tokenii simpli.
TABLE_ANCORE = [
    "bilant", "teritorial", "urbanistici", "teren", "p.o.t", "c.u.t",
    "alei", "pavate", "spatii verzi", "retragere", "categoria", "gradul",
    "rezistenta", "clasa importanta", "categoria de importanta",
    "suprafata construita", "suprafata utila", "locuibila", "desfasurata",
]

_DIACR = {
    "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
    "Ă": "a", "Â": "a", "Î": "i", "Ș": "s", "Ş": "s", "Ț": "t", "Ţ": "t",
}


def _norm(s: str) -> str:
    s = (s or "").lower()
    return "".join(_DIACR.get(c, c) for c in s)


def _detect_format(w_pt: float, h_pt: float) -> str:
    a, b = sorted([w_pt * 25.4 / 72.0, h_pt * 25.4 / 72.0])  # short, long (mm)
    for name, (fw, fh) in _FORMATS_MM.items():
        if abs(a - fw) <= _TOL_MM and abs(b - fh) <= _TOL_MM:
            return name
    return "?"


def _detect_scara(page) -> str:
    text_all = page.get_text("text") or ""
    m = re.search(r"[Ss]cara\s*[:\-]?\s*1\s*[:/]\s*(\d+)", text_all)
    return "1:{}".format(m.group(1)) if m else "—"


def _detect_cartus_bbox(page, W: float, H: float):
    """Returneaza (bbox, n_hits) sau (None, n_hits) daca <3 ancore."""
    words = page.get_text("words")  # (x0,y0,x1,y1,text,block,line,word)
    hits = []
    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        # Exclude titlul de sus (acolo apar fals 'scara'/'plansa')
        if y0 < 0.10 * H:
            continue
        # Cartusul e in jumatatea de jos SAU in treimea din dreapta (cartus vertical)
        in_zone = (y0 > 0.50 * H) or (x0 > 0.66 * W)
        if not in_zone:
            continue
        tl = _norm(text)
        if any(a in tl for a in ANCORE):
            hits.append((x0, y0, x1, y1))

    if len(hits) < 3:
        return None, len(hits)

    bx0 = min(h[0] for h in hits)
    by0 = min(h[1] for h in hits)
    bx1 = max(h[2] for h in hits)
    by1 = max(h[3] for h in hits)
    # margine ca sa acopere chenarul vechi
    m = 6.0
    bbox = fitz.Rect(
        max(0, bx0 - m), max(0, by0 - m),
        min(W, bx1 + m), min(H, by1 + m),
    )
    return bbox, len(hits)


def _detect_tables_bbox(page, W: float, H: float, cy0: float):
    """Bbox al tabelelor arhitectului DEASUPRA cartusului (>=4 ancore de tabel).
    Returneaza fitz.Rect sau None. Plafonat strict la cy0-2 (nu atinge cartusul Zynapse);
    ty0 = limita primei ancore (nu urca peste cote/axe)."""
    words = page.get_text("words")
    hits = []
    for w in words:
        x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
        # In jumatatea de jos, dar STRICT deasupra cartusului
        if not (y0 > 0.55 * H and y1 <= cy0 + 5):
            continue
        tl = _norm(w[4])
        if any(a in tl for a in TABLE_ANCORE):
            hits.append((x0, y0, x1, y1))

    if len(hits) < 4:
        return None

    tx0 = min(h[0] for h in hits)
    ty0 = min(h[1] for h in hits)            # limita primei ancore — NU urca mai sus
    tx1 = max(h[2] for h in hits)
    ty1 = min(max(h[3] for h in hits), cy0 - 2)  # plafonat strict sub cartus

    m = 4.0  # margine mica laterala/jos (ty0 ramane fix; ty1 ramane plafonat)
    tx0 = max(0.0, tx0 - m)
    tx1 = min(W, tx1 + m)
    ty1 = min(ty1 + m, cy0 - 2)

    rect = fitz.Rect(tx0, ty0, tx1, ty1)
    if rect.width <= 0 or rect.height <= 0:
        return None
    return rect


def _detect_tables_right(page, W, H):
    """Bbox-ul blocului administrativ din COLOANA DREAPTA (LANDSCAPE: bilant/indicii/retrageri
    stivuite vertical la dreapta planului): ancore TABLE_ANCORE cu x0 > 0.55W, >=4. Rect sau None."""
    words = page.get_text("words")
    hits = []
    for w in words:
        if w[0] <= 0.55 * W:
            continue
        if any(a in _norm(w[4]) for a in TABLE_ANCORE):
            hits.append((w[0], w[1], w[2], w[3]))
    if len(hits) < 4:
        return None
    return fitz.Rect(min(h[0] for h in hits), min(h[1] for h in hits),
                     max(h[2] for h in hits), max(h[3] for h in hits))


_TITLE_TOP_FRAC = 0.045   # banda titlului plansei (dreapta-sus, ex. "PLAN C1 - CASA") — PROTEJATA
                          # la curatarea coloanei drepte (simetric cu portrait, unde titlul ramane)


def _right_col_safe(page, W, H, G, skip=None):
    """GARDA vectoriala (LANDSCAPE) pt. albirea FULL-HEIGHT a coloanei drepte de la granita
    verticala G: True daca NICIUN vector de PLAN nu traverseaza G (r.x0 < G-6 si r.x1 > G+6).
    Exclusi: chenarul paginii / liniile foarte lungi (span>0.85) + vectorii din blocul cartusului
    (`skip` — se albeste oricum la pasul 5, cartusul traverseaza natural granita). NB: suprapunerea
    cu skip se testeaza MANUAL — Rect.intersects() da False pe liniile degenerate (width/height=0)."""
    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if not r:
                continue
            if r.width > 0.85 * W or r.height > 0.85 * H:
                continue
            if skip is not None and not (r.x1 < skip.x0 or r.x0 > skip.x1
                                         or r.y1 < skip.y0 or r.y0 > skip.y1):
                continue
            if r.x0 < G - 6.0 and r.x1 > G + 6.0:
                return False
        return True
    except Exception:
        return False


def _bottom_band_safe(page, W, H, G):
    """GARDA vectoriala pt. albirea FULL-WIDTH a benzii de jos de la granita G: True daca NICIUN
    vector de PLAN nu traverseaza G (r.y0 < G-6 si r.y1 > G+6). Exclusi (retezati natural la G /
    nu-s plan): chenarul paginii + liniile FOARTE lungi (x-span>0.85W sau y-span>0.85H, ex. limita
    de proprietate verticala). Un perete/cota care traverseaza G => granita taie prin plan -> False."""
    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if not r:
                continue
            if r.width > 0.85 * W or r.height > 0.85 * H:
                continue                                   # chenar pagina / linii lungi de delimitare
            if r.y0 < G - 6.0 and r.y1 > G + 6.0:
                return False
        return True
    except Exception:
        return False                                       # defensiv: garda picata -> fallback partial


# Diacritice -> ASCII cu pastrarea CASE-ului (helv/hebo base14 nu au s/t-comma; Excelul
# de referinta CARTUS.xlsx e oricum fara diacritice: "INSTALATII", "Plansa nr.").
_DIAC_CASE = {"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
              "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T"}


def _txt(s):
    return "".join(_DIAC_CASE.get(c, c) for c in str(s or ""))


def _fit(text, font, size, max_w, min_size=4.0):
    """Micsoreaza fontul pana incape; apoi trunchiaza cu '…'. Intoarce (text, size)."""
    text = _txt(text)
    while size > min_size and fitz.get_text_length(text, fontname=font, fontsize=size) > max_w:
        size -= 0.25
    while len(text) > 1 and fitz.get_text_length(text, fontname=font, fontsize=size) > max_w:
        text = text[:-2].rstrip() + "…"
    return text, size


def _ctext(page, cx0, cx1, y_base, text, size, bold=False):
    """Text CENTRAT orizontal intre cx0..cx1, la baseline y_base (cu fit pe latime)."""
    if not text:
        return
    font = "hebo" if bold else "helv"
    text, size = _fit(text, font, size, (cx1 - cx0) - 3.0)
    w = fitz.get_text_length(text, fontname=font, fontsize=size)
    page.insert_text(fitz.Point((cx0 + cx1 - w) / 2.0, y_base), text,
                     fontsize=size, fontname=font, color=(0, 0, 0))


def _pair_text(page, cx0, cx1, y_base, label, value, lsize, vsize):
    """'Eticheta: Valoare' centrat in celula — eticheta helv mica + valoarea hebo bold."""
    label, value = _txt(label), _txt(value)
    max_w = (cx1 - cx0) - 3.0
    lw = fitz.get_text_length(label, fontname="helv", fontsize=lsize)
    value, vsize = _fit(value, "hebo", vsize, max(6.0, max_w - lw - 2.0))
    vw = fitz.get_text_length(value, fontname="hebo", fontsize=vsize)
    sx = (cx0 + cx1 - (lw + 2.0 + vw)) / 2.0
    page.insert_text(fitz.Point(sx, y_base), label, fontsize=lsize, fontname="helv", color=(0, 0, 0))
    if value:
        page.insert_text(fitz.Point(sx + lw + 2.0, y_base), value, fontsize=vsize, fontname="hebo", color=(0, 0, 0))


def _wrap2(text, font, size, max_w):
    """Titlu pe 1 sau 2 linii: daca nu incape pe o linie, rupe la spatiul cel mai apropiat de mijloc."""
    text = _txt(text)
    if fitz.get_text_length(text, fontname=font, fontsize=size) <= max_w or " " not in text:
        return [text]
    words = text.split()
    best, best_d = 1, 1e9
    for i in range(1, len(words)):
        d = abs(fitz.get_text_length(" ".join(words[:i]), fontname=font, fontsize=size) -
                fitz.get_text_length(" ".join(words[i:]), fontname=font, fontsize=size))
        if d < best_d:
            best, best_d = i, d
    return [" ".join(words[:best]), " ".join(words[best:])]


def _logo_bytes(url):
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def _draw_cartus(page, bbox, cf, cp, plansa_nr, plansa_titlu, scara):
    """Cartus nou pe structura CARTUS.xlsx: grila 10 randuri x 3 zone verticale.
      STANGA (~29.5%): titlu proiectant (2r) | SIGLA (4r) | DATE DE CONTACT (1r) | date firma (3r)
      MIJLOC (~11.6%): 5 casute EGALE a cate 2 randuri (Plansa nr. / Scara / Faza / Nr. proiect / Data),
                       eticheta mica sus + valoare bold jos, pe ACELEASI linii orizontale ca lateralele
      DREAPTA (~58.9%): titlu plansa (2r) | semnaturi 2x2 (Sef proiect/Desenat, Proiectant/Verificat)
                       | Beneficiar (2r) | Amplasament (2r) | Titlu proiect (2r)
    Toate valorile AUTO (cf = setari firma, cp = date proiect, plansa_nr/titlu per plansa, scara
    detectata, data = azi). Intoarce (title_rect, title_base) pt. metadata (titlu per tip de plansa)."""
    x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    w, h = (x1 - x0), (y1 - y0)
    # proportii din CARTUS.xlsx: H-J = 3 col default (25.29) | K = 10.0 | L-Q = 6 col default (50.58)
    xa = x0 + w * 0.2946                       # granita STANGA | MIJLOC
    xb = x0 + w * (0.2946 + 0.1164)            # granita MIJLOC | DREAPTA
    rh = h / 10.0
    ry = lambda k: y0 + k * rh                 # linia orizontala a randului k (0..10)

    # fonturi adaptive la inaltimea randului (aceleasi linii => aceleasi marimi peste tot)
    lab = max(4.0, min(6.0, rh * 0.52))        # etichete mici
    val = max(5.0, min(8.5, rh * 0.72))        # valori bold
    big = max(5.5, min(9.0, rh * 0.78))        # titluri

    BLACK = (0, 0, 0)
    # ── GRILA: chenar + verticale + orizontale ALINIATE intre zone (aceeasi ry(k) peste tot) ──
    page.draw_rect(bbox, color=BLACK, width=1.2)
    page.draw_line(fitz.Point(xa, y0), fitz.Point(xa, y1), color=BLACK, width=0.8)
    page.draw_line(fitz.Point(xb, y0), fitz.Point(xb, y1), color=BLACK, width=0.8)
    xm = (xb + x1) / 2.0                       # mijlocul zonei DREAPTA (split semnaturi L-N | O-Q)
    page.draw_line(fitz.Point(xm, ry(2)), fitz.Point(xm, ry(4)), color=BLACK, width=0.7)
    for k, (lx0, lx1) in [(2, (x0, x1)), (6, (x0, x1)),          # linii comune tuturor zonelor
                          (4, (xa, x1)), (8, (xa, x1)),          # mijloc + dreapta
                          (3, (xb, x1)),                         # doar dreapta (semnaturi)
                          (7, (x0, xa))]:                        # doar stanga (DATE DE CONTACT)
        page.draw_line(fitz.Point(lx0, ry(k)), fitz.Point(lx1, ry(k)), color=BLACK, width=0.7)

    # ── date AUTO ──
    firma_nume = cf.get("firma_nume", "") or ""
    reg = cf.get("firma_reg_com", "") or ""
    cui = cf.get("firma_cui", "") or ""
    tel = cf.get("firma_tel", "") or ""
    email = cf.get("firma_email", "") or ""
    # sef proiect: PRIORITATE valorii confirmate in modal (cp, propusa de Vision din cartusul
    # arhitectului), fallback pe profilul firmei (cf) — backward-compatible cu payload-uri vechi.
    sef = cp.get("sef_proiect", "") or cf.get("sef_proiect", "") or ""
    proiectant = cf.get("proiectant_nume", "") or ""
    verificat = sef                            # fara sursa proprie -> seful de proiect verifica (conventie)
    beneficiar = cp.get("beneficiar", "") or ""
    titlu_proiect = cp.get("titlu_proiect", "") or ""
    amplasament = cp.get("amplasament", "") or ""
    numar_proiect = cp.get("numar_proiect", "") or ""
    faza = cp.get("faza", "") or ""
    data_azi = datetime.now().strftime("%d.%m.%Y")

    # ── STANGA ──
    for i, ln in enumerate(_wrap2("PROIECTANT DE SPECIALITATE INSTALATII ELECTRICE",
                                  "hebo", big, (xa - x0) - 6.0)[:2]):
        _ctext(page, x0, xa, ry(0) + rh * (0.85 + i * 0.95), ln, big, bold=True)
    logo = _logo_bytes(cf.get("firma_logo_url", "") or "")
    if logo:
        try:
            page.insert_image(fitz.Rect(x0 + 4, ry(2) + 3, xa - 4, ry(6) - 3),
                              stream=logo, keep_proportion=True)
        except Exception:
            pass
    _ctext(page, x0, xa, ry(6) + rh * 0.72, "DATE DE CONTACT", val, bold=True)
    reg_cui = "   ".join(filter(None, ["J {}".format(reg) if reg else "",
                                       "C.U.I. {}".format(cui) if cui else ""]))
    tel_email = "   ".join(filter(None, ["Tel. {}".format(tel) if tel else "", email]))
    _ctext(page, x0, xa, ry(7) + rh * 0.78, firma_nume, val, bold=True)
    _ctext(page, x0, xa, ry(8) + rh * 0.75, reg_cui, lab)
    _ctext(page, x0, xa, ry(9) + rh * 0.72, tel_email, lab)

    # ── MIJLOC: 5 casute egale (2 randuri), eticheta sus + valoare bold jos ──
    for k, (label, value) in enumerate([("Plansa nr.", plansa_nr), ("Scara", scara),
                                        ("Faza", faza), ("Nr. proiect", numar_proiect),
                                        ("Data", data_azi)]):
        _ctext(page, xa, xb, ry(2 * k) + rh * 0.80, label, lab)
        _ctext(page, xa, xb, ry(2 * k) + rh * 1.78, value, val, bold=True)

    # ── DREAPTA ──
    title_base = _txt("{} INSTALATII ELECTRICE".format(plansa_titlu or "PLAN").strip())
    title_rect = (xb, y0, x1, ry(2))           # celula titlului -> metadata (sufix per tip plansa)
    lines = _wrap2(title_base, "hebo", big, (x1 - xb) - 6.0)[:2]
    if len(lines) == 1:
        _ctext(page, xb, x1, ry(0) + rh * 1.30, lines[0], big, bold=True)
    else:
        for i, ln in enumerate(lines):
            _ctext(page, xb, x1, ry(0) + rh * (0.85 + i * 0.95), ln, big, bold=True)
    _pair_text(page, xb, xm, ry(2) + rh * 0.72, "Sef proiect:", sef, lab, val)
    _pair_text(page, xm, x1, ry(2) + rh * 0.72, "Desenat:", proiectant, lab, val)
    _pair_text(page, xb, xm, ry(3) + rh * 0.72, "Proiectant:", proiectant, lab, val)
    _pair_text(page, xm, x1, ry(3) + rh * 0.72, "Verificat:", verificat, lab, val)
    for k, (label, value) in [(4, ("Beneficiar", beneficiar)),
                              (6, ("Amplasament", amplasament)),
                              (8, ("Titlu proiect", titlu_proiect))]:
        _ctext(page, xb, x1, ry(k) + rh * 0.80, label, lab)
        _ctext(page, xb, x1, ry(k) + rh * 1.78, value, val, bold=True)

    # casuta "Plansa nr." (prima din MIJLOC, k=0: label sus + valoare bold jos) -> coord pt.
    # restamp_plansa (renumerotare finala IE.N secventiala, o singura sursa de adevar).
    plansa_box = (xa, ry(0), xb, ry(2))
    return title_rect, title_base, plansa_box


def _mask_margins(page, rooms, pad_left=0.03, pad_top=0.03, pad_bottom=0.03, pad_right=0.02,
                  right_cap=0.82, top_cap=0.10, left_cap=0.16, bottom_cap=0.84, protect_top_frac=0.08):
    """Curatare partiala (~80%): maschera gunoiul din MARGINI pastrand arhitectura centrala.
    rooms = [{bbox:{x,y,w,h}} fractii 0-1] (de la Vision). union(bbox) + padding ASIMETRIC = zona pastrata.
    Padding mic pe DREAPTA (pad_right=0.02) fiindca blocul arhitect (BILANT/NOTA) abuta cladirea acolo;
    generos pe stanga/sus/jos (sigur — doar cote). Maschera cu alb cele 4 benzi din AFARA zonei; pastreaza
    o banda subtire sus (nord/titlu). NON-DESTRUCTIV (marja acopera peretele exterior). rooms gol/None ->
    nu maschera nimic (backward-compatible). Axele interioare RAMAN (cioturi). Intoarce [X0,Y0,X1,Y1] pct PDF sau None."""
    if not rooms:
        return None
    xs0, ys0, xs1, ys1 = [], [], [], []
    for r in rooms:
        bb = (r or {}).get("bbox") or {}
        try:
            x = float(bb["x"]); y = float(bb["y"]); w = float(bb["w"]); h = float(bb["h"])
        except (TypeError, ValueError, KeyError):
            continue
        xs0.append(x); ys0.append(y); xs1.append(x + w); ys1.append(y + h)
    if not xs0:
        return None

    # union in fractii + padding ASIMETRIC pe 4 laturi, cu CAP-uri HARD pe toate laturile, clamp [0,1].
    # Vision e non-determinist: poate detecta camera de margine MAI SPRE INTERIOR decat peretele real
    # (ex. camera de sus la y0=0.25 cand peretele e la 0.11) -> zona pastrata ar intra in cladire si masca
    # ar TAIA peretele. Cap-urile leaga zona pastrata de EXTINDEREA REALA STABILA a cladirii (calibrari 132/134):
    # stanga ~0.18, sus ~0.11-0.13, jos ~0.81, dreapta ~0.78. Asezate JUST IN AFARA cladirii, cap-urile
    # garanteaza ca zona pastrata CONTINE MEREU cladirea (stanga<=left_cap, sus<=top_cap, jos>=bottom_cap,
    # dreapta>=right_cap) indiferent ce da Vision. Union poate doar largi conservator zona, niciodata taia.
    # min() pe SUS/STANGA + max() pe JOS => cap-urile DOAR REDUC mascarea (NEW subset al OLD): nu pot taia nimic.
    ux0 = max(0.0, min(min(xs0) - pad_left, left_cap))    # STANGA: cap la left_cap (sub peretele stang ~0.18)
    uy0 = max(0.0, min(min(ys0) - pad_top,  top_cap))     # SUS:    cap la top_cap (deasupra peretelui sus ~0.11)
    ux1 = min(min(max(xs1) + pad_right, right_cap), 1.0)  # DREAPTA: cap la right_cap (peste blocul arhitect)
    uy1 = min(1.0, max(max(ys1) + pad_bottom, bottom_cap))  # JOS:   cap la bottom_cap (sub peretele jos ~0.81)

    W, H = page.rect.width, page.rect.height
    X0, Y0, X1, Y1 = ux0 * W, uy0 * H, ux1 * W, uy1 * H
    top = protect_top_frac * H   # banda subtire de sus protejata (nord/titlu)
    WHITE = (1, 1, 1)

    def rect(x0, y0, x1, y1):
        if x1 - x0 > 0.5 and y1 - y0 > 0.5:
            page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=WHITE, fill=WHITE)

    # SUS (sub banda protejata, pana la arhitectura) — prinde blocul arhitect dreapta-sus
    if Y0 > top:
        rect(0.0, top, W, Y0)
    rect(0.0, Y1, W, H)        # JOS
    rect(0.0, Y0, X0, Y1)      # STANGA (doar inaltimea arhitecturii)
    # DREAPTA pe TOATA inaltimea (0->H) -> acopera si coltul dreapta-sus (titlul arhitect).
    # Nordul e in centru (x < X1) -> ramane in banda de sus protejata, neatins.
    rect(X1, 0.0, W, H)        # DREAPTA (full height)
    return [round(X0, 1), round(Y0, 1), round(X1, 1), round(Y1, 1)]


def swap_cartus_plan(data: dict) -> dict:
    """Detecteaza cartusul arhitectului si il inlocuieste cu cartusul firmei.
    Returneaza dict cu success/pdf_base64/detected sau success:false/error."""
    data = data or {}
    pdf_b64 = data.get("pdf_base64") or ""
    cf = data.get("cartus_firma") or {}
    cp = data.get("cartus_proiect") or {}
    plansa_nr = data.get("plansa_nr") or ""
    plansa_titlu = data.get("plansa_titlu") or ""

    if not pdf_b64:
        return {"success": False, "error": "pdf_base64 lipseste"}

    raw = pdf_b64.split(",", 1)[1] if "," in pdf_b64 else pdf_b64
    try:
        pdf_bytes = base64.b64decode(raw)
    except Exception as e:
        return {"success": False, "error": "pdf_base64 invalid: {}".format(e)}

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count < 1:
        return {"success": False, "error": "PDF fara pagini"}

    page = doc[0]
    W, H = page.rect.width, page.rect.height

    fmt = _detect_format(W, H)
    scara = _detect_scara(page)
    bbox, n_hits = _detect_cartus_bbox(page, W, H)

    if bbox is None:
        return {
            "success": False,
            "error": ("Cartus nedetectat ({} ancore < 3) — nu s-a desenat nimic, "
                      "planul ramane neatins.").format(n_hits),
            "detected": {"format": fmt, "scara": scara, "cartus_bbox": None},
        }

    # 5. Acoperire cartus vechi cu alb opac. +6pt pe laturi: CHENARUL vectorial al cartusului e
    # putin in AFARA bbox-ului text-detectat (masurat pe c7890: linia de sus la y=1055 vs bbox
    # 1059.6) — altfel ramane un chenar dublu subtire la cartusul Zynapse. Blocul e in colt: safe.
    page.draw_rect(fitz.Rect(max(0.0, bbox.x0 - 6.0), max(0.0, bbox.y0 - 6.0),
                             min(W, bbox.x1 + 6.0), min(H, bbox.y1 + 6.0)),
                   color=(1, 1, 1), fill=(1, 1, 1))

    # 5a. GUNOI DE EXPORT + contact izolat — TINTIT pe BBOX-uri de CUVINTE (nu zone: imposibil sa
    # taie din plan): (1) watermark-ul ArchiCAD 'GSPublisherVersion' + numarul de versiune adiacent,
    # ORIUNDE pe plansa (mereu gunoi de export, niciodata continut; pe portrait banda de jos il
    # prinde oricum — aici e universal); (2) LANDSCAPE, in banda cartusului (sub nivelul lui, in
    # afara blocului): telefoane/email/'Tel.'/'contact' — pattern CONSERVATOR: numar cu >=2
    # separatoare (telefon '586.42.43.21' DA; cota '16.80' are 1 -> NU; bulinele/ACCES nu
    # match-uiesc). La dubiu nu se sterge.
    wiped_words = []
    try:
        _words_all = page.get_text("words")
        _marks = []
        _re_ver = re.compile(r"^[\d.]+$")      # STRICT numar de versiune: doar cifre+puncte, >=2 puncte
        for _w in _words_all:
            if "gspublisher" in _norm(_w[4]):
                _marks.append(_w)
                for _v in _words_all:          # versiunea de pe aceeasi linie, imediat dupa ('0.0.100.100')
                    if (_v is not _w and abs(_v[1] - _w[1]) < 3.0 and 0.0 <= _v[0] - _w[2] < 25.0
                            and _re_ver.match(_v[4]) and _v[4].count(".") >= 2):
                        _marks.append(_v)      # cotele planului ('1560', '85') NU trec (0-1 puncte)
        if W > H:
            _re_num = re.compile(r"^[\d\.\-/ ]{8,}$")
            for _w in _words_all:
                if _w[1] < bbox.y0 - 15.0 or (bbox.x0 - 8.0 <= _w[0] <= bbox.x1 + 8.0):
                    continue                   # doar banda cartusului, in AFARA blocului lui
                _t = _norm(_w[4])
                _nsep = _w[4].count(".") + _w[4].count("-") + _w[4].count("/")
                if (_t in ("tel", "tel.", "fax", "fax.", "email", "e-mail", "contact") or "@" in _w[4]
                        or (_re_num.match(_w[4]) and _nsep >= 2)):
                    _marks.append(_w)
        for _w in _marks:
            page.draw_rect(fitz.Rect(_w[0] - 1.5, _w[1] - 1.5, _w[2] + 1.5, _w[3] + 1.5),
                           color=(1, 1, 1), fill=(1, 1, 1))
            wiped_words.append(_w[4])
    except Exception:
        pass

    # 5b. CURATAREA BENZII ADMINISTRATIVE DE JOS (decizia Dan, 08.07.2026 v2). Plansa de
    # arhitectura = PLANUL (sus: camere/cote/axe/titluri — ramane INTACT, fara masca pe margini,
    # fara Vision) + BANDA ADMINISTRATIVA jos (bilant teritorial, indicii, retrageri, categorii,
    # cartusul arhitectului). Banda de JOS se albeste COMPLET -> loc pentru cartusul Zynapse +
    # legenda electrica (plasata manual de inginer). DETERMINIST (text vectorial, NU Vision):
    #   granita G = prima ancora de TABEL administrativ JOS (y>0.55H, >=4 ancore) - 4pt.
    #   Masurat pe plansele reale: GAP plan->tabele = 8-9pt (portrait 9926) -> G nu atinge planul.
    #   GARDA vectoriala (_bottom_band_safe): daca un vector de PLAN traverseaza G (pereti/cote;
    #   exclus chenarul paginii + liniile verticale lungi, ex. limita de proprietate, care sunt
    #   retezate natural la G) -> fallback L-shape DOAR pe zona tabelelor (mai bine partial
    #   decat taiat). FARA tabele JOS (ex. landscape: bilant/NOTA LATERAL — raman, caz acceptat;
    #   sub nivelul cartusului e ACCES-ul/axele planului) -> se albeste doar blocul cartusului
    #   arhitectului (pasul 5). _mask_margins (Vision) RAMANE DEZACTIVAT — taia peretii pe
    #   portrait, intermitent (diagnoza 9926ba23).
    tables_bbox = _detect_tables_bbox(page, W, H, bbox.y0)
    tables_bbox_stanga = None
    tables_bbox_mijloc = None
    bottom_band = None
    right_band = None
    margins_bbox = None
    # 5b-L. LANDSCAPE (W > H): coloana administrativa e in DREAPTA (bilant/indicii/retrageri/NOTA
    # stivuite vertical) -> SIMETRIC cu banda de jos: granita VERTICALA G = prima ancora de tabel
    # din dreapta (x>0.55W) - 4pt, albire FULL-HEIGHT [G -> W] sub banda titlului (protejata,
    # _TITLE_TOP_FRAC — titlul plansei ramane, ca la portrait). GARDA _right_col_safe: vectorii de
    # PLAN care traverseaza G (ex. cote/sageti — ACCES-ul e departe, la ~0.45W) -> fallback fara
    # albire (doar cartusul, pasul 5). Masurat pe c7890d8d: plan pana ~0.69W, ancore de la ~0.75W.
    if W > H:
        _tr = _detect_tables_right(page, W, H)
        if _tr is not None:
            # pad 14: bbox-ul cartusului e din ANCORE-TEXT — chenarul lui vectorial e cu ~7-10pt
            # in afara textului (masurat: linia de sus la y=1055 vs bbox text 1065) si ar umple
            # histograma / declansa garda degeaba.
            _skip = fitz.Rect(bbox.x0 - 14.0, bbox.y0 - 14.0, bbox.x1 + 14.0, bbox.y1 + 14.0)
            # Granita G = mijlocul GOLULUI VECTORIAL dintre plan si coloana administrativa
            # (histograma ocuparii pe X, excl. chenarul paginii + blocul cartusului): planul se
            # termina (pe c7890: axe pana ~1151), box-urile admin incep (~1262) -> gol ~110pt.
            # Prima ancora-TEXT nu e buna ca granita (box-urile incep la STANGA textului si ar
            # traversa G). Fara gol >= 24pt intre 0.55W si ancore -> fallback (fara albire).
            _G = None
            try:
                _x0d, _x1d = 0.5 * W, min(_tr.x0 + 2.0, W)
                _n = max(1, int((_x1d - _x0d) / 2.0))          # benzi de 2pt
                _occ = [False] * _n
                for _d in page.get_drawings():
                    _r = _d.get("rect")
                    if not _r or _r.width > 0.85 * W or _r.height > 0.85 * H:
                        continue
                    if _r.x1 < _x0d:
                        continue
                    # suprapunere cu blocul cartusului testata MANUAL (Rect.intersects() da False
                    # pe liniile degenerate width/height=0 -> cartusul ar fi umplut histograma)
                    if not (_r.x1 < _skip.x0 or _r.x0 > _skip.x1
                            or _r.y1 < _skip.y0 or _r.y0 > _skip.y1):
                        continue
                    _a = max(0, int((_r.x0 - _x0d) / 2.0))
                    _b = min(_n, int((_r.x1 - _x0d) / 2.0) + 1)
                    for _k in range(_a, _b):
                        _occ[_k] = True
                # cel mai larg gol [in benzi] care se termina la ancore / incepe dupa 0.55W
                _best = (0, None)                              # (latime_benzi, centru_pt)
                _run = 0
                for _k in range(_n + 1):
                    if _k < _n and not _occ[_k]:
                        _run += 1
                    else:
                        if _run > _best[0]:
                            _c = _x0d + (_k - _run / 2.0) * 2.0
                            if _c >= 0.55 * W:
                                _best = (_run, _c)
                        _run = 0
                if _best[0] * 2.0 >= 24.0:
                    _G = _best[1]
            except Exception:
                _G = None
            if _G is not None and _right_col_safe(page, W, H, _G, skip=_skip):
                _top = _TITLE_TOP_FRAC * H
                page.draw_rect(fitz.Rect(_G, _top, W, H), color=(1, 1, 1), fill=(1, 1, 1))
                right_band = [round(_G, 1), round(_top, 1), round(W, 1), round(H, 1)]
    if tables_bbox is not None:
        G = max(0.55 * H, tables_bbox.y0 - 4.0)
        if _bottom_band_safe(page, W, H, G):
            # banda administrativa COMPLETA (toata latimea, pana jos) — cartusul Zynapse se
            # deseneaza DUPA, peste banda alba (pasul 6), pe pozitia conventionala dreapta-jos.
            page.draw_rect(fitz.Rect(0.0, G, W, H), color=(1, 1, 1), fill=(1, 1, 1))
            bottom_band = [0.0, round(G, 1), round(W, 1), round(H, 1)]
        else:
            # fallback partial (garda a gasit vectori de plan peste granita): L-shape pe zona
            # tabelelor, ca inainte — STANGA de cartus pana jos + MIJLOC pana deasupra cartusului.
            cx0, cy0 = bbox.x0, bbox.y0
            tx0, ty0, tx1 = tables_bbox.x0, tables_bbox.y0, tables_bbox.x1
            banda = [w for w in page.get_text("words")
                     if w[0] >= tx0 and w[1] >= ty0 and w[3] <= cy0 + 2]
            tx1_mijloc = min(max((w[2] for w in banda), default=tx1) + 4.0, W * 0.96)
            rs = (tx0 - 4.0, ty0 - 4.0, min(tx1 + 4.0, cx0 - 2.0), H - 2.0)
            rm = (max(tx0 - 4.0, cx0 - 2.0), ty0 - 4.0, tx1_mijloc, cy0 - 2.0)
            if rs[0] < rs[2] and rs[1] < rs[3]:
                page.draw_rect(fitz.Rect(*rs), color=(1, 1, 1), fill=(1, 1, 1))
                tables_bbox_stanga = [round(v, 1) for v in rs]
            if rm[0] < rm[2] and rm[1] < rm[3]:
                page.draw_rect(fitz.Rect(*rm), color=(1, 1, 1), fill=(1, 1, 1))
                tables_bbox_mijloc = [round(v, 1) for v in rm]

    # 6. Cartus nou (acelasi bbox, scara detectata)
    title_rect, title_base, plansa_box = _draw_cartus(page, bbox, cf, cp, plansa_nr, plansa_titlu, scara)

    # 6b. Coord celule -> metadata PDF pt. re-stampare ulterioara FARA re-desen complet:
    #   - zy_cartus_title : celula titlului (draw_elements rescrie sufixul "... DE ILUMINAT/FORTA")
    #   - zy_cartus_plansa: casuta "Plansa nr." (restamp_plansa scrie numarul FINAL IE.N — numerotare
    #     secventiala calculata in plansa_numbering.compute_plansa_numbering, o SINGURA sursa de adevar).
    # zy_cartus_plansa e PREFIX -> regex-ul zy_cartus_title din _apply_cartus_suffix ramane neschimbat.
    try:
        doc.set_metadata({**(doc.metadata or {}),
                          "keywords": "zy_cartus_plansa=%.1f,%.1f,%.1f,%.1f|"
                                      "zy_cartus_title=%.1f,%.1f,%.1f,%.1f|%s"
                                      % (plansa_box[0], plansa_box[1], plansa_box[2], plansa_box[3],
                                         title_rect[0], title_rect[1], title_rect[2], title_rect[3],
                                         title_base)})
    except Exception:
        pass  # metadata e optionala — fara ea titlul/numarul raman cele generice

    out = doc.tobytes(deflate=True)
    doc.close()

    safe_nr = str(plansa_nr or "plan").replace("/", "-").replace(" ", "_") or "plan"
    return {
        "success": True,
        "pdf_base64": base64.b64encode(out).decode("utf-8"),
        "filename": "Plan_{}_cartus_zynapse.pdf".format(safe_nr),
        "size_bytes": len(out),
        "detected": {
            "format": fmt,
            "scara": scara,
            "cartus_bbox": [round(bbox.x0, 1), round(bbox.y0, 1),
                            round(bbox.x1, 1), round(bbox.y1, 1)],
            "tables_bbox": ([round(tables_bbox.x0, 1), round(tables_bbox.y0, 1),
                             round(tables_bbox.x1, 1), round(tables_bbox.y1, 1)]
                            if tables_bbox is not None else None),
            "tables_bbox_stanga": tables_bbox_stanga,
            "tables_bbox_mijloc": tables_bbox_mijloc,
            "bottom_band": bottom_band,       # [0,G,W,H] banda de jos albita COMPLET (None = fallback/lateral)
            "right_band": right_band,         # [G,top,W,H] coloana dreapta albita (LANDSCAPE; None = fallback)
            "wiped_words": wiped_words,       # gunoi export (GSPublisherVersion) + contact izolat (bbox-uri albite)
            "margins_masked": margins_bbox,   # mereu None (masca Vision dezactivata — taia planul)
        },
    }


def restamp_plansa(pdf, plansa_nr, plansa_titlu=None):
    """Re-stampeaza casuta "Plansa nr." (= plansa_nr) si, optional, titlul (= plansa_titlu) pe un PDF
    care are DEJA cartus Zynapse. Coord din metadata scrisa la swap: zy_cartus_plansa (casuta numar) +
    zy_cartus_title (celula titlu). AUTORITATEA numerotarii finale IE.N: n8n calculeaza secventa cu
    plansa_numbering.compute_plansa_numbering si cheama asta la final pe fiecare PDF -> numarul TIPARIT
    pe cartus = numarul din documente (o SINGURA sursa de adevar; gata cu "IE.X" / cartus != JSON).

    Acelasi tipar ca draw_elements._apply_cartus_suffix: albeste interiorul celulei si redeseneaza.
    PDF fara metadata (vechi / cartus nedetectat) -> no-op pe celula lipsa (stamped_*=False). Defensiv.

    pdf: base64 (cu/fara prefix "data:...") SAU bytes. plansa_titlu: numele complet (poate lipsi -> doar nr).
    Return: {success, pdf_base64, size_bytes, stamped_nr, stamped_titlu, plansa_nr} sau {success:False,error}.
    """
    try:
        if isinstance(pdf, (bytes, bytearray)):
            pdf_bytes = bytes(pdf)
        else:
            raw = pdf.split(",", 1)[1] if "," in str(pdf) else pdf
            pdf_bytes = base64.b64decode(raw)
    except Exception as e:
        return {"success": False, "error": "pdf invalid: {}".format(e)}

    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            return {"success": False, "error": "PDF fara pagini"}
        page = doc[0]
        kw = (doc.metadata or {}).get("keywords") or ""
        stamped_nr = stamped_titlu = False

        # ── casuta "Plansa nr." (label sus + valoare bold jos), reconstruita ca in _draw_cartus ──
        mp = re.search(r"zy_cartus_plansa=([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+)", kw)
        if mp and plansa_nr:
            px0, py0, px1, py1 = (float(mp.group(i)) for i in range(1, 5))
            rh = (py1 - py0) / 2.0                       # casuta = 2 randuri (label + valoare)
            lab = max(4.0, min(6.0, rh * 0.52))
            val = max(5.0, min(8.5, rh * 0.72))
            page.draw_rect(fitz.Rect(px0 + 1.0, py0 + 1.0, px1 - 1.0, py1 - 1.0),
                           color=(1, 1, 1), fill=(1, 1, 1))   # goleste DOAR interiorul casutei
            _ctext(page, px0, px1, py0 + rh * 0.80, "Plansa nr.", lab)
            _ctext(page, px0, px1, py0 + rh * 1.78, plansa_nr, val, bold=True)
            stamped_nr = True

        # ── titlul plansei (numele COMPLET), rescris ca in _apply_cartus_suffix ──
        mt = re.search(r"zy_cartus_title=([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+)\|", kw)
        if mt and plansa_titlu:
            tx0, ty0, tx1, ty1 = (float(mt.group(i)) for i in range(1, 5))
            page.draw_rect(fitz.Rect(tx0 + 1.0, ty0 + 1.0, tx1 - 1.0, ty1 - 1.0),
                           color=(1, 1, 1), fill=(1, 1, 1))
            rh2 = (ty1 - ty0) / 2.0
            big = max(5.5, min(9.0, rh2 * 0.78))
            lines = _wrap2(plansa_titlu, "hebo", big, (tx1 - tx0) - 6.0)[:2]
            if len(lines) == 1:
                _ctext(page, tx0, tx1, ty0 + rh2 * 1.30, lines[0], big, bold=True)
            else:
                for i, ln in enumerate(lines):
                    _ctext(page, tx0, tx1, ty0 + rh2 * (0.85 + i * 0.95), ln, big, bold=True)
            stamped_titlu = True

        out = doc.tobytes(deflate=True)
        return {
            "success": True,
            "pdf_base64": base64.b64encode(out).decode("utf-8"),
            "size_bytes": len(out),
            "stamped_nr": stamped_nr,
            "stamped_titlu": stamped_titlu,
            "plansa_nr": plansa_nr,
        }
    except Exception as e:
        return {"success": False, "error": "restamp esuat: {}".format(e)}
    finally:
        if doc is not None:
            doc.close()
