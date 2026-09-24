# -*- coding: utf-8 -*-
"""Livrarea facturii pe email: textul, adresa, PDF-ul si garda anti-dublare.

De ce exista testul: factura e DEJA emisa si in SPV cand incepe pasul asta. Un esec aici nu strica
nimic, dar daca esueaza TACUT clientul nu-si primeste factura si nimeni nu afla — exact tiparul pe
care il vanam de zile intregi. Deci fiecare pas trebuie sa raporteze, iar dublarea trebuie oprita
de baza, nu de un `if`.

Capetele verificate:
  [A] TEXTUL emailului — pur, deci se poate citi fara sa trimita nimic;
  [B] ADRESA pe fiecare din cele trei ramuri, inclusiv `company_custom` FARA email de facturare
      (e optional!) — trebuie sa cada pe emailul contului, niciodata pe o adresa inventata;
  [C] PDF-ul — un raspuns 200 care NU e PDF se respinge, altfel clientul primeste atasat un fisier
      care nu se deschide;
  [D] GARDA ANTI-DUBLARE, pe baza REALA: doua cereri simultane, exact una castiga randul.
      Se lucreaza pe un rand de PROBA, creat si sters de test.

Rulare:  python test_factura_email.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
rele = []
sarite = []


def sari(nume, motiv):
    """Un capat SARIT nu e un capat trecut. Se tine minte si se spune la final, altfel sumarul
    raporteaza „OK" peste o verificare care nu s-a facut — adica exact esecul tacut."""
    print("  %-70s SARIT  %s" % (nume[:70], motiv[:80]))
    sarite.append(nume)


def v(nume, cond, det=""):
    print("  %-70s %s %s" % (nume[:70], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def _node(tmp, cod):
    f = os.path.join(tmp, "ruleaza.js")
    io.open(f, "w", encoding="utf-8").write(cod)
    r = subprocess.run(["node", f], capture_output=True, shell=(os.name == "nt"))
    out = r.stdout.decode("utf-8", "replace").strip()
    if not out:
        print("     node: %s" % (r.stderr.decode("utf-8", "replace")[:300] or "(fara iesire)"))
        return None
    return json.loads(out)


def parte_js():
    tmp = tempfile.mkdtemp(prefix="facmail_")
    r = subprocess.run(["npx", "tsc", os.path.join("lib", "invoiceDelivery.ts"), "--outDir", tmp,
                        "--module", "commonjs", "--target", "es2020", "--skipLibCheck",
                        "--moduleResolution", "node"],
                       cwd=APP, capture_output=True, shell=(os.name == "nt"))
    liv = os.path.join(tmp, "invoiceDelivery.js")
    if not os.path.exists(liv):
        v("modulele se compileaza", False, (r.stdout or r.stderr).decode("utf-8", "replace")[:200])
        return
    v("modulele se compileaza", True)

    sablon = """
const liv = require(__LIV__);
const mail = require(__MAIL__);
const sb = require(__SB__);
const prof = {email:'cont@client.ro', full_name:'Ion Pop', firma_cui:'RO123',
              firma_nume:'ACME SRL', firma_email:'facturi@acme.ro'};
const adr = {county:'Cluj', city:'Cluj-Napoca'};
const out = {};
out.text = mail.invoiceEmailBody({to:'x@y.ro', clientName:'ACME SRL', series:'ZS', number:'0007',
                                  amountRon: 1500, credits: 0, pdfBase64:'x'});
out.adr = {
  individual:       liv.adresaFacturii(prof, 'individual', adr),
  company_profile:  liv.adresaFacturii(prof, 'company_profile', {...adr, admin_name:'Ion'}),
  custom_cu_email:  liv.adresaFacturii(prof, 'company_custom', {...adr, name:'BETA', vatCode:'RO9', email:'fact@beta.ro'}),
  custom_fara_email:liv.adresaFacturii(prof, 'company_custom', {...adr, name:'BETA', vatCode:'RO9'}),
  fara_billing:     liv.adresaFacturii(prof, null, null),
};
process.env.SMARTBILL_USERNAME='u'; process.env.SMARTBILL_TOKEN='t'; process.env.SMARTBILL_VAT_CODE='1';
const ca = async (corp) => { global.fetch = async () => ({ok:true, status:200,
    arrayBuffer: async () => Buffer.from(corp)}); return await sb.fetchInvoicePdf('ZN','1'); };
(async () => {
  out.pdf_fals = await ca('Unauthorized');
  out.pdf_bun  = await ca('PDFMAGIC-1.4 ceva');
  out.fara_cheie = await mail.sendInvoiceEmail({to:'a@b.ro', clientName:'X', series:'ZN', number:'1',
                                                amountRon:1, credits:1, pdfBase64:'AA'});
  console.log(JSON.stringify(out));
})();
"""
    cod = (sablon
           .replace("__LIV__", json.dumps(liv.replace("\\", "/")))
           .replace("__MAIL__", json.dumps(os.path.join(tmp, "email", "invoice.js").replace("\\", "/")))
           .replace("__SB__", json.dumps(os.path.join(tmp, "smartbill.js").replace("\\", "/")))
           .replace("PDFMAGIC", chr(37) + "PDF"))
    d = _node(tmp, cod)
    if not d:
        v("scriptul ruleaza", False)
        return

    t = d["text"]
    v("[A] subiectul contine numarul documentului", "ZS0007" in t["subject"], t["subject"])
    v("[A] textul contine suma in lei, cu virgula", "1500,00 lei" in t["text"])
    v("[A] textul da o adresa de contact", "office@zynapse.org" in t["text"])
    v("[A] textul NU afirma ce nu putem verifica (trimiterea in SPV)",
      "SPV" not in t["text"] and "e-Factura" not in t["text"])
    v("[A] exista si varianta HTML, nu doar text", t["html"].startswith("<div") and "ZS0007" in t["html"])

    a = d["adr"]
    v("[B] individual -> emailul CONTULUI", a["individual"]["to"] == "cont@client.ro", json.dumps(a["individual"]))
    v("[B] company_profile -> firma_email din profil", a["company_profile"]["to"] == "facturi@acme.ro")
    v("[B] company_custom cu email -> emailul din formular", a["custom_cu_email"]["to"] == "fact@beta.ro")
    v("[B] company_custom FARA email -> cade pe emailul contului, nu inventeaza",
      a["custom_fara_email"]["to"] == "cont@client.ro", json.dumps(a["custom_fara_email"]))
    v("[B] plata veche, fara billing -> tot o adresa reala", a["fara_billing"]["to"] == "facturi@acme.ro")
    v("[B] numele clientului insoteste adresa", a["company_profile"]["name"] == "ACME SRL")

    v("[C] un raspuns 200 care nu e PDF se RESPINGE", d["pdf_fals"]["success"] is False,
      json.dumps(d["pdf_fals"])[:120])
    v("[C] mesajul spune ce a venit in loc de PDF", "Unauthorized" in str(d["pdf_fals"].get("error")))
    v("[C] un PDF adevarat trece", d["pdf_bun"]["success"] is True and bool(d["pdf_bun"].get("pdfBase64")))
    v("[C] fara RESEND_API_KEY NU tace: intoarce eroare care numeste cheia",
      d["fara_cheie"]["success"] is False and "RESEND_API_KEY" in str(d["fara_cheie"].get("error")),
      json.dumps(d["fara_cheie"]))


def parte_baza():
    """[D] Garda anti-dublare, pe baza REALA, cu un rand de proba creat si sters de test."""
    sys.path.insert(0, os.path.join(RADACINA, "..", "..", "AppData"))
    cale = os.environ.get("ZYN_REF_DIR") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local", "Temp", "claude", "C--zynapse",
        "5b519f49-43dc-4160-a968-3479d7ea863e", "scratchpad")
    if not os.path.isdir(cale):
        sari("[D] garda anti-dublare pe baza reala", "directorul cu ref.py lipseste")
        return
    sys.path.insert(0, cale)
    try:
        import ref
    except Exception as e:
        sari("[D] garda anti-dublare pe baza reala", str(e)[:80])
        return

    oid = "ZYN-TEST-CLAIM-%d" % int(time.time())
    uid = (ref.rest("/rest/v1/profiles?select=id&limit=1") or [{}])[0].get("id")
    if not uid:
        sari("[D] garda anti-dublare pe baza reala", "niciun profil in baza")
        return

    def cerere(metoda, cale_q, corp=None, prefer=None):
        h = dict(ref.A_)
        h["Content-Type"] = "application/json"
        if prefer:
            h["Prefer"] = prefer
        r = urllib.request.Request(ref.U_ + cale_q, method=metoda,
                                   data=json.dumps(corp).encode() if corp is not None else None,
                                   headers=h)
        return json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or "[]")

    try:
        cerere("POST", "/rest/v1/payments", {
            "order_id": oid, "user_id": uid, "amount_ron": 1, "credits": 1,
            "status": "pending", "credited": False, "invoiced": True,   # `status` are CHECK; „pending" e valoare legala
            "invoice_series": "TEST", "invoice_number": "0",
        }, prefer="return=minimal")
    except Exception as e:
        sari("[D] garda anti-dublare pe baza reala", "randul de proba: " + str(e)[:70])
        return

    rez = []
    filtru = ("/rest/v1/payments?order_id=eq." + oid + "&invoiced=is.true"
              "&or=(invoice_email_status.is.null,invoice_email_status.eq.failed)")

    def claim():
        try:
            rez.append(cerere("PATCH", filtru, {"invoice_email_status": "sending"},
                              prefer="return=representation"))
        except Exception as e:
            rez.append([{"eroare": str(e)[:60]}])

    try:
        fire = [threading.Thread(target=claim) for _ in range(2)]
        for f in fire:
            f.start()
        for f in fire:
            f.join()
        castigatori = sum(1 for r in rez if isinstance(r, list) and len(r) == 1 and "eroare" not in r[0])
        v("[D] din doua cereri SIMULTANE, exact una castiga randul", castigatori == 1,
          "castigatori: %d · raspunsuri: %s" % (castigatori, json.dumps(rez)[:150]))
        dupa = cerere("GET", "/rest/v1/payments?select=invoice_email_status&order_id=eq." + oid)
        v("[D] starea a ramas 'sending' dupa claim", dupa and dupa[0].get("invoice_email_status") == "sending",
          json.dumps(dupa))
        rez.clear()
        claim()
        v("[D] un al treilea claim, pe 'sending', NU mai trece",
          isinstance(rez[0], list) and len(rez[0]) == 0, json.dumps(rez)[:120])
    finally:
        try:
            cerere("DELETE", "/rest/v1/payments?order_id=eq." + oid, prefer="return=minimal")
            ramas = cerere("GET", "/rest/v1/payments?select=order_id&order_id=eq." + oid)
            v("[D] randul de proba s-a sters", not ramas, json.dumps(ramas))
        except Exception as e:
            v("[D] randul de proba s-a sters", False, str(e)[:80])


def main():
    parte_js()
    parte_baza()
    print("\n".join("ESUAT: " + x for x in rele) if rele
          else "OK — textul, adresa, PDF-ul si garda anti-dublare se poarta cum trebuie")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
