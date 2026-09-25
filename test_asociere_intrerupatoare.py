"""Asocierea bec <-> intrerupator, stocata (pachetul 1).

DE CE EXISTA. Pana acum nimeni nu putea raspunde la „ce bec comuta intrerupatorul asta": asocierea
se calcula la desen si se arunca. Acum se calculeaza explicit si se scrie in `plan_elements.comutat_de`.

Proba pazeste trei lucruri care, gresite, arata la fel ca cele corecte:
  1. CELE PATRU CAZURI ale lui Dan — rulate, nu citite.
  2. DIVERGENTA fata de `compute_cables` e MASURATA, nu tacuta. Pachetul 1 stocheaza o asociere care
     NU coincide cu ce se deseneaza (compute_cables pune toate becurile pe un singur intrerupator).
     Asta e voit si temporar; pachetul 2 le uneste. Daca cineva sterge divergenta din greseala sau o
     mareste, se vede aici.
  3. NIMENI NU CITESTE `comutat_de` la desen — altfel planşele s-ar schimba, iar pachetul asta are ca
     prim criteriu sa nu schimbe niciuna.

Rulare:  python test_asociere_intrerupatoare.py
"""
import io
import os
import re
import sys

RADACINA = os.path.dirname(os.path.abspath(__file__))
rele = []


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def el(i, tip, x, y, camera="Living"):
    return {"id": "%08d-0000-0000-0000-000000000000" % i, "element_type": tip,
            "x": float(x), "y": float(y), "room": camera}


def main():
    sys.path.insert(0, RADACINA)
    import draw_elements as de

    A = de.asociaza_intrerupatoare
    ids = lambda rez, k: sorted(rez[k])
    harta = lambda r: {u["id"]: sorted(u["comutat_de"]) for u in r["updates"]}

    # ── [A] O camera, UN intrerupator, TREI becuri -> toate pe el ──────────────────────────
    sw = el(1, "intrerupator_simplu", 0, 0)
    b1, b2, b3 = el(2, "lustra_led", 50, 0), el(3, "lustra_led", 100, 0), el(4, "aplica_tavan", 150, 0)
    h = harta(A([sw, b1, b2, b3]))
    v("[A] 3 becuri, 1 intrerupator: toate trei pe el",
      h[b1["id"]] == h[b2["id"]] == h[b3["id"]] == [sw["id"]], str(h))

    # ── [B] DOUA intrerupatoare, DOUA becuri -> unul pe fiecare ────────────────────────────
    s1, s2 = el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 200, 0)
    b1, b2 = el(3, "lustra_led", 30, 0), el(4, "lustra_led", 170, 0)
    h = harta(A([s1, s2, b1, b2]))
    v("[B] 2 becuri, 2 intrerupatoare: fiecare bec la cel mai APROPIAT",
      h[b1["id"]] == [s1["id"]] and h[b2["id"]] == [s2["id"]], str(h))
    v("[B] niciun intrerupator nu ramane fara bec",
      {s1["id"], s2["id"]} == {x for vv in h.values() for x in vv})

    # PATRU becuri, DOUA intrerupatoare, cate doua de fiecare parte. Cazul asta e ALES anume:
    # cu 2 becuri, varianta gresita („toate pe unul") ar fi fost reparata de regula „intrerupatorul
    # gol ia un bec" si ar fi dat acelasi rezultat — deci n-ar fi dovedit nimic. Cu patru, regula de
    # departajare muta UNUL singur, si distributia 2+2 nu mai poate fi imitata.
    s1, s2 = el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 300, 0)
    b1, b2 = el(3, "lustra_led", 10, 0), el(4, "lustra_led", 20, 0)
    b3, b4 = el(5, "lustra_led", 290, 0), el(6, "lustra_led", 295, 0)
    h = harta(A([s1, s2, b1, b2, b3, b4]))
    v("[B] 4 becuri, 2 intrerupatoare: se impart 2+2, dupa apropiere",
      h[b1["id"]] == h[b2["id"]] == [s1["id"]] and h[b3["id"]] == h[b4["id"]] == [s2["id"]], str(h))

    # „ultimul bec trece pe el": al doilea intrerupator e pus LANGA primul, deci pura apropiere
    # i-ar da zero becuri. Regula de departajare i-l da pe cel mai apropiat de el.
    s1, s2 = el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 10, 0)
    b1, b2 = el(3, "lustra_led", 300, 0), el(4, "lustra_led", 400, 0)
    h = harta(A([s1, s2, b1, b2]))
    v("[B] al DOILEA intrerupator, lipit de primul: tot primeste un bec",
      len({x for vv in h.values() for x in vv}) == 2, str(h))

    # ── [C] Se sterge un intrerupator -> cel ramas preia TOATE becurile ────────────────────
    s1, s2 = el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 200, 0)
    b1, b2 = el(3, "lustra_led", 30, 0), el(4, "lustra_led", 170, 0)
    h = harta(A([s1, b1, b2]))                       # s2 sters
    v("[C] dupa stergerea unuia: ambele becuri pe cel ramas",
      h[b1["id"]] == h[b2["id"]] == [s1["id"]], str(h))

    # ── [D] CAP-SCARA: un bec, DOUA intrerupatoare -> forma o permite ──────────────────────
    c1, c2 = el(1, "intrerupator_cap_scara", 0, 0), el(2, "intrerupator_cap_scara", 200, 0)
    b1 = el(3, "lustra_led", 100, 0)
    h = harta(A([c1, c2, b1]))
    v("[D] cap-scara: becul e comutat de AMANDOUA",
      h[b1["id"]] == sorted([c1["id"], c2["id"]]), str(h))
    st = A([c1, c2, b1])["stats"]
    v("[D] se numara ca pereche cap-scara", st["cap_scara"] == 1, str(st))

    # ── [E] Reguli de granita ──────────────────────────────────────────────────────────────
    b1 = el(1, "lustra_led", 0, 0)
    h = harta(A([b1]))
    v("[E] bec fara niciun intrerupator in camera: lista GOALA, nu lipsa",
      h[b1["id"]] == [], str(h))
    sz = el(2, "aplica_senzor", 10, 0)
    h = harta(A([sz]))
    v("[E] senzor SINGUR: nu-l comuta nimic (R2)", h[sz["id"]] == [])
    sw = el(3, "intrerupator_simplu", 20, 0)
    h = harta(A([sz, sw]))
    v("[E] senzor CU intrerupator in camera: devine comutabil (R2)", h[sz["id"]] == [sw["id"]])
    ev = {"id": "e", "element_type": de._EVAC_TYPE, "x": 0.0, "y": 0.0, "room": "Living"}
    h = harta(A([ev, el(4, "intrerupator_simplu", 10, 0)]))
    v("[E] corpul de evacuare NU primeste intrerupator, niciodata", "e" not in h, str(h))
    # camere DIFERITE nu se amesteca
    h = harta(A([el(1, "intrerupator_simplu", 0, 0, "Baie"), el(2, "lustra_led", 5, 0, "Living")]))
    v("[E] un bec nu se leaga de intrerupatorul din ALTA camera (chiar lipit)",
      h["00000002-0000-0000-0000-000000000000"] == [])

    # ── [F] Determinism si idempotenta ─────────────────────────────────────────────────────
    scena = [el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 100, 0),
             el(3, "lustra_led", 40, 0), el(4, "lustra_led", 60, 0), el(5, "aplica_tavan", 80, 0)]
    import copy
    h1 = harta(A(copy.deepcopy(scena)))
    h2 = harta(A(copy.deepcopy(list(reversed(scena)))))
    v("[F] acelasi rezultat indiferent de ORDINEA elementelor", h1 == h2, "%s vs %s" % (h1, h2))
    doi = copy.deepcopy(scena)
    A(doi); r2 = A(doi)                               # a doua oara pe acelasi obiect
    v("[F] idempotent: a doua rulare nu mai schimba nimic",
      all(not u["changed"] for u in r2["updates"]),
      str([u for u in r2["updates"] if u["changed"]])[:80])

    # ── [G] DIVERGENTA fata de compute_cables: masurata, nu tacuta ─────────────────────────
    # O camera cu 2 intrerupatoare si 2 becuri: compute_cables le pune pe AMANDOUA pe unul singur,
    # asocierea le imparte. Atat timp cat nimeni nu citeste `comutat_de` la desen, planşa nu se
    # schimba. Cand pachetul 2 le uneste, capul asta trebuie sa pice — si atunci se rescrie.
    s1, s2 = el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 200, 0)
    b1, b2 = el(3, "lustra_led", 30, 0), el(4, "lustra_led", 170, 0)
    cab, _ = de.compute_cables([s1, s2, b1, b2])
    # ATENTIE: intr-un LANT, `from_xy` e intrerupatorul DOAR la primul segment; de la al doilea
    # incolo e becul anterior. Deci se filtreaza pe TIP, nu pe pozitie — prima varianta a probei a
    # picat tocmai fiindca numara si un bec drept intrerupator.
    sw_cu_bec = {(round(xy[0], 1), round(xy[1], 1)) for c in cab
                 if c.get("kind") in ("bec_lant", "bec_paralel")
                 for tip, xy in ((c["from_type"], c["from_xy"]), (c["to_type"], c["to_xy"]))
                 if tip in de._SWITCH_TYPES}
    h = harta(A([s1, s2, b1, b2]))
    v("[G] compute_cables foloseste UN intrerupator; asocierea foloseste DOUA",
      len(sw_cu_bec) == 1 and len({x for vv in h.values() for x in vv}) == 2,
      "cabluri=%s asociere=%s" % (sw_cu_bec, h))

    # ── [H] Desenul NU citeste asocierea (altfel planşele s-ar schimba) ────────────────────
    dr = io.open(os.path.join(RADACINA, "draw_elements.py"), encoding="utf-8").read()
    corp = dr[dr.index("def compute_cables("):dr.index("def _cid_coboara(")] \
        if "def _cid_coboara(" in dr else dr[dr.index("def compute_cables("):]
    v("[H] compute_cables nu se uita la comutat_de", "comutat_de" not in corp)
    desen = dr[dr.index("def redraw_from_plan_elements("):]
    v("[H] redraw_from_plan_elements nu se uita la comutat_de", "comutat_de" not in desen)

    # ── [I] Asocierea nu se COPIAZA intre apartamente (ar arata spre alt apartament) ───────
    ap = io.open(os.path.join(RADACINA, "apartments.py"), encoding="utf-8").read()
    m = re.search(r'_NU_SE_COPIAZA = \(([^)]*)\)', ap, re.S)
    v("[I] comutat_de e exclus din copierea intre apartamente",
      bool(m) and "comutat_de" in m.group(1), (m.group(1)[:70] if m else "?"))

    # ── [J] Persistarea exista si e defensiva ──────────────────────────────────────────────
    mn = io.open(os.path.join(RADACINA, "main.py"), encoding="utf-8").read()
    v("[J] /regenerate-plan cheama asocierea", "asociaza_intrerupatoare(rows)" in mn)
    v("[J] se scriu DOAR randurile schimbate", '{"comutat_de": _u["comutat_de"]}' in mn)
    i = mn.index("asociaza_intrerupatoare(rows)")
    v("[J] orice eroare NU strica regenerarea",
      "except Exception" in mn[i:i + 500] and "asociaza_intrerupatoare skip" in mn[i:i + 500])

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — asocierea exista, respecta cele patru cazuri, si nu atinge desenul")
    return 0


if __name__ == "__main__":
    sys.exit(main())
