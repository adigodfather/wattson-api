# -*- coding: utf-8 -*-
"""REGULA 1c: conturul care contine eticheta ALTEI camere se respinge.

De ce exista: verificarea pe care o face masuratoarea de ani de zile („conturul isi contine propria
eticheta") are o fata oarba. Un contur care inghite DOUA camere isi contine propria eticheta, deci
iese CORECT — si becul poate ajunge in cealalta camera. Masurat pe baza: 13 din 135 de contururi
validate contineau eticheta altei camere si erau folosite ca atare in productie.

Poarta de arie (1b) nu le prinde: o comasare e mai MARE decat camera, nu mai mica, deci trece de
podea. Plafonul (REGULA 1) nu le prinde nici el, fiindca ramane sub 1,8x.

Cele sase capete:
  [A] contur care contine si eticheta vecinului      -> RESPINS, si pleaca tot (pereti, usi)
  [B] contur curat, cu propria eticheta              -> trece (calea normala, neatinsa)
  [C] eticheta straina PE GRANITA conturului         -> NU respinge (sub `ADANCIME_STRAINA`)
  [D] eticheta care nu se potriveste cu nicio camera -> nu e „straina" pentru nimeni
  [E] nume cu calificativ („Dormitor 1 (parter)" vs «Dormitor 1») -> aceeasi camera, nu respinge
  [F] camera fara eticheta desenata                  -> regula nu se aplica

Rulare:  python test_geom_comasare.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import geometry as G                                                 # noqa: E402

rele = []


def v(nume, cond, det=""):
    print("  %-56s %s%s" % (nume, "OK" if cond else "PICAT", (" — " + det) if det else ""))
    if not cond:
        rele.append(nume)


W, H = 1000.0, 1000.0


def lb(nume, arie, x, y):
    return {"name": nume, "area_m2": arie, "label_x": x / W, "label_y": y / H}


CAMERE = [{"name": "Dormitor 1 (parter)", "area_m2": 14.0},
          {"name": "Baie 1 (parter)", "area_m2": 5.0}]

# conturul de test: 100..400 pe x, 100..400 pe y
L, R, T, B = 100.0, 400.0, 100.0, 400.0

# [A] eticheta vecinului, bine in interior (centru)
h = G._harta_etichete([lb("Dormitor 1", 14.0, 150, 150), lb("Baie 1", 5.0, 250, 250)], CAMERE)
v("[A] eticheta vecinului in centru -> respinge",
  G._eticheta_straina_in(0, L, R, T, B, h, W, H) is not None)

# [B] doar propria eticheta
h = G._harta_etichete([lb("Dormitor 1", 14.0, 250, 250)], CAMERE)
v("[B] doar propria eticheta -> nu respinge",
  G._eticheta_straina_in(0, L, R, T, B, h, W, H) is None)

# [C] eticheta straina pe granita (adancime sub prag)
#     x=105 -> (105-100)/150 = 0.033 < 0.12
h = G._harta_etichete([lb("Baie 1", 5.0, 105, 250)], CAMERE)
v("[C] eticheta straina pe granita -> NU respinge",
  G._eticheta_straina_in(0, L, R, T, B, h, W, H) is None,
  "adancime 0.03 < prag %.2f" % G.ADANCIME_STRAINA)
h = G._harta_etichete([lb("Baie 1", 5.0, 140, 250)], CAMERE)
v("[C2] aceeasi eticheta mai adanc -> respinge",
  G._eticheta_straina_in(0, L, R, T, B, h, W, H) is not None,
  "adancime 0.27 > prag")

# [D] eticheta care nu e a niciunei camere din lista
h = G._harta_etichete([lb("Terasa acoperita", 20.0, 250, 250)], CAMERE)
v("[D] eticheta fara camera in lista -> nu respinge",
  G._eticheta_straina_in(0, L, R, T, B, h, W, H) is None)

# [E] Vision adauga calificativ; desenul nu il are -> tot camera mea
h = G._harta_etichete([lb("Dormitor 1", 14.0, 250, 250)], CAMERE)
v("[E] «Dormitor 1» e a camerei «Dormitor 1 (parter)»",
  h and 0 in h[0][1], "indecsi=%s" % (h[0][1] if h else None))

# [F] fara etichete deloc
v("[F] fara etichete -> regula nu se aplica",
  G._eticheta_straina_in(0, L, R, T, B, G._harta_etichete([], CAMERE), W, H) is None)

# [G] pragul e o constanta, cu valoarea masurata
v("[G] pragul e constanta si sta sub cea mai mica adancime masurata (0,28)",
  isinstance(G.ADANCIME_STRAINA, float) and 0 < G.ADANCIME_STRAINA < 0.28,
  "ADANCIME_STRAINA=%s" % G.ADANCIME_STRAINA)

print()
if rele:
    print("PICAT: %d din 8" % len(rele))
    for r in rele:
        print("   - %s" % r)
    sys.exit(1)
print("Toate cele 8 capete: OK")
