# -*- coding: utf-8 -*-
"""Seed-ul care nu e in camera cautata: verificarea de traversare si conditia de cuprindere.

Cautarea conturului arunca o grila de seed-uri in bbox-ul Vision. Cand bbox-ul e decalat peste un
perete — si e, masurat: la 28 din 38 de camere gresite eticheta camerei cadea in AFARA bbox-ului —
seed-urile aterizeaza in camera vecina, iar conturul intors e al vecinei. Trece de toate celelalte
verificari: e mai MIC, deci sub plafon; incape in bbox; are aspect bun. Asa a primit
`casa test / Dormitor 2` (13,60 mp declarati) conturul de 9,41 mp al BAII.

Un seed se pastreaza doar daca, pana la eticheta camerei:
  (1) nu taie un perete despartitor, si
  (2) conturul pe care il da CUPRINDE eticheta — fiindca (1) se poate satisface si ocolind capatul
      peretelui printr-un gol.

Testul acopera mecanica, sintetic si determinist. Efectul pe corpus (14 conturi straine reparate,
13 camere mute rezolvate, ZERO camere corecte miscate, din 380) se masoara cu sondele din pachet,
care au nevoie de planurile din baza.

Rulare:  python test_geom_seed_traversare.py
"""
import sys

rele = []


def v(nume, cond, det=""):
    print("  %-72s %s %s" % (nume[:72], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def linii(pos, a0, a1):
    """O linie de perete agregata, in formatul lui `_aggregate`: (pozitie, intervale, total)."""
    return [(pos, [(a0, a1)], a1 - a0)]


def main():
    import geometry as g

    # ── (1) verificarea de traversare ────────────────────────────────────────────────────────
    # perete vertical la x=100, intre y=0 si y=200; seed la stanga, eticheta la dreapta
    zid = linii(100.0, 0.0, 200.0)
    v("seed si eticheta despartite de un perete -> traverseaza",
      g._traverseaza_perete(50.0, 100.0, 150.0, 100.0, [], zid, []))
    v("seed si eticheta de aceeasi parte -> NU traverseaza",
      not g._traverseaza_perete(20.0, 100.0, 60.0, 100.0, [], zid, []))
    v("peretele e dincolo de eticheta -> NU traverseaza",
      not g._traverseaza_perete(20.0, 100.0, 90.0, 100.0, [], zid, []))
    v("peretele nu acopera inaltimea trecerii -> NU traverseaza",
      not g._traverseaza_perete(50.0, 300.0, 150.0, 300.0, [], zid, []))
    # USA: acelasi perete, dar cu un arc de usa exact acolo unde trece linia
    v("trecerea printr-o usa NU e traversare",
      not g._traverseaza_perete(50.0, 100.0, 150.0, 100.0, [], zid, [(100.0, 100.0, 40.0)]))
    # STALP / SPALET: bucata de perete mai scurta decat pragul de despartitor
    stalp = linii(100.0, 95.0, 95.0 + g.PERETE_SEPARATOR - 4.0)
    v("un spalet/stalp (sub pragul de despartitor) NU blocheaza",
      not g._traverseaza_perete(50.0, 100.0, 150.0, 100.0, [], stalp, []))
    lung = linii(100.0, 95.0, 95.0 + g.PERETE_SEPARATOR + 4.0)
    v("aceeasi bucata, dar peste prag, blocheaza",
      g._traverseaza_perete(50.0, 100.0, 150.0, 100.0, [], lung, []))
    # perete ORIZONTAL, ca sa nu tinem doar o axa
    v("perete orizontal intre seed si eticheta -> traverseaza",
      g._traverseaza_perete(100.0, 50.0, 100.0, 150.0, linii(100.0, 0.0, 200.0), [], []))
    # camera in L: linia iese din camera prin dreptul nisei, dar intoarcerea nisei e scurta
    v("intoarcerea unei nise (scurta) nu respinge seed-ul din celalalt brat al L-ului",
      not g._traverseaza_perete(40.0, 40.0, 160.0, 160.0,
                                linii(100.0, 96.0, 96.0 + g.PERETE_SEPARATOR - 6.0),
                                linii(100.0, 96.0, 96.0 + g.PERETE_SEPARATOR - 6.0), []))

    # ── (2) ancora: eticheta camerei, neambigua ─────────────────────────────────────────────
    et = [{"name": "Hol acces", "area_m2": 7.62, "label_x": 0.2, "label_y": 0.2},
          {"name": "Hol acces", "area_m2": 13.48, "label_x": 0.8, "label_y": 0.8},
          {"name": "Baie", "area_m2": 5.34, "label_x": 0.5, "label_y": 0.5}]
    cam = {"area_m2": 13.48, "bbox": {"x": 0.0, "y": 0.0, "w": 0.3, "h": 0.3}}
    lb = g._eticheta_camerei("Hol acces", cam, et, sigura=True)
    v("doua etichete cu acelasi nume -> se alege dupa ARIA scrisa, nu dupa distanta",
      lb is not None and abs(lb["label_x"] - 0.8) < 1e-9,
      "a ales label_x=%s" % (lb and lb["label_x"]))
    cam2 = {"area_m2": 9.99, "bbox": {"x": 0.0, "y": 0.0, "w": 0.3, "h": 0.3}}
    v("omonime pe care aria nu le desparte -> fara ancora de incredere",
      g._eticheta_camerei("Hol acces", cam2, et, sigura=True) is None)
    v("aceleasi omonime, fara `sigura` (fallback-ul V4) -> tot intoarce o eticheta",
      g._eticheta_camerei("Hol acces", cam2, et) is not None)
    v("nume unic -> ancora exista", g._eticheta_camerei("Baie", cam2, et, sigura=True) is not None)
    v("nume inexistent pe plan -> fara ancora, deci fara verificare",
      g._eticheta_camerei("Dormitor 9", cam2, et, sigura=True) is None)

    print("\n".join("ESUAT: " + r for r in rele) if rele
          else "OK — seed-urile se filtreaza cum trebuie")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.exit(main())
