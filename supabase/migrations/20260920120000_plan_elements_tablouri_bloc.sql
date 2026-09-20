-- TABLOURILE DE BLOC (P1): cele zece tipuri ale ierarhiei pe patru niveluri.
--   firide de distributie: tablou_bmpt · tablou_tgd · tablou_fdcp · tablou_fdcs
--   tablouri:              tablou_te_ap · tablou_te_sp · tablou_consumatori_comuni ·
--                          tablou_tecv · tablou_tep · tablou_te_lift
--
-- DE CE MIGRATIA E OBLIGATORIE INAINTE DE DEPLOY (lectia panou_led):
-- `save_plan_elements` e NON-BLOCANT — daca un element_type lipseste din CHECK, insert-ul pica, dar
-- eroarea nu opreste fluxul: se pierd TACIT TOATE elementele etajului, nu doar cel nou. In august,
-- `panou_led` / `banda_led_path` / `banda_led_driver` au stat asa zile intregi: 0 randuri din 1246.
-- ORDINEA NE-NEGOCIABILA: migratia -> push -> verificare Render.
--
-- COLIZIUNEA DE NUME, rezolvata explicit: `tablou_tcc` EXISTA DEJA in lista de mai jos si inseamna
-- T.CC, tabloul de curent CONTINUU al fotovoltaicului — opt proiecte din baza il folosesc asa.
-- Blocul cheama TCC „Tablou Consumatori Comuni": acelasi acronim, alt aparat. De aceea tipul NOU se
-- numeste `tablou_consumatori_comuni`, pe litere. Nicio valoare existenta nu se redenumeste, deci
-- niciun rand din baza nu se atinge si nu exista fereastra in care FV-ul sa fie invalid.
--
-- Lista de mai jos e cele 57 de valori EXISTENTE, copiate din constrangerea CURENTA a bazei
-- (`pg_get_constraintdef`, nu din alt fisier de migratie), plus cele 10 noi. Totul ADITIV: nicio
-- valoare nu se scoate, deci niciun rand existent nu devine invalid. ALTER-ul e validat pe randurile
-- existente — daca vreo valoare din baza ar lipsi din lista, migratia esueaza ZGOMOTOS.

alter table public.plan_elements drop constraint if exists chk_element_type;

alter table public.plan_elements add constraint chk_element_type check (element_type in (
  -- iluminat
  'lustra_led', 'aplica_tavan', 'aplica_perete', 'aplica_senzor', 'panou_led', 'banda_led',
  'corp_evacuare', 'banda_led_path', 'banda_led_driver',
  'intrerupator_simplu', 'intrerupator_cap_scara', 'intrerupator_dublu', 'intrerupator_triplu',
  -- tablouri (existente)
  'tablou_teg', 'tablou_tes', 'tablou_te_ct', 'transformator',
  'tablou_tcc', 'tablou_inv', 'tablou_tca',
  -- prize + trasee
  'priza_simpla', 'priza_dubla', 'priza_16a', 'priza_exterior_ip44',
  'legenda', 'traseu', 'ground_electrode_path', 'fv_chain_path',
  'alimentare_receptor', 'receptor_internet',
  -- curenti slabi
  'centrala_efractie', 'tastatura_efractie', 'detector_pir', 'contact_magnetic',
  'sirena_interioara', 'sirena_exterioara', 'buton_panica', 'camera_video', 'nvr', 'rack_9u',
  'sursa_alimentare_cs', 'doza_cs', 'traseu_cs', 'priza_date', 'priza_tv', 'priza_mixta',
  -- detectie incendiu + desfumare
  'detector_fum', 'detector_caldura', 'centrala_detectie', 'buton_incendiu', 'sirena_incendiu',
  'panou_repetor', 'trapa_desfumare', 'ventilator_desfumare', 'clapeta_antifoc', 'grila_admisie',
  'coborare_cabluri',
  -- ── NOI (P1, tablourile de bloc) ─────────────────────────────────────────────────────────────
  'tablou_bmpt', 'tablou_tgd', 'tablou_fdcp', 'tablou_fdcs',
  'tablou_te_ap', 'tablou_te_sp', 'tablou_consumatori_comuni',
  'tablou_tecv', 'tablou_tep', 'tablou_te_lift'
));

comment on constraint chk_element_type on public.plan_elements is
  'Tipurile de element de plan. 67 valori (20 sept 2026: + cele 10 tablouri de bloc). '
  'ATENTIE: tablou_tcc = T.CC, tabloul de CURENT CONTINUU al fotovoltaicului; consumatorii comuni '
  'ai blocului sunt tablou_consumatori_comuni — acelasi acronim TCC, aparate diferite.';
