-- URMA TRIMITERII FACTURII pe email (aditiv, idempotent).
-- Factura e DEJA emisa si in SPV cand ajungem aici: pasii de dupa n-au voie sa strice nimic, dar
-- TREBUIE sa se vada. Pana acum nu exista nicio coloana care sa spuna daca clientul a primit
-- factura, deci la intrebarea „a primit clientul X factura?" nu se putea raspunde deloc.
--
-- invoice_email_status: NULL (neincercat) | 'sending' | 'sent' | 'failed'
--   'sending' e CHEIA anti-dublare: se trece cu UPDATE conditionat intr-o singura instructiune
--   (`... where invoice_email_status is distinct from 'sent' and ... 'sending' returning`), deci
--   din doua cereri simultane exact una primeste randul inapoi. Garda sta in baza, nu intr-un `if`.
--   Un 'sending' ramas agatat (proces cazut la mijloc) se deblocheaza din pagina de admin.
-- invoice_email_to: adresa EXACTA la care s-a trimis — aceeasi pe care a primit-o SmartBill.
-- invoice_email_error: ultimul motiv de esec, ca sa fie vizibil fara sa cauti in loguri.
-- invoice_email_attempts: cate incercari s-au facut (retry manual din admin).
ALTER TABLE public.payments
  ADD COLUMN IF NOT EXISTS invoice_email_status   text,
  ADD COLUMN IF NOT EXISTS invoice_email_to       text,
  ADD COLUMN IF NOT EXISTS invoice_email_at       timestamptz,
  ADD COLUMN IF NOT EXISTS invoice_email_error    text,
  ADD COLUMN IF NOT EXISTS invoice_email_attempts integer NOT NULL DEFAULT 0;

-- Indexul serveste exact intrebarea pe care si-o pune Dan in admin: „ce facturi N-au plecat?"
CREATE INDEX IF NOT EXISTS payments_invoice_email_status_idx
  ON public.payments (invoice_email_status)
  WHERE invoiced = true;
