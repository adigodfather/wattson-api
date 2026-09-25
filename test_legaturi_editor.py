"""Legatura bec<->intrerupator, asa cum o vede inginerul in editor (pachetul 3).

DE CE EXISTA. Editorul primea deja traseele, dar le arata pe TOATE: media era 52 de linii pe plansa
(maxim 85), din care 4 din 5 mergeau spre tablou si traversau tot desenul. Si erau un INSTANTANEU:
mutai un bec, linia ramanea in aer si arata o legatura FALSA — mai rau decat nicio linie.

Proba RULEAZA functiile (le decupeaza din .tsx prin text, le compileaza cu `tsc`, le cheama din
Node), ca sa nu verifice o copie retastata. Trei lucruri pazite:
  1. FILTRUL — daca cineva scoate un `kind` din lista, ghemul se intoarce fara sa pice nimic altceva.
  2. CAPETELE VII — linia trebuie sa se ia dupa pozitiile de ACUM, nu dupa cele din instantaneu.
  3. GRUPUL — la un LANT, al doilea segment leaga bec de bec. O grupare naiva („atinge selectia")
     ar gasi doar jumatate din grup si ar arata corect pe cazul cu doua becuri.

Rulare:  python test_legaturi_editor.py
"""
import io
import json
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
    """Decupeaza o functie, de la antet pana la linia care e doar `}`. Se decupeaza, nu se retasteaza."""
    i = sursa.index(antet)
    linii = sursa[i:].splitlines()
    out = [linii[0]]
    for l in linii[1:]:
        out.append(l)
        if l == "}":
            break
    return "\n".join(out)


def ruleaza():
    ed = io.open(EDITOR, encoding="utf-8").read()
    bucati = [
        re.search(r"^export type Legatura = .*$", ed, re.M).group(0),
        bloc(ed, "export function legaturiDinCabluri("),
        bloc(ed, "export function grupConex("),
    ]
    lucru = tempfile.mkdtemp(prefix="leg_")
    try:
        src = os.path.join(lucru, "leg.ts")
        io.open(src, "w", encoding="utf-8").write("\n\n".join(bucati) + "\n")
        r = subprocess.run(["npx", "tsc", src, "--outDir", lucru, "--target", "es2020",
                            "--module", "es2020", "--moduleResolution", "node"],
                           capture_output=True, text=True, shell=(os.name == "nt"), cwd=APP)
        js = os.path.join(lucru, "leg.js")
        if not os.path.exists(js):
            return None, (r.stdout + r.stderr)[:400]
        shutil.move(js, os.path.join(lucru, "leg.mjs"))
        drv = os.path.join(lucru, "drv.mjs")
        io.open(drv, "w", encoding="utf-8").write("""
import { legaturiDinCabluri, grupConex } from "./leg.mjs";
const E = (id, x, y) => ({ id, x, y });
const out = {};

// scena: intrerupator S + lant de trei becuri (B1-B2-B3), plus un cablu spre TABLOU.
// `path` e INSTANTANEUL de la ultima generare si e pus ANUME: daca cineva se intoarce sa deseneze
// din el in loc sa foloseasca pozitiile de acum, capatul ramane inghetat si proba trebuie sa pice.
// (Prima varianta n-avea `path` in fixturi, si sonda de control abia daca a aprins un cap.)
const lant = [
  { kind: "bec_lant",   from_id: "S",  to_id: "B1", path: [[0,0],[50,0],[50,0]] },
  { kind: "bec_lant",   from_id: "B1", to_id: "B2", path: [[50,0],[100,0],[100,0]] },
  { kind: "bec_lant",   from_id: "B2", to_id: "B3", path: [[100,0],[150,0],[150,0]] },
  { kind: "sw_tablou",  from_id: "S",  to_id: "T",  path: [[0,0],[0,400],[0,400]] },
  { kind: "priza_lant", from_id: "P1", to_id: "P2", path: [[10,10],[20,10],[20,20]] },
  { kind: "senzor_teg", from_id: "Z",  to_id: "T",  path: [[30,30],[0,30],[0,400]] },
];
const elLant = [E("S",0,0), E("B1",50,0), E("B2",100,0), E("B3",150,0), E("T",0,400),
                E("P1",10,10), E("P2",20,20), E("Z",30,30)];
out.lant = legaturiDinCabluri(lant, elLant);
out.lant_grup_S  = [...(grupConex("S",  out.lant) || [])].sort();
out.lant_grup_B3 = [...(grupConex("B3", out.lant) || [])].sort();

// capetele urmaresc elementele: acelasi instantaneu, becul MUTAT
const mutat = elLant.map(e => e.id === "B1" ? E("B1", 50, 300) : e);
out.dupa_mutare = legaturiDinCabluri(lant, mutat);

// un capat STERS -> linia dispare
out.dupa_stergere = legaturiDinCabluri(lant, elLant.filter(e => e.id !== "B2"));

// doua intrerupatoare, cate doua becuri fiecare -> DOUA grupuri distincte
const doua = [
  { kind: "bec_lant", from_id: "S1", to_id: "A1" },
  { kind: "bec_lant", from_id: "A1", to_id: "A2" },
  { kind: "bec_lant", from_id: "S2", to_id: "C1" },
  { kind: "bec_lant", from_id: "C1", to_id: "C2" },
];
const elDoua = [E("S1",0,0), E("A1",10,0), E("A2",20,0), E("S2",300,0), E("C1",290,0), E("C2",280,0)];
out.doua = legaturiDinCabluri(doua, elDoua);
out.grup_S1 = [...(grupConex("S1", out.doua) || [])].sort();
out.grup_S2 = [...(grupConex("S2", out.doua) || [])].sort();

// cap-scara: un bec, doua intrerupatoare
const cs = [{ kind: "cap_scara", from_id: "K1", to_id: "B" },
            { kind: "cap_scara", from_id: "K2", to_id: "B" }];
const elCs = [E("K1",0,0), E("K2",200,0), E("B",100,0)];
out.cap = legaturiDinCabluri(cs, elCs);
out.grup_K1 = [...(grupConex("K1", out.cap) || [])].sort();

// fara selectie, si selectie pe ceva nelegat
out.fara_selectie = grupConex(null, out.lant);
out.selectie_izolata = grupConex("T", out.lant);
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
    rez, err = ruleaza()
    if rez is None:
        v("[0] functiile s-au putut rula", False, err)
        print()
        print("ESUAT: " + "; ".join(rele))
        return 1

    # ── [A] FILTRUL: doar legaturile bec<->intrerupator ────────────────────────────────────
    v("[A] din 6 cabluri (lant, tablou, prize, senzor) raman DOAR cele 3 legaturi",
      len(rez["lant"]) == 3, "%d" % len(rez["lant"]))
    v("[A] cablul spre tablou NU e printre ele",
      all("T" not in (l["a"], l["b"]) for l in rez["lant"]))
    v("[A] lantul de prize si senzorul nici ele",
      all(l["a"] not in ("P1", "Z") and l["b"] not in ("P2", "T") for l in rez["lant"]))

    # ── [B]/[C] GRUPUL la selectie ─────────────────────────────────────────────────────────
    v("[B] selectand intrerupatorul, grupul e TOT lantul (nu doar primul bec)",
      rez["lant_grup_S"] == ["B1", "B2", "B3", "S"], str(rez["lant_grup_S"]))
    v("[B] selectand ULTIMUL bec, grupul e acelasi (conectivitate, nu doar vecinii)",
      rez["lant_grup_B3"] == ["B1", "B2", "B3", "S"], str(rez["lant_grup_B3"]))
    v("[C] doua intrerupatoare: doua grupuri DISTINCTE, fara amestec",
      rez["grup_S1"] == ["A1", "A2", "S1"] and rez["grup_S2"] == ["C1", "C2", "S2"],
      "%s / %s" % (rez["grup_S1"], rez["grup_S2"]))
    v("[C] cele doua grupuri nu au niciun element comun",
      not (set(rez["grup_S1"]) & set(rez["grup_S2"])))
    v("[B] fara selectie: niciun grup aprins (toate la fel de palide)",
      rez["fara_selectie"] is None)
    v("[B] selectie pe un element fara legaturi: tot nimic aprins",
      rez["selectie_izolata"] is None)

    # ── [D] CAP-SCARA ──────────────────────────────────────────────────────────────────────
    v("[D] cap-scara: becul are DOUA legaturi, cate una spre fiecare intrerupator",
      len(rez["cap"]) == 2 and {l["a"] for l in rez["cap"]} == {"K1", "K2"}, str(rez["cap"]))
    v("[D] selectand un intrerupator, se aprinde si celalalt (acelasi bec)",
      rez["grup_K1"] == ["B", "K1", "K2"], str(rez["grup_K1"]))

    # ── [E] CAPETELE URMARESC ELEMENTELE ───────────────────────────────────────────────────
    l0 = rez["lant"][0]["pts"]
    lm = rez["dupa_mutare"][0]["pts"]
    v("[E] dupa ce becul e mutat, capatul liniei se muta cu el (nu ramane in aer)",
      l0[-1] == [50, 0] and lm[-1] == [50, 300], "inainte %s, dupa %s" % (l0[-1], lm[-1]))
    v("[E] si forma in L se recalculeaza (mijlocul se schimba)", l0[1] != lm[1],
      "%s vs %s" % (l0[1], lm[1]))
    v("[E] un capat STERS -> liniile lui dispar, restul raman",
      len(rez["dupa_stergere"]) == 1, "%d ramase" % len(rez["dupa_stergere"]))

    # ── [F] Editorul NU recalculeaza asocierea si nu atinge cablarea ───────────────────────
    ed = io.open(EDITOR, encoding="utf-8").read()
    # „asociaza" apare in editor DOAR intr-un comentariu care trimite la functia din backend — asta
    # e documentatie, nu reimplementare. Ce conteaza cu adevarat: editorul nu SCRIE asocierea si nu
    # o DEDUCE din pozitii; liniile vin din `overlayCables`, adica din ce a calculat backendul.
    v("[F] editorul nu SCRIE niciodata comutat_de",
      not re.search(r'comutat_de\s*:', ed), "apare ca si camp scris")
    v("[F] legaturile vin din instantaneul backendului, nu din pozitii",
      "legaturiDinCabluri(overlayCables, elements)" in ed)
    v("[F] nu exista o a doua sursa de adevar in editor (nicio cautare de intrerupator apropiat)",
      not re.search(r'(snapPerete|nearest\w*)\s*\([^)]*intrerupator', ed, re.I))
    v("[F] liniile se desenau intr-un SINGUR loc", ed.count("<LegaturiLayer") == 1)
    v("[F] instantaneul brut nu se mai deseneaza direct",
      "overlayCables.map(" not in ed)

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — se arata doar legaturile, capetele urmaresc elementele, grupul e intreg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
