# -*- coding: utf-8 -*-
"""Parserul de geometrie + regula de ignorare dau ACELASI rezultat ca `get_drawings`.

DOUA CAPETE, si amandoua trebuie sa tina in acelasi timp — au fost in conflict la fiecare din cele
trei incercari de dinainte, fiecare reparand un capat si stricandu-l pe celalalt:

  CAPATUL BORCAN: pe planuri unde PyMuPDF grupeaza patrulatere in `qu`, geometria noastra nu le
    vede, si NICI parserul nu trebuie sa le vada. Daca le-ar vedea, „Dormitor 2" ar primi conturul
    BAII (5,3 mp in loc de 14,40) si becul ar ajunge in baie. Camera trebuie sa ramana pe Vision.
  CAPATUL BLOC: pe planurile de rola, traseele inchise sunt pereti adevarati, desenati umplut, si
    geometria ii foloseste. Regula nu are voie sa-i piarda — o versiune anterioara taia 186 din
    908 de segmente.

Rulare:  python test_geom_echivalenta.py
Cere planurile de referinta; daca lipsesc, testul spune ce lipseste si iese cu 0 (nu pica un CI
pe un fisier absent).
"""
import os
import sys

PLANURI = {
    "borcan": os.environ.get(
        "ZYN_PLAN_BORCAN",
        r"C:\Users\Adi\AppData\Local\Temp\claude\C--zynapse\5b519f49-43dc-4160-a968-3479d7ea863e\scratchpad\borcan.pdf"),
    "bloc": os.environ.get(
        "ZYN_PLAN_BLOC",
        r"C:\Users\Adi\Desktop\bloc\bloc ie\arhitectura\etaj 1 - arhitectura.pdf"),
}


def segmente_parser(page, geometry, geom_parser):
    """Ce ar folosi geometria daca ar fi alimentata de parser, CU regula de ignorare."""
    h, v = [], []
    for dd in geom_parser.deseneaza(page):
        if not geometry._is_wall_layer(dd.get("layer")):
            continue
        if geometry.trasee_de_ignorat(dd):
            continue
        for it in dd.get("items", []):
            if it[0] != "l":
                continue
            p1, p2 = it[1], it[2]
            dx, dy = abs(p1.x - p2.x), abs(p1.y - p2.y)
            if dx > geometry.MIN_WALL_LEN and dy < geometry.AXIS_TOL:
                h.append((min(p1.x, p2.x), max(p1.x, p2.x), (p1.y + p2.y) / 2.0))
            elif dy > geometry.MIN_WALL_LEN and dx < geometry.AXIS_TOL:
                v.append((min(p1.y, p2.y), max(p1.y, p2.y), (p1.x + p2.x) / 2.0))
    return h, v


def main():
    import fitz
    import geometry
    import geom_parser

    lipsa = [k for k, q in PLANURI.items() if not os.path.exists(q)]
    if lipsa:
        print("planuri de referinta lipsa: %s — testul se sare" % ", ".join(lipsa))
        return 0

    umbra = geometry.UMBRA_PARSER
    geometry.UMBRA_PARSER = False        # testul compara direct, nu prin umbra
    rele = []
    try:
        for nume, q in PLANURI.items():
            d = fitz.open(q)
            pg = d[0]
            hv, vv, _dv = geometry._collect(pg)
            hn, vn = segmente_parser(pg, geometry, geom_parser)
            a = (len(geometry._aggregate(hv)), len(geometry._aggregate(vv)))
            b = (len(geometry._aggregate(hn)), len(geometry._aggregate(vn)))
            d.close()
            ok = a == b
            print("  %-8s linii de perete agregate: vechi H%d V%d · parser H%d V%d  %s"
                  % (nume, a[0], a[1], b[0], b[1], "OK" if ok else "**DIFERIT**"))
            if not ok:
                rele.append("%s: vechi %s vs parser %s" % (nume, a, b))
            # capatul BLOC are si o conditie proprie: segmentele nu au voie sa scada
            if nume == "bloc" and len(hn) < len(hv):
                rele.append("bloc: parserul a PIERDUT segmente (%d -> %d) — regula taie prea mult"
                            % (len(hv), len(hn)))
    finally:
        geometry.UMBRA_PARSER = umbra

    print("\n".join("ESUAT: " + r for r in rele) if rele
          else "OK — parserul + regula dau acelasi rezultat pe amandoua capetele")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.exit(main())
