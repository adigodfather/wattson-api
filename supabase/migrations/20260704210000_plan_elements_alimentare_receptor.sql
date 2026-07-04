-- Bucata A receptoare (pilot): permite element_type 'alimentare_receptor' in plan_elements.
-- Toate receptoarele de alimentare (boiler/cuptor/AC/HRV/EV) folosesc ACEST tip + `label`
-- pentru distinctie; simbolul pe PDF = "alimentare directa" existenta (priza_16a), refolosit.
-- Aditiv / backward-compatible: doar extinde CHECK-ul chk_element_type cu o valoare noua.
-- Reversibil: DROP + ADD constraint fara 'alimentare_receptor' (dupa stergerea eventualelor randuri).

alter table public.plan_elements drop constraint if exists chk_element_type;

alter table public.plan_elements add constraint chk_element_type check (
  element_type = any (array[
    'lustra_led', 'aplica_tavan', 'aplica_perete', 'aplica_senzor', 'banda_led',
    'intrerupator_simplu', 'intrerupator_cap_scara', 'intrerupator_dublu', 'intrerupator_triplu',
    'tablou_teg', 'tablou_tes', 'tablou_te_ct', 'transformator',
    'priza_simpla', 'priza_dubla', 'priza_16a', 'priza_exterior_ip44',
    'legenda', 'traseu', 'ground_electrode_path',
    'alimentare_receptor'
  ])
);
