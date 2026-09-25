"""Editorul nu mai darama pagina: bariera de eroare + garda pe element.

DE CE EXISTA. Dan a deschis un proiect si a primit „Application error: a client-side exception has
occurred" — pagina alba a lui Next. Aplicatia NU avea nicio bariera de eroare, deci orice exceptie
la randare, oriunde, ducea acolo. Datele erau intacte tot timpul in baza; doar nu mai avea cum sa
ajunga la ele, si ecranul nu-i spunea asta.

Cauza exceptiei n-a fost gasita (proiectul a fost sters intre timp, iar in cele ramase nu exista
nicio stare care sa arunce — vezi raportul). Dar forma simptomului e reparabila independent de
cauza, si asta pazeste proba: o exceptie la desen opreste DESENUL, nu aplicatia.

Rulare:  python test_bariera_editor.py
"""
import io
import os
import re
import sys

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
EDITOR = os.path.join(APP, "components", "plan-editor.tsx")
rele = []


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def main():
    ed = io.open(EDITOR, encoding="utf-8").read()

    # ── [1] Bariera din jurul panzei ───────────────────────────────────────────────────────
    v("[1] exista o bariera de eroare in editor", "class PanzaBariera" in ed)
    v("[1] prinde exceptiile la randare (getDerivedStateFromError)",
      "static getDerivedStateFromError" in ed)
    v("[1] si le si LOGHEAZA (altfel cauza s-ar pierde)", "componentDidCatch" in ed)
    # invelirea: <PanzaBariera> ... <Stage> ... </Stage> ... </PanzaBariera>
    m = re.search(r'<PanzaBariera>(.*?)</PanzaBariera>', ed, re.S)
    v("[1] panza (Stage) e INAUNTRUL barierei",
      bool(m) and "<Stage" in m.group(1) and "</Stage>" in m.group(1))
    # mesajul sta in CORPUL clasei, nu in invelitoarea din JSX (prima varianta a probei cauta in
    # locul gresit si a picat degeaba)
    corp = ed[ed.index("class PanzaBariera"):ed.index("// Zonă de hit invizibilă")]
    v("[1] mesajul spune ca datele n-au fost pierdute",
      "neatinse" in corp and "pierdut" in corp)

    # ── [2] Garda PE ELEMENT ───────────────────────────────────────────────────────────────
    v("[2] un element fara coordonate bune nu se deseneaza, dar nici nu opreste restul",
      "if (!Number.isFinite(el.x) || !Number.isFinite(el.y)) return null;" in ed)
    i = ed.find("Number.isFinite(el.x)")
    j = ed.find("{ordered.map((el) => {")
    v("[2] garda e INAINTE de folosirea coordonatelor", 0 < j < i and i < ed.find("const px = el.x * scale", j))

    # ── [3] Bariera de RUTA, pentru ce cade in afara panzei ────────────────────────────────
    ruta = os.path.join(APP, "app", "error.tsx")
    v("[3] exista bariera de ruta (app/error.tsx)", os.path.exists(ruta))
    if os.path.exists(ruta):
        t = io.open(ruta, encoding="utf-8").read()
        v("[3] e componenta de client", t.lstrip().startswith('"use client"'))
        v("[3] primeste `reset` si il ofera utilizatorului", "reset" in t and "onClick={reset}" in t)
        v("[3] spune ca nu s-a pierdut nimic", "neatinse" in t and "pierdut" in t)
        v("[3] logheaza eroarea (altfel n-o mai vede nimeni)", "console.error" in t)

    # ── [4] Regula e CONSECVENTA cu cea de la legaturi ─────────────────────────────────────
    # „ce nu intelegem nu se deseneaza" trebuie sa fie aceeasi peste tot, nu o exceptie locala.
    v("[4] legaturile respecta aceeasi regula (capat lipsa -> linia dispare)",
      "if (!ea || !eb) continue;" in ed)

    # ── [5] Ipoteza rotatiei de colt: respinsa, si scris DE CE ─────────────────────────────
    # gradeAplica e aritmetica pura — nu poate arunca pentru nicio intrare.
    m2 = re.search(r'const gradeAplica = [^;]+;', ed, re.S)
    v("[5] gradeAplica nu are nicio cale care sa arunce",
      bool(m2) and "throw" not in m2.group(0) and "JSON" not in m2.group(0), m2.group(0)[:60] if m2 else "?")

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — o exceptie la desen opreste desenul, nu aplicatia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
