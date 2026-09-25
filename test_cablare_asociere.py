"""Cablarea urmeaza ASOCIEREA, nu apropierea (pachetul 2).

DE CE EXISTA. Pana acum `compute_cables` alegea singur UN intrerupator per camera (cel mai apropiat
de centroidul becurilor) si ii dadea TOATE becurile; celelalte ramaneau fara nimic de comandat.
Acum citeste `comutat_de`, scris de `asociaza_intrerupatoare`.

Doua lucruri pot strica asta fara sa se vada:
  - CAZUL LIPSA. Proiectele de dinainte de pachetul 1 au coloana goala, iar `bom.py` cheama
    compute_cables cu randuri luate direct din baza. Daca poarta de rezerva se strica, planşele lor
    se schimba peste noapte. Proba verifica byte-identitatea desenului fara asociere.
  - TIPUL intrerupatorului. Lantul si ramificatiile arata amandoua ca „niste linii rosii"; numai
    numaratoarea le deosebeste.

Rulare:  python test_cablare_asociere.py
"""
import io
import math
import os
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
    import copy

    TABLOU = {"id": "t", "element_type": "tablou_teg", "x": 0.0, "y": 500.0, "room": None}

    def cabluri(scena, cu_asociere=True):
        s = copy.deepcopy(scena)
        if cu_asociere:
            de.asociaza_intrerupatoare(s)
        cab, st = de.compute_cables(s)
        return cab, st

    def nr(cab, kind):
        return sum(1 for c in cab if c.get("kind") == kind)

    def sw_atinse(cab):
        """Pozitiile intrerupatoarelor care primesc macar un cablu spre un bec.
        Se filtreaza pe TIP, nu pe pozitie: intr-un LANT, `from_xy` e intrerupatorul doar la primul
        segment, de la al doilea incolo e becul anterior."""
        return {(round(xy[0], 1), round(xy[1], 1)) for c in cab
                if c.get("kind") in ("bec_lant", "bec_paralel", "cap_scara")
                for tip, xy in ((c["from_type"], c["from_xy"]), (c["to_type"], c["to_xy"]))
                if tip in de._SWITCH_TYPES}

    # ── [A] 1 SIMPLU + 3 becuri -> LANT, exact ca inainte ──────────────────────────────────
    sc = [TABLOU, el(1, "intrerupator_simplu", 0, 0),
          el(2, "lustra_led", 50, 0), el(3, "lustra_led", 100, 0), el(4, "lustra_led", 150, 0)]
    cab, _ = cabluri(sc)
    v("[A] simplu + 3 becuri: 3 segmente de LANT, zero ramificatii",
      nr(cab, "bec_lant") == 3 and nr(cab, "bec_paralel") == 0, "lant=%d par=%d" % (nr(cab, "bec_lant"), nr(cab, "bec_paralel")))
    vechi, _ = cabluri(sc, cu_asociere=False)
    drumuri = lambda c: sorted(tuple(map(tuple, x.get("path") or [])) for x in c if x.get("kind", "").startswith(("bec", "cap")))
    v("[A] cazul cel mai frecvent: desen IDENTIC cu cel dinainte de pachet",
      drumuri(cab) == drumuri(vechi))

    # ── [B] 1 DUBLU + 2 becuri -> doua RAMIFICATII separate, nu lant ───────────────────────
    sc = [TABLOU, el(1, "intrerupator_dublu", 0, 0),
          el(2, "lustra_led", 50, 0), el(3, "lustra_led", 100, 0)]
    cab, _ = cabluri(sc)
    v("[B] dublu + 2 becuri: doua ramificatii, niciun lant",
      nr(cab, "bec_paralel") == 2 and nr(cab, "bec_lant") == 0,
      "par=%d lant=%d" % (nr(cab, "bec_paralel"), nr(cab, "bec_lant")))
    v("[B] ambele ramificatii pleaca din ACELASI intrerupator", len(sw_atinse(cab)) == 1)
    sc3 = [TABLOU, el(1, "intrerupator_triplu", 0, 0), el(2, "lustra_led", 50, 0),
           el(3, "lustra_led", 100, 0), el(4, "lustra_led", 150, 0)]
    cab3, _ = cabluri(sc3)
    v("[B] triplu + 3 becuri: TREI ramificatii", nr(cab3, "bec_paralel") == 3)

    # ── [C] CAP-SCARA: becul se ramifica spre AMANDOUA, si amandoua merg la tablou ─────────
    sc = [TABLOU, el(1, "intrerupator_cap_scara", 0, 0), el(2, "intrerupator_cap_scara", 200, 0),
          el(3, "lustra_led", 100, 0)]
    cab, _ = cabluri(sc)
    v("[C] cap-scara: DOUA cabluri catre acelasi bec", nr(cab, "cap_scara") == 2)
    v("[C] ...unul din fiecare intrerupator", len(sw_atinse(cab)) == 2, str(sw_atinse(cab)))
    v("[C] AMANDOUA merg si la tablou", nr(cab, "sw_tablou") == 2)
    # si cazul pe care regula veche NU-l prindea: DOUA cap-scara + un intrerupator simplu in camera
    sc = [TABLOU, el(1, "intrerupator_cap_scara", 0, 0), el(2, "intrerupator_cap_scara", 200, 0),
          el(3, "intrerupator_simplu", 100, 300), el(4, "lustra_led", 100, 0), el(5, "lustra_led", 100, 280)]
    cab, _ = cabluri(sc)
    v("[C] cap-scara langa un simplu: perechea ramane pereche, simplul isi ia becul lui",
      nr(cab, "cap_scara") == 2 and nr(cab, "bec_lant") == 1, "cap=%d lant=%d" % (nr(cab, "cap_scara"), nr(cab, "bec_lant")))

    # ── [D] DOUA simple + 4 becuri -> fiecare cu becurile lui, fara lanturi paralele ───────
    sc = [TABLOU, el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 300, 0),
          el(3, "lustra_led", 10, 0), el(4, "lustra_led", 20, 0),
          el(5, "lustra_led", 290, 0), el(6, "lustra_led", 295, 0)]
    cab, _ = cabluri(sc)
    v("[D] 2 simple + 4 becuri: 4 segmente in total (2+2), nu 8",
      nr(cab, "bec_lant") == 4, "lant=%d" % nr(cab, "bec_lant"))
    v("[D] AMBELE intrerupatoare comanda ceva", len(sw_atinse(cab)) == 2, str(sw_atinse(cab)))
    vechi, _ = cabluri(sc, cu_asociere=False)
    v("[D] inainte de pachet, unul singur comanda tot (asta se repara)",
      len(sw_atinse(vechi)) == 1, str(sw_atinse(vechi)))
    # metrii: cu asocierea, lanturile sunt scurte si locale
    L = lambda c: sum(sum(math.hypot(p[i+1][0]-p[i][0], p[i+1][1]-p[i][1]) for i in range(len(p)-1))
                      for p in [x.get("path") or [] for x in c] )
    b_nou = L([c for c in cab if c.get("kind", "").startswith(("bec", "cap"))])
    b_vechi = L([c for c in vechi if c.get("kind", "").startswith(("bec", "cap"))])
    v("[D] metrii bec-intrerupator SCAD in cazul asta", b_nou < b_vechi,
      "%.0f -> %.0f" % (b_vechi, b_nou))

    # ── [E] Bec cu `comutat_de` LIPSA -> camera cade pe logica veche, byte-identic ─────────
    sc = [TABLOU, el(1, "intrerupator_simplu", 0, 0), el(2, "intrerupator_simplu", 300, 0),
          el(3, "lustra_led", 10, 0), el(4, "lustra_led", 290, 0)]
    fara, _ = cabluri(sc, cu_asociere=False)          # exact ce se citeste azi din baza (coloana goala)
    v("[E] fara asociere: se cableaza TOTUSI (niciun bec nu ramane pe dinafara)",
      nr(fara, "bec_lant") + nr(fara, "bec_paralel") + nr(fara, "cap_scara") == 2)
    v("[E] fara asociere: comportamentul VECHI (un singur intrerupator comanda)",
      len(sw_atinse(fara)) == 1)
    # partial: un bec are asociere, celalalt nu -> TOATA camera cade pe vechi (poarta e pe camera)
    partial = copy.deepcopy(sc)
    de.asociaza_intrerupatoare(partial)
    for e in partial:
        if e["element_type"] == "lustra_led" and e["x"] == 290.0:
            e["comutat_de"] = None
            break
    cab_p, _ = de.compute_cables(partial)
    v("[E] camera PARTIAL asociata cade INTREAGA pe logica veche (nu desen amestecat)",
      drumuri(cab_p) == drumuri(fara), "%s vs %s" % (len(drumuri(cab_p)), len(drumuri(fara))))

    # ── [F] Lista GOALA nu inseamna „necalculat" ───────────────────────────────────────────
    sc = [TABLOU, el(1, "intrerupator_simplu", 0, 0), el(2, "lustra_led", 50, 0)]
    g = copy.deepcopy(sc)
    for e in g:
        if e["element_type"] == "lustra_led":
            e["comutat_de"] = []
    cab_g, st_g = de.compute_cables(g)
    v("[F] bec cu lista GOALA: nu se cableaza, si se numara ca atare",
      nr(cab_g, "bec_lant") == 0 and st_g.get("skip_bec_fara_sw", 0) >= 1, str(st_g.get("skip_bec_fara_sw")))

    # ── [G] Senzorul si corpul de evacuare nu se schimba ───────────────────────────────────
    sc = [TABLOU, {"id": "e", "element_type": de._EVAC_TYPE, "x": 10.0, "y": 0.0, "room": "Living"},
          el(1, "aplica_senzor", 50, 0)]
    cab, st = cabluri(sc)
    v("[G] senzor singur -> direct la tablou (SP), ca inainte", st.get("senzor_teg", 0) == 1)
    v("[G] corp de evacuare -> direct la tablou, necondtionat", st.get("evacuare_teg", 0) == 1)

    # ── [H] Tipurile de cablu (kind) au ramas ACELEASI -> BOM-ul nu se rebucketeaza ────────
    import bom
    sc = [TABLOU, el(1, "intrerupator_dublu", 0, 0), el(2, "lustra_led", 50, 0), el(3, "lustra_led", 90, 0)]
    cab, _ = cabluri(sc)
    v("[H] toate kind-urile produse sunt cunoscute de BOM",
      all(c.get("kind") in (bom._ILUM_KINDS | bom._PRIZA_KINDS) for c in cab),
      str({c.get("kind") for c in cab} - (bom._ILUM_KINDS | bom._PRIZA_KINDS)))

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — cablarea urmeaza asocierea; fara ea, desenul de azi ramane neatins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
