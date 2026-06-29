-- SB2: coloane pentru factura SmartBill pe payments (aditiv, idempotent).
-- invoiced       = factura a fost emisa (idempotenta la IPN repetat -> nu emite de 2 ori)
-- invoice_number = numarul facturii returnat de SmartBill
-- invoice_series = seria facturii returnata de SmartBill
ALTER TABLE public.payments
  ADD COLUMN IF NOT EXISTS invoiced       boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS invoice_number text,
  ADD COLUMN IF NOT EXISTS invoice_series text;
