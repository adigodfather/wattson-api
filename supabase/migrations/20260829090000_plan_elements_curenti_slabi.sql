-- CURENTI SLABI: plansa separata de anti-efractie + supraveghere video.
-- Doua constraint-uri intr-o singura migratie, fiindca planşa fara elemente (sau invers) n-are sens.
--
-- ORDINE DE APLICARE (Dan): ACEASTA migratie INAINTE de deploy-ul care scrie 'curenti_slabi' sau
-- tipurile noi. `save_plan_elements` e NON-BLOCANT (inghite eroarea de INSERT), deci un tip lipsa
-- din CHECK nu da eroare vizibila — pierde TACUT toate elementele etajului. S-a intamplat deja:
-- panou_led, banda_led_path si banda_led_driver au ajuns in cod fara migratie si au stat luni de
-- zile respinse de constraint (0 randuri din 1246), reparate abia de migratia 20260828120000.
--
-- Ambele ALTER-uri sunt VALIDATE pe randurile existente: daca vreo valoare din baza lipseste din
-- lista de mai jos, migratia esueaza ZGOMOTOS si nu strica nimic.

-- ── 1. plan_type: al treilea plan ────────────────────────────────────────────────────────────
-- 'ambele' ramane pentru elementele care apar pe MAI MULTE planse (tablourile).
alter table public.plan_elements drop constraint if exists chk_plan_type;

alter table public.plan_elements add constraint chk_plan_type check (
  plan_type = any (array['iluminat', 'forta', 'curenti_slabi', 'ambele'])
);

-- ── 2. element_type: cele 13 tipuri de curenti slabi ─────────────────────────────────────────
-- Lista = cele 30 existente (migratia 20260828120000) + 13 noi. DVR-ul e INTENTIONAT absent:
-- sistemele noi sunt IP, deci doar NVR (decizia Dan). `contact_magnetic` e adaugat desi lipseste
-- din planurile de referinta — e standard la efractie.
alter table public.plan_elements drop constraint if exists chk_element_type;

alter table public.plan_elements add constraint chk_element_type check (
  element_type = any (array[
    -- corpuri de iluminat
    'lustra_led', 'aplica_tavan', 'aplica_perete', 'aplica_senzor', 'panou_led', 'banda_led',
    -- iluminat de siguranta
    'corp_evacuare',
    -- banda LED: traseul desenat + driverul lui
    'banda_led_path', 'banda_led_driver',
    -- aparataj
    'intrerupator_simplu', 'intrerupator_cap_scara', 'intrerupator_dublu', 'intrerupator_triplu',
    -- tablouri (inclusiv FV)
    'tablou_teg', 'tablou_tes', 'tablou_te_ct', 'transformator',
    'tablou_tcc', 'tablou_inv', 'tablou_tca',
    -- prize
    'priza_simpla', 'priza_dubla', 'priza_16a', 'priza_exterior_ip44',
    -- desen (trasee) + legenda
    'legenda', 'traseu', 'ground_electrode_path', 'fv_chain_path',
    -- receptoare
    'alimentare_receptor', 'receptor_internet',
    -- ── CURENTI SLABI: efractie (7) ──
    'centrala_efractie', 'tastatura_efractie', 'detector_pir', 'contact_magnetic',
    'sirena_interioara', 'sirena_exterioara', 'buton_panica',
    -- ── CURENTI SLABI: supraveghere video (5) ──
    -- camera_video acopera si interiorul si exteriorul: distinctia sta in `label`
    -- ("interior"/"exterior"), ca montajul tablourilor FV. Simbolul e acelasi.
    'camera_video', 'nvr', 'rack_9u', 'sursa_alimentare_cs', 'doza_cs',
    -- ── CURENTI SLABI: traseul desenat manual (1) ──
    -- ca banda_led_path / ground_electrode_path: metrii ies din desen, nu din calcul
    'traseu_cs'
  ])
);
