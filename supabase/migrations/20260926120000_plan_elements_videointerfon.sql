-- VIDEOINTERFONUL LA BLOC (P7b): patru tipuri noi de element, toate plasate MANUAL de inginer pe
-- planşa de curenti slabi — panoul de apel, cititorul de control acces, yala electromagnetica si
-- postul interior. Sursa sistemului NU e un tip nou: e un `alimentare_receptor` („Sursa interfon"),
-- deci trece pe TCC ca orice consumator din spatiul comun. Butoanele de iesire si de sonerie se
-- NUMARA (unul per yala, unul per post), nu se deseneaza, deci nici ele nu cer tipuri.
--
-- DE CE MIGRATIA E OBLIGATORIE INAINTE DE DEPLOY (lectia panou_led, repetata la fiecare tip nou):
-- un element_type care lipseste din CHECK face insert-ul sa pice, iar salvarea din editor nu se
-- opreste — elementul se pierde TACUT. In august, `panou_led` / `banda_led_path` /
-- `banda_led_driver` au stat asa zile intregi: 0 randuri din 1246.
-- ORDINEA NE-NEGOCIABILA: migratia -> push -> verificare Render.
--
-- Lista = cele 69 de valori de dupa migratia 20260921090000 (conturul de spatiu comercial), plus
-- patru. ADITIV: nicio valoare nu se scoate, deci niciun rand existent nu devine invalid. ALTER-ul se
-- valideaza pe randurile existente — daca vreo valoare din baza ar lipsi din lista, migratia esueaza
-- ZGOMOTOS, nu tacut.

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
  'contur_apartament', 'contur_spatiu_comercial',
  -- ── NOU (P7b): videointerfonul la bloc ───────────────────────────────────────────────────────
  'panou_apel_interfon', 'cititor_control_acces', 'yala_electromagnetica', 'post_interior_interfon'
));

comment on constraint chk_element_type on public.plan_elements is
  'Tipurile de element de plan. 73 valori (26 sept 2026: + videointerfonul la bloc - panou de apel, '
  'cititor control acces, yala electromagnetica, post interior). '
  'ATENTIE: tablou_tcc = T.CC, tabloul de CURENT CONTINUU al fotovoltaicului; consumatorii comuni '
  'ai blocului sunt tablou_consumatori_comuni - acelasi acronim TCC, aparate diferite.';
