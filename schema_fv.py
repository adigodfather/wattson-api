# -*- coding: utf-8 -*-
"""
ZYNAPSE · Schema monofilara SISTEM FOTOVOLTAIC (planșa IE finală)
=================================================================
Șablon FIX (poziții hardcodate, ca modelul IE.5 al lui Dan) + valorile pachetului injectate
în text. TOATE pachetele trifazate; desenul are MEREU 2 string-uri (textul spune numărul real —
decizia Dan). ReportLab, refolosind fonturile/culorile/cadrul/cartușul din schema_generator
(NU se atinge schema v2 existentă).

Fazare: F0 = pachete + schelet (cadru/titlu/note/legendă/cartuș) · F1 = câmpul PV (string-uri,
panouri, cablu solar, PE câmp) · F2 = T.CC + invertor · F3 = T.CA + contor + TEG · F4 = BMPT.
"""

from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

from schema_generator import (
    FONT, FONT_BOLD,
    COLOR_PHASE_R, COLOR_NEUTRAL, COLOR_PE, COLOR_GREY,
    set_page_height, to_y,
    draw_text, draw_line, draw_rect,
    draw_page_frame, draw_cartouche,
    CartusFirma, CartusProiect,
)

# =============================================================================
# PACHETELE FV (tabelul Dan, 2026-07) — valorile VARIABILE per pachet.
# =============================================================================
FV_PACKAGES = {
    5:  {"nr_panouri": 9,  "pi_kw": 4.95,  "nr_stringuri": 1, "invertor_cc_kw": 5,  "invertor_ca_kw": 5,
         "nr_mppt": 1, "cablu_solar": "2x (1x 6)", "brk_dc_1p": "1x 1P\n1000V\n16A", "brk_dc_2p": "1x 2P\n1000V\n20A",
         "cyy_f": "CYY-F 5x 4", "comutator_ac": "C16 A", "racord_teg": "B32 A", "cyaby": "CYABY 5x 6", "tub": "PVC DN 32"},
    10: {"nr_panouri": 18, "pi_kw": 9.90,  "nr_stringuri": 2, "invertor_cc_kw": 10, "invertor_ca_kw": 10,
         "nr_mppt": 2, "cablu_solar": "4x (1x 6)", "brk_dc_1p": "2x 1P\n1000V\n16A", "brk_dc_2p": "2x 2P\n1000V\n20A",
         "cyy_f": "CYY-F 5x 4", "comutator_ac": "C20 A", "racord_teg": "B63 A", "cyaby": "CYABY 5x 10", "tub": "PVC DN 32"},
    15: {"nr_panouri": 28, "pi_kw": 15.40, "nr_stringuri": 2, "invertor_cc_kw": 15, "invertor_ca_kw": 15,
         "nr_mppt": 2, "cablu_solar": "4x (1x 6)", "brk_dc_1p": "2x 1P\n1000V\n16A", "brk_dc_2p": "2x 2P\n1000V\n20A",
         "cyy_f": "CYY-F 5x 6", "comutator_ac": "C32 A", "racord_teg": "B100 A", "cyaby": "CYABY 5x 16", "tub": "PVC DN 40"},
    20: {"nr_panouri": 36, "pi_kw": 19.80, "nr_stringuri": 2, "invertor_cc_kw": 20, "invertor_ca_kw": 20,
         "nr_mppt": 2, "cablu_solar": "4x (1x 6)", "brk_dc_1p": "2x 1P\n1000V\n16A", "brk_dc_2p": "2x 2P\n1000V\n20A",
         "cyy_f": "CYY-F 5x 10", "comutator_ac": "C40 A", "racord_teg": "B125 A", "cyaby": "CYABY 5x 25", "tub": "PVC DN 50"},
}
# Constante COMUNE tuturor pachetelor (fixe în tabel).
FV_FIXED = {
    "wp": 550, "v_dc": "1000V", "myf_pe": "MYF 1x6 mmp",
    "spd_dc": "2x SPD DC\nTip I,II 20kA", "spd_ac": "SPD 3~\nTip I,II 20kA", "id_bmpt": "id 300mA",
}


def snap_fv_package(power_kw):
    """Puterea din formular (power_kw liber) -> pachetul FV cel mai apropiat (egalitate -> în sus)."""
    try:
        p = float(power_kw)
    except (TypeError, ValueError):
        p = 5.0
    return min(sorted(FV_PACKAGES), key=lambda k: (abs(k - p), -k))


# =============================================================================
# LAYOUT (pagină A3 landscape 420x297, ca modelul IE.5) — poziții FIXE în mm.
# =============================================================================
_W = 420          # lățimea paginii (mm)
_H = 297          # înălțimea paginii (mm)

_BLACK = HexColor('#1a1a1a')
_DC_PLUS = COLOR_PHASE_R      # conductor DC "+" (roșu, ca modelul)
_DC_MINUS = _BLACK            # conductor DC "−" (negru)

# Câmpul PV (dreapta-sus, ca modelul: String 2 deasupra, String 1 dedesubt)
_PV_X0, _PV_X1 = 228.0, 408.0     # zona orizontală a rândurilor de panouri
_PV_S2_Y = 22.0                   # topul rândului String 2
_PV_S1_Y = 58.0                   # topul rândului String 1
_PV_PANEL_W, _PV_PANEL_H, _PV_GAP = 11.0, 24.0, 1.8
_PV_N_VIS = 14                    # panouri DESENATE per string (fix — modelul; textul dă numărul real)
_PV_EXIT_X = 190.0                # unde se opresc cablurile solare în F1 (T.CC vine aici în F2)

# Legendă + note + titlu (stânga-jos / deasupra cartușului). Legenda are ~59mm -> se termină
# la ~219; notele stau SUB ea (ca modelul), titlul chiar deasupra cartușului.
_LEG_X, _LEG_Y, _LEG_W = 10.0, 160.0, 112.0
_NOTE_Y = 224.0
_TITLE_Y = 237.0
_CARTUS_Y0, _CARTUS_Y1 = 244, 293


# =============================================================================
# F1 — CÂMPUL PV
# =============================================================================
def _draw_ground_symbol(c, x_mm, y_mm, color=COLOR_PE):
    """Simbol de împământare: 3 linii orizontale descrescătoare sub punctul (x,y)."""
    for i, half in enumerate((4.0, 2.6, 1.2)):
        draw_line(c, x_mm - half, y_mm + i * 1.6, x_mm + half, y_mm + i * 1.6, width=0.8, color=color)


def _draw_pv_string(c, y_top, label):
    """Un rând de panouri (serie): dreptunghiuri verticale + bus-ul de jos + 2 conductoare (+/−)
    care ies spre STÂNGA. Întoarce (y_plus, y_minus) = y-urile celor 2 conductoare la ieșire."""
    n = _PV_N_VIS
    total_w = n * _PV_PANEL_W + (n - 1) * _PV_GAP
    x0 = _PV_X1 - total_w                          # aliniate la dreapta, ca modelul
    draw_text(c, x0, y_top - 2.5, label, font=FONT_BOLD, size=8)

    bus_y = y_top + _PV_PANEL_H + 2.5              # bus-ul de serie sub panouri
    for i in range(n):
        px = x0 + i * (_PV_PANEL_W + _PV_GAP)
        draw_rect(c, px, y_top, _PV_PANEL_W, _PV_PANEL_H, stroke_width=0.5)
        draw_line(c, px, y_top + 4.5, px + _PV_PANEL_W, y_top + 4.5, width=0.3, color=_BLACK)
        draw_line(c, px + _PV_PANEL_W / 2, y_top + _PV_PANEL_H, px + _PV_PANEL_W / 2, bus_y,
                  width=0.5, color=_BLACK)
    draw_line(c, x0, bus_y, x0 + total_w, bus_y, width=0.5, color=_BLACK)

    # conductoarele string-ului spre stânga: "+" (roșu) și "−" (negru), ușor decalate
    y_plus, y_minus = bus_y - 1.2, bus_y + 1.2
    draw_line(c, x0, bus_y, x0 - 4, bus_y, width=0.6, color=_BLACK)
    draw_line(c, x0 - 4, y_plus, _PV_EXIT_X, y_plus, width=0.6, color=_DC_PLUS)
    draw_line(c, x0 - 4, y_minus, _PV_EXIT_X, y_minus, width=0.6, color=_DC_MINUS)
    draw_line(c, x0 - 4, y_plus, x0 - 4, y_minus, width=0.6, color=_BLACK)
    # capete deschise (F2 le preia în T.CC): cerculețe mici
    for yy, col in ((y_plus, _DC_PLUS), (y_minus, _DC_MINUS)):
        c.setStrokeColor(col)
        c.setLineWidth(0.6)
        c.circle(_PV_EXIT_X * mm, to_y(yy), 0.9 * mm, stroke=1, fill=0)
    return y_plus, y_minus


def _draw_pv_field(c, pkg):
    """Câmpul PV complet: 2 string-uri (MEREU 2 desenate), chenarul PE al ramelor, coborârea la
    priza de pământ a câmpului (MYF + Rp<3Ω), eticheta cablului solar + blocul de text al pachetului."""
    _draw_pv_string(c, _PV_S2_Y, "String 2")
    _draw_pv_string(c, _PV_S1_Y, "String 1")

    # chenarul PE (verde) în jurul întregului câmp — ramele legate la pământ, ca modelul
    fx0, fy0 = _PV_X0 - 3.0, _PV_S2_Y - 7.0
    fx1, fy1 = _PV_X1 + 3.0, _PV_S1_Y + _PV_PANEL_H + 9.0
    draw_rect(c, fx0, fy0, fx1 - fx0, fy1 - fy0, stroke_width=0.6, stroke=COLOR_PE)

    # coborârea PE a câmpului: MYF 1x6 -> priza de pământ dedicată (Rp<3Ω)
    pe_x = fx0 + 42.0
    draw_line(c, pe_x, fy1, pe_x, fy1 + 14.0, width=0.7, color=COLOR_PE)
    draw_text(c, pe_x + 2.5, fy1 + 9.0, FV_FIXED["myf_pe"], size=7, color=COLOR_PE)
    _draw_ground_symbol(c, pe_x, fy1 + 14.0)
    draw_text(c, pe_x + 6.0, fy1 + 16.5, "PE", font=FONT_BOLD, size=7.5, color=COLOR_PE)
    draw_text(c, pe_x + 6.0, fy1 + 20.5, "Rp<3Ω", size=7.5, color=COLOR_PE)

    # eticheta cablului solar (pe mănunchiul dintre string-uri și T.CC) + elipsa mănunchiului
    lbl_x = (_PV_EXIT_X + _PV_X0) / 2.0
    lbl_y = (_PV_S2_Y + _PV_S1_Y) / 2.0 + 12.0
    draw_text(c, lbl_x, lbl_y - 3.0, "Cablu solar", font=FONT_BOLD, size=8, anchor="center")
    draw_text(c, lbl_x, lbl_y + 1.5, "%s mmp" % pkg["cablu_solar"], size=8, anchor="center")

    # blocul de text al pachetului (sub String 1, dreapta — ca modelul)
    tx = _PV_X1 - 52.0
    ty = _PV_S1_Y + _PV_PANEL_H + 14.0
    draw_text(c, tx, ty, "Panouri fotovoltaice %d buc" % pkg["nr_panouri"], font=FONT_BOLD, size=8.5, anchor="center")
    draw_text(c, tx, ty + 4.5, "P= %d Wp" % FV_FIXED["wp"], size=8.5, anchor="center")
    draw_text(c, tx, ty + 9.0, "%d string-uri" % pkg["nr_stringuri"] if pkg["nr_stringuri"] != 1 else "1 string",
              size=8.5, anchor="center")
    draw_text(c, tx, ty + 13.5, "Pi = %.2f kW" % pkg["pi_kw"], size=8.5, anchor="center")


# =============================================================================
# F0 — SCHELET: legendă + note + titlu + cartuș
# =============================================================================
def _draw_breaker_glyph(c, x, y, diferential=False):
    """Glyph mic de disjunctor termo-magnetic (pentru legendă): cârlig + cruce pe traseu."""
    draw_line(c, x, y + 7, x, y + 4.5, width=0.6, color=_BLACK)
    draw_line(c, x, y + 4.5, x + 2.0, y + 1.5, width=0.6, color=_BLACK)     # contactul deschis
    draw_line(c, x, y + 1.5, x, y - 1.0, width=0.6, color=_BLACK)
    draw_line(c, x - 1.1, y + 3.3, x + 1.1, y + 5.5, width=0.5, color=_BLACK)
    if diferential:
        draw_rect(c, x - 2.2, y + 8.0, 4.4, 2.6, stroke_width=0.5)          # blocul diferențial

def _draw_legend(c):
    rows_h = (6.0, 6.0, 12.0, 12.0, 5.5, 5.5, 5.5)
    total_h = sum(rows_h) + 6.5
    draw_rect(c, _LEG_X, _LEG_Y, _LEG_W, total_h, stroke_width=0.5)
    draw_text(c, _LEG_X + 2.5, _LEG_Y + 5.0, "LEGENDA", font=FONT_BOLD, size=8.5)
    draw_line(c, _LEG_X, _LEG_Y + 6.5, _LEG_X + _LEG_W, _LEG_Y + 6.5, width=0.4)
    y = _LEG_Y + 6.5
    sym_cx = _LEG_X + 9.0
    txt_x = _LEG_X + 19.0

    def _row(h, draw_sym, text, bold_label=None):
        nonlocal y
        cy = y + h / 2.0
        if bold_label:
            draw_text(c, sym_cx, cy + 1.5, bold_label, font=FONT_BOLD, size=8, anchor="center")
        if draw_sym:
            draw_sym(cy)
        for j, ln in enumerate(text.split("\n")):
            draw_text(c, txt_x, cy + 1.5 + (j - (text.count("\n")) / 2.0) * 4.0, ln, size=7.5)
        y += h
        draw_line(c, _LEG_X, y, _LEG_X + _LEG_W, y, width=0.2, color=HexColor('#bbbbbb'))

    _row(rows_h[0], None, "Tablou electric general", bold_label="TEG:")
    _row(rows_h[1], None, "Bloc de masura si protectie", bold_label="BMPT:")
    _row(rows_h[2], lambda cy: _draw_breaker_glyph(c, sym_cx, cy - 5.5, diferential=True),
         "Disjunctor termo-magnetic cu\nprotectie diferentiala")
    _row(rows_h[3], lambda cy: _draw_breaker_glyph(c, sym_cx, cy - 5.0),
         "Disjunctor termo-magnetic")
    _row(rows_h[4], lambda cy: draw_line(c, _LEG_X + 3, cy, _LEG_X + 15, cy, width=0.7, color=_BLACK),
         "Conductor faza")
    _row(rows_h[5], lambda cy: draw_line(c, _LEG_X + 3, cy, _LEG_X + 15, cy, width=0.7, color=COLOR_NEUTRAL),
         "Conductor nul")
    _row(rows_h[6], lambda cy: draw_line(c, _LEG_X + 3, cy, _LEG_X + 15, cy, width=0.7, color=COLOR_PE),
         "Conductor impamantare")


def _draw_notes(c):
    draw_text(c, _LEG_X, _NOTE_Y,
              "Nota 1: Sistemul fotovoltaic a fost dimensionat pentru a compensa o parte din consumul total de energie electrica a obiectivului.", size=7)
    draw_text(c, _LEG_X, _NOTE_Y + 4.5,
              "Nota 2: Sistemul fotovoltaic se va lega la o priza de pamant dedicata care trebuie sa aiba rezistenta sub 4 Ω.", size=7)


class _FvCartusShim:
    """Obiect minimal pentru draw_cartouche (folosește doar cartus_firma / cartus_proiect / tablou_nume)."""
    def __init__(self, firma, proiect):
        self.cartus_firma = firma or CartusFirma()
        self.cartus_proiect = proiect or CartusProiect()
        self.tablou_nume = "SISTEM FOTOVOLTAIC"


# =============================================================================
# BUILD
# =============================================================================
def build_fv_schema(package_kw, cartus_firma=None, cartus_proiect=None):
    """Schema monofilară FV pentru pachetul dat (5/10/15/20) -> bytes PDF (o pagină 420x297)."""
    pkg = FV_PACKAGES.get(int(package_kw)) or FV_PACKAGES[snap_fv_package(package_kw)]

    buf = BytesIO()
    set_page_height(_H)
    c = canvas.Canvas(buf, pagesize=(_W * mm, _H * mm))
    draw_page_frame(c, _W)

    _draw_pv_field(c, pkg)          # F1 — câmpul PV (dreapta-sus)
    # F2 (T.CC + invertor), F3 (T.CA + contor + TEG), F4 (BMPT) — fazele următoare

    _draw_legend(c)
    _draw_notes(c)
    draw_text(c, _W * 0.55, _TITLE_Y, "SCHEMA ELECTRICA MONOFILARA SISTEM FOTOVOLTAIC",
              font=FONT_BOLD, size=15, anchor="center")
    draw_cartouche(c, _W, _FvCartusShim(cartus_firma, cartus_proiect),
                   y_start=_CARTUS_Y0, y_end=_CARTUS_Y1)

    c.showPage()
    c.save()
    return buf.getvalue()


if __name__ == "__main__":
    for kw in (15, 5):
        pdf = build_fv_schema(kw)
        path = r"C:\Users\Adi\Desktop\fv_f1_%dkw.pdf" % kw
        open(path, "wb").write(pdf)
        print("PDF:", path, len(pdf), "bytes")
