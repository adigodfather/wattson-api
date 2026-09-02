-- DETECTIE INCENDIU SI DESFUMARE: a PATRA planşa, cu cele zece tipuri de element ale ei.
--   detectie (6): detector_fum · detector_caldura · centrala_detectie · buton_incendiu ·
--                 sirena_incendiu · panou_repetor
--   desfumare (4): trapa_desfumare · ventilator_desfumare · clapeta_antifoc · grila_admisie
--
-- DE CE MIGRATIA E OBLIGATORIE INAINTE DE DEPLOY (lectia panou_led):
-- `save_plan_elements` e NON-BLOCANT — daca un element_type lipseste din CHECK, insert-ul pica, dar
-- eroarea nu opreste fluxul: se pierd TACIT TOATE elementele etajului, nu doar cel nou. In august,
-- `panou_led` / `banda_led_path` / `banda_led_driver` au stat asa zile intregi: 0 randuri din 1246.
-- ORDINEA NE-NEGOCIABILA: migratia -> push -> verificare Render.
--
-- TREI bucati, intr-o singura migratie: planşa fara tipurile ei (sau invers) n-are sens, iar raza
-- fara tipuri n-are pe ce sa se aplice. Toate ADITIVE: nicio valoare existenta nu se scoate, deci
-- niciun rand existent nu devine invalid. Ambele ALTER-uri de CHECK sunt validate pe randurile
-- existente — daca vreo valoare din baza ar lipsi din lista, migratia esueaza ZGOMOTOS.

-- ── 1. plan_type: a PATRA planşa ─────────────────────────────────────────────────────────────
-- 'ambele' ramane pentru elementele care apar pe MAI MULTE planse (tablourile). Detectia NU intra
-- in 'ambele': echipamentele ei traiesc numai pe planşa lor, ca cele de curenti slabi.
alter table public.plan_elements drop constraint if exists chk_plan_type;

alter table public.plan_elements add constraint chk_plan_type check (
  plan_type = any (array['iluminat', 'forta', 'curenti_slabi', 'detectie_incendiu', 'ambele'])
);

comment on constraint chk_plan_type on public.plan_elements is
  'Planşele pe care poate trai un element. 5 valori (2 sept 2026: + detectie_incendiu). ''ambele'' = iluminat SI forta (tablourile).';

-- ── 2. element_type: cele 10 tipuri noi ──────────────────────────────────────────────────────
-- Lista = cele 46 existente (migratia 20260831090000, copiate DIN EA cuvant cu cuvant) + 10 noi.
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
  -- curenti slabi: distributie date si TV
  'priza_date', 'priza_tv', 'priza_mixta',
  -- ── DETECTIE INCENDIU (6) — NOU ──
  -- detectoarele au cerc de acoperire; raza vine din `arie_acoperire_mp` (vezi bucata 3)
  'detector_fum', 'detector_caldura', 'centrala_detectie', 'buton_incendiu',
  'sirena_incendiu', 'panou_repetor',
  -- ── DESFUMARE (4) — NOU ──
  -- ventilatorul si trapa MOTORIZATA au putere reala (230/400 V); grila e pasiva, 0 W.
  -- Trapa are doua variante (motorizata / pneumatica), alese per element prin `label`.
  'trapa_desfumare', 'ventilator_desfumare', 'clapeta_antifoc', 'grila_admisie'
));

comment on constraint chk_element_type on public.plan_elements is
  'Tipurile de element admise pe planşe. ADITIV: valorile se ADAUGA, nu se scot — un tip lipsa face save_plan_elements sa piarda TACIT toate elementele etajului. 56 valori (2 sept 2026: + cele 10 de detectie incendiu si desfumare).';

-- ── 3. aria de acoperire a detectorului ──────────────────────────────────────────────────────
-- DE CE COLOANA NOUA si nu `label`: `label` poarta deja montajul la camere ("interior"/"exterior")
-- si tipul de cablu la trasee, si e citit ca atare in mai multe locuri. Acelasi rationament ca la
-- `camera_tip`: ce determina GEOMETRIA desenata primeste camp propriu.
--
-- DE CE NUMERIC si nu text: valoarea E un numar (metri patrati), iar raza se calculeaza din ea.
-- Text ar fi insemnat comparatii '60' != 60 in patru limbaje diferite. Lista inchisa se pastreaza
-- prin CHECK, deci se castiga si tipul, si imposibilitatea de a scrie o valoare din afara tabelului.
-- Treptele sunt cele din P118/3-2015, tabelul 3.4 (distanta maxima orizontala, tavan sub 20 grade):
--   20 mp -> DH 3,3 m · 40 -> 4,7 · 60 -> 5,7 · 80 -> 6,6 · 100 -> 7,4
-- NULL = detectorul isi ia valoarea implicita din cod (fum 60 mp, caldura 20 mp), ca la `camera_tip`.
alter table public.plan_elements
  add column if not exists arie_acoperire_mp smallint;

alter table public.plan_elements drop constraint if exists chk_arie_acoperire_mp;

alter table public.plan_elements add constraint chk_arie_acoperire_mp check (
  arie_acoperire_mp is null or arie_acoperire_mp in (20, 40, 60, 80, 100)
);

comment on column public.plan_elements.arie_acoperire_mp is
  'Aria acoperita de un detector de incendiu (mp), din treptele P118/3-2015 tab. 3.4: 20/40/60/80/100. Raza desenata se calculeaza din ea. NULL -> valoarea implicita din cod (fum 60, caldura 20).';
