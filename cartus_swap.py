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

    return title_rect, title_base


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

    # 5. Acoperire cartus vechi cu alb opac
    page.draw_rect(bbox, color=(1, 1, 1), fill=(1, 1, 1))

    # 5b. Acoperire tabele arhitect in forma de L (bilant teritorial, suprafete,
    # retrageri, categorii pericol) — face loc legendelor electrice. Inainte de desenarea
    # cartusului Zynapse, dupa detectarea cartus_bbox.
    #   - STANGA (x < cartus): acopera de la ty0 pana JOS (H) — acolo nu e cartus.
    #   - MIJLOC/DEASUPRA cartus: acopera de la ty0 doar pana la cy0-2 (cartus intact).
    # ty0 = prima ancora (cotele/axele de sus raman intacte).
    tables_bbox = _detect_tables_bbox(page, W, H, bbox.y0)
    tables_bbox_stanga = None
    tables_bbox_mijloc = None
    if tables_bbox is not None:
        cx0, cy0 = bbox.x0, bbox.y0
        tx0, ty0, tx1 = tables_bbox.x0, tables_bbox.y0, tables_bbox.x1
        # Marginea dreapta a zonei MIJLOC = include TOATE cuvintele din banda tabelelor
        # (nu doar ancorele) — prinde valorile izolate din extrema dreapta (C/3/IV/D,
        # "sau"/"cu"/"de" etc.) care altfel raman ca o coada vizibila deasupra cartusului.
        banda = [w for w in page.get_text("words")
                 if w[0] >= tx0 and w[1] >= ty0 and w[3] <= cy0 + 2]
        tx1_mijloc = max((w[2] for w in banda), default=tx1)
        # plafoneaza ca sa NU atingi rama/chenarul planului din dreapta
        tx1_mijloc = min(tx1_mijloc + 4.0, W * 0.96)
        # a) STANGA: pana jos la H-2, doar pana la marginea stanga a cartusului (cx0-2)
        rs = (tx0, ty0, min(tx1, cx0 - 2.0), H - 2.0)
        # b) MIJLOC: de la marginea stanga a cartusului pana la tx1_mijloc, doar pana la cy0-2
        rm = (max(tx0, cx0 - 2.0), ty0, tx1_mijloc, cy0 - 2.0)
        if rs[0] < rs[2] and rs[1] < rs[3]:
            page.draw_rect(fitz.Rect(*rs), color=(1, 1, 1), fill=(1, 1, 1))
            tables_bbox_stanga = [round(rs[0], 1), round(rs[1], 1),
                                  round(rs[2], 1), round(rs[3], 1)]
        if rm[0] < rm[2] and rm[1] < rm[3]:
            page.draw_rect(fitz.Rect(*rm), color=(1, 1, 1), fill=(1, 1, 1))
            tables_bbox_mijloc = [round(rm[0], 1), round(rm[1], 1),
                                  round(rm[2], 1), round(rm[3], 1)]

    # 5c. Curatare partiala: maschera marginile (bloc arhitect, cote/bule exterioare, legende vechi)
    # pe baza union(rooms.bbox)+padding. INAINTE de cartus -> cartusul Zynapse ramane DEASUPRA mastii.
    margins_bbox = _mask_margins(page, data.get("rooms"))

    # 6. Cartus nou (acelasi bbox, scara detectata)
    title_rect, title_base = _draw_cartus(page, bbox, cf, cp, plansa_nr, plansa_titlu, scara)

    # 6b. Celula titlului -> metadata PDF: planasele derivate (iluminat/forta) rescriu DOAR titlul
    # cu sufixul per tip ("... DE ILUMINAT" / "... DE FORTA") in draw_elements, FARA modificari n8n.
    try:
        doc.set_metadata({**(doc.metadata or {}),
                          "keywords": "zy_cartus_title=%.1f,%.1f,%.1f,%.1f|%s"
                                      % (title_rect[0], title_rect[1], title_rect[2],
                                         title_rect[3], title_base)})
    except Exception:
        pass  # metadata e optionala — fara ea titlul ramane cel generic

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
            "margins_masked": margins_bbox,   # [X0,Y0,X1,Y1] pct PDF (None daca fara rooms)
        },
    }
