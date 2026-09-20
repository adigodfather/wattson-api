-- COPIEREA INTRE APARTAMENTE IDENTICE (P4): marcajul „de aici am primit continutul".
--
-- IDEMPOTENTA e punctul delicat al pachetului, si de-aia marcajul sta pe CONTURUL TINTA, nu pe
-- fiecare element copiat:
--   pe elemente ar fi insemnat ca stergerea unui bec copiat sterge si dovada ca s-a copiat — la
--   urmatoarea deschidere a etajului becul ar reveni, si inginerul n-ar putea CORECTA nimic;
--   pe contur, copierea se intampla O SINGURA DATA per apartament. Ce sterge sau muta inginerul
--   dupa aceea ramane asa, fiindca nimeni nu se mai uita.
--
-- Inginerul poate cere o RE-COPIERE golind campul (sau stergand si redesenand conturul) — deci
-- automatismul ramane corectabil in ambele sensuri, nu doar „sterg ce nu-mi place".
--
-- NULLABLE si FARA valoare implicita: toate cele 1291 de randuri existente raman valide neatinse,
-- iar absenta lui inseamna exact ce inseamna azi — „n-a fost copiat nimic aici".
--
-- ON DELETE SET NULL: daca inginerul sterge conturul SURSA, tinta nu devine invalida si nici nu se
-- sterge — doar uita de unde a primit. Copierea nu se reia, fiindca apartamentul nu mai e gol.

alter table public.plan_elements
  add column if not exists copiat_din uuid
  references public.plan_elements (id) on delete set null;

comment on column public.plan_elements.copiat_din is
  'Doar pe contur_apartament: id-ul conturului SURSA de la care apartamentul a primit continutul '
  '(P4). NULL = nu s-a copiat inca. Marcajul sta pe contur, nu pe elemente, ca stergerea unui '
  'element copiat sa nu declanseze o re-copiere si inginerul sa poata corecta.';

-- Cautarea „ce contururi au primit deja continut" merge pe (project_id, floor) la deschiderea
-- etajului; indexul partial tine doar randurile care chiar au marcajul (azi: zero).
create index if not exists idx_plan_elements_copiat_din
  on public.plan_elements (project_id, floor)
  where copiat_din is not null;
