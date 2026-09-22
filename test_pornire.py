# -*- coding: utf-8 -*-
"""Pornirea serverului nu are voie sa depinda de retea.

DE CE EXISTA. Pe 22 sept, un deploy a ramas blocat 15 minute fara sa deschida portul si fara
nicio eroare in log: build reusit, „Running 'uvicorn main:app'" la 14:04:58, „Port scan timeout"
la 14:19:51. Tiparul asta — niciun port, niciun mesaj — arata a blocaj INAINTE de deschiderea
portului, fiindca uvicorn importa `main:app` intai si abia apoi asculta. Un apel de retea fara
timeout facut la import da exact asta.

De data aia nu era: importul dureaza ~1 s si nu atinge reteaua deloc. Dar nimic nu PAZEA
proprietatea, iar ea se pierde usor — e de ajuns ca cineva sa citeasca o setare din baza la
nivel de modul, sau sa faca un client HTTP „ca sa fie gata". Testul asta o pazeste.

Rulare:  python test_pornire.py
"""
import os
import socket
import sys
import time

# Cat are voie sa dureze importul. Masurat: ~1 s. Pragul e larg, ca sa nu pice pe o masina lenta,
# dar destul de strans cat sa prinda ceva care ASTEAPTA (un apel de retea, o citire din baza).
PRAG_IMPORT_S = 20.0

_cereri = []
_conn, _conn_ex, _gai = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo


def _e_local(adr):
    gazda = adr[0] if isinstance(adr, tuple) else str(adr)
    return str(gazda) in ("127.0.0.1", "::1", "localhost", "0.0.0.0")


def _connect(self, adr):
    if not _e_local(adr):
        _cereri.append(("connect", adr))
        raise OSError("retea blocata de test: %s" % (adr,))
    return _conn(self, adr)


def _connect_ex(self, adr):
    if not _e_local(adr):
        _cereri.append(("connect_ex", adr))
        return 1
    return _conn_ex(self, adr)


def _getaddrinfo(gazda, port, *a, **k):
    if gazda not in ("127.0.0.1", "::1", "localhost", "0.0.0.0", None):
        _cereri.append(("dns", gazda))
        raise socket.gaierror("dns blocat de test: %s" % gazda)
    return _gai(gazda, port, *a, **k)


def main():
    socket.socket.connect = _connect
    socket.socket.connect_ex = _connect_ex
    socket.getaddrinfo = _getaddrinfo

    # variabilele de pe Render, ca importul sa mearga pe caile de PRODUCTIE, nu pe fallback-uri
    for cheie, val in (("RENDER", "true"), ("SUPABASE_URL", "https://exemplu.supabase.co"),
                       ("SUPABASE_SERVICE_KEY", "test"), ("ZYNAPSE_INTERNAL_KEY", "test"),
                       ("ANTHROPIC_API_KEY", "test")):
        os.environ.setdefault(cheie, val)

    t0 = time.time()
    import main as _m
    durata = time.time() - t0
    rute = len([r for r in _m.app.routes if hasattr(r, "path")])

    print("import: %.2f s · %d rute · cereri de retea: %d" % (durata, rute, len(_cereri)))
    rele = []
    if _cereri:
        for tip, adr in _cereri[:10]:
            print("   !! %s %s" % (tip, adr))
        rele.append("importul atinge reteaua — muta apelul intr-o initializare lenesa, "
                    "sau da-i un timeout scurt")
    if durata > PRAG_IMPORT_S:
        rele.append("importul dureaza %.1f s (prag %.0f) — ceva ASTEAPTA la pornire" % (durata, PRAG_IMPORT_S))
    if rute < 20:
        rele.append("doar %d rute inregistrate — importul n-a mers pana la capat" % rute)

    print("\n".join("ESUAT: " + r for r in rele) if rele else "OK — pornirea nu depinde de retea")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.exit(main())
