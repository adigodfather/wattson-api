# -*- coding: utf-8 -*-
"""
VIDEOINTERFONUL LA BLOC (P7b) — sursa UNICA a familiei.

Sistemul e pe DOUA FIRE (magistrala nepolarizata): panoul de apel de la intrare, cititorul de
control acces si yala usii de acces, apoi coloana care urca prin bloc pana la postul interior din
fiecare apartament. Totul e plasat MANUAL de inginer, pe planşa de curenti slabi — nimic nu se
pune singur si nimic nu se calculeaza din presupuneri (varianta A, aprobata de Dan).

CE STA AICI si de ce intr-un singur loc:
  - TIPURILE familiei. `draw_elements` le adauga la curentii slabi (desen, legenda, lista de
    cantitati, inventarul care ajunge in memoriu), iar schema de curenti slabi le EXCLUDE — au
    schema lor. Amandoua citesc tuplul de aici, deci nu pot ajunge sa creada lucruri diferite.
  - CONDITIA planşei „Schema de distributie retea de interfon": `are_interfon`. O citesc
    numerotarea (/plansa-numbering) si generatorul schemei, iar n8n si borderoul citesc raspunsul
    numerotarii. Nicio bifa si niciun `has_interfon` trimis de cineva: planşa exista fiindca exista
    elementele, exact ca schema de curenti slabi.
  - ACCESORIILE NUMARATE, nedesenate: un buton de iesire per yala, un buton de sonerie per post.
    Regula sta AICI; lista de cantitati, memoriul si caietul o cer de la `accesorii`.
  - SURSA sistemului nu e un tip nou: e un `alimentare_receptor` („Sursa interfon") plasat in
    spatiul comun, deci ajunge pe TCC ca orice consumator comun, cu protectia din regulile de azi.
  - AVERTISMENTELE: esecurile TACUTE ale unui sistem plasat de mana (un apartament fara post, posturi
    fara panou de apel, sistem fara sursa). Le vede inginerul la „Obtine plan", inainte de documente.
"""

import apartments as _ap
import floors as _fl

PANOU = "panou_apel_interfon"
CITITOR = "cititor_control_acces"
YALA = "yala_electromagnetica"
POST = "post_interior_interfon"
# ordinea = ordinea de citit (de la usa blocului spre apartament), folosita de legenda si de BOM
TIPURI = (PANOU, CITITOR, YALA, POST)

# Receptorul care alimenteaza sistemul. ETICHETA e ce scrie butonul din editor pe element (fara
# diacritice, ca restul etichetelor de receptor: `receptor_type_of` nu le normalizeaza); TIPUL e ce
# intoarce `enrich_circuits.receptor_type_of` pentru orice eticheta care contine „interfon".
SURSA_ETICHETA = "Sursa interfon"
SURSA_TIP = "sursa_interfon"

# Felul de cablu al coloanei (traseu_cs.label), ca `fo24` la coloana de date.
CABLU = "interfon"

# PROTECTIA SURSEI (decizia lui Dan, 26 sept): MCB 10 A, cablu CYY-F 3x1,5 — in formatul catalogului
# de receptoare mici din enrich (amperaj minim, cablu, sectiune). Curba (B) vine din regula generala a
# receptoarelor dedicate. TINTITA pe sursa, recunoscuta prin `este_sursa`: regulile generale (minim
# 16 A, sectiunea scalata cu siguranta) raman neatinse pentru orice alt receptor.
PROTECTIE_SURSA = (10, "CYY-F 3x1.5", 1.5)


def _tip(el):
    return str((el or {}).get("element_type") or "")


def are_interfon(plan_elements):
    """Proiectul are sistem de interfon? = exista cel putin un element al familiei, pe orice nivel.

    CONDITIA PLANSEI, intr-un singur loc. Sursa singura nu aprinde planşa: fara panou si fara
    posturi n-ar avea ce sa arate."""
    return any(_tip(el) in TIPURI for el in (plan_elements or []))


def este_sursa(el):
    """Elementul e sursa sistemului de interfon? Receptor recunoscut dupa ETICHETA, prin aceeasi
    functie care ii da puterea si circuitul (`receptor_type_of`) — nu printr-o a doua regula."""
    if _tip(el) != "alimentare_receptor":
        return False
    try:
        from enrich_circuits import receptor_type_of
    except Exception:
        return False
    return receptor_type_of((el or {}).get("label")) == SURSA_TIP


def numara(plan_elements):
    """{tip: numar} pentru cele patru tipuri + sursa. Doar ce e CHIAR pe plan."""
    out = {}
    for el in (plan_elements or []):
        t = _tip(el)
        if t in TIPURI:
            out[t] = out.get(t, 0) + 1
        elif este_sursa(el):
            out[SURSA_TIP] = out.get(SURSA_TIP, 0) + 1
    return out


def accesorii(comp):
    """Accesoriile NUMARATE, nedesenate (decizia lui Dan): un buton de iesire per yala — deblocheaza
    usa din interior — si un buton de sonerie la usa fiecarui apartament, adica unul per post.
    `comp` = {tip: numar} (inventarul de pe plan sau cel purtat pe circuite)."""
    def _n(k):
        try:
            return max(0, int((comp or {}).get(k) or 0))
        except (TypeError, ValueError):
            return 0
    return {"buton_iesire": _n(YALA), "buton_sonerie": _n(POST)}


def _enumera(etichete, max_n=12):
    """„P1_2, P2_1 și P3_4" — cu plafon, ca un bloc intreg fara posturi sa nu umple ecranul."""
    lst = list(etichete)
    if len(lst) > max_n:
        rest = len(lst) - max_n
        return "%s și încă %d" % (", ".join(lst[:max_n]), rest)
    return lst[0] if len(lst) == 1 else ", ".join(lst[:-1]) + " și " + lst[-1]


def apartamente_fara_post(plan_elements):
    """Etichetele apartamentelor CONTURATE care n-au niciun post interior in contur.

    Apartenenta trece prin ACEEASI functie ca circuitele (`apartament_al_elementului`), pe nivelul
    elementului: un post pus pe alt nivel, sau cazut in afara liniei, nu acopera apartamentul.
    Doar apartamentele — spatiile comerciale nu primesc post de interfon."""
    els = list(plan_elements or [])
    lipsa = []
    niveluri = sorted({_fl.floor_canonic(e.get("floor")) for e in els}, key=_fl.floor_index)
    for fk in niveluri:
        conturi = _ap.conturi_nivel(els, fk, _fl.floor_canonic, tipuri=(_ap.CONTUR,))
        if not conturi:
            continue
        acoperite = {_ap.apartament_al_elementului(e, conturi) for e in els
                     if _tip(e) == POST and _fl.floor_canonic(e.get("floor")) == fk}
        lipsa += [c["eticheta"] for c in conturi if c["eticheta"] not in acoperite]
    return lipsa


def avertismente(plan_elements):
    """Esecurile TACUTE ale unui sistem plasat de mana. AVERTIZEAZA, nu blocheaza.

    Doar cand proiectul CHIAR are interfon: un bloc fara niciun element de interfon n-are sistemul
    in proiect (o alegere, nu o scapare), deci nu primeste niciun avertisment — si ramane identic cu
    ce era. Ce prinde, cand sistemul exista:
      - apartamente conturate fara post interior (copierea P4 se face O SINGURA DATA per apartament:
        un post pus dupa copiere nu mai urca singur la etajele deja copiate);
      - posturi fara niciun panou de apel;
      - sistem fara sursa (fara ea nu exista circuit pe TCC, iar schema n-ar avea de unde alimenta
        yala si cititorul)."""
    els = list(plan_elements or [])
    if not are_interfon(els):
        return []
    out = []
    lipsa = apartamente_fara_post(els)
    if lipsa:
        out.append(("Apartamentul %s nu are post de interfon" if len(lipsa) == 1
                    else "Apartamentele %s nu au post de interfon") % _enumera(lipsa))
    tipuri = {_tip(e) for e in els}
    if POST in tipuri and PANOU not in tipuri:
        out.append("Există posturi de interfon, dar niciun panou de apel")
    if not any(este_sursa(e) for e in els):
        out.append("Sistemul de interfon nu are sursă de alimentare: plasează „Sursă interfon” "
                   "în spațiul comun, pe planul de forță")
    return out
