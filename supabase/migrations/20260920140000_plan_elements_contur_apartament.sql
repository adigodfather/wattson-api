-- CONTURUL DE APARTAMENT (P2): poligonul desenat manual care spune „aceste camere sunt un
-- apartament". Element de tip poligon, ca `ground_electrode_path` si `fv_chain_path` — punctele
-- stau in `cable_path`, deci nu apare nicio coloana noua.
--
-- Decizia lui Dan (20 sept 2026): se deseneaza pe FIECARE NIVEL care are apartamente, nu o data
-- proiectat in sus. Parterul blocului lui are 4 apartamente cu alt layout decat etajele 1-2 (noua
-- fiecare), iar E3 retras are cinci cu al treilea layout: un singur set de contururi n-ar putea
-- descrie toate trei.
--
-- DE CE MIGRATIA E OBLIGATORIE INAINTE DE DEPLOY (lectia panou_led):
-- `save_plan_elements` e NON-BLOCANT — daca un element_type lipseste din CHECK, insert-ul pica, dar
-- eroarea nu opreste fluxul: se pierd TACIT TOATE elementele etajului, nu doar cel nou. In august,
-- `panou_led` / `banda_led_path` / `banda_led_driver` au stat asa zile intregi: 0 randuri din 1246.
-- ORDINEA NE-NEGOCIABILA: migratia -> push -> verificare Render.
--
-- Lista = cele 67 de valori de dupa migratia 20260920120000 (tablourile de bloc), copiate din
-- constrangerea CURENTA a bazei, plus una singura. ADITIV: nicio valoare nu se scoate, deci niciun
-- rand existent nu devine invalid. ALTER-ul e validat pe randurile existente — daca vreo valoare
-- din baza ar lipsi din lista, migratia esueaza ZGOMOTOS.

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
  -- ── NOU (P2) ─────────────────────────────────────────────────────────────────────────────────
  'contur_apartament'
));

comment on constraint chk_element_type on public.plan_elements is
  'Tipurile de element de plan. 68 valori (20 sept 2026: + contur_apartament). '
  'ATENTIE: tablou_tcc = T.CC, tabloul de CURENT CONTINUU al fotovoltaicului; consumatorii comuni '
  'ai blocului sunt tablou_consumatori_comuni - acelasi acronim TCC, aparate diferite.';
