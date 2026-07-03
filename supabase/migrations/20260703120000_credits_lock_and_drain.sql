-- Fix flux credite (debitare server-side pe succes + lock 1 generare/user + drain-to-zero).
-- Context: consume_credits se muta din client (configurator.tsx) in /api/generate, server-side,
-- pe calea de SUCCES. Aceasta migrare adauga: (1) lock-ul de concurenta pe profiles, (2) drain-to-zero
-- in consume_credits pentru discrepanta manual-vs-desfasurata. NU schimba facturarea (pe desfasurata reala).

-- ─────────────────────────────────────────────────────────────────────────────
-- (1) LOCK — 1 generare simultana / user. Camp nullable pe profiles + acquire/release atomice.
-- ─────────────────────────────────────────────────────────────────────────────
alter table public.profiles
  add column if not exists generating_since timestamptz;

-- ACQUIRE: reuseste (returneaza true) DOAR daca nu exista lock activ PROASPAT. TTL 5 min:
-- un lock mai vechi de 5 min (ruta a murit fara release) e considerat expirat si e "furat" ->
-- userul nu ramane blocat permanent. UPDATE...WHERE e ATOMIC (lock pe rand) -> fara race.
create or replace function public.acquire_generation_lock()
returns boolean
language plpgsql
security definer
set search_path to 'public'
as $function$
declare v_id uuid;
begin
  if auth.uid() is null then
    return false;
  end if;
  update public.profiles
    set generating_since = now()
    where id = auth.uid()
      and (generating_since is null or generating_since < now() - interval '5 minutes')
    returning id into v_id;
  return v_id is not null;   -- rand actualizat = lock obtinut; niciun rand = generare deja in curs
end;
$function$;

-- RELEASE: elibereaza neconditionat lock-ul userului (apelat in finally, pe TOATE caile).
create or replace function public.release_generation_lock()
returns void
language plpgsql
security definer
set search_path to 'public'
as $function$
begin
  if auth.uid() is null then
    return;
  end if;
  update public.profiles set generating_since = null where id = auth.uid();
end;
$function$;

revoke execute on function public.acquire_generation_lock() from anon;
revoke execute on function public.release_generation_lock() from anon;
grant execute on function public.acquire_generation_lock() to authenticated;
grant execute on function public.release_generation_lock() to authenticated;

-- ─────────────────────────────────────────────────────────────────────────────
-- (2) consume_credits — DRAIN-TO-ZERO pe discrepanta manual-vs-desfasurata (#4).
-- Sold-check-ul server (/api/generate) blocheaza generarea daca sold < cost pe MANUAL.
-- Singurul mod de a ajunge aici cu sold < cost: desfasurata reala (Vision) > manual -> cost mai mare.
-- Generarea DEJA s-a produs (Anthropic consumat) -> luam cat are userul (sold la 0) + notam shortfall,
-- FARA cont negativ, FARA a pierde proiectul. Restul (facturare pe desfasurata, idempotenta) NESCHIMBAT.
-- consume_credits e apelata DOAR de /api/generate (dupa sold-check) -> drain-ul e sigur (nu poate fi abuzat).
create or replace function public.consume_credits(
  p_surface_mp numeric,
  p_phase text,
  p_project_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  v_uid uuid := auth.uid();
  v_per_m2 integer;
  v_cost integer;
  v_balance integer;
  v_new_balance integer;
  v_desfasurata numeric;
  v_surface_final numeric;
  v_debit integer;
  v_short integer;
begin
  if v_uid is null then
    return jsonb_build_object('success', false, 'error', 'Neautentificat');
  end if;
  if p_surface_mp is null or p_surface_mp <= 0 then
    return jsonb_build_object('success', false, 'error', 'Suprafata invalida');
  end if;

  v_per_m2 := case
    when lower(regexp_replace(coalesce(p_phase, ''), '[^a-zA-Z]', '', 'g')) like '%pt%'
    then 3 else 1 end;

  -- suprafata reala (desfasurata) din proiectul PROPRIU; null -> ramane pe manual
  if p_project_id is not null then
    select (result_data->'project_info'->'surfaces'->>'desfasurata_mp')::numeric
      into v_desfasurata
      from public.projects
      where id = p_project_id and user_id = v_uid;
  end if;
  -- factureaza pe maximul dintre real si manual (niciodata sub ce declara userul)
  v_surface_final := greatest(coalesce(v_desfasurata, 0), p_surface_mp);
  v_cost := ceil(v_surface_final * v_per_m2)::integer;

  -- idempotenta (neschimbata): daca proiectul a fost deja debitat -> nu redebita
  if p_project_id is not null and exists (
    select 1 from public.credits_transactions
    where user_id = v_uid and type = 'generation'
      and note like 'proj=' || p_project_id::text || '%'
  ) then
    select credits_balance into v_balance from public.profiles where id = v_uid;
    return jsonb_build_object('success', true, 'new_balance', v_balance,
      'cost', v_cost, 'note', 'deja consumat');
  end if;

  select credits_balance into v_balance from public.profiles where id = v_uid for update;
  if not found then
    return jsonb_build_object('success', false, 'error', 'Profil inexistent');
  end if;

  -- DRAIN-TO-ZERO: daca soldul nu acopera costul (desfasurata > manual, sold-check trecuse pe manual)
  -- -> debiteaza cat are userul (sold la 0), noteaza shortfall. NICIODATA cont negativ.
  if v_balance < v_cost then
    v_debit := v_balance;          -- luam tot soldul ramas
    v_short := v_cost - v_balance; -- cat a ramas nefacturat (audit)
  else
    v_debit := v_cost;
    v_short := 0;
  end if;

  v_new_balance := v_balance - v_debit;   -- >= 0 mereu
  update public.profiles set credits_balance = v_new_balance where id = v_uid;

  -- nota auditabila: suprafata facturata + manual + desfasurata + shortfall (daca drained)
  insert into public.credits_transactions (user_id, amount, type, balance_after, note, project_id)
  values (v_uid, -v_debit, 'generation', v_new_balance,
    'proj=' || coalesce(p_project_id::text, 'n/a')
      || ' ' || coalesce(p_phase, '') || ' ' || v_surface_final::text || 'mp'
      || ' (man=' || p_surface_mp::text || ', desf=' || coalesce(v_desfasurata::text, 'null') || ')'
      || case when v_short > 0 then ' DRAIN short=' || v_short::text else '' end,
    p_project_id);

  return jsonb_build_object('success', true, 'new_balance', v_new_balance, 'cost', v_cost,
    'billed', v_debit, 'shortfall', v_short, 'drained', (v_short > 0),
    'surface_billed', v_surface_final, 'manual', p_surface_mp, 'desfasurata', v_desfasurata);
end;
$function$;
