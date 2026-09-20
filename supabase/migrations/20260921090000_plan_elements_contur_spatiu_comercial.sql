-- CONTURUL DE SPATIU COMERCIAL (P6b): poligonul care spune „aceste camere sunt magazinul SP1".
-- Acelasi mecanism ca `contur_apartament` — puncte in `cable_path`, deci nicio coloana noua.
--
-- DE CE TIP NOU SI NU UN FLAG PE CONTURUL DE APARTAMENT:
-- singurul flag care n-ar fi cerut o coloana noua era prefixul ETICHETEI („SP1" fata de „P1_5"),
-- iar eticheta e un camp LIBER, editabil de inginer. Tipul dedus dintr-o eticheta editabila
-- inseamna ca o redenumire muta TACIT circuitele de pe TE-SP pe TE-AP — greşit si plauzibil. Un
-- flag pe o coloana noua ar fi costat exact aceeasi migratie ca un tip nou, dar fara sa dea
-- conturului buton propriu in editor si simbol propriu in legenda.
--
-- CE REPARA, masurat: pana acum elementele unui spatiu comercial de la parterul unui bloc nu cadeau
-- in niciun contur, deci ajungeau in grupul COMUN -> pe TCC, tabloul consumatorilor comuni. Mai rau,
-- iluminatul magazinului se contopea cu al casei scarii intr-un singur circuit „Iluminat parter",
-- fiindca `compute_circuits` face bin-packing peste tot ce primeste in acelasi apel.
--
-- DE CE MIGRATIA E OBLIGATORIE INAINTE DE DEPLOY (lectia panou_led):
-- `save_plan_elements` e NON-BLOCANT — daca un element_type lipseste din CHECK, insert-ul pica, dar
-- eroarea nu opreste fluxul: se pierd TACIT TOATE elementele etajului, nu doar cel nou. In august,
-- `panou_led` / `banda_led_path` / `banda_led_driver` au stat asa zile intregi: 0 randuri din 1246.
-- ORDINEA NE-NEGOCIABILA: migratia -> push -> verificare Render.
--
-- Lista = cele 68 de valori de dupa migratia 20260920140000 (conturul de apartament), plus una
-- singura. ADITIV: nicio valoare nu se scoate, deci niciun rand existent nu devine invalid.
-- ALTER-ul e validat pe randurile existente — daca vreo valoare din baza ar lipsi din lista,
-- migratia esueaza ZGOMOTOS.

alter table public.plan_elements drop constraint if exists chk_element_type;

alter table public.plan_elements add constraint chk_element_type check (element_type in (
  -- iluminat
  'lustra_led', 'aplica_tavan', 'aplica_perete', 'aplica_senzor', 'panou_led', 'banda_led',
  'corp_evacuare', 'banda_led_path', 'banda_led_driver',
  'intrerupator_simplu', 'intrerupator_cap_scara', 'intrerupator_dublu', 'intrerupator_triplu',
  -- tablouri (existente + FV)
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
  -- tablourile de bloc (P1)
  'tablou_bmpt', 'tablou_tgd', 'tablou_fdcp', 'tablou_fdcs',
  'tablou_te_ap', 'tablou_te_sp', 'tablou_consumatori_comuni',
  'tablou_tecv', 'tablou_tep', 'tablou_te_lift',
  -- contururi de grupare (P2 + P6b)
  'contur_apartament',
  -- ── NOU (P6b) ────────────────────────────────────────────────────────────────────────────────
  'contur_spatiu_comercial'
));

comment on constraint chk_element_type on public.plan_elements is
  'Tipurile de element de plan. 69 valori (21 sept 2026: + contur_spatiu_comercial). '
  'ATENTIE: tablou_tcc = T.CC, tabloul de CURENT CONTINUU al fotovoltaicului; consumatorii comuni '
  'ai blocului sunt tablou_consumatori_comuni - acelasi acronim TCC, aparate diferite.';
