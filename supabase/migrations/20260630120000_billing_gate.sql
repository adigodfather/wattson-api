-- G1 (gate facturare): alegerea de facturare pe payment + persistare pe profil (aditiv, idempotent).
-- billing_type: 'company_profile' (firma din profil) | 'company_custom' (date ad-hoc) | 'individual' (B2C)
-- billing_data: date ad-hoc opţiunea 2 (nume/CIF/adresă) + nume administrator opţiunea 1
ALTER TABLE public.payments
  ADD COLUMN IF NOT EXISTS billing_type text,
  ADD COLUMN IF NOT EXISTS billing_data jsonb;

-- persistă ultima alegere + numele administratorului (default la următoarea cumpărare; editabil)
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS last_billing_type text,
  ADD COLUMN IF NOT EXISTS admin_name text;
