# -*- coding: utf-8 -*-
"""Etichetele de camera se citesc si cand textul planului e rotit.

Numele camerei e linia de deasupra ariei — dar „deasupra" se masoara in cadrul de coordonate AL
TEXTULUI. Pe `Casa Borcan` (singurul plan din 30 cu liniile de arie rotite 270°) cautarea in
coordonatele paginii gasea 10 linii de arie si ZERO etichete, deci pe proiectul primului client
platitor erau oprite si fallback-ul V4, si ancora filtrului de seed-uri.

A doua parte a regulii — numele se cauta doar printre liniile scrise in ACEEASI directie — a
reparat un defect care nu se vedea: pe trei planuri, extractorul lipea coduri de tamplarie rotite
(«U», «U1», «U-04») ca nume de camera langa arii orizontale.

Rulare:  python test_geom_etichete.py
"""
import os
import sys

rele = []


def v(nume, cond, det=""):
    print("  %-72s %s %s" % (nume[:72], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


ORIZ, SUS, JOS = (1.0, 0.0), (0.0, -1.0), (0.0, 1.0)


def main():
    import geometry as g

    # ── cadrul textului ───────────────────────────────────────────────────────────────────
    b = (10.0, 20.0, 50.0, 30.0)
    v("text orizontal -> cadrul e chiar pagina (calculul de azi, neatins)",
      g._cadru_text(b, ORIZ) == (10.0, 20.0, 50.0, 30.0), str(g._cadru_text(b, ORIZ)))
    u = g._cadru_text(b, SUS)
    v("text rotit 270° -> axele se schimba intre ele",
      (round(u[0], 1), round(u[1], 1), round(u[2], 1), round(u[3], 1)) == (-30.0, 10.0, -20.0, 50.0),
      str(u))
    v("latimea pe axa textului e inaltimea de pe pagina",
      abs((u[2] - u[0]) - (b[3] - b[1])) < 1e-9)

    # ── imperecherea nume <-> arie ────────────────────────────────────────────────────────
    W = H = 1000.0
    # orizontal: numele DEASUPRA ariei, pe pagina
    oriz = [((100.0, 100.0, 200.0, 112.0), "DORMITOR 1", ORIZ),
            ((100.0, 114.0, 200.0, 126.0), "S = 14,40 mp", ORIZ)]
    r = g._room_labels_from_lines(oriz, W, H)
    v("orizontal: numele de deasupra se lipeste de arie",
      len(r) == 1 and r[0]["name"] == "DORMITOR 1" and abs(r[0]["area_m2"] - 14.40) < 1e-9,
      str(r))
    # rotit 270°: numele e in STANGA ariei pe pagina, dar „deasupra" in cadrul textului
    rot = [((100.0, 100.0, 112.0, 200.0), "DORMITOR 2", SUS),
           ((114.0, 100.0, 126.0, 200.0), "S = 14,40 mp", SUS)]
    r = g._room_labels_from_lines(rot, W, H)
    v("rotit 270°: numele din stanga ariei se lipeste de ea",
      len(r) == 1 and r[0]["name"] == "DORMITOR 2", str(r))
    # rotit 90°: oglinda celui de sus
    rot90 = [((114.0, 100.0, 126.0, 200.0), "BAIE", JOS),
             ((100.0, 100.0, 112.0, 200.0), "S = 5,50 mp", JOS)]
    r = g._room_labels_from_lines(rot90, W, H)
    v("rotit 90°: acelasi lucru, in partea cealalta", len(r) == 1 and r[0]["name"] == "BAIE", str(r))
    # directii DIFERITE: un cod de tamplarie rotit nu e nume pentru o arie orizontala
    mixt = [((100.0, 100.0, 112.0, 200.0), "U-04", SUS),
            ((100.0, 114.0, 200.0, 126.0), "S = 3,79 mp", ORIZ)]
    r = g._room_labels_from_lines(mixt, W, H)
    v("nume rotit + arie orizontala -> NU se lipesc (cartusul si tamplaria raman afara)",
      r == [], str(r))
    # formatul vechi (perechi fara directie) trebuie sa mearga in continuare
    r = g._room_labels_from_lines([(l[0], l[1]) for l in oriz], W, H)
    v("perechi fara directie (formatul vechi) -> se presupune orizontal",
      len(r) == 1 and r[0]["name"] == "DORMITOR 1")

    # ── planul real, daca exista ──────────────────────────────────────────────────────────
    plan = os.environ.get(
        "ZYN_PLAN_BORCAN",
        r"C:\Users\Adi\AppData\Local\Temp\claude\C--zynapse\5b519f49-43dc-4160-a968-3479d7ea863e\scratchpad\borcan.pdf")
    if not os.path.exists(plan):
        print("  (planul rotit de referinta lipseste — partea pe plan real se sare)")
    else:
        import fitz
        d = fitz.open(plan)
        pg = d[0]
        lab = g._room_labels_from_lines(g._collect_text_lines(pg), pg.rect.width, pg.rect.height)
        d.close()
        nume = {x["name"]: x["area_m2"] for x in lab}
        v("planul rotit da 10 etichete (inainte: zero)", len(lab) == 10, "%d" % len(lab))
        for n, a in (("DORMITOR 2", 14.4), ("BAIE", 5.5), ("LIVING", 39.69), ("GARAJ", 35.4)):
            v("«%s» = %s mp" % (n, a), abs((nume.get(n) or -1) - a) < 1e-9, str(nume.get(n)))

    print("\n".join("ESUAT: " + r for r in rele) if rele
          else "OK — etichetele se citesc in cadrul textului, orice orientare ar avea")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.exit(main())
