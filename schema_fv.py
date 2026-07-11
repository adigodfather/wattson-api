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
_PANEL_FILL = HexColor('#1E5799')   # albastru panou fotovoltaic (fill)
_PANEL_CELL = HexColor('#9DBEE8')   # grila celulelor (albastru deschis, vizibil pe fill)

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
        # panou ALBASTRU cu grila de celule (3x3) — rama neagra, fill albastru, linii deschise
        draw_rect(c, px, y_top, _PV_PANEL_W, _PV_PANEL_H, stroke_width=0.5, fill=_PANEL_FILL)
        for fx in (1.0 / 3.0, 2.0 / 3.0):
            draw_line(c, px + _PV_PANEL_W * fx, y_top + 0.4, px + _PV_PANEL_W * fx,
                      y_top + _PV_PANEL_H - 0.4, width=0.3, color=_PANEL_CELL)
        for fy in (1.0 / 3.0, 2.0 / 3.0):
            draw_line(c, px + 0.4, y_top + _PV_PANEL_H * fy, px + _PV_PANEL_W - 0.4,
                      y_top + _PV_PANEL_H * fy, width=0.3, color=_PANEL_CELL)
        draw_line(c, px + _PV_PANEL_W / 2, y_top + _PV_PANEL_H, px + _PV_PANEL_W / 2, bus_y,
                  width=0.5, color=_BLACK)
    draw_line(c, x0, bus_y, x0 + total_w, bus_y, width=0.5, color=_BLACK)

    # conductoarele string-ului spre stânga: "+" (roșu) și "−" (negru), ușor decalate;
    # se opresc la _PV_EXIT_X — T.CC (F2) le continuă de acolo spre invertor.
    y_plus, y_minus = bus_y - 1.2, bus_y + 1.2
    draw_line(c, x0, bus_y, x0 - 4, bus_y, width=0.6, color=_BLACK)
    draw_line(c, x0 - 4, y_plus, _PV_EXIT_X, y_plus, width=0.6, color=_DC_PLUS)
    draw_line(c, x0 - 4, y_minus, _PV_EXIT_X, y_minus, width=0.6, color=_DC_MINUS)
    draw_line(c, x0 - 4, y_plus, x0 - 4, y_minus, width=0.6, color=_BLACK)
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
# F2 — T.CC (breakere DC + SPD DC) + INVERTORUL (MPPT / DC-AC / releu / filtre EMI / borne)
# =============================================================================
# Perechile DC din F1 (y-urile conductoarelor +/− per string, la _PV_EXIT_X):
_DC_S2 = (47.3, 49.7)     # String 2 (sus):  bus la _PV_S2_Y+24+2.5=48.5 ∓1.2
_DC_S1 = (83.3, 85.7)     # String 1 (jos):  bus la _PV_S1_Y+24+2.5=84.5 ∓1.2
# T.CC (chenar punctat, între câmpul PV și invertor) + invertorul (chenar solid, stânga-sus)
_TCC_X0, _TCC_X1, _TCC_Y0, _TCC_Y1 = 136.0, 196.0, 38.0, 111.0
_INV_X0, _INV_X1, _INV_Y0, _INV_Y1 = 22.0, 118.0, 32.0, 94.0
_BRK_X0, _BRK_X1 = 162.0, 173.0    # cutia breakerului DC pe conductori (liniile se întrerup aici)


def _draw_dc_pair(c, y_pair, x_from, x_to):
    """Continuă perechea de conductoare DC (+ roșu / − negru) de la x_from la x_to."""
    draw_line(c, x_from, y_pair[0], x_to, y_pair[0], width=0.6, color=_DC_PLUS)
    draw_line(c, x_from, y_pair[1], x_to, y_pair[1], width=0.6, color=_DC_MINUS)


def _draw_dc_breaker(c, y_pair):
    """Breaker DC pe pereche: cutie cu câte un contact oblic per pol (schematic monofilar)."""
    draw_rect(c, _BRK_X0, y_pair[0] - 4.0, _BRK_X1 - _BRK_X0, (y_pair[1] - y_pair[0]) + 8.0, stroke_width=0.5)
    for yy in y_pair:
        draw_line(c, _BRK_X0 + 2.0, yy, _BRK_X0 + 4.5, yy, width=0.5, color=_BLACK)
        draw_line(c, _BRK_X0 + 4.5, yy, _BRK_X1 - 2.0, yy - 2.6, width=0.5, color=_BLACK)   # contact deschis
        draw_line(c, _BRK_X1 - 2.0, yy, _BRK_X1 - 3.5, yy, width=0.5, color=_BLACK)


def _draw_spd_dc(c, x, y_tap, y_box_top):
    """SPD DC pe DERIVAȚIE (protecție la supratensiune): NOD pe conductorul DC (punct plin la
    y_tap) -> ramură verticală -> cutia SPD (vârf de descărcare) -> coborâre verde la PĂMÂNT.
    Se citește ca derivație de pe circuit, nu simbol plutind."""
    c.setFillColor(_BLACK)
    c.circle(x * mm, to_y(y_tap), 0.55 * mm, stroke=0, fill=1)        # nodul de derivație
    draw_line(c, x, y_tap, x, y_box_top, width=0.5, color=_BLACK)     # ramura din circuit
    draw_rect(c, x - 3.0, y_box_top, 6.0, 10.0, stroke_width=0.5)
    draw_line(c, x, y_box_top + 1.5, x, y_box_top + 5.0, width=0.6, color=_BLACK)
    for dx in (-1.4, 0.0, 1.4):
        draw_line(c, x + dx, y_box_top + 5.0, x, y_box_top + 7.5, width=0.4, color=_BLACK)
    draw_line(c, x, y_box_top + 10.0, x, y_box_top + 12.5, width=0.6, color=COLOR_PE)
    _draw_ground_symbol(c, x, y_box_top + 12.5)


def _draw_tcc(c, pkg):
    """T.CC: chenar punctat pe conductorii DC — breaker per string cu ETICHETA SUB simbol +
    SPD per string pe DERIVAȚIE (nod pe conductor -> SPD -> pământ), cu eticheta sub zona SPD.
    Conductorii F1 se opresc la _PV_EXIT_X; aici îi continuăm prin breakere până la invertor."""
    draw_rect_dashed(c, _TCC_X0, _TCC_Y0, _TCC_X1 - _TCC_X0, _TCC_Y1 - _TCC_Y0)

    for y_pair in (_DC_S2, _DC_S1):
        _draw_dc_pair(c, y_pair, _PV_EXIT_X, _BRK_X1 - 2.0)          # PV -> breaker
        _draw_dc_breaker(c, y_pair)
        _draw_dc_pair(c, y_pair, _BRK_X0 + 2.0, _INV_X1)             # breaker -> invertor (PV1/PV2)

    # etichetele breakerelor DIRECT SUB simbolul fiecăruia (nu bloc separat)
    brk_cx = (_BRK_X0 + _BRK_X1) / 2.0
    draw_text(c, brk_cx, _DC_S2[1] + 8.0, pkg["brk_dc_2p"].replace("\n", " "),
              font=FONT_BOLD, size=5.5, anchor="center")
    draw_text(c, brk_cx, _DC_S1[1] + 8.0, pkg["brk_dc_1p"].replace("\n", " "),
              font=FONT_BOLD, size=5.5, anchor="center")

    # SPD per string, pe DERIVAȚIE de pe conductorul "−" al perechii -> pământ (fără traversări)
    _draw_spd_dc(c, 144.0, _DC_S2[1], 54.0)                          # String 2 (sus)
    _draw_spd_dc(c, 154.0, _DC_S1[1], 90.0)                          # String 1 (jos)
    # eticheta SPD (totalul, textul fix) sub zona SPD1 — lângă simboluri, nu plutind
    draw_text(c, 144.0, 75.5, FV_FIXED["spd_dc"].split("\n")[0], font=FONT_BOLD, size=5.5, anchor="center")
    draw_text(c, 144.0, 79.0, FV_FIXED["spd_dc"].split("\n")[1], size=5.5, anchor="center")

    draw_text(c, (_TCC_X0 + _TCC_X1) / 2, _TCC_Y1 + 4.5, "T.CC", font=FONT_BOLD, size=8.5, anchor="center")
    draw_text(c, (_TCC_X0 + _TCC_X1) / 2, _TCC_Y1 + 8.5, "(Tablou electric de interventie)", size=6.5, anchor="center")


def draw_rect_dashed(c, x_mm, y_top_mm, w, h, color=_BLACK):
    """Chenar PUNCTAT (tablourile T.CC / T.CA, ca modelul) — draw_rect nu are dash."""
    for (x1, y1, x2, y2) in ((x_mm, y_top_mm, x_mm + w, y_top_mm),
                             (x_mm + w, y_top_mm, x_mm + w, y_top_mm + h),
                             (x_mm + w, y_top_mm + h, x_mm, y_top_mm + h),
                             (x_mm, y_top_mm + h, x_mm, y_top_mm)):
        draw_line(c, x1, y1, x2, y2, width=0.5, color=color, dash=(2, 1.6))


def _inv_block(c, x0, y0, x1, y1, lines, fs=5.0):
    """Bloc intern al invertorului: dreptunghi + text centrat pe mai multe rânduri."""
    draw_rect(c, x0, y0, x1 - x0, y1 - y0, stroke_width=0.5)
    cy = (y0 + y1) / 2.0 - (len(lines) - 1) * 1.9
    for ln in lines:
        draw_text(c, (x0 + x1) / 2.0, cy + 1.4, ln, size=fs, anchor="center")
        cy += 3.8


def _draw_inverter(c, pkg):
    """Invertorul (schematic, ca modelul): borne PV1/PV2 pe dreapta -> MPPT1/MPPT2 -> filtru EMI
    intrare -> DC/AC converter -> releu insularizare -> filtru EMI ieșire -> bornele R-S-T-N-PE
    (ies prin marginea de jos; T.CA le preia în F3). Mereu 2 MPPT desenate (textul dă nr. real)."""
    draw_rect(c, _INV_X0, _INV_Y0, _INV_X1 - _INV_X0, _INV_Y1 - _INV_Y0, stroke_width=0.7)
    draw_text(c, (_INV_X0 + _INV_X1) / 2, _INV_Y0 - 7.5,
              "Invertor %d kWp CC / %d kW CA" % (pkg["invertor_cc_kw"], pkg["invertor_ca_kw"]),
              font=FONT_BOLD, size=8, anchor="center")
    draw_text(c, (_INV_X0 + _INV_X1) / 2, _INV_Y0 - 3.0,
              "%dx MPPT, %s" % (pkg["nr_mppt"], FV_FIXED["v_dc"]), size=7, anchor="center")

    # bornele PV pe marginea DREAPTĂ (la y-urile perechilor DC) + etichete PV1/PV2 și +/−
    for y_pair, name in ((_DC_S2, "PV1"), (_DC_S1, "PV2")):
        draw_text(c, _INV_X1 + 2.0, (y_pair[0] + y_pair[1]) / 2 - 3.2, name, font=FONT_BOLD, size=6)
        draw_text(c, _INV_X1 - 3.5, y_pair[0] + 1.0, "+", size=6, color=_DC_PLUS)
        draw_text(c, _INV_X1 - 3.5, y_pair[1] + 2.2, "-", size=6, color=_DC_MINUS)

    # blocurile interne (lanț dreapta -> stânga)
    _inv_block(c, 96, 42, 113, 54, ["MPPT1"], fs=6)
    _inv_block(c, 96, 78, 113, 90, ["MPPT2"], fs=6)
    _inv_block(c, 94, 59, 114, 73, ["Filtru", "Electromagnetic", "(EMI) intrare"], fs=4.2)
    _inv_block(c, 62, 58, 82, 74, ["DC/AC", "converter"], fs=5.5)
    _inv_block(c, 45, 58, 58, 74, ["Releu", "insulari-", "zare"], fs=4.4)
    _inv_block(c, 26, 58, 42, 74, ["Filtru", "Electromagnetic", "(EMI) iesire"], fs=4.2)

    # conexiunile interne: PV1/PV2 -> MPPT-uri -> EMI intrare -> DC/AC -> releu -> EMI ieșire
    draw_line(c, 113, 48, _INV_X1, 48, width=0.5, color=_BLACK)      # PV1 -> MPPT1
    draw_line(c, 113, 84, _INV_X1, 84, width=0.5, color=_BLACK)      # PV2 -> MPPT2
    draw_line(c, 104.5, 54, 104.5, 59, width=0.5, color=_BLACK)      # MPPT1 -> EMI intrare
    draw_line(c, 104.5, 73, 104.5, 78, width=0.5, color=_BLACK)      # EMI intrare <- MPPT2
    draw_line(c, 94, 66, 82, 66, width=0.5, color=_BLACK)            # EMI intrare -> DC/AC
    draw_line(c, 62, 66, 58, 66, width=0.5, color=_BLACK)            # DC/AC -> releu
    draw_line(c, 45, 66, 42, 66, width=0.5, color=_BLACK)            # releu -> EMI ieșire

    # bornele de ieșire R-S-T-N-PE: fan-out din EMI ieșire, ies prin marginea de JOS (F3 le preia)
    fan_y = 82.0
    draw_line(c, 34, 74, 34, fan_y, width=0.5, color=_BLACK)         # EMI ieșire -> bara de distribuție
    xs = (28.0, 33.0, 38.0, 43.0, 48.0)
    cols = (_BLACK, _BLACK, _BLACK, COLOR_NEUTRAL, COLOR_PE)
    labels = ("R", "S", "T", "N", "PE")
    draw_line(c, xs[0], fan_y, xs[-1], fan_y, width=0.5, color=_BLACK)
    for x, col, lbl in zip(xs, cols, labels):
        if lbl == "PE":
            continue                                   # PE are coborârea lui dedicată (mai jos)
        draw_line(c, x, fan_y, x, _INV_Y1 + 4.0, width=0.6, color=col)
        draw_text(c, x, _INV_Y1 + 7.5, lbl, font=FONT_BOLD, size=5.5, anchor="center",
                  color=col if lbl == "N" else _BLACK)

    # PE-ul INVERTORULUI: coborâre verde vizibilă -> PRIZĂ DE PĂMÂNT DEDICATĂ (Rp<4Ω),
    # SEPARATĂ de priza câmpului de panouri (aceea e la câmp, MYF, Rp<3Ω). Traseul face un L
    # spre dreapta ca să lase loc T.CA-ului (F3) sub bornele R-S-T-N.
    pe_x = xs[-1]
    draw_line(c, pe_x, fan_y, pe_x, 104.0, width=0.7, color=COLOR_PE)
    draw_text(c, pe_x + 1.8, _INV_Y1 + 7.5, "PE", font=FONT_BOLD, size=5.5, color=COLOR_PE)
    draw_line(c, pe_x, 104.0, 72.0, 104.0, width=0.7, color=COLOR_PE)
    draw_line(c, 72.0, 104.0, 72.0, 110.0, width=0.7, color=COLOR_PE)
    _draw_ground_symbol(c, 72.0, 110.0)
    draw_text(c, 78.0, 108.5, "Priza de pamant", size=6, color=COLOR_PE)
    draw_text(c, 78.0, 112.0, "dedicata invertor", size=6, color=COLOR_PE)
    draw_text(c, 78.0, 115.5, "Rp<4Ω", font=FONT_BOLD, size=6, color=COLOR_PE)


# =============================================================================
# F3 — RAMURA AC: T.CA (SPD 3~ pe derivație + comutator) -> contor producție -> TEG
# =============================================================================
# Conductorii R/S/T/N pleacă din bornele invertorului (xs 28/33/38/43, etichete la _INV_Y1+7.5)
_AC_XS = (28.0, 33.0, 38.0, 43.0)
_AC_COLS = (_BLACK, _BLACK, _BLACK, COLOR_NEUTRAL)
_AC_Y_START = 103.5                 # sub etichetele bornelor (mic gap standard sub text)
_TCA_X0, _TCA_X1, _TCA_Y0, _TCA_Y1 = 12.0, 50.0, 106.0, 146.0
_SW_Y0, _SW_Y1 = 118.0, 128.0      # cutia comutatorului 3P+N (pe conductorii verticali)
_AC_BUS_YS = (136.5, 138.5, 140.5, 142.5)   # traseul orizontal spre contor/TEG (R,S,T,N)
_METER_X0, _METER_X1 = 95.0, 115.0
_TEG_X0, _TEG_X1, _TEG_Y0, _TEG_Y1 = 135.0, 200.0, 128.0, 154.0


def _draw_tca(c, pkg):
    """T.CA: chenar punctat pe conductorii AC — SPD 3~ pe DERIVAȚIE (nod -> SPD -> pământ, ca
    T.CC) + comutatorul 3P+N (contact per pol), fiecare cu eticheta SUB simbolul lui."""
    draw_rect_dashed(c, _TCA_X0, _TCA_Y0, _TCA_X1 - _TCA_X0, _TCA_Y1 - _TCA_Y0)

    # conductorii verticali R/S/T/N: bornele invertorului -> comutator -> cotul spre orizontală
    for x, col, y_bus in zip(_AC_XS, _AC_COLS, _AC_BUS_YS):
        draw_line(c, x, _AC_Y_START, x, _SW_Y0 + 2.5, width=0.6, color=col)
        draw_line(c, x, _SW_Y0 + 2.5, x + 2.2, _SW_Y0 + 7.5, width=0.5, color=_BLACK)   # contact per pol
        draw_line(c, x, _SW_Y0 + 8.0, x, y_bus, width=0.6, color=col)

    # cutia comutatorului peste cei 4 poli + eticheta SUB (coloana din dreapta)
    draw_rect(c, _AC_XS[0] - 3.0, _SW_Y0, (_AC_XS[-1] - _AC_XS[0]) + 6.0, _SW_Y1 - _SW_Y0, stroke_width=0.5)
    # eticheta comutatorului LA DREAPTA cutiei (conductorii coboara vertical din ea — sub cutie ar
    # fi traversata de ei)
    draw_text(c, _TCA_X1 + 2.5, 122.0, "Comutator", font=FONT_BOLD, size=5.5)
    draw_text(c, _TCA_X1 + 2.5, 126.0, "3P+N %s" % pkg["comutator_ac"], size=5.5)

    # SPD 3~ pe DERIVAȚIE de pe faza R (nod -> ramură orizontală -> cutie -> pământ) + eticheta SUB
    c.setFillColor(_BLACK)
    c.circle(_AC_XS[0] * mm, to_y(110.0), 0.55 * mm, stroke=0, fill=1)
    draw_line(c, _AC_XS[0], 110.0, 20.0, 110.0, width=0.5, color=_BLACK)
    draw_line(c, 20.0, 110.0, 20.0, 112.0, width=0.5, color=_BLACK)
    draw_rect(c, 17.0, 112.0, 6.0, 10.0, stroke_width=0.5)
    draw_line(c, 20.0, 113.5, 20.0, 117.0, width=0.6, color=_BLACK)
    for dx in (-1.4, 0.0, 1.4):
        draw_line(c, 20.0 + dx, 117.0, 20.0, 119.5, width=0.4, color=_BLACK)
    draw_line(c, 20.0, 122.0, 20.0, 124.5, width=0.6, color=COLOR_PE)
    _draw_ground_symbol(c, 20.0, 124.5)
    draw_text(c, 20.0, 132.5, "SPD 3~", font=FONT_BOLD, size=5.5, anchor="center")
    draw_text(c, 20.0, 136.0, "Tip I,II 20kA", size=5.5, anchor="center")

    draw_text(c, (_TCA_X0 + _TCA_X1) / 2, _TCA_Y1 + 4.5, "T.CA", font=FONT_BOLD, size=8.5, anchor="center")
    draw_text(c, (_TCA_X0 + _TCA_X1) / 2, _TCA_Y1 + 8.5, "(Tablou electric de interfata)", size=6.5, anchor="center")


def _draw_ac_run_and_meter(c, pkg):
    """Traseul AC orizontal T.CA -> TEG, cu eticheta cablului CYY-F + CONTORUL de producție
    (cutie kWh cu fill alb peste linii => conductorii 'intră/ies' din contor)."""
    for x, col, y_bus in zip(_AC_XS, _AC_COLS, _AC_BUS_YS):
        draw_line(c, x, y_bus, _TEG_X0, y_bus, width=0.6, color=col)   # cotul: vertical -> orizontal

    draw_text(c, 74.0, 131.5, "%s mmp" % pkg["cyy_f"], font=FONT_BOLD, size=6, anchor="center")

    draw_rect(c, _METER_X0, 131.5, _METER_X1 - _METER_X0, 15.0, stroke_width=0.6, fill=HexColor('#ffffff'))
    draw_text(c, (_METER_X0 + _METER_X1) / 2, 141.0, "kWh", font=FONT_BOLD, size=8, anchor="center")
    draw_text(c, (_METER_X0 + _METER_X1) / 2, 125.5, "Contor productie", size=6, anchor="center")
    draw_text(c, (_METER_X0 + _METER_X1) / 2, 129.0, "solara, 400V", size=6, anchor="center")


def _draw_teg(c):
    """TEG (Tablou electric general): chenarul racordului, cu bornele R/S/T/N pe intrarea din
    stânga (de la contor) + etichetele RST/N/PE (racordul spre BMPT vine în F4)."""
    draw_rect(c, _TEG_X0, _TEG_Y0, _TEG_X1 - _TEG_X0, _TEG_Y1 - _TEG_Y0, stroke_width=0.8)
    draw_text(c, (_TEG_X0 + _TEG_X1) / 2, _TEG_Y0 + 9.0, "TEG", font=FONT_BOLD, size=13, anchor="center")
    draw_text(c, (_TEG_X0 + _TEG_X1) / 2, _TEG_Y0 + 14.5, "(Tablou electric general)", size=6, anchor="center")
    # bornele intrării FV (stânga) — punct per conductor + etichetele racordului
    for y_bus, lbl, col in zip(_AC_BUS_YS, ("R", "S", "T", "N"), _AC_COLS):
        c.setFillColor(col)
        c.circle(_TEG_X0 * mm, to_y(y_bus), 0.55 * mm, stroke=0, fill=1)
    draw_text(c, _TEG_X0 + 3.0, _TEG_Y1 - 6.5, "RST", font=FONT_BOLD, size=6)
    draw_text(c, _TEG_X0 + 11.0, _TEG_Y1 - 6.5, "N", font=FONT_BOLD, size=6, color=COLOR_NEUTRAL)
    draw_text(c, _TEG_X0 + 16.0, _TEG_Y1 - 6.5, "PE", font=FONT_BOLD, size=6, color=COLOR_PE)


# =============================================================================
# F4 — RACORDUL: TEG -> breaker racord -> CYABY -> BMPT (kWh 3~ CE + id + PD+DPS) -> limita DEER
# =============================================================================
_RAC_YS = (133.0, 136.0, 139.0, 142.0)      # R,S,T,N pe traseul TEG -> BMPT
_RAC_PE_Y = 145.5                            # PE (verde) — NU trece prin breaker (3P+N)
_RAC_BRK_X0, _RAC_BRK_X1 = 213.0, 225.0     # breakerul de racord (pe faze+N)
_BMPT_X0, _BMPT_X1, _BMPT_Y0, _BMPT_Y1 = 300.0, 385.0, 126.0, 198.0
_LIMIT_X = 395.0                             # limita de proprietate (punctată verticală)


def _draw_racord_bmpt(c, pkg):
    """Racordul TEG -> rețea: breaker {racord_teg} 3P+N + cablul CYABY/tub -> BMPT (contor consum
    kWh 3~ CE + diferențial id 300mA + PD+DPS cu priza de pământ Rp<4Ω) -> limita de proprietate
    (Instalatia Consumator | Instalatia DEER). Stil consecvent cu T.CC/T.CA."""
    # conductorii R/S/T/N + PE din TEG (dreapta) spre BMPT; breakerul întrerupe fazele+N
    for y, col in zip(_RAC_YS, _AC_COLS):
        draw_line(c, _TEG_X1, y, _RAC_BRK_X0 + 2.0, y, width=0.6, color=col)
        draw_line(c, _RAC_BRK_X0 + 2.0, y, _RAC_BRK_X0 + 4.5, y - 0.0, width=0.5, color=_BLACK)
        draw_line(c, _RAC_BRK_X0 + 4.5, y, _RAC_BRK_X1 - 3.0, y - 2.4, width=0.5, color=_BLACK)  # contact
        draw_line(c, _RAC_BRK_X1 - 3.0, y, _RAC_BRK_X1 - 2.0, y, width=0.5, color=_BLACK)
        draw_line(c, _RAC_BRK_X1 - 2.0, y, _BMPT_X0, y, width=0.6, color=col)
    draw_line(c, _TEG_X1, _RAC_PE_Y, _BMPT_X0, _RAC_PE_Y, width=0.6, color=COLOR_PE)
    draw_rect(c, _RAC_BRK_X0, _RAC_YS[0] - 3.0, _RAC_BRK_X1 - _RAC_BRK_X0,
              (_RAC_YS[-1] - _RAC_YS[0]) + 6.0, stroke_width=0.5)
    brk_cx = (_RAC_BRK_X0 + _RAC_BRK_X1) / 2.0
    draw_text(c, brk_cx, _RAC_PE_Y + 6.0, "3P+N %s" % pkg["racord_teg"], font=FONT_BOLD, size=5.5, anchor="center")

    # cablul de branșament: CYABY + tubul, pe traseu (deasupra liniilor)
    cyaby_cx = (_RAC_BRK_X1 + _BMPT_X0) / 2.0
    draw_text(c, cyaby_cx, 126.5, "%s mmp" % pkg["cyaby"], font=FONT_BOLD, size=6, anchor="center")
    draw_text(c, cyaby_cx, 130.0, pkg["tub"], size=6, anchor="center")

    # BMPT — chenar + titlu deasupra
    draw_rect(c, _BMPT_X0, _BMPT_Y0, _BMPT_X1 - _BMPT_X0, _BMPT_Y1 - _BMPT_Y0, stroke_width=0.7)
    draw_text(c, (_BMPT_X0 + _BMPT_X1) / 2, _BMPT_Y0 - 3.5, "BMPT", font=FONT_BOLD, size=9, anchor="center")

    # conductorii TREC prin BMPT (intrare -> kWh -> id -> ieșire); cutiile cu fill alb îi acoperă
    for y, col in zip(_RAC_YS, _AC_COLS):
        draw_line(c, _BMPT_X0, y, _BMPT_X1, y, width=0.6, color=col)
    draw_line(c, _BMPT_X0, _RAC_PE_Y, 344.0, _RAC_PE_Y, width=0.6, color=COLOR_PE)   # PE -> nodul PD+DPS

    # contorul de consum (kWh 3~ CE, cu telegestiune) — cutie cu fill alb peste linii
    draw_rect(c, 310.0, 129.0, 30.0, 20.0, stroke_width=0.6, fill=HexColor('#ffffff'))
    draw_text(c, 325.0, 138.0, "kWh 3~", font=FONT_BOLD, size=7, anchor="center")
    draw_text(c, 325.0, 145.0, "CE", size=6, anchor="center")

    # diferențialul (id 300mA) — cutie fill alb peste linii + eticheta SUB
    draw_rect(c, 348.0, 129.0, 18.0, 20.0, stroke_width=0.6, fill=HexColor('#ffffff'))
    draw_text(c, 357.0, 140.5, "id", font=FONT_BOLD, size=7, anchor="center")
    draw_text(c, 357.0, 153.5, FV_FIXED["id_bmpt"], size=5.5, anchor="center")

    # PD+DPS: derivație de pe bara PE (nodul în golul kWh–id, vizibil) -> bloc -> priza de
    # pământ a BMPT (Rp<4Ω)
    c.setFillColor(COLOR_PE)
    c.circle(344.0 * mm, to_y(_RAC_PE_Y), 0.55 * mm, stroke=0, fill=1)
    draw_line(c, 344.0, _RAC_PE_Y, 344.0, 162.0, width=0.6, color=COLOR_PE)
    draw_rect(c, 330.0, 162.0, 28.0, 13.0, stroke_width=0.5)
    draw_text(c, 344.0, 170.0, "PD+DPS", font=FONT_BOLD, size=6, anchor="center")
    draw_line(c, 344.0, 175.0, 344.0, 182.0, width=0.7, color=COLOR_PE)
    _draw_ground_symbol(c, 344.0, 182.0)
    draw_text(c, 350.0, 189.0, "PE", font=FONT_BOLD, size=6, color=COLOR_PE)
    draw_text(c, 350.0, 193.0, "Rp<4Ω", size=6, color=COLOR_PE)

    # ieșirea spre rețea + LIMITA DE PROPRIETATE (punctată) + Instalatia Consumator | DEER
    for y, col in zip(_RAC_YS, _AC_COLS):
        draw_line(c, _BMPT_X1, y, _LIMIT_X + 9.0, y, width=0.6, color=col)
    draw_line(c, _LIMIT_X, 112.0, _LIMIT_X, 218.0, width=0.5, color=_BLACK, dash=(2.5, 2))
    draw_text(c, _LIMIT_X - 2.5, 116.0, "Instalatia", size=5.5, anchor="right")
    draw_text(c, _LIMIT_X - 2.5, 119.5, "Consumator", size=5.5, anchor="right")
    draw_text(c, _LIMIT_X + 2.5, 116.0, "Instalatia", font=FONT_BOLD, size=5.5)
    draw_text(c, _LIMIT_X + 2.5, 119.5, "DEER", font=FONT_BOLD, size=5.5)


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
    _draw_tcc(c, pkg)               # F2 — T.CC (breakere DC + SPD DC) pe conductorii DC
    _draw_inverter(c, pkg)          # F2 — invertorul (MPPT / DC-AC / releu / filtre EMI / borne)
    _draw_tca(c, pkg)               # F3 — T.CA (SPD 3~ pe derivație + comutator 3P+N)
    _draw_ac_run_and_meter(c, pkg)  # F3 — traseul AC (CYY-F) + contorul de producție
    _draw_teg(c)                    # F3 — TEG
    _draw_racord_bmpt(c, pkg)       # F4 — racordul (breaker + CYABY) + BMPT + limita DEER

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
    import sys
    faza = sys.argv[1] if len(sys.argv) > 1 else "f2"
    for kw in (15, 5):
        pdf = build_fv_schema(kw)
        path = r"C:\Users\Adi\Desktop\fv_%s_%dkw.pdf" % (faza, kw)
        open(path, "wb").write(pdf)
        print("PDF:", path, len(pdf), "bytes")
