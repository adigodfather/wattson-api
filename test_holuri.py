# -*- coding: utf-8 -*-
"""Holul ca spatiu ramas: brate, praguri de acceptare, si ce NU se aplica.

Holul si accesul n-au pereti proprii si n-au usi — sunt golul dintre celelalte camere, deci
cautarea de contur n-are ce inchide si camera cade pe dreptunghiul Vision. Aici se verifica
mecanica inlocuitoare, sintetic si determinist: un hol drept da un brat, unul in L doua, bugetul
taie ce iese din aria declarata, iar pragurile refuza ce nu e hol.

Scara e data explicit (0,01 m/pt => 1 m = 100 pt), ca lungimile din test sa se citeasca direct.

Rulare:  python test_holuri.py
"""
import sys

SCARA = 0.01          # m/pt -> 1 m = 100 pt
rele = []


def v(nume, cond, det=""):
    print("  %-70s %s %s" % (nume[:70], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def plan(pereti_h, pereti_v, W=1200, H=1000, cunoscute=(), scara=SCARA):
    import holuri
    return holuri.harta_plan(list(pereti_h), list(pereti_v), list(cunoscute), W, H, scara)


def main():
    import holuri

    # ── clasificarea ────────────────────────────────────────────────────────────────────────
    for n in ("Hol", "Hol acces", "Vestibul", "Sas", "Palier", "Windfang", "Casa scarii"):
        v("«%s» e circulatie" % n, holuri.e_circulatie(n))
    for n in ("Dormitor 2", "Bucatarie", "Terasa acces", "Balcon acces", "Garaj"):
        v("«%s» NU e circulatie" % n, not holuri.e_circulatie(n))

    # ── un hol DREPT: coridor de 1 m x 5 m, inchis de jur imprejur ─────────────────────────
    # camera de 2..7 m pe x, 3..4 m pe y (in pt: 200..700, 300..400)
    h = [(150, 750, 300), (150, 750, 400)]          # pereti lungi sus/jos
    vv = [(250, 450, 200), (250, 450, 700)]          # capete stanga/dreapta
    hm = plan(h, vv)
    br = holuri.brate_camerei(hm, (450, 350), 5.0, SCARA)
    bune = [b for b in br if b.get("rect")]
    v("hol drept -> UN brat", len(bune) == 1, "%d brate" % len(bune))
    if bune:
        b = bune[0]
        v("bratul e orizontal", b["o"] == "H", b["o"])
        v("latimea ~1 m", 0.8 <= b["lat_m"] <= 1.2, "%.2f m" % b["lat_m"])
        v("lungimea ~5 m", 4.0 <= b["lung_m"] <= 5.2, "%.2f m" % b["lung_m"])
        v("cei doi pereti laterali sunt marginile bratului pe directia subtire",
          abs(b["pereti"][1] - b["pereti"][0] - (b["lat_m"] / SCARA)) < 6.0, str(b["pereti"]))

    # ── un hol in L: brat orizontal (x 200..700, y 300..400) + brat vertical care coboara din
    #    capatul drept (x 600..700, y 400..900). Peretii sunt doar laturile REALE ale L-ului.
    hL = [(150, 750, 300),      # sus, peste tot bratul orizontal
          (150, 620, 400),      # jos la bratul orizontal, pana unde incepe cel vertical
          (550, 750, 900)]      # jos, capatul bratului vertical
    vL = [(250, 450, 200),      # capatul din stanga al bratului orizontal
          (250, 950, 700),      # latura din dreapta, comuna ambelor brate
          (380, 950, 600)]      # latura din stanga a bratului vertical
    hm = plan(hL, vL)
    br = holuri.brate_camerei(hm, (450, 350), 12.0, SCARA)
    bune = [b for b in br if b.get("rect")]
    v("hol in L -> DOUA brate", len(bune) == 2, "%d brate: %s" % (len(bune), [b["o"] for b in bune]))
    v("un brat orizontal si unul vertical", {b["o"] for b in bune} == {"H", "V"},
      str([b["o"] for b in bune]))

    # ── bugetul: aceeasi geometrie, dar aria declarata mica -> bratul se taie ──────────────
    hm = plan(h, vv)
    br_mic = [b for b in holuri.brate_camerei(hm, (450, 350), 2.0, SCARA) if b.get("rect")]
    v("aria declarata mica -> bratul se taie sub ea",
      br_mic and br_mic[0]["arie_m2"] <= 2.0 + 1e-6, str([round(b["arie_m2"], 2) for b in br_mic]))
    v("dupa taiere bratul tot contine eticheta",
      br_mic and br_mic[0]["rect"][0] <= 450 <= br_mic[0]["rect"][2],
      str(br_mic[0]["rect"]) if br_mic else "-")

    # ── ce NU se aplica ───────────────────────────────────────────────────────────────────
    hm = plan(h, vv)
    fara = holuri.brate_camerei(hm, (450, 350), 0, SCARA)
    v("fara arie declarata -> niciun brat (nu inventam buget)",
      not [b for b in fara if b.get("rect")] and fara[0]["respinse"].get("fara_buget"))
    # camera LATA: 4 m x 5 m -> peste pragul de 3 m
    hlat = [(150, 750, 100), (150, 750, 500)]
    vlat = [(50, 550, 200), (50, 550, 700)]
    hm = plan(hlat, vlat)
    lat = holuri.brate_camerei(hm, (450, 300), 20.0, SCARA)
    v("camera mai lata de 3 m -> niciun brat (nu mai e hol)",
      not [b for b in lat if b.get("rect")], str([b.get("lat_m") for b in lat]))
    # ancora in afara oricarui gol
    hm = plan(h, vv)
    afara = holuri.brate_camerei(hm, (50, 50), 5.0, SCARA)
    v("ancora in afara cladirii -> niciun brat",
      not [b for b in afara if b.get("rect")] and afara[0]["respinse"].get("fara_gol"))

    print("\n".join("ESUAT: " + r for r in rele) if rele
          else "OK — bratele ies din forma golului, iar pragurile tin")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.exit(main())
