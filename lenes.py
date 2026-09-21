# -*- coding: utf-8 -*-
"""Import amanat pana la prima folosire, pentru bibliotecile grele si rar chemate.

Procesul pornea cu 83 MB ocupati, din care 43 veneau din trei biblioteci pe care majoritatea
cererilor nu le ating niciodata: reportlab (13,5 MB, doar la scheme), python-docx (12,4 MB, doar
la memoriu si caiet) si requests (17,4 MB, doar cand se descarca un logo). Pe o instanta de
512 MB, 43 MB inseamna vreo 23 000 de primitive de desen in plus care incap.

Amanarea nu schimba niciun rezultat: prima cerere care chiar are nevoie de biblioteca o incarca,
si de acolo e in cache-ul de module ca orice alt import. Se plateste o data, nu la fiecare pornire.

Folosire — se inlocuieste `from X import Y` cu:
    Y = lenes.simbol("X", "Y")      # o clasa, o functie, un enum
    X = lenes.modul("X")            # tot modulul (`X.ceva`)

CE NU MERGE: proxy-ul se poarta ca obiectul real la apel (`Y(...)`) si la atribut (`Y.CEVA`), dar
NU e obiectul real pentru `isinstance`, pentru subclasare sau pentru aritmetica. Constantele
numerice raman import normal — oricum nu costa nimic: `reportlab.lib.units` e 0,1 MB.
"""
import importlib


class _Amanat(object):
    __slots__ = ("_modul", "_simbol", "_real")

    def __init__(self, modul, simbol=None):
        object.__setattr__(self, "_modul", modul)
        object.__setattr__(self, "_simbol", simbol)
        object.__setattr__(self, "_real", None)

    def _adu(self):
        r = object.__getattribute__(self, "_real")
        if r is None:
            m = importlib.import_module(object.__getattribute__(self, "_modul"))
            s = object.__getattribute__(self, "_simbol")
            r = getattr(m, s) if s else m
            object.__setattr__(self, "_real", r)
        return r

    def __getattr__(self, k):
        return getattr(self._adu(), k)

    def __call__(self, *a, **k):
        return self._adu()(*a, **k)

    def __repr__(self):
        s = object.__getattribute__(self, "_simbol")
        return "<lenes %s%s>" % (object.__getattribute__(self, "_modul"), "." + s if s else "")


def modul(nume):
    """`requests` -> se importa la primul `requests.get(...)`."""
    return _Amanat(nume)


def simbol(nume_modul, nume_simbol):
    """`from docx import Document` -> `Document = lenes.simbol("docx", "Document")`."""
    return _Amanat(nume_modul, nume_simbol)
