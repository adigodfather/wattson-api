-- consume_credits: consum atomic de Z-Coins la generare (A5).
-- SECURITY DEFINER. Userul = auth.uid() INTERN (clientul NU trimite user_id).
-- Costul se calculeaza SERVER-SIDE din surface_mp + faza (anti-frauda, ca la plata).
-- Idempotenta pe p_project_id (un proiect = un singur consum).
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
begin
  if v_uid is null then
    return jsonb_build_object('success', false, 'error', 'Neautentificat');
  end if;
  if p_surface_mp is null or p_surface_mp <= 0 then
    return jsonb_build_object('success', false, 'error', 'Suprafata invalida');
  end if;

  -- PRET SERVER-SIDE (oglindeste CREDIT_PRICING din lib): DTAC=1/mp, DTAC+PT=3/mp.
  -- Regula faza: contine 'PT' -> 3 (DTAC+PT); altfel (DTAC) -> 1.
  v_per_m2 := case when upper(coalesce(p_phase, '')) like '%PT%' then 3 else 1 end;
  v_cost := ceil(p_surface_mp * v_per_m2)::integer;

  -- IDEMPOTENTA: daca exista deja un consum 'generation' pentru acest project_id -> nu re-scadem.
  -- (project_id codat in note ca 'proj=<uuid>...'; credits_transactions nu are coloana project_id.)
  if p_project_id is not null and exists (
    select 1 from public.credits_transactions
    where user_id = v_uid and type = 'generation'
      and note like 'proj=' || p_project_id::text || '%'
  ) then
    select credits_balance into v_balance from public.profiles where id = v_uid;
    return jsonb_build_object('success', true, 'new_balance', v_balance,
      'cost', v_cost, 'note', 'deja consumat');
  end if;

  -- LOCK pe randul de profil (atomicitate)
  select credits_balance into v_balance from public.profiles where id = v_uid for update;
  if not found then
    return jsonb_build_object('success', false, 'error', 'Profil inexistent');
  end if;

  if v_balance < v_cost then
    return jsonb_build_object('success', false, 'error', 'Sold insuficient',
      'cost', v_cost, 'balance', v_balance);
  end if;

  v_new_balance := v_balance - v_cost;
  update public.profiles set credits_balance = v_new_balance where id = v_uid;

  -- amount NEGATIV (conventie consum; add_credits_from_purchase foloseste pozitiv la creditare)
  insert into public.credits_transactions (user_id, amount, type, balance_after, note)
  values (v_uid, -v_cost, 'generation', v_new_balance,
    'proj=' || coalesce(p_project_id::text, 'n/a')
      || ' ' || coalesce(p_phase, '') || ' ' || p_surface_mp::text || 'mp');

  return jsonb_build_object('success', true, 'new_balance', v_new_balance, 'cost', v_cost);
end;
$function$;

revoke all on function public.consume_credits(numeric, text, uuid) from public, anon;
grant execute on function public.consume_credits(numeric, text, uuid) to authenticated, service_role;
