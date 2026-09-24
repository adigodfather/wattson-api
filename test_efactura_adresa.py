# -*- coding: utf-8 -*-
"""Adresa fiscala a cumparatorului: judet + localitate pe TOATE ramurile de facturare.

De ce exista testul: e-Factura cere localitatea (BT-52) si judetul (BT-54) pentru ORICE cumparator,
firma sau persoana. Pana acum se cereau doar la `individual`, iar pe ramurile de firma nici macar nu
se MAPAU catre SmartBill — se colectau (sau nici atat) si se pierdeau. Factura se emitea, dar
transmiterea in SPV era respinsa, fara niciun semn de partea noastra. Exact asta a patit ZN0001.

Capetele verificate:
  [A] COMPORTAMENT — `mapSmartbillClient` trimite city+county pe toate trei ramurile;
  [B] COMPORTAMENT — payload-ul final le duce pana la SmartBill, pe fiecare ramura;
  [C] COMPORTAMENT — fara ele, campurile lipsesc (nu se inventeaza un judet gol);
  [D] STRUCTURAL — poarta de pe server verifica judet+localitate INAINTE de ramificarea pe tip,
      deci nicio ramura n-o poate ocoli. (Ruta e Next + Supabase auth, nu se poate rula de aici;
      verificarea e pe text si e marcata ca atare.)

Rulare:  python test_efactura_adresa.py
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
RUTA = os.path.join(APP, "app", "api", "payment", "start", "route.ts")

rele = []


def v(nume, cond, det=""):
    print("  %-70s %s %s" % (nume[:70], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def main():
    tmp = tempfile.mkdtemp(prefix="efadr_")
    r = subprocess.run(["npx", "tsc", TS, "--outDir", tmp, "--module", "commonjs",
                        "--target", "es2020", "--skipLibCheck"],
                       cwd=APP, capture_output=True, shell=(os.name == "nt"))
    js = os.path.join(tmp, "smartbill.js")
    if not os.path.exists(js):
        v("fisierul se compileaza", False, (r.stdout or r.stderr).decode("utf-8", "replace")[:200])
        return 1
    v("fisierul se compileaza", True)

    cod = """
const sb = require(%s);
process.env.SMARTBILL_SERIES = 'ZN';
process.env.SMARTBILL_VAT_CODE = '1';
const prof = {email:'a@b.ro', full_name:'Ion Pop', firma_cui:'RO123', firma_nume:'ACME SRL',
              firma_adresa:'Str. X 1', firma_email:'f@acme.ro'};
const adr = {county:'Cluj', city:'Cluj-Napoca'};
const B = {
  individual:      {type:'individual', ...adr},
  company_profile: {type:'company_profile', adminName:'Ion', ...adr},
  company_custom:  {type:'company_custom', name:'BETA SRL', vatCode:'RO9', address:'Str Y 2', ...adr},
};
const out = {cu: {}, fara: {}, payload: {}};
for (const [k, b] of Object.entries(B)) {
  const c = sb.mapSmartbillClient(prof, b);
  out.cu[k] = {city: c.city ?? null, county: c.county ?? null};
  const {county, city, ...bFara} = b;
  const c2 = sb.mapSmartbillClient(prof, bFara);
  out.fara[k] = {city: c2.city ?? null, county: c2.county ?? null};
  const p = sb.buildInvoicePayload(prof, {amount_ron:19, credits:100, order_id:'X'}, {billing: b});
  out.payload[k] = {city: p.client.city ?? null, county: p.client.county ?? null};
}
console.log(JSON.stringify(out));
""" % json.dumps(js.replace("\\", "/"))
    f = os.path.join(tmp, "ruleaza.js")
    io.open(f, "w", encoding="utf-8").write(cod)
    p = subprocess.run(["node", f], capture_output=True, shell=(os.name == "nt"))
    out = p.stdout.decode("utf-8", "replace").strip()
    if not out:
        v("scriptul ruleaza", False, p.stderr.decode("utf-8", "replace")[:200])
        return 1
    d = json.loads(out)

    for ram in ("individual", "company_profile", "company_custom"):
        c = d["cu"][ram]
        v("[A] %s trimite localitatea si judetul" % ram,
          c["city"] == "Cluj-Napoca" and c["county"] == "Cluj", json.dumps(c))
        pl = d["payload"][ram]
        v("[B] %s le duce pana in payload-ul SmartBill" % ram,
          pl["city"] == "Cluj-Napoca" and pl["county"] == "Cluj", json.dumps(pl))
        fz = d["fara"][ram]
        v("[C] %s fara ele nu inventeaza campuri goale" % ram,
          fz["city"] is None and fz["county"] is None, json.dumps(fz))

    # [D] poarta de pe server: verificarea sta INAINTE de ramificarea pe tip
    src = io.open(RUTA, encoding="utf-8").read()
    i_check = src.find('Completează județul și localitatea')
    i_prof = src.find('if (bType === "company_profile")')
    i_cust = src.find('bType === "company_custom"')
    v("[D-structural] poarta de judet+localitate exista in ruta", i_check > 0)
    v("[D-structural] sta INAINTEA ramurii company_profile", 0 < i_check < i_prof,
      "check@%d vs company_profile@%d" % (i_check, i_prof))
    v("[D-structural] sta INAINTEA ramurii company_custom", 0 < i_check < i_cust,
      "check@%d vs company_custom@%d" % (i_check, i_cust))
    v("[D-structural] nu mai exista o a doua verificare, doar in ramura B2C",
      src.count('Completează județul și localitatea') == 1,
      "aparitii: %d" % src.count('Completează județul și localitatea'))

    print("\n".join("ESUAT: " + x for x in rele) if rele
          else "OK — adresa fiscala ajunge la SmartBill pe toate cele trei ramuri")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
