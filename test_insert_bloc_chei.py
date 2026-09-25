"""Inserarea in BLOC: toate randurile trebuie sa aiba EXACT aceleasi chei.

DE CE EXISTA. Generarea nu mai scria niciun element, iar proiectul se deschidea gol. Cauza:
`supabase-js`, la o inserare in bloc, trimite `?columns=` cu REUNIUNEA cheilor din toate randurile,
iar randurile carora le lipseste o cheie primesc **NULL**, nu valoarea implicita a coloanei.
Randurile de bec aveau `kit_panica`, cele de intrerupator nu. `kit_panica` e NOT NULL, deci un
singur rand fara ea respingea TOT blocul (23502), si nu se insera NIMIC.

Defectul a intrat pe 8 sept (dd0881b), cand `kit_panica` a fost pus doar pe becuri, si a fost
copiat pe 23 sept in calea de pe server (efada79) odata cu restul codului. Nu se vedea: inserarea
esua in tacere, cu un `console.error`, iar editorul arata pur si simplu gol.

Proba compara SETURILE DE CHEI din fiecare bloc de inserare, in ambele cai. Un camp adaugat pe un
singur fel de rand pica proba, inainte sa ajunga in productie.

Rulare:  python test_insert_bloc_chei.py
"""
import io
import os
import re
import sys

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
rele = []


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def chei_din_push(sursa, nume_lista):
    """Cheile de nivel 1 din fiecare `<lista>.push({...})`, prin potrivirea acoladelor."""
    out = []
    for m in re.finditer(re.escape(nume_lista) + r"\.push\(\{", sursa):
        i = m.end() - 1
        adanc, j = 0, i
        while j < len(sursa):
            if sursa[j] == "{":
                adanc += 1
            elif sursa[j] == "}":
                adanc -= 1
                if adanc == 0:
                    break
            j += 1
        corp = sursa[i + 1:j]
        # cheile de NIVEL 1: sarim peste ce e in acolade/paranteze imbricate
        chei, d = [], 0
        for linie in corp.splitlines():
            t = linie.strip()
            if not t or t.startswith("//"):
                continue
            if d == 0:
                for k in re.findall(r'(?:^|,)\s*([a-z_][a-z0-9_]*)\s*:', t):
                    chei.append(k)
            d += t.count("{") + t.count("(") - t.count("}") - t.count(")")
        out.append(set(chei))
    return out


def main():
    cazuri = [
        ("server  /api/generate", os.path.join(APP, "app", "api", "generate", "route.ts"), "randuri"),
        ("browser configurator", os.path.join(APP, "components", "configurator.tsx"), "planElements"),
    ]
    for eticheta, cale, lista in cazuri:
        s = io.open(cale, encoding="utf-8").read()
        seturi = chei_din_push(s, lista)
        v("[%s] s-au gasit blocurile de inserare" % eticheta, len(seturi) >= 2,
          "%d gasite" % len(seturi))
        if len(seturi) < 2:
            continue
        toate = set().union(*seturi)
        lipsa = {i: sorted(toate - st) for i, st in enumerate(seturi) if toate - st}
        v("[%s] TOATE randurile au aceleasi chei" % eticheta, not lipsa,
          "lipsesc: %s" % lipsa)
        v("[%s] kit_panica (NOT NULL) e pe fiecare rand" % eticheta,
          all("kit_panica" in st for st in seturi),
          "pe %d din %d" % (sum(1 for st in seturi if "kit_panica" in st), len(seturi)))

    # coloanele NOT NULL fara valoare trimisa sunt exact capcana; le tinem enumerate aici, ca
    # urmatorul care adauga una sa vada de ce conteaza
    v("[*] motivul e scris in cod, in ambele cai",
      all("REUNIUNEA cheilor" in io.open(c, encoding="utf-8").read() for _e, c, _l in cazuri))

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — niciun rand nu intra intr-un bloc cu alte chei decat vecinii lui")
    return 0


if __name__ == "__main__":
    sys.exit(main())
