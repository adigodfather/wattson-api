# -*- coding: utf-8 -*-
"""Poarta `/validate-plan`: planul care nu poarta pereti avertizeaza INAINTE de consum.

De ce exista testul: poarta numara peretii de mult, dar avertisment dadea doar cand plansa n-avea
NICI etichete de arie — un SI. O plansa care ARE camere cu suprafata scrisa si ZERO pereti trecea
`ok`, iar userul platea fara sa stie ca prizele vor fi puse pe conturul aproximativ al camerei.
Masurat pe baza: o plansa din unsprezece exact asa (Casa Bogdan P 90mp — 8 etichete, 0 pereti).

Cele cinci capete verificate:
  [A] plan cu pereti pe layer de perete            -> ok            (nimic nou pentru majoritate)
  [B] plan cu etichete de arie, FARA pereti        -> warning „fara_pereti"   (cazul nou)
  [C] fara etichete SI fara pereti                 -> warning „not_a_plan"    (neschimbat)
  [D] fara strat de text (raster)                  -> rejected                (neschimbat)
  [E] campul `surface` ramane in AMBELE avertismente — modalul de pret il citeste, iar fara el
      pretul afisat ar cadea tacut pe suprafata declarata exact la planurile cele mai slabe.

Rulare:  python test_poarta_pereti.py
"""
import io
import sys

import fitz

sys.stdout.reconfigure(encoding="utf-8")

import main                                                          # noqa: E402

rele = []


def v(nume, cond, det=""):
    print("  %-58s %s%s" % (nume, "OK" if cond else "PICAT", (" — " + det) if det else ""))
    if not cond:
        rele.append(nume)


def _pdf(cu_pereti=True, cu_etichete=True, cu_text=True, n=30):
    """Un plan sintetic: pereti pe un layer numit „PERETI", etichete de arie ca text."""
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    if cu_pereti:
        oc = doc.add_ocg("PERETI")
        for i in range(n):
            y = 80 + i * 18
            pg.draw_line(fitz.Point(60, y), fitz.Point(520, y), width=1.2, oc=oc)
            pg.draw_line(fitz.Point(60 + i * 12, 80), fitz.Point(60 + i * 12, 700), width=1.2, oc=oc)
    else:
        # linii REALE, dar pe layerul implicit (fara nume) — exportul aplatizat
        for i in range(n):
            y = 80 + i * 18
            pg.draw_line(fitz.Point(60, y), fitz.Point(520, y), width=1.2)
    if cu_text:
        pg.insert_text(fitz.Point(70, 60), "PLAN PARTER", fontsize=11)
        if cu_etichete:
            for i in range(6):
                pg.insert_text(fitz.Point(80 + i * 70, 740), "A: %d.5 mp" % (10 + i), fontsize=8)
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _poarta(pdf_bytes):
    import base64
    cerere = main.ValidatePlanRequest(pdf_base64=base64.b64encode(pdf_bytes).decode())
    # `_protejat` e decoratorul de semafor; functia dinauntru e cea testata
    fn = getattr(main.validate_plan_endpoint, "__wrapped__", main.validate_plan_endpoint)
    return fn(cerere)


print("=== poarta de pereti din /validate-plan ===")

# [A] plan normal: pereti pe layer recunoscut
a = _poarta(_pdf(cu_pereti=True, cu_etichete=True))
v("[A] plan cu pereti -> ok", a.get("status") == "ok",
  "status=%s pereti=%s" % (a.get("status"), (a.get("detected") or {}).get("walls")))

# [B] cazul NOU: are camere cu suprafata scrisa, dar zero pereti colectati
b = _poarta(_pdf(cu_pereti=False, cu_etichete=True))
v("[B] etichete de arie, fara pereti -> warning/fara_pereti",
  b.get("status") == "warning" and b.get("reason") == "fara_pereti",
  "status=%s reason=%s pereti=%s" % (b.get("status"), b.get("reason"),
                                     (b.get("detected") or {}).get("walls")))
v("[B2] mesajul spune ce se intampla cu prizele",
  "prizele" in (b.get("message") or "").lower() and "layere" in (b.get("message") or "").lower(),
  repr((b.get("message") or "")[:64]))

# [C] nici etichete, nici pereti: mesajul vechi, neschimbat ca verdict
c = _poarta(_pdf(cu_pereti=False, cu_etichete=False))
v("[C] fara etichete si fara pereti -> warning/not_a_plan",
  c.get("status") == "warning" and c.get("reason") == "not_a_plan",
  "reason=%s" % c.get("reason"))

# [D] raster: blocare hard, neatinsa
d = _poarta(_pdf(cu_pereti=False, cu_etichete=False, cu_text=False))
v("[D] fara strat de text -> rejected", d.get("status") == "rejected",
  "status=%s reason=%s" % (d.get("status"), d.get("reason")))

# [E] pretul: `surface` trebuie sa existe in AMBELE avertismente
v("[E] `surface` prezent in warning/fara_pereti", "surface" in b)
v("[E2] `surface` prezent in warning/not_a_plan", "surface" in c)

# [F] un singur prag, folosit de ambele conditii
v("[F] pragul e o constanta, nu un numar scris de doua ori",
  isinstance(getattr(main, "PRAG_PERETI", None), int) and main.PRAG_PERETI == 20,
  "PRAG_PERETI=%s" % getattr(main, "PRAG_PERETI", None))

print()
if rele:
    print("PICAT: %d din %d" % (len(rele), 8))
    for r in rele:
        print("   - %s" % r)
    sys.exit(1)
print("Toate cele 8 capete: OK")
