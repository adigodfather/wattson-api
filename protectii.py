# -*- coding: utf-8 -*-
"""CURBA si CAPACITATEA DE RUPERE a disjunctoarelor — sursa unica.

Pana aici emiteam curba C, fara capacitate de rupere: „MCB 1P+N 16A C". Pe planşele lui Dan scrie
„1P+N, 16A, B, 6kA". Schimbarea atinge TOATE proiectele, nu doar blocurile — de-aia sta intr-un
singur loc, nu replicata in schema, BOM, memoriu si caiet.

REGULA DE CURBA, CITITA DE PE PLANSE (rand de protectii aliniat pe COLOANE, nu pe rand — alinierea
pe rand amesteca valorile cand textul se rupe in doua):

    monofazat (1P+N) -> B    38 din 38 circuite, pe AP-1, TCC si TECV
    trifazat  (3P+N) -> C    4 din 5

Singura exceptie masurata e TECV C2, ventilatorul de desfumare (3P+N 25A B 6kA). Un motor pe curba B
e neobisnuit — curba B sare la 3..5x In, iar pornirea unui motor trece de-acolo. La P3 am lasat-o
NEIMPLEMENTATA, ca pe o alegere a lui pe care n-o generalizez fara sa intreb. Dan a confirmat pe
20 sept 2026 ca a fost intentionata, deci de la P6 e in cod — vezi `B_DESFUMARE`, cu motivul.

EXCEPTIE PASTRATA DIN COD: driverele de banda LED raman pe C. Motivul era deja scris langa ele —
„inrush-ul surselor LED ar arunca curba B" — si e acelasi motiv pentru care un motor n-ar sta pe B.
Regula noua nu are voie sa stearga o decizie luata pe un motiv fizic.

CAPACITATEA DE RUPERE (kA) urmeaza POZITIA IN IERARHIE: cu cat esti mai aproape de sursa, cu atat
curentul de scurtcircuit prezumat e mai mare, deci aparatul trebuie sa rupa mai mult.

    circuit terminal de iluminat        -> 4,5 kA
    circuit terminal, restul            -> 6 kA
    intrerupatorul general al unui tablou / coloana catre un tablou   -> 10 kA
    ...al unui tablou alimentat DIRECT din BMPT sau TGD               -> 15 kA

Reproduce: AP-1 C1 iluminat 4,5 · AP-1 prize 6 · AP-1 C0 10 · TCC C0 si TECV C0 15 · TECV C6
(coloana catre tabloul camerei de pompe) 10. Nu reproduce TCC C13 (LIFT, 3P+N 25A C 6kA), unde
Dan a pus 6 desi e coloana catre un tablou — singura nepotrivire din cele citite.
"""

CURBA_MONO = "B"
CURBA_TRI = "C"

KA_ILUMINAT = 4.5
KA_TERMINAL = 6.0
KA_TABLOU = 10.0
KA_TABLOU_GENERAL = 15.0

# Tipuri de circuit care raman pe C indiferent de faze, fiindca sarcina are varf de pornire.
# `banda_led` = driverele: motivul („inrush-ul surselor LED ar arunca curba B") era deja in cod.
INRUSH_C = ("banda_led",)

# EXCEPTIA INVERSA, si singura: ventilatorul de desfumare TRIFAZAT ramane pe B, desi regula generala
# trimite orice trifazat pe C. TECV C2 de pe IE.30 (3P+N, 25A, B, 6kA) nu-i o scapare de tipar — Dan
# a confirmat (20 sept 2026) ca a fost INTENTIONAT. Curba B sare la 3..5x In, iar pornirea unui motor
# trece de-acolo; a ales-o oricum, fiindca pe un circuit de siguranta la incendiu declansarea rapida
# la defect conteaza mai mult decat pornirea comoda.
# E acelasi FEL de motiv ca la driverele de banda LED, doar in sens opus: amandoua sunt decizii
# FIZICE, luate pe comportamentul sarcinii, si o regula noua n-are voie sa le stearga. De-aia stau
# una langa alta, cu motivul scris.
B_DESFUMARE = ("ventilator_desfumare",)


def curba(tri=False, inrush=False, forta_b=False):
    """Litera curbei. `inrush` = sarcina cu varf la pornire (drivere LED) -> C.
    `forta_b` = exceptia de mai sus (motor de desfumare) -> B chiar trifazat; bate si `tri`, si
    `inrush`, fiindca e o decizie explicita, nu un implicit."""
    if forta_b:
        return CURBA_MONO
    return CURBA_TRI if (tri or inrush) else CURBA_MONO


def icn_ka(tip=None, este_tablou=False, din_general=False):
    """Capacitatea de rupere, in kA.

    `este_tablou`  = intrerupatorul general al unui tablou, sau coloana care-l alimenteaza;
    `din_general`  = acel tablou atarna direct de BMPT / TGD (cel mai aproape de sursa)."""
    if este_tablou:
        return KA_TABLOU_GENERAL if din_general else KA_TABLOU
    return KA_ILUMINAT if str(tip or "") == "iluminat" else KA_TERMINAL


def _ka_txt(ka):
    """„4.5 kA" / „6kA" — formatul lui Dan: spatiu la zecimale, lipit la intregi."""
    return ("%.1f kA" % ka) if abs(ka - round(ka)) > 1e-9 else ("%dkA" % int(round(ka)))


def breaker_type(tri=False, inrush=False, rccb_ma=None, forta_b=False):
    """Campul `breaker_type` al circuitului: „MCB-1P-B" / „MCB-3P-C" (+ RCCB, ca pana acum).

    FORMA RAMANE „MCB-<poli>-<curba>": `bom.py` cauta „3P" in el ca sa numere polii, iar
    `caiet_sarcini_generator` il tipareste ca atare. Se schimba DOAR litera — un camp nou ar fi
    insemnat sa modific fiecare cititor ca sa vada ceva ce deja era acolo."""
    bt = "MCB-%s-%s" % ("3P" if tri else "1P", curba(tri, inrush, forta_b))
    return bt + (" + RCCB %dmA" % rccb_ma if rccb_ma else "")


def eticheta(amp, tri=False, inrush=False, tip=None, este_tablou=False, din_general=False,
             rccb_ma=None, prefix="MCB", forta_b=False):
    """Eticheta COMPLETA, in formatul de pe planşele lui Dan:
    „MCB 1P+N 16A B 6kA" (+ „ 30mA" cand are diferential).

    `format_protection_short` din schema_generator o rupe deja corect in doua randuri — exemplul
    din docstring-ul ei era chiar „MCB 3P+N 40A C 10kA", deci formatul era prevazut, doar ca nu
    ajungea niciodata la circuitele obisnuite."""
    poli = "3P+N" if tri else "1P+N"
    out = "%s %s %dA %s %s" % (prefix, poli, int(amp or 0), curba(tri, inrush, forta_b),
                               _ka_txt(icn_ka(tip, este_tablou, din_general)))
    if rccb_ma:
        out += " %dmA" % rccb_ma
    return out.strip()


# ── NORMALIZAREA unei etichete VENITE din afara (n8n) ─────────────────────────────────────────
# Eticheta de pe schema nu se construieste in backend: n8n o asambleaza din `breaker_type` si
# `breaker_a` si o trimite ca sir in `protectie` (verificat: campul NU exista pe niciunul dintre
# cele 546 de circuite salvate in baza — deci nu se persista, se face pe loc).
# De-aia schema NORMALIZEAZA ce primeste, in loc sa astepte ca n8n sa se schimbe: aceeasi cale prin
# care „; AFDD" a ajuns pe tabel. Cand n8n va trimite deja formatul nou, functia il lasa neatins.
_CURBE = ("B", "C", "D")


def normalizeaza(protectie, tri=None, inrush=False, tip=None, este_tablou=False,
                 din_general=False, forta_b=False):
    """Rescrie curba si adauga kA pe o eticheta deja formata („MCB 1P+N 16A C" -> „... B 6kA").

    Idempotenta: daca eticheta are deja kA, nu se atinge. Fara amperaj recognoscibil, se intoarce
    neschimbata — o eticheta pe care n-o inteleg n-are voie sa fie stricata."""
    s = str(protectie or "").strip()
    if not s or "kA" in s:
        return s
    parts = s.split()
    i_amp = next((i for i, p in enumerate(parts)
                  if p.rstrip(",").endswith("A") and any(ch.isdigit() for ch in p)), -1)
    if i_amp < 0:
        return s
    if tri is None:
        tri = "3P" in s
    cap = parts[:i_amp + 1]
    coada = [p for p in parts[i_amp + 1:] if p.strip(",") not in _CURBE]
    return " ".join(cap + [curba(tri, inrush, forta_b),
                           _ka_txt(icn_ka(tip, este_tablou, din_general))] + coada)
