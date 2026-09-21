# -*- coding: utf-8 -*-
"""MODUL DE AVERTIZARE pentru campurile netrimise pe niciun model (PASUL 2 din trei).

DE CE EXISTA. Pydantic ARUNCA in tacere orice cheie pe care modelul n-o declara. Endpointul
raspunde 200, apelantul crede ca a trimis, iar campul nu ajunge nicaieri. S-a intamplat de TREI ori
in proiectul asta si de fiecare data a costat ore, fiindca esecul arata exact ca un succes:

    14 iul   `extra_floors` / `has_tect` pe cererea de memoriu
    P7       `PlansaNumberingRequest` declara 4 din cei 20 de parametri
    P9       `plansa_numbering` pe `GenerateMemoriuRequest` — zece minute de asteptat un deploy
             care n-avea ce sa schimbe, desi avertismentul era scris de-o luna deasupra campului vecin

Leacul e `extra="forbid"`: cererea cade cu o eroare care NUMESTE campul. Dar aprins direct, opreste
productia — n8n n-are mediu de test, si o singura cheie in plus intr-un nod ar taia TOATE
finalizarile. De-aia sunt trei pasi, iar asta e al doilea:

    PASUL 1  INVENTAR (facut): ce trimit apelantii LIVE vs ce declara modelele.
             Rezultat: DOUA campuri nedeclarate in tot fluxul, amandoua gunoi de nod
             (`_panel_name`, `_floor` catre /generate-schema-b64), niciunul „folosit dar nedeclarat".
    PASUL 2  ASTA: campul necunoscut se LOGHEAZA, cererea TRECE. Zero schimbare de comportament —
             `extra="ignore"` e chiar implicitul lui Pydantic, deci `model_dump()` iese identic.
    PASUL 3  `extra="forbid"`, DOAR dupa ce Dan vede logul curat. O singura linie, mai jos.

CE INSEAMNA „LOG CURAT". Nu „n-am vazut nimic" — aia poate sa insemne si ca endpointul n-a fost
chemat deloc. De-aia se numara si ATINGERILE: un model cu zero atingeri nu e o dovada, e un gol de
acoperire. Criteriul de trecere la pasul 3 e „zero campuri necunoscute SI fiecare model atins macar
o data de trafic real", si se citeste de la `GET /campuri-necunoscute`.

DEDUPLICARE: o pereche (model, camp) se raporteaza O SINGURA DATA pe proces. Fara asta, un camp in
plus pe un circuit ar scrie o linie pentru fiecare din cele ~200 de circuite ale unui bloc si logul
ar deveni ilizibil tocmai cand are ceva de spus. Repornirea instantei reseteaza — si asta e dorit:
dupa un deploy vrei sa vezi din nou starea.
"""
import contextvars
import logging
import threading
import time

from pydantic import BaseModel, ConfigDict, model_validator

logger = logging.getLogger(__name__)

# Calea cererii care se valideaza ACUM. Modelele imbricate (Circuit, CartusFirma, …) nu apartin
# unui singur endpoint, deci harta statica n-ar sti ce sa spuna despre ele — iar cerinta e ca
# mesajul sa numeasca ENDPOINTUL si CAMPUL. Se pune de un middleware care citeste doar
# `request.url.path`: corpul cererii nu se atinge, deci nu se poate rupe nimic din fluxul HTTP.
ruta_curenta = contextvars.ContextVar("zyn_ruta", default=None)

# PASUL 3 SE FACE AICI, schimband un singur cuvant: "ignore" -> "forbid".
# Nu inainte ca `GET /campuri-necunoscute` sa arate `curat: true`.
POLITICA_EXTRA = "ignore"

_lacat = threading.Lock()
_necunoscute = {}       # (model, camp) -> {model, camp, ruta, nr}
_atingeri = {}          # model -> de cate ori a fost validat
_rute = {}              # model -> ruta (completata la pornire din app.routes)
_de_la = time.time()    # contoarele traiesc cat instanta; un deploy le reseteaza

# Modelele astea nu pot fi atinse de trafic real, fiindca endpointul lor n-are NICIUN apelant —
# constatat la PASUL 1, cautand in nodurile n8n LIVE si in tot frontendul. Daca ar sta in
# `modele_neatinse`, poarta `curat` n-ar putea deveni verde NICIODATA, iar o poarta imposibil de
# trecut e ca si cum n-ar exista: se ignora. Daca vreunul incepe sa fie chemat, iese de aici de la
# sine, fiindca atunci apare cu atingeri.
FARA_APELANT = {
    "ProjectData": "/calc-electric",
    "RestampPlansaRequest": "/restamp-plansa",
}


def inregistreaza_rute(app):
    """Model -> calea pe care e folosit. Se cheama o data, la pornire.

    Harta se ia din rutele CHIAR montate, nu dintr-o lista scrisa de mana: o lista de mana ar fi
    exact inca o oglinda de intretinut, iar cand ar ramane in urma ar minti in log."""
    import inspect
    for r in getattr(app, "routes", []):
        fn = getattr(r, "endpoint", None)
        cale = getattr(r, "path", None)
        if not fn or not cale:
            continue
        try:
            sem = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        for p in sem.parameters.values():
            t = p.annotation
            if isinstance(t, type) and issubclass(t, BaseModel):
                _rute.setdefault(t.__name__, cale)
    return len(_rute)


def raport():
    """Ce s-a vazut pana acum. `curat` = se poate trece la pasul 3."""
    with _lacat:
        nec = sorted(_necunoscute.values(), key=lambda x: (x["ruta"], x["model"], x["camp"]))
        at = dict(_atingeri)
        de_la = _de_la
    modele = sorted(_rute)
    neatinse = [m for m in modele if not at.get(m) and m not in FARA_APELANT]
    return {
        "pas": 2,
        "politica": POLITICA_EXTRA,
        # Contoarele traiesc cat instanta. Un raport „curat" dupa doua minute de la un deploy nu
        # spune nimic, de-aia se publica si de cand se numara.
        "de_la": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(de_la)) + " UTC",
        "ore": round((time.time() - de_la) / 3600.0, 1),
        "curat": not nec and not neatinse,
        "campuri_necunoscute": nec,
        "modele_neatinse": neatinse,      # zero atingeri = gol de acoperire, nu dovada
        "modele_fara_apelant": {m: FARA_APELANT[m] for m in sorted(FARA_APELANT)},
        "atingeri": {m: at.get(m, 0) for m in modele},
        # Modelele IMBRICATE (Circuit, CartusFirma, …) nu apartin unui endpoint anume, deci nu intra
        # in criteriul de acoperire — dar un camp necunoscut in ele se raporteaza la fel de tare.
        "atingeri_imbricate": {m: n for m, n in sorted(at.items()) if m not in _rute},
    }


class ZynModel(BaseModel):
    """Baza modelelor de cerere. Identica cu BaseModel ca efect — doar ca vorbeste."""

    model_config = ConfigDict(extra=POLITICA_EXTRA)

    @model_validator(mode="before")
    @classmethod
    def _avertizeaza_campuri_necunoscute(cls, date):
        if not isinstance(date, dict):
            return date
        nume = cls.__name__
        with _lacat:
            _atingeri[nume] = _atingeri.get(nume, 0) + 1
        cunoscute = set(cls.model_fields)
        for c in cls.model_fields.values():
            if getattr(c, "alias", None):
                cunoscute.add(c.alias)
        ruta = ruta_curenta.get() or _rute.get(nume) or "(ruta necunoscuta)"
        noi = []
        for k in date:
            if k in cunoscute:
                continue
            cheie = (nume, k)
            with _lacat:
                v = _necunoscute.get(cheie)
                if v is None:
                    _necunoscute[cheie] = {"model": nume, "camp": k, "ruta": ruta, "nr": 1}
                    noi.append(k)
                else:
                    v["nr"] += 1
        for k in noi:
            logger.warning(
                "[CAMP NECUNOSCUT] %s · camp `%s` · model %s — IGNORAT acum; la pasul 3 va fi "
                "REFUZAT. Ori declara-l pe model (daca e nevoie de el), ori scoate-l din apelant.",
                ruta, k, nume)
        return date
