# -*- coding: utf-8 -*-
"""Poarta de arie (REGULA 1b): conturul care nu se potriveste cu aria declarata se respinge.

De ce exista testul: plafonul (REGULA 1) prinde conturul prea MARE, dar nimic nu prindea conturul
prea MIC — adica exact camera vecina, luata dincolo de un perete de un seed scapat. Pe Casa Borcan,
cu parserul de geometrie, „Dormitor 2" (14,40 mp) primea conturul BAII (5,30 mp).

Cele patru capete verificate aici:
  [C] un contur de 0,37 din aria declarata e RESPINS (cazul Borcan, reprodus prin parser);
  [D] fara arie declarata poarta e INERTA (nu inventam o valoare de comparat);
  [D2] o camera corecta din capatul de jos al distributiei masurate (0,505) TRECE;
  [E] respingerea scoate TOT ce s-a dedus din conturul strain (centroid, geom_bbox, pereti, usi) —
      altfel becul s-ar muta, dar prizele ar ramane pe peretii vecinului.

Rulare:  python test_geom_poarta_arie.py
Planul de referinta lipsa -> capatul [C] se sare (nu pica un CI pe un fisier absent).
"""
import os
import sys

PLAN_BORCAN = os.environ.get(
    "ZYN_PLAN_BORCAN",
    r"C:\Users\Adi\AppData\Local\Temp\claude\C--zynapse\5b519f49-43dc-4160-a968-3479d7ea863e\scratchpad\borcan.pdf")

# camerele Vision ale proiectului „Casa Borcan", exact cum le-a dat Vision (bbox normalizat 0-1)
CAMERE_BORCAN = [
    {"name": "Garaj", "area_m2": 35.4, "bbox": {"x": 0.145, "y": 0.36, "w": 0.2, "h": 0.28}},
    {"name": "Spatiu tehnic", "area_m2": 10.6, "bbox": {"x": 0.19, "y": 0.2, "w": 0.155, "h": 0.14}},
    {"name": "Dormitor 1", "area_m2": 14.4, "bbox": {"x": 0.35, "y": 0.2, "w": 0.13, "h": 0.14}},
    {"name": "Bucatarie", "area_m2": 15.36, "bbox": {"x": 0.505, "y": 0.2, "w": 0.155, "h": 0.14}},
    {"name": "Terasa deschisa", "area_m2": 12.93, "bbox": {"x": 0.665, "y": 0.2, "w": 0.2, "h": 0.14}},
    {"name": "Baie", "area_m2": 5.5, "bbox": {"x": 0.35, "y": 0.36, "w": 0.115, "h": 0.13}},
    {"name": "Dormitor 2", "area_m2": 14.4, "bbox": {"x": 0.35, "y": 0.5, "w": 0.13, "h": 0.14}},
    {"name": "Hol", "area_m2": 4.1, "bbox": {"x": 0.485, "y": 0.5, "w": 0.08, "h": 0.14}},
    {"name": "Living", "area_m2": 39.69, "bbox": {"x": 0.565, "y": 0.36, "w": 0.3, "h": 0.28}},
    {"name": "Terasa acces", "area_m2": 3.9, "bbox": {"x": 0.475, "y": 0.65, "w": 0.14, "h": 0.09}},
]

rele = []


def v(nume, cond, det=""):
    print("  %-70s %s %s" % (nume[:70], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def _collect_prin_parser(geometry, geom_parser):
    """`_collect` alimentat de parser, FARA regula de ignorare — asa apare defectul Borcan.

    Regula de ignorare (`trasee_de_ignorat`) ascunde azi patrulaterele care produc peretii in plus;
    testul o ocoleste intentionat, ca sa reproduca conturul gresit pe care poarta trebuie sa-l
    opreasca. Comutarea pe parser, cand va veni, trebuie sa gaseasca poarta deja la locul ei.
    """
    def _collect(page):
        h, vv = [], []
        for dd in geom_parser.deseneaza(page):
            if not geometry._is_wall_layer(dd.get("layer")):
                continue
            for it in dd.get("items", []):
                if it[0] != "l":
                    continue
                p1, p2 = it[1], it[2]
                dx, dy = abs(p1.x - p2.x), abs(p1.y - p2.y)
                if dx > geometry.MIN_WALL_LEN and dy < geometry.AXIS_TOL:
                    h.append((min(p1.x, p2.x), max(p1.x, p2.x), (p1.y + p2.y) / 2.0))
                elif dy > geometry.MIN_WALL_LEN and dx < geometry.AXIS_TOL:
                    vv.append((min(p1.y, p2.y), max(p1.y, p2.y), (p1.x + p2.x) / 2.0))
        return h, vv, []
    return _collect


def main():
    import fitz
    import geometry
    import geom_parser

    print("prag: MIN_AREA_RATIO = %.2f (plafonul pereche: MAX_AREA_RATIO = %.1f)"
          % (geometry.MIN_AREA_RATIO, geometry.MAX_AREA_RATIO))
    v("pragul e sub cea mai mica camera corecta masurata (0,505)", geometry.MIN_AREA_RATIO < 0.505,
      "prag %.3f" % geometry.MIN_AREA_RATIO)
    v("pragul e peste cazul Borcan (5,30/14,40 = 0,368)", geometry.MIN_AREA_RATIO > 5.30 / 14.40,
      "prag %.3f" % geometry.MIN_AREA_RATIO)

    if not os.path.exists(PLAN_BORCAN):
        print("  planul de referinta lipseste (%s) — capetele [C]/[D]/[E] se sar" % PLAN_BORCAN)
        return 1 if rele else 0

    raw = open(PLAN_BORCAN, "rb").read()
    d = fitz.open(stream=raw, filetype="pdf")
    W, H = d[0].rect.width, d[0].rect.height
    d.close()

    umbra, colect = geometry.UMBRA_PARSER, geometry._collect
    geometry.UMBRA_PARSER = False
    geometry._collect = _collect_prin_parser(geometry, geom_parser)
    try:
        rez = geometry.extract_room_geometry(raw, CAMERE_BORCAN, W, H)
        d2 = next(r for r in rez if r["name"] == "Dormitor 2")
        arie = d2.get("area_geometric_m2") or 0
        rap = arie / 14.40
        # [C] conturul gasit e intr-adevar cel mic (baia), si e respins
        v("[C] Dormitor 2 primeste un contur de ~0,37 din aria declarata", 0.30 < rap < 0.45,
          "raport %.3f (arie %.2f)" % (rap, arie))
        v("[C] Dormitor 2 NU se valideaza geometric", not d2.get("geometric"),
          str(d2.get("reason"))[:70])
        v("[C] motivul numeste poarta", "REGULA 1b" in str(d2.get("reason")),
          str(d2.get("reason"))[:70])
        # [E] nu ramane nimic dedus din conturul strain
        v("[E] fara centroid din conturul strain", d2.get("centroid") is None)
        v("[E] fara pereti din conturul strain", not d2.get("wall_segments"))
        v("[E] fara usi din conturul strain", not d2.get("doors"))
        v("[E] geom_bbox nu vine din perete", (d2.get("geom_source") or "") != "wall",
          "sursa %r" % d2.get("geom_source"))

        # [D] fara arie declarata, poarta nu se aplica: aceleasi camere, fara `area_m2`
        fara = [dict(c, area_m2=None) for c in CAMERE_BORCAN]
        rez_f = geometry.extract_room_geometry(raw, fara, W, H)
        d2f = next(r for r in rez_f if r["name"] == "Dormitor 2")
        v("[D] fara arie declarata poarta e inerta (niciun respins REGULA 1b)",
          all("REGULA 1b" not in str(r.get("reason")) for r in rez_f),
          [str(r.get("reason"))[:40] for r in rez_f if "REGULA 1b" in str(r.get("reason"))][:1])
        v("[D] si camera ramane pe traseul ei normal", d2f.get("area_geometric_m2") is not None)
    finally:
        geometry._collect = colect
        geometry.UMBRA_PARSER = umbra

    print("\n".join("ESUAT: " + r for r in rele) if rele else "OK — poarta de arie se poarta cum trebuie")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.exit(main())
