-- Limite de rata pe rutele care consuma procesare reala (FastAPI pe o singura instanta de 512 MB,
-- plus Anthropic Vision). Un singur utilizator care insista poate consuma bugetul si opri serviciul
-- pentru toti ceilalti — exact ce s-a intamplat cand un plan de bloc a doborat instanta.
--
-- UNDE STA CONTORUL SI DE CE IN BAZA:
-- rutele sunt functii serverless pe Vercel, deci nu au memorie proprie intre invocari si pot rula
-- in instante diferite in paralel. Un contor in memorie ar fi resetat la fiecare pornire la rece
-- si n-ar fi vazut de celelalte instante — adica n-ar limita nimic. Postgres e singurul loc comun,
-- si e deja tiparul folosit la chat (`/api/chat` numara randurile de azi din `chat_messages`).
--
-- UN RAND PE CERERE, nu un contor agregat. Costa cateva randuri pe zi in plus, dar raspunde la
-- intrebarea la care azi NU se poate raspunde: cate cereri face de fapt un proiect real, pe fiecare
-- ruta. `audit_log` exista de mult si e GOL — n-a scris nimeni in el niciodata, deci nu exista
-- telemetrie. Tabelul asta e si garda, si masuratoarea care lipseste: dupa cateva zile de trafic
-- real, pragurile se pot stramta pe cifre, nu pe presupuneri.
create table if not exists public.rate_events (
  id          bigserial primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  ruta        text not null,
  succes      boolean,          -- null = cerere pornita, inca fara verdict
  created_at  timestamptz not null default now()
);

-- Interogarile sunt mereu „ultimele N ale ACESTUI user": index pe (user, timp) si pe (user, ruta, timp).
create index if not exists rate_events_user_timp_idx on public.rate_events (user_id, created_at desc);
create index if not exists rate_events_user_ruta_timp_idx on public.rate_events (user_id, ruta, created_at desc);

-- RLS activat FARA politici = numai `service_role`. Utilizatorul nu trebuie sa-si poata nici citi,
-- nici — mai ales — sterge propriile randuri: un contor pe care subiectul il poate goli nu e contor.
alter table public.rate_events enable row level security;

comment on table public.rate_events is
  'Contor de limitare pe utilizator + telemetrie de frecventa. Scris DOAR cu service role din rutele API.';
comment on column public.rate_events.succes is
  'null = pornita; true/false = verdictul. Pauza dupa esecuri se uita la ultimele randuri cu verdict.';
