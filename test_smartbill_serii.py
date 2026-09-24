# -*- coding: utf-8 -*-
"""Seriile de facturi: structura pentru serii independente, fara sa atinga seria de credite.

De ce exista testul: contorul numerelor NU e la noi — il tine SmartBill, per serie, iar `seriesName`
se trimite in fiecare cerere. Deci doua serii au contoare independente prin constructie, si singurul
lucru pe care-l putem strica din codul nostru e sa trimitem seria GRESITA. Un document fiscal emis
pe seria de credite in locul celei de servicii nu se retrage decat prin stornare.

Capetele verificate:
  [A] calea de AZI (credite) e neschimbata — payload-ul iese IDENTIC cu cel din HEAD, camp cu camp;
  [B] seriile sunt independente: fiecare isi citeste variabila ei, iar una n-o atinge pe cealalta;
  [C] seria ceruta si NECONFIGURATA da eroare care NUMESTE variabila lipsa — niciodata cadere tacuta
      pe seria de credite;
  [D] `buildInvoicePayload` ia seria din `seriesFor`, nu din `process.env` direct (altfel [C] se
      poate ocoli fara sa observe nimeni).

Nu exista runner de TypeScript in aplicatie, asa ca testul COMPILEAZA fisierul cu `tsc` si-l ruleaza
cu node — comportament, nu citire de text.
Rulare:  python test_smartbill_serii.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
TS = os.path.join(APP, "lib", "smartbill.ts")

rele = []


def v(nume, cond, det=""):
    print("  %-72s %s %s" % (nume[:72], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def _compileaza(sursa_ts, unde):
    """tsc pe UN fisier, fara dependinte (smartbill.ts nu importa nimic). -> calea .js sau None."""
    os.makedirs(unde, exist_ok=True)
    r = subprocess.run(["npx", "tsc", sursa_ts, "--outDir", unde, "--module", "commonjs",
                        "--target", "es2020", "--skipLibCheck"],
                       cwd=APP, capture_output=True, shell=(os.name == "nt"))
    js = os.path.join(unde, os.path.basename(sursa_ts).replace(".ts", ".js"))
    if not os.path.exists(js):
        print("     tsc: %s" % (r.stdout or r.stderr).decode("utf-8", "replace")[:300])
        return None
    return js


def _node(js, cod):
    """Ruleaza `cod` cu modulul deja cerut ca `sb`; intoarce JSON-ul tiparit de el.

    Scriptul se scrie in FISIER, nu se paseaza prin `node -e`: pe Windows, un script multi-linie cu
    ghilimele trecut prin shell se intoarce ciuntit, iar node iese fara stdout SI fara stderr —
    adica esec tacut exact in unealta care trebuie sa prinda esecuri tacute.
    """
    f = os.path.join(os.path.dirname(js), "ruleaza_%d.js" % (abs(hash(cod)) % 10 ** 8))
    io.open(f, "w", encoding="utf-8").write(
        "const sb = require(%s);\n%s" % (json.dumps(js.replace("\\", "/")), cod))
    r = subprocess.run(["node", f], capture_output=True, shell=(os.name == "nt"))
    out = r.stdout.decode("utf-8", "replace").strip()
    if not out:
        print("     node: %s" % (r.stderr.decode("utf-8", "replace")[:300] or "(fara iesire)"))
        return None
    return json.loads(out)


def main():
    tmp = tempfile.mkdtemp(prefix="sbserii_")
    js_nou = _compileaza(TS, os.path.join(tmp, "nou"))
    v("fisierul se compileaza", js_nou is not None)
    if not js_nou:
        return 1

    # [A] calea de credite, comparata cu HEAD — payload IDENTIC, camp cu camp
    vechi_src = subprocess.run(["git", "show", "HEAD:apps/zynapse-configurator/lib/smartbill.ts"],
                               cwd=RADACINA, capture_output=True).stdout.decode("utf-8")
    js_vechi = None
    if vechi_src.strip():
        p = os.path.join(tmp, "smartbill.ts")
        io.open(p, "w", encoding="utf-8").write(vechi_src)
        js_vechi = _compileaza(p, os.path.join(tmp, "vechi"))

    CAZ = """
process.env.SMARTBILL_SERIES = 'ZN';
process.env.SMARTBILL_VAT_CODE = '12345678';
const prof = {email:'client@firma.ro', full_name:'Ion Pop', firma_cui:'RO123', firma_nume:'ACME SRL',
              firma_adresa:'Str. X 1', firma_email:'fact@acme.ro'};
const pay = {amount_ron: 19, credits: 100, order_id: 'ZYN-1'};
const out = {};
out.implicit = sb.buildInvoicePayload(prof, pay);
out.b2c = sb.buildInvoicePayload({email:'p@f.ro', full_name:'Ion Pop'}, pay,
            {billing:{type:'individual', county:'Prahova', city:'Ploiesti'}});
console.log(JSON.stringify(out));
"""
    a = _node(js_vechi, CAZ) if js_vechi else None
    b = _node(js_nou, CAZ)
    v("[A] payload-ul se construieste", b is not None)
    if a and b:
        for k in ("implicit", "b2c"):
            va, vb = dict(a[k]), dict(b[k])
            va.pop("issueDate", None)
            vb.pop("issueDate", None)   # data de azi, aceeasi in ambele rulari
            v("[A] factura de credite (%s) IDENTICA cu HEAD" % k, va == vb,
              "difera la: %s" % [x for x in set(va) | set(vb) if va.get(x) != vb.get(x)])
    else:
        print("     (HEAD nu s-a putut compila — comparatia [A] se sare)")
    if b:
        v("[A] seria implicita ramane cea de credite", b["implicit"]["seriesName"] == "ZN",
          "seria = %r" % b["implicit"]["seriesName"])

    # [B] + [C] + [D]
    r = _node(js_nou, """
process.env.SMARTBILL_SERIES = 'ZN';
delete process.env.SMARTBILL_SERIES_SERVICII;
const o = {};
o.credite_fara_servicii = sb.seriesFor('credite');
o.servicii_neconfigurat = sb.seriesFor('servicii');
process.env.SMARTBILL_SERIES_SERVICII = 'ZS';
o.servicii = sb.seriesFor('servicii');
o.credite_dupa = sb.seriesFor('credite');
process.env.SMARTBILL_SERIES = 'ZN2';
o.servicii_neatins = sb.seriesFor('servicii');
o.payload_servicii = sb.buildInvoicePayload({email:'a@b.ro'}, {amount_ron:1,credits:1,order_id:'X'},
                       {seriesKind:'servicii'}).seriesName;
console.log(JSON.stringify(o));
""")
    v("[B] cele doua serii se citesc", r is not None)
    if r:
        v("[B] seria de credite nu e afectata de cea de servicii",
          r["credite_fara_servicii"] == "ZN" and r["credite_dupa"] == "ZN")
        v("[B] seria de servicii nu e afectata de cea de credite",
          r["servicii"] == "ZS" and r["servicii_neatins"] == "ZS")
        v("[C] seria de servicii neconfigurata iese GOALA, nu cade pe cea de credite",
          r["servicii_neconfigurat"] == "", "a iesit %r" % r["servicii_neconfigurat"])
        v("[D] payload-ul de servicii ia seria de servicii", r["payload_servicii"] == "ZS",
          "a iesit %r" % r["payload_servicii"])

    # [C] createInvoice: seria lipsa -> eroare care NUMESTE variabila, si NICIUN apel de retea
    r2 = _node(js_nou, """
process.env.SMARTBILL_USERNAME='u'; process.env.SMARTBILL_TOKEN='t'; process.env.SMARTBILL_VAT_CODE='1';
process.env.SMARTBILL_SERIES='ZN'; delete process.env.SMARTBILL_SERIES_SERVICII;
let chemat = false;
global.fetch = async () => { chemat = true; throw new Error('nu trebuia chemat'); };
sb.createInvoice({email:'a@b.ro'}, {amount_ron:1,credits:1,order_id:'X'}, {seriesKind:'servicii'})
  .then(res => console.log(JSON.stringify({res, chemat})));
""")
    v("[C] createInvoice raspunde fara serie", r2 is not None)
    if r2:
        v("[C] esueaza in loc sa emita pe seria de credite", r2["res"]["success"] is False)
        v("[C] eroarea NUMESTE variabila lipsa", "SMARTBILL_SERIES_SERVICII" in str(r2["res"].get("error")),
          str(r2["res"].get("error")))
        v("[C] nu s-a atins reteaua", r2["chemat"] is False)

    print("\n".join("ESUAT: " + x for x in rele) if rele
          else "OK — seriile sunt independente, iar calea de credite e neschimbata")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
