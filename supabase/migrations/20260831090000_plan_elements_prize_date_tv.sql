-- PRIZE DE DATE SI TV pe planşa de curenti slabi: trei tipuri noi de element.
--   priza_date   — priza de date RJ45 (cat. 5e/6)
--   priza_tv     — priza TV (coaxiala)
--   priza_mixta  — priza mixta, date + TV in aceeasi doza
--
-- DE CE MIGRATIA E OBLIGATORIE INAINTE DE DEPLOY (lectia panou_led):
-- `save_plan_elements` e NON-BLOCANT — daca un element_type lipseste din CHECK, insert-ul pica, dar
-- eroarea nu opreste fluxul: se pierd TACIT TOATE elementele etajului, nu doar cel nou. In august,
-- `panou_led` / `banda_led_path` / `banda_led_driver` au stat asa zile intregi: 0 randuri din 1246.
-- ORDINEA NE-NEGOCIABILA: migratia -> push -> verificare Render.
--
-- Constraint-ul se reface intreg (Postgres n-are "add value to CHECK"): 43 valori -> 46.
-- Aditiv pur: nicio valoare existenta nu se scoate, deci niciun rand existent nu devine invalid.

alter table public.plan_elements drop constraint if exists chk_element_type;

alter table public.plan_elements add constraint chk_element_type check (element_type in (
  -- iluminat
  'lustra_led', 'aplica_tavan', 'aplica_perete', 'aplica_senzor', 'panou_led', 'banda_led',
  'corp_evacuare', 'banda_led_path', 'banda_led_driver',
  'intrerupator_simplu', 'intrerupator_cap_scara', 'intrerupator_dublu', 'intrerupator_triplu',
  -- tablouri
  'tablou_teg', 'tablou_tes', 'tablou_te_ct', 'transformator',
  'tablou_tcc', 'tablou_inv', 'tablou_tca',
  -- forta
  'priza_simpla', 'priza_dubla', 'priza_16a', 'priza_exterior_ip44',
  'legenda', 'traseu', 'ground_electrode_path', 'fv_chain_path',
  'alimentare_receptor', 'receptor_internet',
  -- curenti slabi: efractie
  'centrala_efractie', 'tastatura_efractie', 'detector_pir', 'contact_magnetic',
  'sirena_interioara', 'sirena_exterioara', 'buton_panica',
  -- curenti slabi: supraveghere video
  'camera_video', 'nvr', 'rack_9u', 'sursa_alimentare_cs', 'doza_cs', 'traseu_cs',
  -- curenti slabi: distributie date si TV (NOU)
  'priza_date', 'priza_tv', 'priza_mixta'
));

comment on constraint chk_element_type on public.plan_elements is
  'Tipurile de element admise pe planşe. ADITIV: valorile se ADAUGA, nu se scot — un tip lipsa face save_plan_elements sa piarda TACIT toate elementele etajului. 46 valori (31 aug 2026: + priza_date, priza_tv, priza_mixta).';
