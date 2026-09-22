# -*- coding: utf-8 -*-
"""Ramura geometrica din /bom s-a EXECUTAT — nu doar „endpointul a raspuns 200".

De ce exista testul: `/bom` calculeaza metrii de cablu pe traseul real al peretilor (FIX-C1,
e4546cf) doar daca poate deschide plansa. Citea `result_data.planuri[].pdf_base64`, iar mutarea
blob-urilor in Storage (dad356a) a golit campul la toate proiectele. Ramura a incetat sa se
execute, raspunsul a ramas `success: True`, si metrii au cazut pe rutarea veche — cu 1,3% pana la
7,5% mai putin cablu, la 15 din 19 proiecte. Nimic nu a semnalat nimic: cititorul nu AFISA nimic,
doar CALCULA.

Testul cere doua lucruri pe care cadea vechea stare:
  (1) `plansa_bytes` aduce plansa si cand randul are doar referinta (cale + amprenta);
  (2) raspunsul lui `/bom` spune prin `geom_rooms` cate camere au intrat cu conturul lor real.

Rulare:  python test_bom_geometrie.py
Fara acces la baza, testul sare partea [2] si ramane pe [1] (nu pica un CI fara retea).
"""
import hashlib
import os
import sys
import types

rele = []


def v(nume, cond, det=""):
    print("  %-70s %s %s" % (nume[:70], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


class _Galeata:
    def __init__(self, date, bucket):
        self.date, self.bucket = date, bucket

    def download(self, cale):
        if cale not in self.date:
            raise KeyError(cale)
        return self.date[cale]


class _ClientFals:
    """Doar cat foloseste `plansa_bytes`: un bucket si un download."""
    def __init__(self, date, bucket="project-files"):
        self.date, self.bucket = date, bucket
        self.storage = types.SimpleNamespace(from_=lambda b: _Galeata(date, b))


def _importa_client():
    """`supabase_client` fara pachetul `supabase` instalat.

    Masina de dezvoltare are un requirements ciuntit intentionat, iar modulul face
    `from supabase import create_client, Client` la import. Testul nu are nevoie de clientul
    adevarat (isi pune singur unul fals), deci pune un inlocuitor DOAR daca pachetul lipseste —
    altfel testul ar fi verde numai pe Render, adica exact unde nu ma uit cand scriu codul.
    """
    try:
        from supabase import create_client                       # noqa: F401
    except ImportError:
        # atentie: pe masina asta `import supabase` REUSESTE (exista un pachet partial), dar
        # `create_client` lipseste — verificarea trebuie sa fie pe ce se importa efectiv
        gol = types.ModuleType("supabase")
        gol.create_client = lambda *a, **k: None
        gol.Client = object
        sys.modules["supabase"] = gol
    import supabase_client as sc
    return sc


def main():
    sc = _importa_client()

    PDF = b"%PDF-1.7\nastea sunt octetii plansei\n%%EOF\n"
    amp = hashlib.sha256(PDF).hexdigest()
    vechi = sc._client
    sc._client = _ClientFals({"proiecte/x/IE.1.pdf": PDF})
    try:
        # [1] cititorul: rand cu base64, rand cu referinta, si cazurile in care trebuie sa taca
        import base64
        v("plansa cu base64 in rand -> octetii ei",
          sc.plansa_bytes({"pdf_base64": base64.b64encode(PDF).decode()}) == PDF)
        v("plansa cu base64 prefixat data: -> tot octetii ei",
          sc.plansa_bytes({"pdf_base64": "data:application/pdf;base64," + base64.b64encode(PDF).decode()}) == PDF)
        v("plansa DOAR cu referinta (cale + amprenta) -> se aduce din Storage",
          sc.plansa_bytes({"pdf_base64_path": "proiecte/x/IE.1.pdf", "pdf_base64_sha256": amp}) == PDF)
        v("referinta fara amprenta -> se aduce oricum",
          sc.plansa_bytes({"pdf_base64_path": "proiecte/x/IE.1.pdf"}) == PDF)
        v("amprenta care NU se potriveste -> None (un fisier strain nu e mai bun decat lipsa lui)",
          sc.plansa_bytes({"pdf_base64_path": "proiecte/x/IE.1.pdf", "pdf_base64_sha256": "0" * 64}) is None)
        v("cale inexistenta -> None, fara exceptie",
          sc.plansa_bytes({"pdf_base64_path": "nu/exista.pdf"}) is None)
        v("plansa fara nici base64, nici cale -> None",
          sc.plansa_bytes({"plansa_nr": "IE.1"}) is None)
        v("intrare care nu e dict -> None", sc.plansa_bytes(None) is None)
    finally:
        sc._client = vechi

    # [2] endpointul: `geom_rooms` exista si e > 0 pe un proiect real cu plan
    proiect = os.environ.get("ZYN_PROIECT_BOM", "")
    if not proiect:
        print("  (fara ZYN_PROIECT_BOM: partea prin endpoint se sare — vezi sonda s8 din pachet)")
    else:
        import main as M
        r = M.bom_endpoint(M.BomRequest(project_id=proiect,
                                        form={"power_phase": "mono", "extra_equipment": []}))
        v("/bom raspunde", bool(r.get("success")), str(r.get("error"))[:60])
        gr = r.get("geom_rooms") or {}
        v("raspunsul SPUNE daca ramura geometrica s-a executat (`geom_rooms`)",
          isinstance(r.get("geom_rooms"), dict))
        v("ramura geometrica S-A EXECUTAT (camere cu contur real > 0)",
          any(int(n or 0) > 0 for n in gr.values()), "geom_rooms=%r" % (gr,))

    print("\n".join("ESUAT: " + r for r in rele) if rele
          else "OK — plansa se aduce si prin referinta, iar executia ramurii e vizibila")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.exit(main())
