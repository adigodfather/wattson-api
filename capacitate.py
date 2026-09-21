# -*- coding: utf-8 -*-
"""Protectia instantei: o singura operatie grea odata, si nimic peste puterea ei.

DE CE. `page.get_drawings()` materializeaza TOATE primitivele de desen ca obiecte Python: masurat,
~1,85 KB de RAM pentru fiecare. Instanta are 512 MB, deci pragul fizic e pe la 230 000 de primitive.
Un plan de bloc de rola are intre 138 000 si 925 000 — la 925 000 varful masurat a fost 1772 MB, de
3,5 ori limita, iar instanta a murit cu „Ran out of memory" si a raspuns 502/503 TUTUROR celorlalti
utilizatori pana s-a repornit (21 sept, 23:35).

Nu e doar problema blocurilor: `santandrei`, o casa reala din baza, cere 240 MB. Doua incarcari
simultane de case de felul asta se aduna si trec de limita. De aici cele doua paze:

  1. SEMAFORUL — o singura cerere grea la un moment dat. Nu face nicio cerere mai ieftina; doar
     opreste varfurile sa se adune. La asteptare prea lunga raspunde 503 cu `Retry-After`, ca sa
     cada cererea, nu serviciul.
  2. POARTA — numara primitivele INAINTE de a le materializa, direct din content stream, si refuza
     planul daca e peste ce incape. Utilizatorul primeste un mesaj care spune ce s-a intamplat.

Nicio paza nu schimba vreun rezultat: un plan care trecea, trece la fel, byte-identic.
Reparatia de fond (citirea segmentelor fara get_drawings) e alta etapa.
"""
import re
import threading

# ─────────────────────────────── 1. SEMAFORUL ───────────────────────────────
# UNA, nu doua. Masurat: `santandrei` (o casa reala, nu un caz extrem) cere 240 MB. Doua deodata
# fac 480 MB, plus memoria de repaus a procesului — peste 512 MB. Chiar si la pragul portii de mai
# jos, o singura cerere poate ajunge la ~370 MB, deci a doua n-are unde incapea.
CONCURENTA = 1

# Cat asteapta o cerere la coada inainte sa renunte. Bugetele clientilor: Vercel da 60 s pentru
# /validate-plan, /extract-geometry si /render-base-png, 120 s pentru /regenerate-plan; nodul n8n
# de adnotare taie la 30 s. Cu 20 s de asteptare raman cel putin 10 s de executie chiar pe cel mai
# strans, si 40 s pe cele de 60 — iar un 503 rapid e mai bun decat un client care expira in gol.
ASTEPTARE_MAX_S = 20.0

_semafor = threading.BoundedSemaphore(CONCURENTA)


class Ocupat(Exception):
    """Coada n-a avansat in `ASTEPTARE_MAX_S`. Apelantul raspunde 503 cu Retry-After."""


class poarta_grea(object):
    """Context manager: `with capacitate.poarta_grea():` in jurul partii care mananca memorie.

    Se pune cat mai STRANS posibil in jurul operatiei grele, nu pe toata cererea: decodarea
    base64 si validarea intrarii n-au de ce sa stea la coada.
    """

    def __enter__(self):
        if not _semafor.acquire(timeout=ASTEPTARE_MAX_S):
            raise Ocupat()
        return self

    def __exit__(self, *a):
        _semafor.release()
        return False


def mesaj_ocupat():
    """Corpul raspunsului 503 — acelasi peste tot, ca utilizatorul sa vada mereu aceeasi explicatie."""
    return {"error": "Serverul proceseaza alt plan chiar acum. Incearca din nou peste cateva "
                     "secunde — nu s-a consumat nimic.",
            "retry_after_s": 5}


# ──────────────────────────────── 2. POARTA ────────────────────────────────
# Cate primitive incap. Bugetul: 512 MB, minus memoria de repaus a procesului (masurata: 72 MB
# dupa amanarea importurilor, de la 83) si o rezerva de ~100 MB pentru uvicorn, raspuns si sistem
# -> ~340 MB pentru desen, adica ~185 000 de primitive la 1,85 KB bucata.
#
# Pragul se exprima insa in unitatile TOKENIZERULUI de mai jos, fiindca el e singurul care se poate
# calcula ieftin. Masurat pe 16 planuri (blocul lui Dan + fiecare plan din baza), raportul
# get_drawings/tokenizer sta intre 0,24 si 0,50 — deci `get_drawings <= 0,5 x tokenizer`, si un
# prag de 400 000 de tokeni tine materializarea sub ~200 000 de primitive.
#
# Ce accepta si ce refuza, verificat:
#   cea mai mare casa din baza (`santandrei`)  178 972  ->  trece, cu marja de 2,2x
#   a doua ca marime                            50 141  ->  trece
#   bloc/subsol, etaj 1, etaj 2         332 000..358 000 ->  trec
#   bloc/parter, etaj 3               1 734 000..2 170 000 -> REFUZATE (ele au omorat instanta)
PRAG_PRIMITIVE = 400_000

# Operatorii care CONSTRUIESC traseu: m/l (punct, linie), c/v/y (Bezier), re (dreptunghi).
# Pentru NUMARAT nu e nevoie de matricea de transformare — conteaza cate sunt, nu unde cad.
#
# DOUA tipare, nu unul. Cel exact cere operanzii intregi inaintea operatorului; e riguros, dar
# backtracking-ul il face lent — 5,3 s pe un plan de bloc si 3,8 s pe cea mai mare casa din baza,
# adaugate la FIECARE cerere. Cel ieftin cere doar o cifra inaintea operatorului: pe toate cele 14
# planuri reale masurate a dat exact aceleasi numere, in 0,01-0,44 s, adica de 12 ori mai repede.
# Fiind mai permisiv, ar putea in principiu sa numere in plus (o secventa dintr-un sir de text), si
# atunci ar respinge un plan bun — asa ca numaratoarea lui se ia de buna doar cand e departe de
# prag; aproape de prag, unde chiar decide, se reface cu tiparul exact.
_NUM = rb"-?\d+(?:\.\d+)?"
_RX_EXACT = re.compile(rb"(?:%s\s+){2}(?:m|l)\b|(?:%s\s+){6}c\b|(?:%s\s+){4}(?:re|v|y)\b"
                       % (_NUM, _NUM, _NUM))
_RX_IEFTIN = re.compile(rb"[\d.]\s+(?:m|l|c|v|y|re)[\s\r\n]")
# Banda in care raspunsul ieftin chiar decide soarta planului si merita renumarat exact. Sub ea
# planul trece oricum; peste ea e atat de departe de prag incat nicio supraevaluare plauzibila
# n-ar schimba verdictul — si acolo refuzul trebuie sa fie RAPID, nu sa mai coste inca 5 secunde.
_RECONTROL_JOS, _RECONTROL_SUS = 0.80, 1.50
_RX_DO = rb"/%s\s+Do\b"


def _numara_cu(doc, pno, rx):
    """Numaratoarea propriu-zisa, cu tiparul dat.

    XOBJECT-URILE CONTEAZA. Prima varianta citea doar `page.read_contents()` si iesea de 14 ori pe
    langa pe planurile cu Form XObject: parterul blocului are 25 si raporta 281 000 de „primitive"
    in loc de 925 000, adica exact planul care omoara instanta parea cel mai cuminte. Aici fiecare
    XObject se numara inmultit cu de cate ori e instantiat (`/Nume Do`).
    """
    pg = doc[pno]
    date = pg.read_contents()
    n = len(rx.findall(date))
    try:
        xobiecte = doc.get_page_xobjects(pno)
    except Exception:
        xobiecte = []
    for t in xobiecte:
        try:
            flux = doc.xref_stream(t[0])
        except Exception:
            continue
        if not flux:
            continue
        # `or 1`: daca numele nu se gaseste in stream (instantiat dintr-un alt XObject), se
        # numara macar o data — mai bine supraestimat decat invizibil.
        ori = len(re.findall(_RX_DO % re.escape(str(t[1]).encode()), date)) or 1
        n += len(rx.findall(flux)) * ori
    return n


def numara_primitive(doc, pno=0):
    """Cate primitive de desen are pagina, citite din content stream — FARA sa le materializeze.

    Tiparul ieftin intai; daca raspunsul cade aproape de prag, se reface cu cel exact, ca o
    supraevaluare a lui sa nu refuze un plan bun. Costul obisnuit: 0,01-0,44 s.
    """
    n = _numara_cu(doc, pno, _RX_IEFTIN)
    if PRAG_PRIMITIVE * _RECONTROL_JOS < n <= PRAG_PRIMITIVE * _RECONTROL_SUS:
        n = _numara_cu(doc, pno, _RX_EXACT)
    return n


class PreaComplex(Exception):
    """Planul depaseste ce poate procesa instanta. Apelantul raspunde 413 cu mesajul de mai jos."""

    def __init__(self, n):
        self.n = n
        Exception.__init__(self, "plan prea complex: %d primitive" % n)


def verifica(doc, pno=0):
    """Arunca `PreaComplex` daca planul nu incape. Intoarce numarul, ca sa poata fi logat."""
    n = numara_primitive(doc, pno)
    if n > PRAG_PRIMITIVE:
        raise PreaComplex(n)
    return n


def mesaj_prea_complex(n):
    """Ce vede utilizatorul. Spune CE s-a intamplat si ce poate face, nu doar ca a esuat."""
    return {"error": "Planul e prea complex pentru procesare (%s elemente de desen, limita %s). "
                     "De obicei se intampla la planse de rola cu tot proiectul pe ele. Incearca un "
                     "export doar cu nivelul de care ai nevoie, fara straturile de instalatii, "
                     "mobilier sau detalii." % ("{:,}".format(n).replace(",", " "),
                                                "{:,}".format(PRAG_PRIMITIVE).replace(",", " ")),
            "primitive": n, "limita": PRAG_PRIMITIVE}
