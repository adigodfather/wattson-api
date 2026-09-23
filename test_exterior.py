# -*- coding: utf-8 -*-
"""Spatiile exterioare nu primesc nimic automat — si cele doua limbi nu se despart.

De ce exista testul: notiunea de „spatiu exterior" traieste in DOUA locuri, fiindca prizele se
plaseaza in TypeScript (`lib/auto-prize.ts`) iar becurile in Python (`draw_elements.py`). Doua liste
tinute in sincron prin bunavointa diverg — asa au aparut, in trecut, prize IP44 pe circuit fara RCCB.
Testul citeste FISIERUL .ts si pica daca regexul de acolo nu mai e identic cu cel din Python.

Capetele verificate:
  [A] regexul din .ts == regexul din Python, caracter cu caracter;
  [B] numele REALE de terase/balcoane/podeste de pe planuri sunt recunoscute ca exterior;
  [C] «Hol acces», «Platforma acces» si «Radiologie» NU sunt — primele doua fiindca „acces" a fost
      scos dinadins din lista, a treia fiindca „logie" are granita de cuvant;
  [D] o camera exterioara nu primeste bec nici din bucla, nici din invariantul „fiecare camera are
      bec" — invariantul e al doilea loc, si e cel care ar pune becul inapoi pe tacute.

Rulare:  python test_exterior.py
"""
import io
import os
import re
import sys

TS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "apps", "zynapse-configurator", "lib", "auto-prize.ts")

# numele exact cum apar pe planurile din baza (masurate, nu inventate)
EXTERIOARE = ["Terasa", "Terasa Acoperita", "Terasa acces", "Terasa acoperita (parter)",
              "Terasa acoperita acces", "Terasa acoperita peste subsol", "Balcon neacoperit 1 (etaj)",
              "Podest Acoperit", "Podest intrare", "Loggia", "Logie", "Curte interioara"]
INTERIOARE = ["Hol acces", "Hol acces (central)", "Hol acces (dormitoare)", "Hol acces 1",
              "Hol acces mic", "Platforma acces", "Radiologie", "Tehnologie", "Biologie",
              "Living", "Dormitor 1", "Baie", "Camara", "Spatiu tehnic", "Garaj"]

rele = []


def v(nume, cond, det=""):
    print("  %-72s %s %s" % (nume[:72], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import draw_elements as D

    # [A] aceeasi notiune, doua limbi, un singur text
    if not os.path.exists(TS):
        v("[A] fisierul .ts exista", False, TS)
        return 1
    src = io.open(TS, encoding="utf-8").read()
    m = re.search(r"export const EXTERIOR_RX = /(.+?)/i;", src)
    v("[A] `EXTERIOR_RX` se gaseste in auto-prize.ts", m is not None)
    if m:
        v("[A] regexul din .ts e identic cu `_EXTERIOR_RX_SRC` din Python",
          m.group(1) == D._EXTERIOR_RX_SRC,
          "ts=%r  py=%r" % (m.group(1), D._EXTERIOR_RX_SRC))
    # lista de cuvinte nu mai are voie sa existe separat in editor
    ed = os.path.join(os.path.dirname(TS), "..", "components", "plan-editor.tsx")
    if os.path.exists(ed):
        v("[A] editorul NU mai tine o a doua lista de cuvinte (EXTERIOR_KW)",
          "EXTERIOR_KW" not in io.open(ed, encoding="utf-8").read())

    # [B] + [C] ce prinde si ce NU prinde
    for n in EXTERIOARE:
        v("[B] «%s» e spatiu exterior" % n, D._e_exterior(n))
    for n in INTERIOARE:
        v("[C] «%s» NU e spatiu exterior" % n, not D._e_exterior(n))

    # [D] nici bucla, nici invariantul nu dau bec unei camere exterioare
    rooms = [{"name": "Living", "area_m2": 24.0, "bbox": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3}},
             {"name": "Terasa acoperita", "area_m2": 18.0, "bbox": {"x": 0.5, "y": 0.1, "w": 0.3, "h": 0.3}},
             {"name": "Balcon neacoperit 1", "area_m2": 8.0, "bbox": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2}}]
    centers, stats = D._vision_centers(rooms, 1000.0, 1000.0)
    camere = {c["room"] for c in centers}
    v("[D] camera interioara primeste bec", 0 in camere)
    v("[D] terasa NU primeste bec", 1 not in camere, "becuri: %s" % sorted(camere))
    v("[D] balconul NU primeste bec", 2 not in camere, "becuri: %s" % sorted(camere))
    v("[D] invariantul de bec-per-camera nu le readauga",
      stats.get("bulbs_guaranteed", 0) == 0 or (1 not in camere and 2 not in camere),
      "bulbs_guaranteed=%s" % stats.get("bulbs_guaranteed"))

    print("\n".join("ESUAT: " + r for r in rele) if rele
          else "OK — exteriorul nu primeste nimic automat, iar cele doua limbi spun acelasi lucru")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
