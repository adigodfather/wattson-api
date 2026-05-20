"""
ZYNAPSE · Schema monofilară generator v2
========================================
Format panoramic: 297mm înălțime fixă, lățime variabilă (420/594/841mm).
Multi-page pentru tablouri mari (>18 circuite).

Acest modul (3a) implementează:
  - Modele Pydantic pentru request
  - Decizia de format (pick_layout)
  - Cadrul paginii + cartușul jos cu logo & date firmă
  - Stub pentru zona de schemă (umplut în Pasul 3b)
"""

from __future__ import annotations
from typing import List, Optional, Dict
from io import BytesIO
import base64
import os
import requests

from pydantic import BaseModel, Field
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, black

# =============================================================================
# FONTS (cu suport diacritice românești)
# =============================================================================

def _register_fonts():
    """DejaVu Sans pentru diacritice. Fallback la Helvetica."""
    candidates = [
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        ('/usr/share/fonts/dejavu/DejaVuSans.ttf',
         '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'),
    ]
    for regular, bold in candidates:
        if os.path.exists(regular) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont('Zynapse', regular))
                pdfmetrics.registerFont(TTFont('Zynapse-Bold', bold))
                return 'Zynapse', 'Zynapse-Bold'
            except Exception:
                pass
    return 'Helvetica', 'Helvetica-Bold'


FONT, FONT_BOLD = _register_fonts()

# =============================================================================
# CULORI (pentru linii faza — schema ramane lizibila si in B&W)
# =============================================================================
COLOR_PHASE_R       = HexColor('#c0392b')
COLOR_PHASE_S       = HexColor('#2c3e50')
COLOR_PHASE_T       = HexColor('#1a1a1a')
COLOR_NEUTRAL       = HexColor('#2980b9')
COLOR_PE            = HexColor('#27ae60')
COLOR_GREY          = HexColor('#888888')
COLOR_LIGHT_GREY    = HexColor('#dddddd')
COLOR_BUS_HIGHLIGHT = HexColor('#1a1a1a')


# =============================================================================
# CONSTANTE LAYOUT
# =============================================================================

# Page height — updated at runtime based on chosen format
_page_height_mm: int = 297


def set_page_height(h_mm: int):
    global _page_height_mm
    _page_height_mm = h_mm


def get_page_height() -> int:
    return _page_height_mm

MARGIN_MM = 6
HEADER_HEIGHT_MM = 22       # y: 6 → 28
SCHEMA_HEIGHT_MM = 130      # y: 30 → 160
TABLE_HEIGHT_MM = 50        # y: 162 → 212
LEGEND_NOTES_HEIGHT_MM = 28 # y: 214 → 242
CARTOUCHE_HEIGHT_MM = 49    # y: 244 → 293 (până la 297 - 4 margine jos)

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CartusFirma(BaseModel):
    """Date firmă din Supabase profile (populate prin /settings)."""
    firma_nume: str = ""
    firma_cui: str = ""
    firma_reg_com: str = ""
    firma_tel: str = ""
    firma_email: str = ""
    firma_adresa: str = ""
    firma_logo_url: str = ""
    proiectant_nume: str = ""
    desenator_nume: str = ""


class CartusProiect(BaseModel):
    """Date proiect din formular sau extrase din planșă."""
    beneficiar: str = ""
    amplasament: str = ""
    titlu_proiect: str = ""
    numar_proiect: str = ""
    data_proiect: str = ""
    faza: str = "DTAC+PT"
    plansa_nr: str = "IE.4"
    scara: str = "—"
    sef_proiect: str = ""


class Circuit(BaseModel):
    nr: str
    fasa: str = "R"             # "R" | "S" | "T" | "RST"
    destinatie: str = ""
    pi_kw: float = 0.0
    ia_a: float = 0.0
    protectie: str = ""
    cablu: str = ""
    tub: str = ""
    tip_consumator: str = "iluminat"   # "iluminat" | "priza" | "dedicat" | "sub_tablou"
    cantitate: int = 1
    rccb_group: Optional[str] = None
    has_rccb_individual: bool = False
    sub_tablou_color1: Optional[str] = None  # ex: "#00bfff"
    sub_tablou_color2: Optional[str] = None  # ex: "#ff69b4"


class MainBreaker(BaseModel):
    cod: str = "C0"
    tip: str = "MCB 3P+N 40A C 10kA"
    cablu_alim: str = "CYABY 5×10mmp"
    sursa: str = "De la BMPT"
    has_spd: bool = True
    spd_type: str = "Tip 2"


class RccbGroup(BaseModel):
    id: str
    cod: str = ""
    tip: str = "RCCB 4P 40A/30mA tip A"
    description: str = ""


class SchemaRequest(BaseModel):
    tablou_nume: str = "TEG"
    tablou_descriere: str = "TABLOU ELECTRIC GENERAL"
    pi_total_kw: float = 0
    pa_total_kw: float = 0
    ia_total_a: float = 0
    ku: float = 0.70
    racord: str = "Trifazat"
    main_breaker: MainBreaker = Field(default_factory=MainBreaker)
    rccb_groups: List[RccbGroup] = []
    circuits: List[Circuit] = []
    cartus_firma: CartusFirma = Field(default_factory=CartusFirma)
    cartus_proiect: CartusProiect = Field(default_factory=CartusProiect)
    format_preference: str = "auto"


# =============================================================================
# LAYOUT DECISION
# =============================================================================

def pick_layout(n_circuits: int, preference: str = "auto") -> Dict:
    """O singură pagină — A3 sau A2 — text mereu orizontal."""
    if preference == "A3":
        width, height = 420, 297
    elif preference == "A2":
        width, height = 594, 420
    else:  # auto
        if n_circuits <= 10:
            width, height = 420, 297
        else:
            width, height = 594, 420

    return {
        "width_mm": width,
        "height_mm": height,
        "circuits_per_page": n_circuits,
        "n_pages": 1,
        "rotated_text": False,
    }


def split_circuits(circuits: List[Circuit], cap: int) -> List[List[Circuit]]:
    return [circuits[i:i + cap] for i in range(0, len(circuits), cap)]


def get_zones(page_height_mm: int) -> Dict:
    """Y-uri zone pentru A3 sau A2. Tabel mai larg pentru detalii complete."""
    if page_height_mm <= 297:
        # A3 — pentru ≤ 10 circuite
        return {
            "schema_top": 30,
            "schema_bottom": 150,
            "table_top": 153,
            "table_bottom": 215,
            "legend_top": 218,
            "legend_bottom": 242,
            "cartouche_top": 244,
            "cartouche_bottom": 293,
        }
    else:
        # A2 — pentru 11+ circuite (până la ~40-50)
        return {
            "schema_top": 30,
            "schema_bottom": 150,
            "table_top": 153,
            "table_bottom": 295,
            "legend_top": 298,
            "legend_bottom": 322,
            "cartouche_top": 325,
            "cartouche_bottom": page_height_mm - 4,
        }


# =============================================================================
# COORDINATE HELPERS (top-down mm → ReportLab bottom-up points)
# =============================================================================

def to_y(y_top_mm: float) -> float:
    return (_page_height_mm - y_top_mm) * mm


# =============================================================================
# LOGO FETCHING
# =============================================================================

def fetch_logo(url: str) -> Optional[ImageReader]:
    """Download logo from public URL (Supabase storage). PNG/JPEG/WebP only."""
    if not url or not url.startswith('http'):
        return None
    if url.lower().endswith('.svg') or 'svg' in url.lower():
        # SVG not supported in this version (would need svglib)
        return None
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        return ImageReader(BytesIO(r.content))
    except Exception:
        return None


# =============================================================================
# PRIMITIVE DRAWING
# =============================================================================

def draw_text(c, x_mm, y_top_mm, text, font=FONT, size=8,
              color=black, anchor="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    text_str = str(text) if text is not None else ""
    if anchor == "center":
        c.drawCentredString(x_mm * mm, to_y(y_top_mm), text_str)
    elif anchor == "right":
        c.drawRightString(x_mm * mm, to_y(y_top_mm), text_str)
    else:
        c.drawString(x_mm * mm, to_y(y_top_mm), text_str)


def draw_line(c, x1, y1, x2, y2, width=0.4, color=black, dash=None):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    if dash:
        c.setDash(dash)
    c.line(x1 * mm, to_y(y1), x2 * mm, to_y(y2))
    if dash:
        c.setDash([])


def draw_rect(c, x_mm, y_top_mm, w, h, stroke_width=0.4,
              stroke=black, fill=None):
    c.setStrokeColor(stroke)
    c.setLineWidth(stroke_width)
    rl_y = to_y(y_top_mm + h)
    if fill:
        c.setFillColor(fill)
        c.rect(x_mm * mm, rl_y, w * mm, h * mm, stroke=1, fill=1)
    else:
        c.rect(x_mm * mm, rl_y, w * mm, h * mm, stroke=1, fill=0)


# =============================================================================
# SIMBOLURI ELECTRICE
# =============================================================================

def draw_mcb_box(c, cx_mm, y_top_mm, w_mm=22, h_mm=18,
                 line1="", line2="", font_size=7):
    """Box MCB cu text intern pe 2 linii. font_size configurabil pentru coloane înguste."""
    x = cx_mm - w_mm / 2
    draw_rect(c, x, y_top_mm, w_mm, h_mm, stroke_width=0.5)
    # Diagonal break line (simbol contactor)
    draw_line(c, cx_mm - 1.2, y_top_mm + 3, cx_mm + 1.2, y_top_mm + 5.5,
              width=0.5)
    # Pivot dot
    c.setFillColor(black)
    c.circle(cx_mm * mm, to_y(y_top_mm + 3), 0.4 * mm, stroke=0, fill=1)
    # Text
    if line1:
        draw_text(c, cx_mm, y_top_mm + h_mm - 7, line1,
                  font=FONT_BOLD, size=font_size, anchor="center")
    if line2:
        draw_text(c, cx_mm, y_top_mm + h_mm - 2, line2,
                  size=font_size, anchor="center")


def draw_rccb_box(c, cx_mm, y_top_mm, w_mm=22, h_mm=12, label="30mA"):
    """Box RCCB compact (sub MCB), cand circuitul are RCCB individual."""
    x = cx_mm - w_mm / 2
    draw_rect(c, x, y_top_mm, w_mm, h_mm, stroke_width=0.5)
    p = c.beginPath()
    side = 1.8
    p.moveTo((cx_mm - side) * mm, to_y(y_top_mm + 6))
    p.lineTo((cx_mm + side) * mm, to_y(y_top_mm + 6))
    p.lineTo(cx_mm * mm, to_y(y_top_mm + 3))
    p.close()
    c.setStrokeColor(black)
    c.setLineWidth(0.5)
    c.drawPath(p, stroke=1, fill=0)
    draw_text(c, cx_mm, y_top_mm + h_mm - 2, label,
              size=6, anchor="center")


def draw_lamp_symbol(c, cx_mm, cy_top_mm, r_mm=3, color=None):
    """⊗ — corp de iluminat. Default culoare ROȘU."""
    stroke_color = color if color is not None else HexColor('#c0392b')
    c.setStrokeColor(stroke_color)
    c.setLineWidth(0.7)
    c.circle(cx_mm * mm, to_y(cy_top_mm), r_mm * mm, stroke=1, fill=0)
    d = r_mm * 0.7
    c.line((cx_mm - d) * mm, to_y(cy_top_mm - d),
           (cx_mm + d) * mm, to_y(cy_top_mm + d))
    c.line((cx_mm - d) * mm, to_y(cy_top_mm + d),
           (cx_mm + d) * mm, to_y(cy_top_mm - d))
    # Reset stroke color la negru pentru elementele următoare
    c.setStrokeColor(black)


def draw_socket_symbol(c, cx_mm, cy_top_mm, r_mm=2.5):
    """Simbol priza 2P+E (Schuko) — semicerc deschis in sus (IEC 60617)."""
    c.setStrokeColor(black)
    c.setLineWidth(0.7)
    x1 = (cx_mm - r_mm) * mm
    y1 = to_y(cy_top_mm + r_mm)
    x2 = (cx_mm + r_mm) * mm
    y2 = to_y(cy_top_mm - r_mm)
    c.arc(x1, y1, x2, y2, 180, 180)  # semicerc deschis in sus


def draw_dedicated_symbol(c, cx_mm, cy_top_mm, size_mm=3):
    """Receptor dedicat (triunghi cu linie jos)."""
    c.setStrokeColor(black)
    c.setLineWidth(0.6)
    p = c.beginPath()
    p.moveTo((cx_mm - size_mm) * mm, to_y(cy_top_mm - size_mm / 2))
    p.lineTo((cx_mm + size_mm) * mm, to_y(cy_top_mm - size_mm / 2))
    p.lineTo(cx_mm * mm, to_y(cy_top_mm + size_mm * 1.3))
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    draw_line(c, cx_mm, cy_top_mm - size_mm * 1.5,
              cx_mm, cy_top_mm - size_mm / 2 - 0.5, width=0.7)


def draw_subtablou_symbol(c, cx_mm, cy_top_mm, w_mm=8, h_mm=5,
                          color1="#00bfff", color2="#ff69b4"):
    """Simbol sub-tablou (TE-CT, DCCS+NVR etc) — dreptunghi cu 2 triunghiuri
    dreptunghice colorate pe diagonala."""
    x_left  = cx_mm - w_mm / 2
    x_right = cx_mm + w_mm / 2
    y_top    = cy_top_mm - h_mm / 2
    y_bottom = cy_top_mm + h_mm / 2

    x_l = x_left  * mm
    x_r = x_right * mm
    y_t = to_y(y_top)
    y_b = to_y(y_bottom)

    # Triunghi 1: stanga-sus (top-left, top-right, bottom-left)
    p1 = c.beginPath()
    p1.moveTo(x_l, y_t)
    p1.lineTo(x_r, y_t)
    p1.lineTo(x_l, y_b)
    p1.close()
    c.setFillColor(HexColor(color1))
    c.setStrokeColor(black)
    c.setLineWidth(0.4)
    c.drawPath(p1, stroke=0, fill=1)

    # Triunghi 2: dreapta-jos (top-right, bottom-right, bottom-left)
    p2 = c.beginPath()
    p2.moveTo(x_r, y_t)
    p2.lineTo(x_r, y_b)
    p2.lineTo(x_l, y_b)
    p2.close()
    c.setFillColor(HexColor(color2))
    c.drawPath(p2, stroke=0, fill=1)

    # Outer border
    c.setStrokeColor(black)
    c.setFillColor(black)  # reset fill
    c.setLineWidth(0.5)
    c.rect(x_l, y_b, (x_right - x_left) * mm, (y_bottom - y_top) * mm,
           stroke=1, fill=0)

    # Diagonal separator
    c.setLineWidth(0.3)
    c.line(x_l, y_b, x_r, y_t)


def draw_load_symbol(c, cx_mm, cy_top_mm, circuit):
    """Dispatch pe tip_consumator. Accepta circuit intreg pentru culori."""
    tip = (circuit.tip_consumator or "").lower()
    if tip == "iluminat":
        draw_lamp_symbol(c, cx_mm, cy_top_mm, r_mm=2.5,
                         color=HexColor('#c0392b'))
    elif tip == "priza":
        draw_socket_symbol(c, cx_mm, cy_top_mm, r_mm=2.5)
    elif tip in ("sub_tablou", "subtablou", "tablou", "sub-tablou", "te"):
        c1 = circuit.sub_tablou_color1 or "#00bfff"
        c2 = circuit.sub_tablou_color2 or "#ff69b4"
        draw_subtablou_symbol(c, cx_mm, cy_top_mm, w_mm=8, h_mm=5,
                              color1=c1, color2=c2)
    else:
        draw_dedicated_symbol(c, cx_mm, cy_top_mm, size_mm=2.5)


def wrap_text(text: str, max_chars: int = 12, max_lines: int = 2) -> List[str]:
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    if not words:
        return [text[:max_chars]]
    lines = [words[0]]
    for w in words[1:]:
        candidate = lines[-1] + " " + w
        if len(candidate) <= max_chars:
            lines[-1] = candidate
        elif len(lines) < max_lines:
            lines.append(w)
        else:
            # truncate with ellipsis
            if len(lines[-1]) + 1 <= max_chars:
                lines[-1] = lines[-1] + "…"
            break
    return lines


# =============================================================================
# HELPERS — formatare continut text
# =============================================================================

def format_protection_short(protectie: str) -> tuple:
    """Imparte protectia in 2 linii scurte pentru afisare in box MCB.

    Exemple:
      'MCB 1P+N 10A C 30mA' -> ('MCB 1P+N 10A', 'C 30mA')
      'MCB 3P+N 40A C 10kA' -> ('MCB 3P+N 40A', 'C 10kA')
      'MCB 1P+N 16A C'      -> ('MCB 1P+N 16A', 'C')
    """
    parts = (protectie or "").split()
    if len(parts) <= 1:
        return protectie or "", ""
    amp_idx = -1
    for i, p in enumerate(parts):
        if p.endswith('A') and any(ch.isdigit() for ch in p):
            amp_idx = i
            break
    if 0 < amp_idx < len(parts) - 1:
        return " ".join(parts[:amp_idx + 1]), " ".join(parts[amp_idx + 1:])
    mid = len(parts) // 2
    return " ".join(parts[:mid]), " ".join(parts[mid:])


def format_quantity(circuit) -> str:
    """Eticheta cantitate sub simbolul de consumator."""
    qty = max(1, circuit.cantitate or 1)
    tip = (circuit.tip_consumator or "").lower()
    if tip == "iluminat":
        return f"{qty} LL"
    if tip == "priza":
        return f"{qty} LP"
    if tip in ("sub_tablou", "subtablou", "tablou", "sub-tablou", "te"):
        return ""  # destinatia apare in tabel; nimic sub simbol
    return "1 receptor" if qty == 1 else f"{qty} receptori"


def is_trifazat(racord: str) -> bool:
    return "tri" in (racord or "").lower()


def get_phase_label(circuit, idx: int) -> str:
    """Eticheta faza deasupra coloanei. Trifazat → 'R,S,T'."""
    nr_clean = (circuit.nr or f"C{idx}").lstrip("C")
    fasa_raw = (circuit.fasa or "R").upper().replace(" ", "").replace(",", "")

    if fasa_raw in ("RST", "TRIFAZAT", "TRI", "3F"):
        fasa_display = "R,S,T"
    elif len(fasa_raw) > 1 and all(ch in "RSTN" for ch in fasa_raw):
        fasa_display = ",".join(fasa_raw)
    else:
        fasa_display = fasa_raw

    return f"{nr_clean}({fasa_display})"


def phase_color(fasa: str):
    f = (fasa or "R").upper()
    if "R" in f:
        return COLOR_PHASE_R
    if "S" in f:
        return COLOR_PHASE_S
    if "T" in f:
        return COLOR_PHASE_T
    return COLOR_BUS_HIGHLIGHT


# =============================================================================
# PAGE FRAME
# =============================================================================

def draw_page_frame(c, width_mm: float):
    h = get_page_height()
    draw_rect(c, 3, 3, width_mm - 6, h - 6, stroke_width=0.8)
    draw_rect(c, 5, 5, width_mm - 10, h - 10, stroke_width=0.3)


# =============================================================================
# HEADER
# =============================================================================

def draw_header(c, width_mm: float, request: SchemaRequest):
    y_base = 10
    # LEFT
    draw_text(c, 10, y_base,      f"Pi = {request.pi_total_kw:.2f} kW", size=9, font=FONT)
    draw_text(c, 10, y_base + 5,  f"Pa = {request.pa_total_kw:.2f} kW", size=9, font=FONT)
    draw_text(c, 10, y_base + 10, f"Ia = {request.ia_total_a:.2f} A",   size=9, font=FONT)
    # CENTER
    cx = width_mm / 2
    draw_text(c, cx, y_base + 1,
              f"{request.tablou_nume} — {request.tablou_descriere}",
              font=FONT_BOLD, size=13, anchor="center")
    if request.cartus_proiect.titlu_proiect:
        draw_text(c, cx, y_base + 8, request.cartus_proiect.titlu_proiect,
                  size=9, anchor="center")
    if request.cartus_proiect.amplasament:
        draw_text(c, cx, y_base + 14, request.cartus_proiect.amplasament,
                  size=8, anchor="center")
    # RIGHT — show plansa_nr instead of "Pagina X din Y"
    rx = width_mm - 10
    draw_text(c, rx, y_base,     request.racord, size=9, anchor="right")
    draw_text(c, rx, y_base + 5, f"ku = {request.ku:.2f} · I7-2011", size=9, anchor="right")
    plansa = request.cartus_proiect.plansa_nr
    if plansa:
        draw_text(c, rx, y_base + 10, f"Planșa: {plansa}", size=9, anchor="right")
    # Underline
    draw_line(c, 6, 28, width_mm - 6, 28, width=0.3)


# =============================================================================
# SCHEMA AREA (stub — populat în Pasul 3b)
# =============================================================================

# =============================================================================
# MAIN BREAKER (zona stanga)
# =============================================================================

MAIN_BREAKER_WIDTH_MM = 60
SCHEMA_X_PADDING = 6
BUS_Y_TOP = 38
BUS_LINE_SPACING = 3
MCB_Y_TOP = 60
MCB_HEIGHT = 18
RCCB_Y_TOP = 80
RCCB_HEIGHT = 12


def draw_main_breaker(c, x_left_mm, width_mm, request):
    """Deseneaza blocul main breaker C0 pe stanga schemei."""
    cx = x_left_mm + width_mm / 2
    mb = request.main_breaker
    trifaz = is_trifazat(request.racord)

    draw_text(c, cx, 32, mb.cablu_alim or "", size=8, anchor="center")
    draw_text(c, cx, 35.5, mb.sursa or "", size=7, anchor="center",
              color=COLOR_GREY)

    conductors = [('R', COLOR_PHASE_R)] + (
        [('S', COLOR_PHASE_S), ('T', COLOR_PHASE_T)] if trifaz else []
    ) + [('N', COLOR_NEUTRAL)]

    spacing = 3
    total = (len(conductors) - 1) * spacing
    start_x = cx - total / 2
    for i, (phase, color) in enumerate(conductors):
        lx = start_x + i * spacing
        draw_line(c, lx, 39, lx, 58, width=1.2, color=color)

    mb_w = 40
    mb_h = 16
    mb_y = 58
    draw_rect(c, cx - mb_w / 2, mb_y, mb_w, mb_h, stroke_width=0.7)
    draw_text(c, cx, mb_y + 6, mb.cod or "C0",
              font=FONT_BOLD, size=11, anchor="center")
    draw_text(c, cx, mb_y + 12, mb.tip or "",
              size=7, anchor="center")

    if mb.has_spd:
        spd_y = mb_y + mb_h + 2
        draw_rect(c, cx - mb_w / 2, spd_y, mb_w, 10, stroke_width=0.5)
        draw_text(c, cx, spd_y + 6, f"SPD {mb.spd_type or 'Tip 2'}",
                  size=8, anchor="center")
        below = spd_y + 10
    else:
        below = mb_y + mb_h

    draw_line(c, cx, below + 1, cx, 100, width=1)

    draw_text(c, cx, 110, f"Pi = {request.pi_total_kw:.2f} kW",
              size=7, anchor="center")
    draw_text(c, cx, 114, f"Pa = {request.pa_total_kw:.2f} kW",
              size=7, anchor="center")
    draw_text(c, cx, 118, f"Ia = {request.ia_total_a:.2f} A",
              size=7, anchor="center", font=FONT_BOLD)
    draw_text(c, cx, 124, f"ku = {request.ku:.2f}",
              size=7, anchor="center", color=COLOR_GREY)


# =============================================================================
# BUS BARS (zona centrala sus)
# =============================================================================

def draw_bus_bars(c, x_start, x_end, racord: str):
    """Bare orizontale de distributie (R/S/T/N sau L/N)."""
    trifaz = is_trifazat(racord)
    if trifaz:
        bars = [('R', COLOR_PHASE_R), ('S', COLOR_PHASE_S),
                ('T', COLOR_PHASE_T), ('N', COLOR_NEUTRAL)]
    else:
        bars = [('L', COLOR_PHASE_R), ('N', COLOR_NEUTRAL)]

    for i, (label, color) in enumerate(bars):
        y = BUS_Y_TOP + i * BUS_LINE_SPACING
        draw_line(c, x_start, y, x_end, y, width=0.8, color=color)
        draw_text(c, x_start - 1.5, y + 1, label,
                  size=7, anchor="right", color=color)


# =============================================================================
# RCCB GROUP BRACKETS
# =============================================================================

def draw_rccb_brackets(c, page_circuits, columns_x, rccb_groups):
    """Deseneaza brackets orizontale deasupra grupelor de circuite
    care impart un RCCB comun."""
    if not rccb_groups or not page_circuits:
        return

    bus_bottom = BUS_Y_TOP + 3 * BUS_LINE_SPACING + 2
    groups_to_indices = {}
    for i, circuit in enumerate(page_circuits):
        gid = circuit.rccb_group
        if gid:
            groups_to_indices.setdefault(gid, []).append(i)

    groups_by_id = {g.id: g for g in rccb_groups}

    bracket_y = bus_bottom + 1.5
    bracket_drop = 2

    for gid, indices in groups_to_indices.items():
        x1 = columns_x[indices[0]] - 4
        x2 = columns_x[indices[-1]] + 4
        draw_line(c, x1, bracket_y, x1, bracket_y + bracket_drop, width=0.5)
        draw_line(c, x1, bracket_y, x2, bracket_y, width=0.5)
        draw_line(c, x2, bracket_y, x2, bracket_y + bracket_drop, width=0.5)
        rccb = groups_by_id.get(gid)
        if rccb:
            label = rccb.tip
            if rccb.description:
                label += f" — {rccb.description}"
            draw_text(c, (x1 + x2) / 2, bracket_y - 1, label,
                      size=7, anchor="center")


# =============================================================================
# RESERVE INDICATOR (zona dreapta)
# =============================================================================

def draw_reserve_indicator(c, x_start, x_end, y_top, y_bottom):
    """Box punctat cu 'REZERVA 30%' pe partea dreapta a schemei."""
    w = x_end - x_start
    h = y_bottom - y_top
    if w < 15:
        return
    draw_rect(c, x_start, y_top, w, h, stroke_width=0.4, stroke=COLOR_GREY)
    cx = x_start + w / 2
    draw_text(c, cx, y_top + 8,  "REZERVA",   font=FONT_BOLD, size=8, anchor="center")
    draw_text(c, cx, y_top + 13, "30%",        font=FONT_BOLD, size=9, anchor="center")
    draw_text(c, cx, y_top + 22, "3 plecari",  size=7, anchor="center", color=COLOR_GREY)
    draw_text(c, cx, y_top + 27, "libere",     size=7, anchor="center", color=COLOR_GREY)
    draw_text(c, cx, y_top + 40, "extindere",  size=7, anchor="center", color=COLOR_GREY)
    draw_text(c, cx, y_top + 45, "viitoare",   size=7, anchor="center", color=COLOR_GREY)


# =============================================================================
# COLOANA CIRCUIT INDIVIDUAL
# =============================================================================

def draw_circuit_column(c, cx_mm: float, col_width_mm: float,
                        circuit, idx: int, y_coords=None):
    """Coloană simplificată: phase + MCB + cable line + symbol + cantitate + Cn header.
    Detaliile tehnice complete (destinație, cablu, tub, protecție) apar doar în tabel.
    """
    # Font size adaptat pentru coloane înguste
    fs_small = 5.5 if col_width_mm < 17 else 6.5
    fs_mcb   = 5   if col_width_mm < 17 else 6
    fs_qty   = 6.5 if col_width_mm < 17 else 7.5
    fs_nr    = 7   if col_width_mm < 17 else 8

    # Phase label deasupra bus-ului
    fasa_color = phase_color(circuit.fasa)
    draw_text(c, cx_mm, 36, get_phase_label(circuit, idx),
              font=FONT_BOLD, size=fs_small, anchor="center", color=fasa_color)

    # Linia verticală principală — de la bus la MCB
    draw_line(c, cx_mm, 44, cx_mm, MCB_Y_TOP, width=0.4)

    # Box MCB
    line1, line2 = format_protection_short(circuit.protectie)
    mcb_w = min(col_width_mm - 1, 14)
    draw_mcb_box(c, cx_mm, MCB_Y_TOP, w_mm=mcb_w, h_mm=MCB_HEIGHT,
                 line1=line1, line2=line2, font_size=fs_mcb)

    bottom_mcb = MCB_Y_TOP + MCB_HEIGHT

    # RCCB individual (opțional)
    if circuit.has_rccb_individual:
        rccb_y = bottom_mcb + 2
        draw_line(c, cx_mm, bottom_mcb, cx_mm, rccb_y, width=0.4)
        draw_rccb_box(c, cx_mm, rccb_y, w_mm=mcb_w, h_mm=RCCB_HEIGHT, label="30mA")
        below_rccb = rccb_y + RCCB_HEIGHT
    else:
        below_rccb = bottom_mcb

    # Cablu line vertical simpla (fara text — detaliile sunt in tabel)
    cable_end_y = 122  # mai aproape de simbol (load_y=125)
    draw_line(c, cx_mm, below_rccb, cx_mm, cable_end_y, width=0.4)

    # Load symbol cu culoare specifica tipului
    load_y = 125
    draw_load_symbol(c, cx_mm, load_y, circuit)

    # Cantitate sub simbol: "12 LL", "5 LP", "1 receptor"
    draw_text(c, cx_mm, 134, format_quantity(circuit),
              font=FONT_BOLD, size=fs_qty, anchor="center")

    # Header circuit "Cn"
    draw_text(c, cx_mm, 144, circuit.nr or f"C{idx}",
              font=FONT_BOLD, size=fs_nr, anchor="center")


# =============================================================================
# SCHEMA FULL (v3b-fix) — single-page with optional rotated text
# =============================================================================

def draw_schema_full(c, width_mm: float, request, page_circuits,
                     page_num: int, layout: Dict, zones: Dict):
    """Versiunea finală — text mereu orizontal, layout INSTAUDITOR style."""
    if not page_circuits:
        draw_text(c, width_mm / 2, 95, "Nicio plecare pe această pagină",
                  size=9, anchor="center", color=COLOR_GREY)
        return

    schema_bottom = zones["schema_bottom"]

    # Main breaker stânga
    mb_x = SCHEMA_X_PADDING
    mb_w = MAIN_BREAKER_WIDTH_MM
    draw_main_breaker(c, mb_x, mb_w, request)

    # Coloane circuite + zona rezervă
    circuits_x_start = mb_x + mb_w + 4
    reserve_w = 22
    circuits_x_end = width_mm - SCHEMA_X_PADDING - reserve_w - 2

    n = len(page_circuits)
    available = circuits_x_end - circuits_x_start
    col_width = available / n
    columns_x = [circuits_x_start + col_width * (i + 0.5) for i in range(n)]

    # Bus bars
    bus_start = mb_x + mb_w / 2 + 2
    bus_end   = circuits_x_end
    draw_bus_bars(c, bus_start, bus_end, request.racord)

    # RCCB brackets (opționale, deasupra grupelor)
    draw_rccb_brackets(c, page_circuits, columns_x, request.rccb_groups)

    # Puncte de conexiune la bus
    for i, x in enumerate(columns_x):
        fasa = (page_circuits[i].fasa or "R").upper()
        bus_y_target = BUS_Y_TOP
        if "S" in fasa and "R" not in fasa:
            bus_y_target = BUS_Y_TOP + BUS_LINE_SPACING
        elif "T" in fasa and "R" not in fasa and "S" not in fasa:
            bus_y_target = BUS_Y_TOP + 2 * BUS_LINE_SPACING
        c.setFillColor(black)
        c.circle(x * mm, to_y(bus_y_target), 0.5 * mm, stroke=0, fill=1)

    # Coloane circuite
    for i, circuit in enumerate(page_circuits):
        draw_circuit_column(c, columns_x[i], col_width, circuit, i + 1)

    # Rezervă
    draw_reserve_indicator(c, circuits_x_end + 2,
                           width_mm - SCHEMA_X_PADDING,
                           BUS_Y_TOP, schema_bottom - 4)


def draw_schema_stub(c, width_mm: float, circuits: List[Circuit]):
    """Stub gri pentru zona schemei. Înlocuit în Pasul 3b."""
    y_start = 30
    draw_rect(c, 6, y_start, width_mm - 12, SCHEMA_HEIGHT_MM,
              stroke_width=0.3, stroke=HexColor('#cccccc'))
    draw_text(c, width_mm / 2, y_start + SCHEMA_HEIGHT_MM / 2 - 5,
              f"[ Zona schemei — {len(circuits)} circuite ]",
              size=11, anchor="center", color=HexColor('#888888'),
              font=FONT_BOLD)
    draw_text(c, width_mm / 2, y_start + SCHEMA_HEIGHT_MM / 2 + 3,
              "se umple în Pasul 3b (main breaker · RCCB · MCB · cabluri · simboluri)",
              size=8, anchor="center", color=HexColor('#999999'))


def draw_table_full(c, width_mm: float, page_circuits,
                    y_start: int, y_end: int):
    """Tabel detaliat — 7 coloane (ca INSTAUDITOR):
    Nr. | Destinatie | Pi (kW) | Ia (A) | Protectie | Cablu/conductor | Tub/pozare
    """
    h = y_end - y_start
    x_start = SCHEMA_X_PADDING
    w = width_mm - 2 * SCHEMA_X_PADDING

    # Outer border
    draw_rect(c, x_start, y_start, w, h, stroke_width=0.6)

    # Header row
    header_h = 5
    draw_rect(c, x_start, y_start, w, header_h,
              stroke_width=0.3, fill=HexColor('#f5f5f5'))

    # 7 coloane: Nr | Destinatie | Pi | Ia | Protectie | Cablu | Tub
    col_pct = [0.05, 0.24, 0.08, 0.08, 0.17, 0.20, 0.18]
    col_w = [w * p for p in col_pct]
    col_x = [x_start]
    for cw in col_w[:-1]:
        col_x.append(col_x[-1] + cw)

    headers = ['Nr.', 'Destinatie', 'Pi (kW)', 'Ia (A)',
               'Protectie', 'Cablu / conductor', 'Tub / pozare']
    for x, cw, lbl in zip(col_x, col_w, headers):
        draw_text(c, x + cw / 2, y_start + 3.5, lbl,
                  font=FONT_BOLD, size=7, anchor="center")

    # Vertical separators
    for x in col_x[1:]:
        draw_line(c, x, y_start, x, y_end, width=0.3)

    # Data rows
    n = len(page_circuits)
    if n == 0:
        return

    row_h = (h - header_h) / max(n, 1)

    # Font scalat in functie de inaltimea randului
    if row_h >= 5.5:
        font_size = 8
    elif row_h >= 4.5:
        font_size = 7
    elif row_h >= 3.5:
        font_size = 6
    else:
        font_size = 5.5

    for i, circuit in enumerate(page_circuits):
        ry = y_start + header_h + i * row_h
        if i > 0:
            draw_line(c, x_start, ry, x_start + w, ry,
                      width=0.15, color=COLOR_LIGHT_GREY)
        cy = ry + row_h - 1.5

        # 1. Nr (centrat, bold)
        draw_text(c, col_x[0] + col_w[0] / 2, cy, circuit.nr or "-",
                  size=font_size, anchor="center", font=FONT_BOLD)
        # 2. Destinatie (left aligned, complet)
        dest = circuit.destinatie or "-"
        max_dest_chars = int(col_w[1] / (font_size * 0.18))
        if len(dest) > max_dest_chars:
            dest = dest[:max_dest_chars - 1] + "..."
        draw_text(c, col_x[1] + 2, cy, dest, size=font_size)
        # 3. Pi
        draw_text(c, col_x[2] + col_w[2] / 2, cy, f"{circuit.pi_kw:.2f}",
                  size=font_size, anchor="center")
        # 4. Ia
        draw_text(c, col_x[3] + col_w[3] / 2, cy, f"{circuit.ia_a:.2f}",
                  size=font_size, anchor="center")
        # 5. Protectie
        prot = circuit.protectie or "-"
        max_prot_chars = int(col_w[4] / (font_size * 0.20))
        if len(prot) > max_prot_chars:
            prot = prot[:max_prot_chars - 1] + "..."
        draw_text(c, col_x[4] + 2, cy, prot, size=font_size)
        # 6. Cablu
        cab = circuit.cablu or "-"
        max_cab_chars = int(col_w[5] / (font_size * 0.20))
        if len(cab) > max_cab_chars:
            cab = cab[:max_cab_chars - 1] + "..."
        draw_text(c, col_x[5] + 2, cy, cab, size=font_size)
        # 7. Tub
        tub = circuit.tub or "-"
        max_tub_chars = int(col_w[6] / (font_size * 0.20))
        if len(tub) > max_tub_chars:
            tub = tub[:max_tub_chars - 1] + "..."
        draw_text(c, col_x[6] + 2, cy, tub, size=font_size)


def draw_table_stub(c, width_mm: float, circuits: List[Circuit]):
    y_start = 162
    h = TABLE_HEIGHT_MM
    draw_rect(c, 6, y_start, width_mm - 12, h,
              stroke_width=0.3, stroke=HexColor('#cccccc'))
    draw_text(c, width_mm / 2, y_start + h / 2,
              f"[ Tabel date — Nr / Pi / Ia / Cablu / Tub — {len(circuits)} rânduri ]",
              size=9, anchor="center", color=HexColor('#888888'))


def draw_legend_notes_full(c, width_mm: float, zones: Dict = None):
    if zones:
        y_start = zones["legend_top"]
        h = zones["legend_bottom"] - y_start
    else:
        y_start = 214
        h = 28

    # ---- LEGENDA (stanga, ~32% latime) ----
    leg_w = width_mm * 0.32
    leg_x = SCHEMA_X_PADDING
    draw_rect(c, leg_x, y_start, leg_w, h, stroke_width=0.5)
    draw_text(c, leg_x + leg_w / 2, y_start + 4, "LEGENDA",
              font=FONT_BOLD, size=9, anchor="center")
    draw_line(c, leg_x, y_start + 6, leg_x + leg_w, y_start + 6, width=0.2)

    ly = y_start + 10
    draw_mcb_box(c, leg_x + 7, ly - 1, w_mm=10, h_mm=6, line1="", line2="")
    draw_text(c, leg_x + 16, ly + 1.5, "MCB — disjunctor termo-magnetic", size=7)
    ly += 5
    draw_rccb_box(c, leg_x + 7, ly - 1, w_mm=10, h_mm=6, label="")
    draw_text(c, leg_x + 16, ly + 1.5, "RCCB — protectie diferentiala", size=7)
    ly += 5
    draw_lamp_symbol(c, leg_x + 7, ly, r_mm=2.2, color=HexColor('#c0392b'))
    draw_text(c, leg_x + 16, ly + 1, "LL — corp de iluminat 230V", size=7)
    ly += 5
    draw_socket_symbol(c, leg_x + 7, ly, r_mm=1.8)
    draw_text(c, leg_x + 16, ly + 1, "LP — priza 230V", size=7)
    ly += 5
    draw_subtablou_symbol(c, leg_x + 7, ly, w_mm=6, h_mm=3.5,
                          color1="#00bfff", color2="#ff69b4")
    draw_text(c, leg_x + 16, ly + 1, "Sub-tablou (TE-CT, anexe, etc.)", size=7)

    # ---- NOTE (dreapta, restul) ----
    notes_x = leg_x + leg_w + 4
    notes_w = width_mm - SCHEMA_X_PADDING - notes_x
    draw_rect(c, notes_x, y_start, notes_w, h, stroke_width=0.5)
    draw_text(c, notes_x + notes_w / 2, y_start + 4, "NOTE",
              font=FONT_BOLD, size=9, anchor="center")
    draw_line(c, notes_x, y_start + 6, notes_x + notes_w, y_start + 6, width=0.2)
    ny = y_start + 10
    notes = [
        "Nota 1: I7-2011 Tab. 3.5 — coeficient de utilizare ku conform tip cladire.",
        "Nota 2: Executantul va respecta I7-2011, SR EN 60364, Legea 10/1995.",
        "Nota 3: Protectiile se reverifica daca Isc difera de cel de calcul.",
        "Nota 4: Toate prizele din bai se conecteaza la RCCB tip A 10mA.",
    ]
    for note in notes:
        draw_text(c, notes_x + 3, ny, note, size=7)
        ny += 4


def draw_legend_notes_stub(c, width_mm: float):
    y_start = 214
    h = LEGEND_NOTES_HEIGHT_MM
    # Legendă (stânga)
    draw_rect(c, 6, y_start, width_mm * 0.35, h, stroke_width=0.5)
    draw_text(c, 6 + (width_mm * 0.35) / 2, y_start + 4,
              "LEGENDA", font=FONT_BOLD, size=9, anchor="center")
    draw_text(c, 10, y_start + 10,
              "MCB · RCCB · corp iluminat · priza · receptor dedicat",
              size=7)
    # Note (dreapta)
    nx = 6 + width_mm * 0.35 + 4
    nw = width_mm - 10 - nx
    draw_rect(c, nx, y_start, nw, h, stroke_width=0.5)
    draw_text(c, nx + nw / 2, y_start + 4, "NOTE",
              font=FONT_BOLD, size=9, anchor="center")
    draw_text(c, nx + 2, y_start + 10,
              "Nota 1: I7-2011 Tab. 3.5 — coeficient de utilizare ku conform tip cladire.",
              size=7)
    draw_text(c, nx + 2, y_start + 15,
              "Nota 2: Executantul va respecta I7-2011, SR EN 60364, Legea 10/1995.",
              size=7)
    draw_text(c, nx + 2, y_start + 20,
              "Nota 3: Protectiile se reverifca daca Isc difera de calcul.",
              size=7)


# =============================================================================
# CARTOUCHE (full implementation in 3a — to be tested)
# =============================================================================

def draw_cartouche(c, width_mm: float, request: SchemaRequest, zones: Dict = None):
    """
    Cartus jos pe toata latimea. Trei zone:
      [STANGA] Logo + date firma         (latime 80mm)
      [CENTRU] Proiectant / Beneficiar   (latime flexibila)
      [DREAPTA] Faza / Plansa / Data     (latime 70mm)
    """
    if zones:
        y_start = zones["cartouche_top"]
        h = zones["cartouche_bottom"] - y_start
    else:
        y_start = 244
        h = CARTOUCHE_HEIGHT_MM
    x = 6
    w = width_mm - 12

    draw_rect(c, x, y_start, w, h, stroke_width=0.7)

    # ----- ZONA STANGA: Logo + firma -----
    left_w = 80
    draw_rect(c, x, y_start, left_w, h, stroke_width=0.3)

    firma = request.cartus_firma
    logo_h = 18
    logo_w = left_w - 8
    logo_x = x + 4
    logo_y = y_start + 3

    logo = fetch_logo(firma.firma_logo_url)
    if logo:
        try:
            c.drawImage(logo, logo_x * mm, to_y(logo_y + logo_h),
                        width=logo_w * mm, height=logo_h * mm,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            draw_text(c, x + left_w / 2, logo_y + logo_h / 2,
                      "[ logo error ]", size=7, anchor="center",
                      color=HexColor('#999999'))
    else:
        draw_text(c, x + left_w / 2, logo_y + logo_h / 2 + 1,
                  "[ LOGO ]", font=FONT_BOLD, size=10, anchor="center",
                  color=HexColor('#bbbbbb'))

    # Firma details — sub logo
    fy = y_start + logo_h + 6
    fx_center = x + left_w / 2
    if firma.firma_nume:
        draw_text(c, fx_center, fy, firma.firma_nume,
                  font=FONT_BOLD, size=8, anchor="center")
    fy += 4
    if firma.firma_cui or firma.firma_reg_com:
        line = " · ".join(filter(None, [firma.firma_cui, firma.firma_reg_com]))
        draw_text(c, fx_center, fy, line, size=7, anchor="center")
    fy += 4
    if firma.firma_tel:
        draw_text(c, fx_center, fy, f"tel: {firma.firma_tel}",
                  size=7, anchor="center")
    fy += 4
    if firma.firma_email:
        draw_text(c, fx_center, fy, firma.firma_email,
                  size=7, anchor="center")
    fy += 4
    if firma.firma_adresa:
        addr_lines = wrap_text(firma.firma_adresa, max_chars=32, max_lines=2)
        for line in addr_lines:
            draw_text(c, fx_center, fy, line, size=7, anchor="center")
            fy += 4

    # ----- ZONA DREAPTA: Faza / Plansa / Data / Scara -----
    right_w = 70
    right_x = x + w - right_w
    draw_rect(c, right_x, y_start, right_w, h, stroke_width=0.3)

    proiect = request.cartus_proiect
    rows = [
        ("Faza:",    proiect.faza or "DTAC+PT"),
        ("Plansa:",  proiect.plansa_nr or "IE.4"),
        ("Proiect:", proiect.numar_proiect or "—"),
        ("Data:",    proiect.data_proiect or "—"),
        ("Scara:",   proiect.scara or "—"),
    ]
    row_h = (h - 6) / len(rows)
    for i, (label, value) in enumerate(rows):
        ry = y_start + 3 + i * row_h
        draw_text(c, right_x + 3, ry + row_h - 2, label, size=8)
        draw_text(c, right_x + right_w - 3, ry + row_h - 2, value,
                  font=FONT_BOLD, size=8, anchor="right")
        if i < len(rows) - 1:
            draw_line(c, right_x, ry + row_h, right_x + right_w, ry + row_h,
                      width=0.2, color=HexColor('#cccccc'))

    # ----- ZONA CENTRU: Proiectant + Beneficiar -----
    center_x = x + left_w
    center_w = w - left_w - right_w
    draw_rect(c, center_x, y_start, center_w, h, stroke_width=0.3)

    # Sus: roluri proiectant
    cy = y_start + 4
    draw_text(c, center_x + 3, cy, "PROIECTANT INSTALATII ELECTRICE",
              font=FONT_BOLD, size=8)
    draw_line(c, center_x, cy + 1, center_x + center_w, cy + 1,
              width=0.2, color=HexColor('#cccccc'))
    cy += 5
    role_rows = [
        ("Sef proiect:", proiect.sef_proiect or firma.proiectant_nume or "—"),
        ("Proiectat:",   firma.proiectant_nume or "—"),
        ("Desenat:",     firma.desenator_nume or "—"),
    ]
    for label, value in role_rows:
        draw_text(c, center_x + 3, cy, label, size=8)
        draw_text(c, center_x + 26, cy, value, font=FONT_BOLD, size=8)
        cy += 4.5

    # Mijloc: separator
    draw_line(c, center_x, cy + 1, center_x + center_w, cy + 1,
              width=0.3, color=HexColor('#999999'))
    cy += 5

    # Jos: beneficiar + amplasament + titlu
    draw_text(c, center_x + 3, cy, "Beneficiar:", size=8)
    draw_text(c, center_x + 26, cy,
              proiect.beneficiar or "—", font=FONT_BOLD, size=8)
    cy += 4.5
    draw_text(c, center_x + 3, cy, "Amplasament:", size=8)
    draw_text(c, center_x + 26, cy, (proiect.amplasament or "—")[:60], size=8)
    cy += 4.5
    draw_text(c, center_x + 3, cy, "Titlu proiect:", size=8)
    draw_text(c, center_x + 26, cy, (proiect.titlu_proiect or "—")[:60], size=8)

    # Titlul schemei jos centrat
    draw_text(c, center_x + center_w / 2, y_start + h - 4,
              f"SCHEMA ELECTRICA MONOFILARA — {request.tablou_nume}",
              font=FONT_BOLD, size=10, anchor="center")


# =============================================================================
# MAIN PDF GENERATOR
# =============================================================================

def generate_schema_pdf(request: SchemaRequest) -> bytes:
    """Generate the schema PDF as a single page, returning raw bytes."""
    n_circuits = len(request.circuits)
    layout = pick_layout(n_circuits, request.format_preference)

    page_h = layout["height_mm"]
    set_page_height(page_h)
    zones = get_zones(page_h)

    buf = BytesIO()
    page_size = (layout["width_mm"] * mm, page_h * mm)
    c = canvas.Canvas(buf, pagesize=page_size)

    draw_page_frame(c, layout["width_mm"])
    draw_header(c, layout["width_mm"], request)
    draw_schema_full(c, layout["width_mm"], request,
                     request.circuits or [], 1, layout, zones)
    draw_table_full(c, layout["width_mm"], request.circuits or [],
                    zones["table_top"], zones["table_bottom"])
    draw_legend_notes_full(c, layout["width_mm"], zones)
    draw_cartouche(c, layout["width_mm"], request, zones)
    c.showPage()

    c.save()
    return buf.getvalue()


# =============================================================================
# SAMPLE DATA (pentru endpoint de test)
# =============================================================================

def build_sample_request() -> SchemaRequest:
    """Sample TEG cu 31 circuite — Camin Cultural Orvisele."""
    circuits = []
    for i in range(1, 11):
        circuits.append(Circuit(
            nr=f"C{i}", fasa="RST"[(i - 1) % 3],
            destinatie=f"Iluminat zona {i}",
            pi_kw=0.62, ia_a=2.95,
            protectie="MCB 1P+N 10A C 30mA",
            cablu="CYY-F 3x1.5 mmp",
            tub="tub IPEY d16 mm",
            tip_consumator="iluminat", cantitate=8,
            rccb_group="block_1",
        ))
    for i in range(11, 29):
        circuits.append(Circuit(
            nr=f"C{i}", fasa="RST"[(i - 1) % 3],
            destinatie=f"Prize P{i - 10:02d}",
            pi_kw=1.50, ia_a=6.52,
            protectie="MCB 1P+N 16A C 30mA",
            cablu="CYY-F 3x2.5 mmp",
            tub="tub IPEY d20 mm",
            tip_consumator="priza", cantitate=5,
            rccb_group="block_2",
        ))
    circuits += [
        Circuit(nr="C29", fasa="R", destinatie="DCCS+NVR — Distributie control",
                pi_kw=0.5, ia_a=2.17,
                protectie="MCB 1P+N 10A B 6kA 30mA",
                cablu="CYY-F 3x1.5 mmp",
                tub="tub IPEY d16 mm",
                tip_consumator="sub_tablou", cantitate=1,
                sub_tablou_color1="#00bfff",
                sub_tablou_color2="#ff69b4"),
        Circuit(nr="C30", fasa="RST", destinatie="TE-CT — Tablou Camera Tehnica",
                pi_kw=16.34, ia_a=22.95,
                protectie="MCB 3P+N 25A B 10kA",
                cablu="CYY-F 5x4 mmp",
                tub="tub IPEY d32 mm",
                tip_consumator="sub_tablou", cantitate=1,
                sub_tablou_color1="#ffffff",
                sub_tablou_color2="#3498db"),
        Circuit(nr="C31", fasa="T", destinatie="Boiler ACM",
                pi_kw=3.0, ia_a=13.04,
                protectie="MCB 1P+N 16A C",
                cablu="CYY-F 3x2.5 mmp",
                tub="tub IPEY d20 mm",
                tip_consumator="dedicat", cantitate=1),
    ]
    return SchemaRequest(
        tablou_nume="TEG-A",
        tablou_descriere="TABLOU ELECTRIC GENERAL",
        pi_total_kw=62.85, pa_total_kw=43.99, ia_total_a=100.79,
        ku=0.70, racord="Trifazat 3x230V+N+PE",
        main_breaker=MainBreaker(
            cod="C0", tip="MCB 3P+N 40A C 10kA",
            cablu_alim="CYABY 5x10mmp", sursa="De la BMPT",
            has_spd=True, spd_type="Tip 2"),
        rccb_groups=[
            RccbGroup(id="block_1",
                      tip="RCCB 4P 40A/30mA tip A",
                      description="Iluminat sali"),
            RccbGroup(id="block_2",
                      tip="RCCB 4P 40A/30mA tip A",
                      description="Prize generale"),
        ],
        circuits=circuits,
        cartus_proiect=CartusProiect(
            beneficiar="COMUNA BRUSTURI",
            amplasament="Sat Orvisele, com. Brusturi, jud. Bihor",
            titlu_proiect="Amenajari interioare si extindere terasa · Camin Cultural",
            numar_proiect="5/8/03",
            data_proiect="2026",
            faza="DTAC+PT",
            plansa_nr="IE.4A",
            scara="—",
        ),
    )
