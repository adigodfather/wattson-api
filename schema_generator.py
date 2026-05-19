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
# CONSTANTE LAYOUT
# =============================================================================

PAGE_HEIGHT_MM = 297  # fix — A3 short edge

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
    tip_consumator: str = "iluminat"   # "iluminat" | "priza" | "dedicat"
    cantitate: int = 1
    rccb_group: Optional[str] = None
    has_rccb_individual: bool = False


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
    if preference == "A3":
        width, cap = 420, 7
    elif preference == "A2":
        width, cap = 594, 12
    elif preference == "A1":
        width, cap = 841, 18
    else:
        if n_circuits <= 7:
            width, cap = 420, 7
        elif n_circuits <= 12:
            width, cap = 594, 12
        else:
            width, cap = 841, 18

    n_pages = max(1, (n_circuits + cap - 1) // cap)
    return {
        "width_mm": width,
        "height_mm": PAGE_HEIGHT_MM,
        "circuits_per_page": cap,
        "n_pages": n_pages,
    }


def split_circuits(circuits: List[Circuit], cap: int) -> List[List[Circuit]]:
    return [circuits[i:i + cap] for i in range(0, len(circuits), cap)]


# =============================================================================
# COORDINATE HELPERS (top-down mm → ReportLab bottom-up points)
# =============================================================================

def to_y(y_top_mm: float) -> float:
    return (PAGE_HEIGHT_MM - y_top_mm) * mm


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
# PAGE FRAME
# =============================================================================

def draw_page_frame(c, width_mm: float):
    draw_rect(c, 3, 3, width_mm - 6, PAGE_HEIGHT_MM - 6, stroke_width=0.8)
    draw_rect(c, 5, 5, width_mm - 10, PAGE_HEIGHT_MM - 10, stroke_width=0.3)


# =============================================================================
# HEADER
# =============================================================================

def draw_header(c, width_mm: float, request: SchemaRequest,
                page_num: int, n_pages: int):
    y_base = 10
    # LEFT
    draw_text(c, 10, y_base, f"Pi = {request.pi_total_kw:.2f} kW",
              size=9, font=FONT)
    draw_text(c, 10, y_base + 5, f"Pa = {request.pa_total_kw:.2f} kW",
              size=9, font=FONT)
    draw_text(c, 10, y_base + 10, f"Ia = {request.ia_total_a:.2f} A",
              size=9, font=FONT)
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
    # RIGHT
    rx = width_mm - 10
    draw_text(c, rx, y_base, request.racord, size=9, anchor="right")
    draw_text(c, rx, y_base + 5, f"ku = {request.ku:.2f} · I7-2011",
              size=9, anchor="right")
    if n_pages > 1:
        draw_text(c, rx, y_base + 10, f"Pagina {page_num} din {n_pages}",
                  size=9, anchor="right")
    # Underline
    draw_line(c, 6, 28, width_mm - 6, 28, width=0.3)


# =============================================================================
# SCHEMA AREA (stub — populat în Pasul 3b)
# =============================================================================

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


def draw_table_stub(c, width_mm: float, circuits: List[Circuit]):
    y_start = 162
    h = TABLE_HEIGHT_MM
    draw_rect(c, 6, y_start, width_mm - 12, h,
              stroke_width=0.3, stroke=HexColor('#cccccc'))
    draw_text(c, width_mm / 2, y_start + h / 2,
              f"[ Tabel date — Nr / Pi / Ia / Cablu / Tub — {len(circuits)} rânduri ]",
              size=9, anchor="center", color=HexColor('#888888'))


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

def draw_cartouche(c, width_mm: float, request: SchemaRequest):
    """
    Cartus jos pe toata latimea. Trei zone:
      [STANGA] Logo + date firma         (latime 80mm)
      [CENTRU] Proiectant / Beneficiar   (latime flexibila)
      [DREAPTA] Faza / Plansa / Data     (latime 70mm)
    """
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
    """Generate the schema PDF, returning raw bytes."""
    n_circuits = len(request.circuits)
    layout = pick_layout(n_circuits, request.format_preference)
    pages = split_circuits(request.circuits, layout["circuits_per_page"]) \
        if request.circuits else [[]]

    buf = BytesIO()
    page_size = (layout["width_mm"] * mm, PAGE_HEIGHT_MM * mm)
    c = canvas.Canvas(buf, pagesize=page_size)

    for idx, page_circuits in enumerate(pages, start=1):
        c.setPageSize(page_size)
        draw_page_frame(c, layout["width_mm"])
        draw_header(c, layout["width_mm"], request, idx, layout["n_pages"])
        draw_schema_stub(c, layout["width_mm"], page_circuits)        # 3b
        draw_table_stub(c, layout["width_mm"], page_circuits)         # 3b
        draw_legend_notes_stub(c, layout["width_mm"])                  # 3b
        draw_cartouche(c, layout["width_mm"], request)
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
        Circuit(nr="C29", fasa="R", destinatie="Panouri fotovoltaice",
                pi_kw=5.0, ia_a=21.7,
                protectie="MCB 1P+N 20A C",
                cablu="CYY-F 3x4 mmp",
                tub="tub IPEY d25 mm",
                tip_consumator="dedicat", cantitate=1),
        Circuit(nr="C30", fasa="S", destinatie="Boiler ACM",
                pi_kw=3.0, ia_a=13.04,
                protectie="MCB 1P+N 16A C",
                cablu="CYY-F 3x2.5 mmp",
                tub="tub IPEY d20 mm",
                tip_consumator="dedicat", cantitate=1),
        Circuit(nr="C31", fasa="T", destinatie="Ventilatie cu recuperare",
                pi_kw=1.5, ia_a=6.52,
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
