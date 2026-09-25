"""Coltul scos la intrerupatoare/aplice + simbolurile marite DOAR in editor.

DE CE EXISTA. Doua decizii care arata bine si gresit la fel:

1. Ramura de COLT (bisectoarea) e buna pentru camere si PIR-uri — de acolo se vede toata incaperea.
   La intrerupatoare si aplice e gresita: nu montezi un intrerupator pe muchia a doi pereti, iar
   tocul usii sta fix acolo. Poarta e un parametru (`cuColt`), deci se poate pierde tacut la un
   refactor: apelul ar continua sa mearga, doar ca elementele s-ar lipi iar pe bisectoare. Proba
   RULEAZA functia, nu o citeste.

2. Marirea simbolurilor e INTENTIONAT doar pe ecran. Pericolul e sa se scurga pe plansa: fie prin
   modificarea cotelor din `switchSymbol`/`bulbSymbol` (care trebuie sa ramana identice cu
   backend-ul), fie printr-un numar strecurat in `draw_elements.py`. Proba verifica amandoua, plus
   ca marirea NU atinge corpurile de tavan.

Rulare:  python test_simboluri_editor.py
"""
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
EDITOR = os.path.join(APP, "components", "plan-editor.tsx")
rele = []


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def bloc(sursa, antet):
    """Decupeaza textul unei functii/declaratii, de la antet pana la linia care e doar `}`.

    Se decupeaza, nu se retasteaza: daca cineva schimba functia, proba ruleaza versiunea NOUA.
    """
    i = sursa.index(antet)
    linii = sursa[i:].splitlines()
    out = [linii[0]]
    for l in linii[1:]:
        out.append(l)
        if l == "}":
            break
    return "\n".join(out)


def ruleaza_snap():
    """Compileaza snapPerete (cu dependentele ei) si o cheama pe o camera dreptunghiulara."""
    ed = io.open(EDITOR, encoding="utf-8").read()
    bucati = [
        re.search(r"^type WallSeg = .*$", ed, re.M).group(0),
        re.search(r"^const CAM_CORNER_SNAP = .*$", ed, re.M).group(0),
        bloc(ed, "function projectOnSegment("),
        bloc(ed, "function snapToWall("),
        bloc(ed, "export function snapPerete("),
    ]
    lucru = tempfile.mkdtemp(prefix="snap_")
    try:
        src = os.path.join(lucru, "snap.ts")
        io.open(src, "w", encoding="utf-8").write("\n\n".join(bucati) + "\n")
        r = subprocess.run(["npx", "tsc", src, "--outDir", lucru, "--target", "es2020",
                            "--module", "es2020", "--moduleResolution", "node"],
                           capture_output=True, text=True, shell=(os.name == "nt"), cwd=APP)
        js = os.path.join(lucru, "snap.js")
        if not os.path.exists(js):
            return None, (r.stdout + r.stderr)[:400]
        shutil.move(js, os.path.join(lucru, "snap.mjs"))
        # camera dreptunghiulara 200 x 150, colt la (0,0)
        drv = os.path.join(lucru, "drv.mjs")
        io.open(drv, "w", encoding="utf-8").write("""
import { snapPerete } from "./snap.mjs";
const W = [{x1:0,y1:0,x2:200,y2:0}, {x1:200,y1:0,x2:200,y2:150},
           {x1:200,y1:150,x2:0,y2:150}, {x1:0,y1:150,x2:0,y2:0}];
const out = {
  cam_langa_colt:   snapPerete(10, 6, W, true),
  sw_langa_colt:    snapPerete(10, 6, W, false),
  sw_chiar_in_colt: snapPerete(2, 2, W, false),
  cam_chiar_in_colt:snapPerete(2, 2, W, true),
  sw_mijloc_perete: snapPerete(100, 7, W, false),
  sw_departe:       snapPerete(100, 75, W, false),
};
process.stdout.write(JSON.stringify(out));
""")
        r2 = subprocess.run(["node", drv], capture_output=True, text=True,
                            shell=(os.name == "nt"), cwd=lucru)
        if not r2.stdout.strip():
            return None, (r2.stdout + r2.stderr)[:400]
        return json.loads(r2.stdout), ""
    finally:
        shutil.rmtree(lucru, ignore_errors=True)


def main():
    ed = io.open(EDITOR, encoding="utf-8").read()
    dr = io.open(os.path.join(RADACINA, "draw_elements.py"), encoding="utf-8").read()

    # ── [1] COMPORTAMENTUL la colt, rulat ──────────────────────────────────────────────────
    rez, err = ruleaza_snap()
    if rez is None:
        v("[1] snapPerete s-a putut rula", False, err)
    else:
        pe_perete = lambda p: abs(p["x"]) < 0.01 or abs(p["y"]) < 0.01 \
                              or abs(p["x"] - 200) < 0.01 or abs(p["y"] - 150) < 0.01
        in_colt = lambda p: abs(p["x"]) < 0.01 and abs(p["y"]) < 0.01

        c = rez["cam_langa_colt"]
        v("[1] CAMERA langa colt: tot pe colt, pe bisectoare (NEATINS)",
          in_colt(c) and abs(c["rot"] - math.pi / 4) < 0.01, json.dumps(c))

        s = rez["sw_langa_colt"]
        v("[1] INTRERUPATOR langa colt: pe PERETE, nu pe colt",
          pe_perete(s) and not in_colt(s), json.dumps(s))
        v("[1] ...si anume pe peretele CEL MAI APROPIAT (sus, la 6 pt, nu stanga la 10)",
          abs(s["y"]) < 0.01 and abs(s["x"] - 10) < 0.01, json.dumps(s))
        v("[1] ...cu fata perpendiculara SPRE INTERIOR (in jos de la peretele de sus)",
          s["rot"] is not None and abs(s["rot"] - math.pi / 2) < 0.01, json.dumps(s))

        sc = rez["sw_chiar_in_colt"]
        v("[1] INTRERUPATOR tras CHIAR in colt: tot se lipeste, nu ramane nelipit",
          sc["rot"] is not None and pe_perete(sc), json.dumps(sc))
        v("[1] cele doua ramuri chiar DIVERG (camera != intrerupator pe acelasi punct)",
          rez["cam_chiar_in_colt"] != sc)

        v("[1] la mijloc de perete nu s-a schimbat nimic",
          abs(rez["sw_mijloc_perete"]["y"]) < 0.01 and rez["sw_mijloc_perete"]["rot"] is not None)
        v("[1] in mijlocul camerei, departe de orice perete, ramane nelipit",
          rez["sw_departe"]["rot"] is None, json.dumps(rez["sw_departe"]))

    # ── [2] Cine primeste coltul: DOAR camerele si PIR-urile ───────────────────────────────
    m = re.search(r'const cuColt = ([^;]+);', ed)
    cond = m.group(1) if m else ""
    v("[2] coltul se cere doar pentru camera_video si detector_pir",
      '"camera_video"' in cond and '"detector_pir"' in cond
      and "aplica" not in cond and "intrerupator" not in cond, cond[:80])
    v("[2] apelul din tragere chiar transmite poarta", "snapPerete(xPdf, yPdf, walls, cuColt)" in ed)

    # ── [3] Marirea: DOAR in editor, doar pe cele doua familii ─────────────────────────────
    ma = re.search(r'const MARIRE_APLICA = ([\d.]+);', ed)
    ms = re.search(r'const MARIRE_SWITCH = ([\d.]+);', ed)
    v("[3] factorii sunt declarati explicit", bool(ma) and bool(ms),
      "%s / %s" % (ma.group(1) if ma else "?", ms.group(1) if ms else "?"))
    v("[3] amandoi > 1 (chiar maresc)", bool(ma) and bool(ms)
      and float(ma.group(1)) > 1 and float(ms.group(1)) > 1)
    v("[3] decizia e SCRISA in cod, ca divergenta asumata fata de plansa",
      "MARIRE DOAR IN EDITOR" in ed and "plansa generata ramane" in ed.replace("ă", "a").replace("â", "a"))

    # aplicarea: pe grupurile care rotesc deja, nu pe cotele simbolului
    v("[3] aplicele se scaleaza pe grupul lor",
      re.search(r'gradeAplica\(el\.rotation\)[^>]*scaleX=\{MARIRE_APLICA\}', ed, re.S) is not None)
    v("[3] intrerupatoarele se scaleaza pe grupul lor",
      "scaleX={MARIRE_SWITCH}" in ed and "switchSymbol(el.element_type)" in ed)
    v("[3] zona de apucat creste odata cu simbolul (altfel marginea n-ar mai fi clicabila)",
      ed.count("WALL_BULBS.has(type) ? MARIRE_APLICA : 1") == 2)

    # ── [4] Corpurile de TAVAN raman exact cum erau ────────────────────────────────────────
    for t in ("lustra_led", "aplica_tavan", "panou_led"):
        v("[4] %s nu primeste nicio marire" % t,
          not re.search(r'"%s"[^\n]*MARIRE' % t, ed))
    v("[4] ramura fara rotatie (tavanul) cheama bulbSymbol direct, nescalat",
      ") : bulbSymbol(el.element_type, el.kit_panica ? COL_SAFETY : COL_BULB_DEFAULT)}" in ed)

    # ── [5] PLANSA: marirea nu s-a scurs in backend ────────────────────────────────────────
    v("[5] draw_elements.py nu stie nimic despre vreo marire",
      "MARIRE" not in dr and "MARIRE_APLICA" not in dr)
    # cotele intrerupatorului din editor trebuie sa ramana ALE BACKEND-ULUI (marirea e din afara)
    cote_py = dict(re.findall(r'(R1|L1|R2|L2)\s*=\s*([\d.]+)\s*\*\s*s', dr))
    m3 = re.search(r'const R1 = ([\d.]+), L1 = ([\d.]+), R2 = ([\d.]+), L2 = ([\d.]+),', ed)
    v("[5] cotele din switchSymbol au ramas cele ale plansei (nu s-au inmultit)",
      bool(m3) and bool(cote_py)
      and float(m3.group(1)) == float(cote_py.get("R1", -1))
      and float(m3.group(4)) == float(cote_py.get("L2", -1)),
      "py=%s ts=%s" % (cote_py, m3.groups() if m3 else "?"))
    # raza aplicei din editor = raza din backend (9), nemarita la sursa
    v("[5] raza aplicei din bulbSymbol a ramas 9 (marirea nu e coapta in simbol)",
      len(re.findall(r'outerRadius=\{9\} angle=\{180\}', ed)) == 2)

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — coltul doar la camere/PIR, marirea doar pe ecran, plansa neatinsa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
