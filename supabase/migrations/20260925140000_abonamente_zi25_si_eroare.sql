-- Doua decizii ale lui Dan, amandoua aditive si verificate inainte de aplicare.
--
-- [1] ZIUA DE EMITERE: maximum 25, nu 28.
-- Cu plafonul la 25 problema lunilor scurte dispare COMPLET, fara nicio regula speciala nicaieri:
-- 25 exista in orice luna, inclusiv februarie, inclusiv in an bisect. La 28 ar fi mers si el, dar
-- 25 lasa si marja de cateva zile pana la finalul lunii. Verificat inainte: zero abonamente cu
-- ziua 26..28, deci CHECK-ul nou nu are ce sa respinga retroactiv.
ALTER TABLE public.abonamente_servicii DROP CONSTRAINT IF EXISTS abonamente_servicii_zi_emitere_check;
ALTER TABLE public.abonamente_servicii
  ADD CONSTRAINT abonamente_servicii_zi_emitere_check CHECK (zi_emitere BETWEEN 1 AND 25);

-- [2] ESECUL SE VEDE LANGA ABONAMENT, cu motivul.
-- Pana acum un esec traia doar pe randul de factura. Dar intrebarea pe care si-o pune Dan nu e
-- „ce factura a picat", ci „care abonament nu si-a facut treaba" — deci raspunsul sta pe abonament.
-- Fara email, deocamdata: ecranul e sursa de adevar.
ALTER TABLE public.abonamente_servicii
  ADD COLUMN IF NOT EXISTS ultima_rulare_at  timestamptz,
  ADD COLUMN IF NOT EXISTS ultima_eroare     text,
  ADD COLUMN IF NOT EXISTS ultima_perioada   text;   -- ultima luna facturata cu succes ('YYYY-MM')
