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


def _line(page, x, y_base, text, size, bold=False, max_w=None):
    """Scrie o linie de text la baseline (insert_text NU pica silentios pe overflow,
    spre deosebire de insert_textbox). Trunchiaza daca depaseste latimea disponibila."""
    if not text:
        return
    font = "hebo" if bold else "helv"
    if max_w:
        # trunchiere aproximativa: ~0.5*size latime medie per caracter (Helvetica)
        max_chars = max(4, int(max_w / (size * 0.5)))
        if len(text) > max_chars:
            text = text[:max_chars - 1] + "…"
    page.insert_text(fitz.Point(x, y_base), text, fontsize=size,
                     fontname=font, color=(0, 0, 0))


def _draw_cartus(page, bbox, cf, cp, plansa_nr, plansa_titlu, scara):
    x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    w, h = (x1 - x0), (y1 - y0)

    # Chenar exterior negru
    page.draw_rect(bbox, color=(0, 0, 0), width=1.0)

    firma_nume = cf.get("firma_nume", "") or ""
    reg = cf.get("firma_reg_com", "") or ""
    cui = cf.get("firma_cui", "") or ""
    tel = cf.get("firma_tel", "") or ""
    email = cf.get("firma_email", "") or ""
    sef = cf.get("sef_proiect", "") or ""
    proiectant = cf.get("proiectant_nume", "") or ""

    beneficiar = cp.get("beneficiar", "") or ""
    titlu_proiect = cp.get("titlu_proiect", "") or ""
    amplasament = cp.get("amplasament", "") or ""
    numar_proiect = cp.get("numar_proiect", "") or ""
    faza = cp.get("faza", "") or ""
    data_azi = datetime.now().strftime("%d.%m.%Y")

    reg_cui = "   ".join(filter(None, [
        "Reg. Com. {}".format(reg) if reg else "",
        "C.U.I. {}".format(cui) if cui else "",
    ]))
    tel_email = "   ".join(filter(None, [
        "Tel. {}".format(tel) if tel else "",
        email,
    ]))

    # Continut pe randuri: (text, size, bold)
    rows = [
        (firma_nume, 8, True),
        (reg_cui, 6, False),
        (tel_email, 6, False),
        ("Beneficiar: {}".format(beneficiar), 7, False),
        ("Amplasament: {}".format(amplasament), 7, False),
        ("Lucrare: {}".format(titlu_proiect), 7, False),
        ("Faza: {}    Proiect nr: {}    Data: {}".format(faza, numar_proiect, data_azi), 7, False),
        ("Scara: {}    Plansa: {}".format(scara, plansa_nr), 7, True),
        (plansa_titlu or "", 7, True),
        ("Sef proiect: {}    Proiectat: {}    Desenat: {}".format(sef, proiectant, proiectant), 6, False),
    ]

    n = len(rows)
    row_h = h / n
    # Font adaptiv la inaltimea randului (cartus mic -> font mic, dar lizibil)
    base_size = max(4.5, min(9.0, row_h * 0.7))
    max_w = w - 8
    for i, (text, size_pref, bold) in enumerate(rows):
        size = min(size_pref, base_size + (1.0 if (bold and i == 0) else 0.0))
        y_base = y0 + i * row_h + row_h * 0.72  # baseline catre baza randului
        _line(page, x0 + 4, y_base, text, size, bold=bold, max_w=max_w)

    # Linii separatoare: dupa header (rand 3) si inainte de semnaturi (ultimul rand)
    page.draw_line(
        fitz.Point(x0, y0 + 3 * row_h), fitz.Point(x1, y0 + 3 * row_h),
        color=(0, 0, 0), width=0.5,
    )
    page.draw_line(
        fitz.Point(x0, y1 - row_h), fitz.Point(x1, y1 - row_h),
        color=(0, 0, 0), width=0.5,
    )

    # Logo optional (colt dreapta-sus al cartusului)
    logo_url = cf.get("firma_logo_url", "") or ""
    if logo_url:
        try:
            resp = requests.get(logo_url, timeout=10)
            resp.raise_for_status()
            lw = min(28.0, w * 0.18)
            lh = min(row_h * 1.6, 22.0)
            img_rect = fitz.Rect(x1 - 3 - lw, y0 + 2, x1 - 3, y0 + 2 + lh)
            page.insert_image(img_rect, stream=resp.content, keep_proportion=True)
        except Exception:
            pass


def _mask_margins(page, rooms, pad_frac=0.08, protect_top_frac=0.08):
    """Curatare partiala (~80%): maschera gunoiul din MARGINI pastrand arhitectura centrala.
    rooms = [{bbox:{x,y,w,h}} fractii 0-1] (de la Vision). union(bbox) + padding GENEROS = zona arhitecturii.
    Maschera cu alb cele 4 benzi din AFARA zonei; pastreaza o banda subtire sus (nord/titlu).
    NON-DESTRUCTIV pe arhitectura (padding). rooms gol/None -> nu maschera nimic (backward-compatible).
    Axele interioare RAMAN (cioturi) — acceptat la Pas 1. Intoarce [X0,Y0,X1,Y1] puncte PDF sau None."""
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

    # union in fractii + padding generos, clamp [0,1]
    ux0 = max(0.0, min(xs0) - pad_frac)
    uy0 = max(0.0, min(ys0) - pad_frac)
    ux1 = min(1.0, max(xs1) + pad_frac)
    uy1 = min(1.0, max(ys1) + pad_frac)

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
    rect(X1, Y0, W, Y1)        # DREAPTA
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
    _draw_cartus(page, bbox, cf, cp, plansa_nr, plansa_titlu, scara)

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
