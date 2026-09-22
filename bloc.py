# -*- coding: utf-8 -*-
"""REGULILE DE BLOC: consumatorii COMUNI (TCC), cei VITALI (TECV), camera de pompe (TEP),
cablul rezistent la foc si grupul electrogen.

Cele trei tablouri exista de la P1 ca noduri in registru si ca tipuri de element. Aici primesc
CONTINUT: ce circuite au, de unde se alimenteaza si cu ce cablu.

CE DECIDE CA UN PROIECT E BLOC: un contur de apartament desenat, oriunde in proiect.
Nu tipul de cladire din formular (un camp care nu constrange planul cu nimic) si nu prezenta unui
element `tablou_consumatori_comuni` (ar cere inginerului sa puna tabloul INAINTE sa existe circuite
pentru el). Conturul e criteriul fiindca el e cel care da inteles cuvantului „comun": fara
apartamente, „ce nu-i intr-un apartament" inseamna TOATA casa. E acelasi comutator pe care-l
foloseste deja P2 pentru cheia de grupare, deci nu apare o a doua definitie a lui „bloc".

CONSECINTA DIRECTA, si ea e intentionata: pe o casa functia intoarce False si niciuna din regulile
de aici nu se aprinde. Desfumarea ramane pe TEG, cu mentiunea din memoriu ca la cladirile care cer
circuit de siguranta se trateaza separat. La bloc CHIAR se trateaza separat — de-aia mentiunea se
schimba acolo, si numai acolo.

TRIGGERUL E PE PROIECT, APARTENENTA E PE NIVEL. Subsolul blocului lui Dan n-are niciun apartament
(e parcare), dar iluminatul lui sta pe TCC — circuitele C1..C3 „ILUMINAT SUBSOL". Daca triggerul ar
fi fost per nivel, subsolul n-ar fi fost „bloc" si iluminatul lui ar fi ramas pe TEG.
"""

import apartments as _apm            # contururile de grupare (sursa unica a tipurilor)

# ── NUMELE TABLOURILOR (cele din registrul P1) ────────────────────────────────────────────────
TCC = "TCC"           # consumatori comuni: iluminat de circulatie, lift, prize de serviciu
TECV = "TECV"         # consumatori vitali: desfumare, detectie, pompe — alimentati si din grup
TEP = "TEP"           # tabloul camerei de POMPE (nu de parcare — confirmat de Dan la R&D)

# ── CABLUL REZISTENT LA FOC ───────────────────────────────────────────────────────────────────
# E90 = 90 de minute de functionare in foc. NU E ACELASI LUCRU CU E30 al buclelor de detectie
# (`draw_elements._CS_CABLE["e30"]`, JEH(St)H 2x2x0,8): acela e cablu de SEMNAL, ecranat, doua
# perechi de 0,8 mm, si tine 30 de minute; asta e cablu de FORTA, 230/400 V, si tine 90. Doua
# produse diferite, doua randuri diferite in deviz. Numele de familie le tine separate prin
# constructie — nicaieri nu exista un „cablu rezistent la foc" generic sub care sa se amestece.
FAMILIE_E90 = "NHXH E90"

# Unde se aplica, citit de pe planşele lui Dan:
#   IE.30 (TECV) — TOATE circuitele, si coloana lui: „NHXH E90 5x 16 mmp", „... 3x 4", „... 5x 4";
#   IE.30 C6     — coloana catre TEP: „NHXH E90 5x 10 mmp";
#   IE.29 C9/C10 — iluminatul de evacuare si marcarea hidrantilor: „NHXH E90 4x 1.5 mmp".
# Pastram conventia NOASTRA de numar de conductoare (3x mono / 5x trifazat): sectiunea si numarul
# de fire vin din aceeasi functie ca la orice alt circuit, si doar FAMILIA se schimba. Dan scrie
# 4x1,5 la evacuare fiindca la el corpul are si linie permanenta si linie comandata — o diferenta
# de SCHEMA a corpului, nu de cablu, si n-o inventez aici.




# ── ELEMENTELE VITALE ─────────────────────────────────────────────────────────────────────────
# Exact tipurile care primesc deja circuit dedicat la detectie/desfumare (`_DET_CIRCUIT`), minus
# cele care nu se alimenteaza. Nu inventez tipuri noi: toate cinci exista de la pachetul de detectie
# incendiu, cu migratia lor facuta atunci.
VITALE = ("centrala_detectie", "ventilator_desfumare", "clapeta_antifoc", "trapa_desfumare",
          "grila_admisie")

# MOTORUL de desfumare: singurul vital care poate fi trifazat si care are exceptia de curba.
MOTOARE_DESFUMARE = ("ventilator_desfumare",)

EL_TEP = "tablou_tep"
EL_TCC = "tablou_consumatori_comuni"
EL_TECV = "tablou_tecv"
EL_BMPT = "tablou_bmpt"
EL_TGD = "tablou_tgd"

# Camera de pompe, dupa nume — plasa pentru proiectele unde inginerul n-a pus inca elementul
# `tablou_tep`. Aceeasi forma ca `_TECH_ROOM_KW` pentru camera tehnica.
POMPE_KW = ("camera pompe", "camera pompelor", "statie pompe", "statie de pompare", "pompe incendiu")


def _tip(el):
    return str((el or {}).get("element_type") or "")


def este_bloc(plan_elements):
    """Proiectul e BLOC? = exista cel putin un contur de APARTAMENT desenat, pe orice nivel.

    Conturul de SPATIU COMERCIAL nu conteaza aici, si nu din scapare: un imobil numai cu spatii
    comerciale nu e bloc de locuinte — n-are casa scarii cu iluminat comun, n-are consumatori comuni,
    deci n-are TCC. Spatiile lui isi primesc oricum tabloul (TE-SP) din contur, fiindca ruta aia
    trece prin apartenenta la contur, nu prin `este_bloc`. Un bloc cu parterul intreg comercial ramane
    bloc: apartamentele de deasupra il declara."""
    return any(_tip(el) == _apm.CONTUR for el in (plan_elements or []))


def este_vital(el):
    """Elementul e consumator vital (desfumare / detectie)?"""
    return _tip(el) in VITALE




def camera_pompe(plan_elements):
    """Numele camerei de pompe, sau None.

    Aceeasi sursa unica ca la camera tehnica: room-ul PERSISTAT al elementului `tablou_tep`, cu
    plasa pe nume pentru planurile unde tabloul n-a fost inca plasat. Ordinea conteaza — elementul
    e o decizie a inginerului, numele e o ghicire."""
    for el in (plan_elements or []):
        if _tip(el) == EL_TEP:
            r = str((el or {}).get("room") or "").strip()
            if r:
                return r
    for el in (plan_elements or []):
        r = str((el or {}).get("room") or "").strip()
        if r and any(k in r.lower() for k in POMPE_KW):
            return r
    return None




def tablou_sursa(plan_elements, fallback):
    """Tabloul din care se alimenteaza TCC si TECV.

    Topologia e citita de pe planşele lui Dan, nu presupusa: IE.29 scrie pe coloana lui TCC
    „...la BMPT", iar IE.30 scrie pe a lui TECV „De la AAR / BMPT". Deci amandoua atarna de BMPT,
    ca frati ai lui TEGD, nu sub el.

    Ordinea: BMPT desenat -> TEGD/TGD desenat -> `fallback` (tabloul parterului). Ultimul e plasa de
    la P2: mai bine tabloul care exista sigur decat un parinte inventat ca sa arate graful intreg."""
    for et in (EL_BMPT, EL_TGD):
        for el in (plan_elements or []):
            if _tip(el) == et:
                lbl = str((el or {}).get("label") or "").strip()
                if lbl:
                    return lbl
                return "BMPT" if et == EL_BMPT else "TEGD"
    return fallback


# ── GRUPUL ELECTROGEN + AAR ───────────────────────────────────────────────────────────────────
# Treptele comerciale uzuale de grupuri diesel 400 V / 50 Hz. Nu-s rotunjiri alese de mine: sunt
# marimile pe care le gasesti in oferta (45 kVA / 36 kW e o marime de catalog, 41,6 nu e).
TREPTE_KVA = (10, 15, 20, 22, 25, 30, 33, 40, 45, 50, 60, 66, 80, 100, 110, 125,
              150, 175, 200, 250, 275, 300, 350, 400, 500)

# FACTORUL, si de ce e 2,0.
# Dan are pe acelasi proiect DOUA valori pentru acelasi grup: 45 kVA pe IE.19 si 80 kVA pe IE.20.
# Intrebat (20 sept 2026), a confirmat ca 45 e cea corecta — se potriveste si cu intreruptorul de
# 50 A de pe IE.20 (50 A x 636,4 = 31,8 kW, adica ~40 kVA, deci 80 n-ar avea ce proteja acolo).
# Factorul acopera DOUA lucruri deodata: trecerea din kW absorbiti in kVA aparenti, si curentul de
# pornire directa al motoarelor de desfumare, care sunt mai toata sarcina tabloului. Pe cifrele lui:
# 20,80 kW x 2,0 = 41,6 -> prima treapta peste = 45 kVA. Exact valoarea lui.
FACTOR_GRUP = 2.0


def grup_electrogen_kva(pa_w):
    """Puterea aparenta a grupului, in kVA, din puterea ABSORBITA a consumatorilor vitali.

    Zero sau negativ -> 0: fara consumatori vitali nu exista grup, si o treapta minima intoarsa
    aici ar face sa apara un grup electrogen pe un proiect care n-are ce salva."""
    try:
        pa_kw = float(pa_w or 0) / 1000.0
    except (TypeError, ValueError):
        return 0
    if pa_kw <= 0:
        return 0
    cerut = pa_kw * FACTOR_GRUP
    for t in TREPTE_KVA:
        if t >= cerut - 1e-9:
            return t
    return TREPTE_KVA[-1]


AAR_NUME = "AAR - anclansarea automata a rezervei"
GRUP_NUME = "Grup electrogen %d kVA, pornire automata"


# ── SPATIUL COMERCIAL „LA ROSU" ───────────────────────────────────────────────────────────────
# DECIZIA LUI DAN: spatiile comerciale din bloc se predau la rosu. Proiectul blocului le da tabloul,
# coloana si un set minim de circuite; cine cumpara spatiul isi face proiectul lui, pe functiunea
# lui. De-aia NU se aplica aici regulile comerciale pe sub-tip (`comercial_subtip`) — acelea descriu
# un cabinet sau un salon ANUME, iar la predare nu se stie care va fi.
#
# Decizia DIFERA de propriul lui desen, ca si la AFDD-ul de la P3: SP1 (IE.27) are 15 circuite, cu
# AC, centrala termica pe gaz, senzor de gaz, DTC, ventilator axial si centrala antiefractie — adica
# un spatiu FINISAT. Noi emitem mai putin, intentionat.
#
# CELE SASE sunt MASURATE pe IE.27, nu alese: C5..C10 sunt sase circuite de priza de 2 kW (cinci
# „PRIZE" plus alimentarea de aer conditionat). DDCS-ul e acelasi element ca la locuinte
# (`receptor_internet`), doar ca la comercial se eticheteaza RACK.
SP_PRIZE_CIRCUITE = 6
SP_PRIZA_W = 2000            # Pi normativ per circuit de priza, ca peste tot (Regula 1)
SP_DDCS_W = 150              # baza DDCS/RACK, fara echipamente de curenti slabi desenate

# CAND se emite setul: DOAR daca spatiul e GOL. Daca inginerul a desenat ceva inauntru, circuitele
# lui castiga si genericul nu mai apare — aceeasi consecventa stricta ca la prizele camerei tehnice
# (decizia Dan, 18 iul 2026): un plan LUCRAT nu primeste plase peste ce-a facut omul.



# ── PRIZA DE PAMANT: SECTIUNEA BENZII ─────────────────────────────────────────────────────────
# 40x4 PESTE TOT, inclusiv la blocuri.
#
# Dan foloseste 40x6 pe IE.36 (masurat, de doua ori in text) si o vreme am diferentiat: 40x6 la
# bloc, 40x4 in rest. Am scos diferentierea dupa documentarea lui, 21 sept 2026: 40x4 e standardul
# si la blocuri, iar in fundatie 40x6 nu aduce castig tehnic — grosimea conteaza pentru coroziune,
# iar banda e protejata in beton. Minimul normativ pentru otel zincat ingropat e 30x3,5; 40x4 are
# 160 mm2, cu marja.
#
# FUNCTIA RAMANE, desi intoarce o constanta, fiindca valoarea ei nu era niciodata alegerea, ci
# UNICITATEA: banda e numita in PATRU documente — lista de materiale, legenda planşei, caietul de
# sarcini si detaliul IE.36. Scrisa de mana in fiecare, primul care se schimba face devizul sa ceara
# un material si planşa sa deseneze altul. E acelasi fel de divergenta ca planşa-vs-borderou, doar
# ca intre documente.
#
# N-ARE PARAMETRU, si asta e intentionat. Varianta de dinainte primea `plan_elements` (sau
# `circuits`); pastrat dupa ce raspunsul a devenit acelasi in toate cazurile, argumentul ar fi
# sugerat ca sectiunea variaza pe proiect si ar fi pus pe cineva sa caute de ce nu variaza. Cand
# chiar va trebui sa depinda de ceva, parametrul se adauga atunci, cu motivul lui.
BANDA_PRIZA = "40x4"


def sectiune_banda():
    """Sectiunea benzii prizei de pamant, ca text („40x4"). Sursa unica — vezi nota de mai sus."""
    return BANDA_PRIZA
