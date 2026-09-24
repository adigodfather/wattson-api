-- FACTURARE SERVICII (automatizari, softuri, site-uri) — separata de facturarea CREDITELOR.
-- Creditele raman pe `payments` + seria ZN, complet neatinse. Aici traiesc clientii de servicii,
-- abonamentele lor si facturile emise pe seria de servicii.
--
-- RLS: activat FARA politici = nimeni nu ajunge la tabele prin cheia publica. Se citesc si se scriu
-- exclusiv cu service role, din rutele de admin. Datele fiscale ale clientilor n-au ce cauta in
-- browser-ul altcuiva.

CREATE TABLE IF NOT EXISTS public.clienti_servicii (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  denumire         text NOT NULL,
  cui              text NOT NULL,
  reg_com          text,
  adresa           text NOT NULL,
  -- judet + localitate: OBLIGATORII, nu optionale. e-Factura le cere pentru orice cumparator
  -- (BT-54 judetul, BT-52 localitatea), iar fara ele factura se emite dar SPV refuza transmiterea,
  -- tacut din punctul nostru de vedere. Lectia de la ZN0001.
  judet            text NOT NULL,
  localitate       text NOT NULL,
  email            text NOT NULL,
  persoana_contact text,
  activ            boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now()
);
-- Un CUI = un client. Impiedica dublurile introduse din graba, la o intalnire.
CREATE UNIQUE INDEX IF NOT EXISTS clienti_servicii_cui_idx ON public.clienti_servicii (cui);
ALTER TABLE public.clienti_servicii ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.abonamente_servicii (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id   uuid NOT NULL REFERENCES public.clienti_servicii(id) ON DELETE RESTRICT,
  descriere   text NOT NULL,
  suma_ron    numeric(12,2) NOT NULL CHECK (suma_ron > 0),
  -- COBORAT ULTERIOR LA 25 de `20260925140000_abonamente_zi25_si_eroare.sql` (decizia lui Dan).
  -- Ziua din luna se opreste la 28 DINADINS: cu 29, 30 sau 31 ar exista luni in care scadenta nu
  -- pica niciodata, iar abonamentul ar sari luni intregi fara ca nimeni sa observe.
  zi_emitere  integer NOT NULL CHECK (zi_emitere BETWEEN 1 AND 28),
  data_start  date NOT NULL,
  activ       boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);
-- ON DELETE RESTRICT (mai sus): un client cu abonamente NU poate fi sters. Altfel abonamentul ar
-- ramane activ cu un client inexistent si ar incerca sa factureze in gol la fiecare scadenta.
-- Clientii se DEZACTIVEAZA (`activ=false`), nu se sterg.
ALTER TABLE public.abonamente_servicii ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.facturi_servicii (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id     uuid NOT NULL REFERENCES public.clienti_servicii(id) ON DELETE RESTRICT,
  abonament_id  uuid REFERENCES public.abonamente_servicii(id) ON DELETE SET NULL,
  -- `perioada` ('YYYY-MM') exista DOAR la facturile de abonament si e cheia IDEMPOTENTEI.
  perioada      text,
  descriere     text NOT NULL,
  suma_ron      numeric(12,2) NOT NULL CHECK (suma_ron > 0),
  status        text NOT NULL DEFAULT 'pending',   -- pending | emisa | esuata
  serie         text,
  numar         text,
  emisa_at      timestamptz,
  smartbill_error text,
  -- Aceleasi cinci coloane ca la credite, cu aceleasi nume: mecanismul de livrare e acelasi, si
  -- asa se citesc la fel in admin.
  invoice_email_status   text,
  invoice_email_to       text,
  invoice_email_at       timestamptz,
  invoice_email_error    text,
  invoice_email_attempts integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);
-- IDEMPOTENTA ABONAMENTELOR, in BAZA nu in cod: o singura factura per abonament per luna.
-- Fluxul zilnic INSEREAZA randul INAINTE sa cheme SmartBill; daca ruleaza de doua ori, a doua
-- inserare pica pe indexul asta si nu se mai emite nimic. O factura fiscala emisa de doua ori nu se
-- sterge, se storneaza — deci garda nu are voie sa fie citeste-apoi-scrie.
CREATE UNIQUE INDEX IF NOT EXISTS facturi_servicii_abonament_perioada_idx
  ON public.facturi_servicii (abonament_id, perioada)
  WHERE abonament_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS facturi_servicii_client_idx ON public.facturi_servicii (client_id, created_at DESC);
ALTER TABLE public.facturi_servicii ENABLE ROW LEVEL SECURITY;
