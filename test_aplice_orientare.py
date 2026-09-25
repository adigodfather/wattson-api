"""Aplice de perete si intrerupatoare: lipire la perete cu orientare, in AMBELE oglinzi.

DE CE EXISTA. Simbolul se deseneaza in doua locuri scrise separat: `draw_elements.py` (plansa) si
`plan-editor.tsx` (editorul, oglinda tastata de mana). Lectia de la corpul de evacuare: daca
schimbi unul si uiti celalalt, arata diferit pe ecran si pe hartie, si nimeni nu observa pana nu
compara. Proba verifica geometria CITIND ambele fisiere, plus randeaza ca sa vada ca desenul chiar
se intoarce.

Rulare:  python test_aplice_orientare.py
"""
import io
import math
import os
import re
import sys

RADACINA = os.path.dirname(os.path.abspath(__file__))
EDITOR = os.path.join(RADACINA, "apps", "zynapse-configurator", "components", "plan-editor.tsx")
rele = []


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def main():
    import fitz
    sys.path.insert(0, RADACINA)
    import draw_elements as de
    import bom

    ed = io.open(EDITOR, encoding="utf-8").read()
    dr = io.open(os.path.join(RADACINA, "draw_elements.py"), encoding="utf-8").read()
    bo = io.open(os.path.join(RADACINA, "bom.py"), encoding="utf-8").read()

    # ── [1] Ce se lipeste: ACEEASI multime in toate cele TREI locuri ────────────────────────
    v("[1] draw_elements: corpurile de perete sunt exact cele doua",
      de._WALL_BULBS == {"aplica_perete", "aplica_senzor"}, str(sorted(de._WALL_BULBS)))
    m = re.search(r'const WALL_BULBS = new Set\(\[([^\]]*)\]\)', ed)
    ed_set = set(re.findall(r'"([a-z_]+)"', m.group(1))) if m else set()
    v("[1] editorul are ACEEASI multime", ed_set == de._WALL_BULBS, str(sorted(ed_set)))
    m2 = re.search(r'_WALL_BULBS = \{([^}]*)\}', bo)
    bom_set = set(re.findall(r'"([a-z_]+)"', m2.group(1))) if m2 else set()
    v("[1] bom.py (a treia copie) spune acelasi lucru", bom_set == de._WALL_BULBS, str(sorted(bom_set)))
    v("[1] corpurile de TAVAN raman in afara",
      not ({"aplica_tavan", "lustra_led", "panou_led"} & de._WALL_BULBS))

    # ── [2] Geometria intrerupatorului: aceleasi cote in ambele oglinzi ─────────────────────
    cote_py = dict(re.findall(r'(R1|L1|R2|L2)\s*=\s*([\d.]+)\s*\*\s*s', dr))
    m3 = re.search(r'const R1 = ([\d.]+), L1 = ([\d.]+), R2 = ([\d.]+), L2 = ([\d.]+), HK = ([\d.]+), HKA = ([\d.]+);', ed)
    v("[2] editorul declara cotele intrerupatorului", bool(m3))
    if m3 and cote_py:
        ok = (float(m3.group(1)) == float(cote_py.get("R1", -1))
              and float(m3.group(2)) == float(cote_py.get("L1", -1))
              and float(m3.group(3)) == float(cote_py.get("R2", -1))
              and float(m3.group(4)) == float(cote_py.get("L2", -1)))
        v("[2] cotele R1/L1/R2/L2 sunt IDENTICE plansa vs editor", ok,
          "py=%s ts=%s" % (cote_py, m3.groups()[:4]))
        mhk = re.search(r'HK, HKA = ([\d.]+) \* s, ([\d.]+)', dr)
        v("[2] carligul (HK, HKA) identic", bool(mhk) and float(m3.group(5)) == float(mhk.group(1))
          and float(m3.group(6)) == float(mhk.group(2)),
          "py=%s ts=(%s,%s)" % (mhk.groups() if mhk else "?", m3.group(5), m3.group(6)))

    # ── [3] Desenul chiar se INTOARCE (nu doar accepta parametrul) ──────────────────────────
    def randeaza(rot):
        d = fitz.open(); pg = d.new_page(width=60, height=60)
        de._draw_bulb(pg, 30, 30, "aplica_perete", y_offset=0, rotation=rot)
        b = pg.get_pixmap(dpi=100).tobytes("png")
        d.close()
        return b
    fara = randeaza(None)
    la0 = randeaza(0.0)
    la90 = randeaza(math.pi / 2)
    v("[3] rotatia schimba desenul (0 != 90 de grade)", la0 != la90)
    v("[3] patru directii dau patru desene DIFERITE",
      len({randeaza(a) for a in (0.0, math.pi / 2, math.pi, -math.pi / 2)}) == 4)

    # ── [4] NON-REGRESIE: fara orientare, desenul e cel istoric, pixel cu pixel ─────────────
    # Referinta = desenul ISTORIC, reconstruit din cod: start la dreapta, sweep 180, punct sub centru.
    # `y_offset=0` in ambele, ca sa comparam acelasi loc (implicit e -22, si prima varianta a probei
    # a picat tocmai fiindca referinta desena in alta parte a paginii).
    d = fitz.open(); pg = d.new_page(width=60, height=60)
    RED = de._RED_DEFAULT
    pg.draw_sector(fitz.Point(30, 30), fitz.Point(30 + 9, 30), 180, color=RED, width=1.2, fullSector=True)
    pg.draw_circle(fitz.Point(30, 30 + 4), 1.8, color=RED, fill=RED, width=0.8)
    istoric = pg.get_pixmap(dpi=100).tobytes("png")
    d.close()
    v("[4] rotatia lipsa -> desenul ISTORIC, pixel cu pixel (proiectele vechi nu se misca)",
      fara == istoric)

    # ── [5] Editorul: corpurile de tavan NU primesc rotatie ─────────────────────────────────
    v("[5] editorul roteste DOAR corpurile de perete",
      "isWallBulb(el.element_type) ? (" in ed and "gradeAplica(el.rotation)" in ed)
    v("[5] corectia de 90 de grade exista si e explicata",
      "* 180) / Math.PI - 90" in ed and "fata" in ed.lower())

    # ── [6] Un singur mecanism de lipire, nu doua ───────────────────────────────────────────
    v("[6] aplicele si intrerupatoarele folosesc ACELASI snap ca la camere",
      "|| isWallBulb(el.element_type) || isSwitchType(el.element_type)" in ed)
    v("[6] nu s-a nascut o a doua functie de lipire",
      ed.count("function snapPerete") == 1 and "function snapAplica" not in ed
      and "function snapSwitch" not in ed)

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — aplicele si intrerupatoarele se lipesc si se orienteaza, la fel in ambele oglinzi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
