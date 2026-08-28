"""Oglinda Python a lui apps/zynapse-configurator/lib/comercial.ts - camerele spatiilor comerciale.

GENERAT din TS. NU-l edita de mana: schimba TS-ul si regenereaza, altfel frontendul si backendul dau
raspunsuri diferite pe acelasi nume de camera (exact capcana _BATH_RX / BATH_RX). Regexurile primesc
numele NORMALIZAT (lowercase, fara diacritice) - vezi _norm_name_ro din draw_elements.py.
"""
import re

# cheie -> (eticheta, regex de recunoastere pe numele normalizat)
CAMERE = {
    "grup_sanitar":   ("Grup sanitar",               re.compile(r"\bg\s*\.?\s*s\.?\b|sanitar|\bwc\b|\bbaie\b|toaleta")),
    "depozit":        ("Depozit",                    re.compile(r"\bdep\.?\b|depoz|depozit|magazie|\bcamara\b")),
    "birou":          ("Birou",                      re.compile(r"\bbir\.?\b|\bbirou")),
    "vestiar":        ("Vestiar",                    re.compile(r"\bvest\.?\b|\bvst\.?\b|vestiar|garderob")),
    "chicineta":      ("Chicinetă",                  re.compile(r"\bchic\.?\b|chicinet|\boficiu\b")),
    "receptie":       ("Recepție",                   re.compile(r"\brec\.?\b|receptie|recept|\bprimire\b")),
    "camera_tehnica": ("Cameră tehnică",             re.compile(r"\bcam\.?\s*tehnic|\bc\s*\.\s*t\s*\.?(?!\w)|sp\.?\s*tehnic|\btehnic")),
    "hol":            ("Hol / circulație",           re.compile(r"\bh\.?\b|\bhol\b|culoar|coridor")),
    "vanzare":        ("Spațiu vânzare",             re.compile(r"vanzare|\bmagazin")),
    "casa_marcat":    ("Casă de marcat",             re.compile(r"casa\s*(de\s+)?marcat|\bc\.?\s*m\.?\b|zona\s*case")),
    "cam_frigorifica": ("Cameră frigorifică",         re.compile(r"frigorific|camera\s*frig")),
    "receptie_marfa": ("Recepție marfă",             re.compile(r"rec\.?\s*marfa|receptie\s*marfa|primire\s*marfa")),
    "oficina":        ("Oficină",                    re.compile(r"oficina|\bfarmacie\b")),
    "receptura":      ("Receptură",                  re.compile(r"receptura|prep\.?\s*medicament")),
    "expunere":       ("Spațiu expunere",            re.compile(r"expunere|showroom")),
    "servire":        ("Sală servire",               re.compile(r"servire|sala\s*mese|sala\s*restaurant|sala\s*consum|\bcafenea\b")),
    "bucatarie":      ("Bucătărie",                  re.compile(r"\bbuc\.?\b|bucatar")),
    "bar":            ("Bar",                        re.compile(r"\bbar\b|tejghea|zona\s*bar")),
    "spalator_vase":  ("Spălător vase",              re.compile(r"spalator|sp\.?\s*vase|spalare\s*vase")),
    "zona_preparare": ("Zonă preparare",             re.compile(r"zona\s*prep|preparare")),
    "terasa":         ("Terasă",                     re.compile(r"\bteras|\bter\.?\b")),
    "sala_lucru":     ("Sală lucru",                 re.compile(r"\blucru\b|coafura|\bsalon\b|frizerie")),
    "zona_spalare":   ("Zonă spălare",               re.compile(r"zona\s*spalare|\bscafe\b|sp\.?\s*spalare|\bspalare\b")),
    "sterilizare":    ("Sterilizare",                re.compile(r"steril")),
    "manichiura":     ("Sală manichiură",            re.compile(r"manichiura|salon\s*unghii")),
    "cabina_trat":    ("Cabină tratament",           re.compile(r"cab\.?\s*tratament|\bcabina\b")),
    "primire":        ("Spațiu primire",             re.compile(r"sp\.?\s*primire|\bprimire\b")),
    "sala_masini":    ("Sală mașini",                re.compile(r"\bmasini\b")),
    "zona_calcat":    ("Zonă călcat",                re.compile(r"calcat|calcatorie")),
    "cabinet":        ("Cabinet",                    re.compile(r"\bcab\.?\b|\bcbt\.?\b|cabinet|consultatii|\bunit\b")),
    "radiologie":     ("Radiologie",                 re.compile(r"radiolog|\brx\b|\bcbct\b")),
    "asteptare":      ("Sală așteptare",             re.compile(r"asteptare")),
    "sala_tratament": ("Sală tratament",             re.compile(r"tratament|proceduri")),
    "recoltare":      ("Sală recoltare",             re.compile(r"recoltar")),
    "laborator":      ("Laborator",                  re.compile(r"\blab\.?\b|laborator|\blabor\.?\b")),
    "dep_reactivi":   ("Depozit reactivi",           re.compile(r"reactivi")),
    "chirurgie":      ("Sală chirurgie",             re.compile(r"chirurgie|\boperatii\b")),
    "cazare_animale": ("Cazare animale",             re.compile(r"\bcazare\b|\bpadoc\b|\bcusti\b|stationar")),
    "sala_aparate":   ("Sală aparate",               re.compile(r"\baparate\b|\bfitness\b|s\.?\s*sport\b")),
    "sala_clase":     ("Sală clase",                 re.compile(r"\bclase\b|sala\s*grup\b|aerobic|\bstudio\b")),
    "vestiar_b":      ("Vestiar bărbați",            re.compile(r"vest\.?\s*barbati|\bv\.?\s*barbati|vestiar\s*b\b")),
    "vestiar_f":      ("Vestiar femei",              re.compile(r"vest\.?\s*femei|\bv\.?\s*femei|vestiar\s*f\b")),
    "dusuri":         ("Dușuri",                     re.compile(r"\bdusuri\b|\bdus\b|zona\s*dusuri")),
    "sala_principala": ("Sală principală",            re.compile(r"principala|evenimente|sala\s*mare")),
    "zona_joaca":     ("Zonă joacă",                 re.compile(r"joaca")),
    "sala_birouri":   ("Sală birouri",               re.compile(r"birouri|open\s*-?\s*space")),
    "sala_sedinte":   ("Sală ședințe",               re.compile(r"sedinte")),
    "camera_server":  ("Cameră server",              re.compile(r"\bserver\b|camera\s*it\b|\brack\b")),
    "arhiva":         ("Arhivă",                     re.compile(r"\barhiva\b|\barh\.?\b")),
    "atelier":        ("Atelier",                    re.compile(r"\bat\.?\b|\batel\.?\b|atelier")),
    "sala_grupa":     ("Sală grupă",                 re.compile(r"\bgrupa\b|\bclasa\b")),
    "sala_mese":      ("Sală mese",                  re.compile(r"\bmese\b")),
    "dormitor_copii": ("Dormitor",                   re.compile(r"\bdorm\.?\b|dormitor|\bsomn\b")),
}

# sub-tip -> (camere in ordine, generic pentru "Sala", generic pentru "Spatiu")
SUBTIPURI = {
    "a1_magazin_general": (['vanzare', 'casa_marcat', 'grup_sanitar', 'depozit', 'vestiar', 'chicineta', 'birou', 'receptie', 'camera_tehnica', 'hol'], 'vanzare', 'vanzare'),
    "a2_alimentar": (['vanzare', 'casa_marcat', 'cam_frigorifica', 'receptie_marfa', 'depozit', 'vestiar', 'grup_sanitar'], 'vanzare', 'vanzare'),
    "a3_farmacie": (['oficina', 'receptura', 'depozit', 'birou', 'vestiar', 'grup_sanitar'], 'oficina', 'oficina'),
    "a4_showroom": (['expunere', 'depozit', 'birou', 'grup_sanitar'], 'expunere', 'expunere'),
    "b1_restaurant": (['servire', 'bucatarie', 'bar', 'spalator_vase', 'depozit', 'cam_frigorifica', 'vestiar', 'grup_sanitar', 'terasa'], 'servire', 'servire'),
    "b2_cafenea": (['servire', 'bar', 'zona_preparare', 'depozit', 'vestiar', 'grup_sanitar'], 'servire', 'servire'),
    "c1_frizerie": (['sala_lucru', 'zona_spalare', 'receptie', 'sterilizare', 'depozit', 'vestiar', 'grup_sanitar'], 'sala_lucru', 'sala_lucru'),
    "c2_unghii": (['manichiura', 'cabina_trat', 'receptie', 'sterilizare', 'depozit', 'grup_sanitar'], 'manichiura', 'manichiura'),
    "c3_spalatorie": (['primire', 'sala_masini', 'zona_calcat', 'depozit', 'grup_sanitar'], 'sala_masini', 'primire'),
    "d1_stomatologic": (['cabinet', 'sterilizare', 'radiologie', 'receptie', 'asteptare', 'camera_tehnica', 'vestiar', 'grup_sanitar'], 'asteptare', 'asteptare'),
    "d2_medical": (['cabinet', 'sala_tratament', 'receptie', 'asteptare', 'sterilizare', 'vestiar', 'grup_sanitar'], 'asteptare', 'asteptare'),
    "d3_laborator": (['recoltare', 'laborator', 'receptie', 'asteptare', 'dep_reactivi', 'grup_sanitar'], 'asteptare', 'asteptare'),
    "d4_veterinar": (['cabinet', 'chirurgie', 'receptie', 'asteptare', 'sterilizare', 'cazare_animale', 'grup_sanitar'], 'asteptare', 'asteptare'),
    "e1_fitness": (['sala_aparate', 'sala_clase', 'receptie', 'vestiar_b', 'vestiar_f', 'dusuri', 'depozit', 'grup_sanitar'], 'sala_aparate', 'sala_aparate'),
    "e2_evenimente": (['sala_principala', 'zona_joaca', 'chicineta', 'depozit', 'vestiar', 'grup_sanitar'], 'sala_principala', 'sala_principala'),
    "f1_birou": (['sala_birouri', 'birou', 'sala_sedinte', 'receptie', 'camera_server', 'chicineta', 'arhiva', 'grup_sanitar'], 'sala_birouri', 'sala_birouri'),
    "f2_atelier": (['atelier', 'receptie', 'depozit', 'grup_sanitar'], 'atelier', 'atelier'),
    "f3_gradinita": (['sala_grupa', 'sala_mese', 'dormitor_copii', 'chicineta', 'vestiar', 'grup_sanitar', 'birou', 'depozit'], 'sala_grupa', 'sala_grupa'),
}

# REGULI PE DESTINATIE, pe cheia camerei canonice (vezi comentariul din comercial.ts):
#   cheie -> (lx documentar, element_type, W, pas_mp | None,
#             prize fixe, pas_prize_mp | None, tip_priza | None, umed "10ma"/"30ma" | None)
# Cheile COMUNE (depozit/birou/receptie/vanzare/...) lipsesc INTENTIONAT: au deja reguli si raman
# neatinse. Cheie absenta -> se cade pe eticheta canonica si pe regulile vechi.
REGULI = {
    "cam_frigorifica": (150, 'aplica_tavan', 25, None, 2, None, None, None),
    "receptie_marfa":  (200, 'aplica_tavan', 25, 12.0, 2, None, None, None),
    "oficina":         (500, 'panou_led', 40, 8.0, 4, 12.0, None, None),
    "receptura":       (500, 'panou_led', 40, 8.0, 4, None, None, None),
    "expunere":        (300, 'panou_led', 40, 10.0, 4, 12.0, None, None),
    "servire":         (200, 'panou_led', 40, 12.0, 4, 15.0, None, None),
    "bucatarie":       (500, 'panou_led', 40, 8.0, 6, 8.0, None, None),
    "bar":             (300, 'panou_led', 40, 10.0, 6, 8.0, None, None),
    "spalator_vase":   (300, 'aplica_tavan', 25, None, 4, None, None, '30ma'),
    "zona_preparare":  (500, 'panou_led', 40, 8.0, 6, 8.0, None, None),
    "terasa":          (100, 'aplica_senzor', 30, 15.0, 2, None, None, None),
    "sala_lucru":      (500, 'panou_led', 40, 8.0, 4, 6.0, None, None),
    "zona_spalare":    (300, 'aplica_tavan', 25, None, 2, None, None, '30ma'),
    "manichiura":      (500, 'panou_led', 40, 8.0, 4, 6.0, None, None),
    "cabina_trat":     (300, 'aplica_tavan', 25, None, 2, None, None, None),
    "sala_masini":     (300, 'panou_led', 40, 12.0, 6, 10.0, None, '30ma'),
    "zona_calcat":     (300, 'panou_led', 40, 12.0, 6, 10.0, None, None),
    "primire":         (200, 'aplica_tavan', 25, 12.0, 2, None, None, None),
    "cabinet":         (500, 'panou_led', 40, 8.0, 6, None, None, None),
    "sala_tratament":  (500, 'panou_led', 40, 8.0, 4, 12.0, None, None),
    "sterilizare":     (300, 'panou_led', 40, None, 4, None, None, None),
    "radiologie":      (300, 'aplica_tavan', 25, 8.0, 2, None, None, None),
    "laborator":       (500, 'panou_led', 40, 8.0, 4, None, None, None),
    "recoltare":       (500, 'panou_led', 40, 8.0, 4, None, None, None),
    "dep_reactivi":    (150, 'aplica_tavan', 25, None, 2, None, None, None),
    "chirurgie":       (500, 'panou_led', 40, 8.0, 6, None, None, None),
    "cazare_animale":  (150, 'aplica_tavan', 25, 12.0, 2, None, None, None),
    "asteptare":       (200, 'aplica_tavan', 25, 12.0, 2, None, None, None),
    "sala_aparate":    (300, 'panou_led', 40, 10.0, 4, 15.0, None, None),
    "sala_clase":      (300, 'panou_led', 40, 10.0, 4, 12.0, None, None),
    "dusuri":          (200, 'aplica_tavan', 25, 8.0, 2, None, 'ip44', '10ma'),
    "sala_principala": (300, 'panou_led', 40, 10.0, 4, 15.0, None, None),
    "zona_joaca":      (300, 'panou_led', 40, 10.0, 4, 15.0, None, None),
    "sala_sedinte":    (500, 'panou_led', 40, 8.0, 6, 12.0, None, None),
    "camera_server":   (300, 'aplica_tavan', 25, 8.0, 6, 12.0, None, None),
    "arhiva":          (200, 'aplica_tavan', 25, 12.0, 2, None, None, None),
    "atelier":         (500, 'panou_led', 40, 8.0, 6, 10.0, None, None),
    "sala_grupa":      (300, 'panou_led', 40, 10.0, 4, 15.0, None, None),
    "sala_mese":       (300, 'panou_led', 40, 10.0, 4, 15.0, None, None),
    "dormitor_copii":  (100, 'aplica_tavan', 25, 12.0, 4, 15.0, None, None),
}

SUBTIP_DEFAULT = "a1_magazin_general"

# Numele PUR generice - doar ele se rezolva prin sub-tip. Cer cuvantul singur (eventual cu numar),
# nu ca prefix: "Sala sedinte" NU e generic, e sala de sedinte.
_RX_GENERIC_SALA = re.compile(r"^(sala|sal\.?|s\.)\s*\d*$")
_RX_GENERIC_SPATIU = re.compile(r"^(spatiu|spat\.?|sp\.)\s*\d*$")


def camera_canonica(nume_normalizat, subtip):
    """Cheia camerei canonice pentru un nume de pe plansa, in contextul unui sub-tip comercial.
    Numele trebuie sa vina DEJA normalizat (_norm_name_ro). Ordinea: camerele SPECIFICE ale
    sub-tipului, apoi numele pur generic -> camera principala. None = necunoscut."""
    n = (nume_normalizat or "").strip()
    if not n:
        return None
    st = SUBTIPURI.get(subtip) or SUBTIPURI.get(SUBTIP_DEFAULT)
    if not st:
        return None
    camere, g_sala, g_spatiu = st
    for key in camere:
        d = CAMERE.get(key)
        if d and d[1].search(n):
            return key
    if g_sala and _RX_GENERIC_SALA.match(n):
        return g_sala
    if g_spatiu and _RX_GENERIC_SPATIU.match(n):
        return g_spatiu
    return None


def eticheta_canonica(nume_normalizat, subtip):
    """Eticheta camerei canonice (ex. "Sala aparate") sau None. Regulile de iluminat/prize se aplica
    pe EA, nu pe numele generic de pe plan."""
    k = camera_canonica(nume_normalizat, subtip)
    return CAMERE[k][0] if k else None
