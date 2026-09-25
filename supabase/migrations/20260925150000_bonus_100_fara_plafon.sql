-- Campania „primii 100 primesc 500" se inchide. De acum: 100 de credite pentru ORICE cont nou,
-- fara plafon de beneficiari.
--
-- DE CE NU MAI E NEVOIE DE MECANISM ANTI-ABUZ — scris aici dinadins, ca sa nu fie „strans" mai
-- tarziu de cineva care nu stie de ce a fost lasat larg:
--   Cu 100 de credite NU se poate genera un proiect complet. O casa obisnuita cere 200-300
--   (1 credit/mp la DTAC, 3 la DTAC+PT, pe desfasurata REALA masurata din plan).
--   Cineva cu 50 de conturi aduna credite IMPRASTIATE in 50 de locuri, din care niciunul nu-i
--   ajunge: poarta de sold din `/api/generate` refuza fiecare incercare cu 402 INAINTE de orice
--   procesare. Ca sa le foloseasca, ar trebui sa puna bani pe fiecare cont — adica exact ce face
--   un client cinstit.
--   Asa abuzul devine fara sens de la sine, iar un utilizator real nu simte nicio frictiune.
-- De-aia plafonul se SCOATE, nu se ridica: un plafon ridicat ar fi ramas o valoare de intretinut
-- degeaba si inca un loc care poate diverge de restul.

-- ── [1] VALOAREA — in DOUA locuri, nu unul ──────────────────────────────────────────────────
-- Randul curent SI default-ul coloanei. Default-ul era 500: daca randul de configurare ar fi fost
-- vreodata recreat, bonusul vechi s-ar fi intors TACUT. Exact tiparul „doua locuri care pot
-- diverge" — de-aia se schimba amandoua in aceeasi migrare.
update public.credits_config set gift_amount = 100 where id = 1;
alter table public.credits_config alter column gift_amount set default 100;

-- ── [2] PLAFONUL — scos ─────────────────────────────────────────────────────────────────────
-- Singurul lui cititor era `grant_signup_gift()`, rescrisa mai jos fara el. NULL se citeste
-- „fara plafon" si nu poate fi confundat cu un plafon activ de 100, cum ar fi fost daca lasam
-- valoarea pe loc.
alter table public.credits_config alter column gift_user_limit drop not null;
alter table public.credits_config alter column gift_user_limit drop default;
update public.credits_config set gift_user_limit = null where id = 1;
comment on column public.credits_config.gift_user_limit is
  'NEFOLOSIT din 25 sept 2026: plafonul a fost scos din grant_signup_gift(). NULL = fara plafon.';

-- ── [3] FUNCTIA ─────────────────────────────────────────────────────────────────────────────
-- Pana acum exista DOAR in baza (creata din dashboard), deci nimeni n-o putea revizui la cod, iar
-- o refacere din migrari n-ar fi recreat-o. De acum e versionata.
--
-- Ce ramane neschimbat si de ce:
--   * `OLD.email_confirmed_at IS NULL AND NEW... IS NOT NULL` — doar PRIMA confirmare. O a doua
--     confirmare pe acelasi cont nu mai potriveste conditia, deci bonusul nu se poate lua de doua
--     ori pe acelasi cont.
--   * `FOR UPDATE` pe randul de configurare — serializeaza inregistrarile simultane, ca ledgerul
--     si contorul sa nu se desincronizeze.
--   * SECURITY DEFINER + `SET search_path` — fara search_path fixat, o functie DEFINER e calea
--     clasica de escaladare.
create or replace function public.grant_signup_gift()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare cfg public.credits_config%rowtype;
begin
  if old.email_confirmed_at is null and new.email_confirmed_at is not null then
    select * into cfg from public.credits_config where id = 1 for update;
    update public.profiles set credits_balance = credits_balance + cfg.gift_amount
      where id = new.id;
    insert into public.credits_transactions (user_id, amount, type, balance_after, note)
      values (new.id, cfg.gift_amount, 'gift_signup',
              (select credits_balance from public.profiles where id = new.id),
              'Bonus de bun-venit');
    -- Contorul RAMANE, dar de acum e o STATISTICA, nu o poarta: nimic nu-l mai compara cu un
    -- plafon. Ramane fiindca „cate bonusuri s-au dat" e o intrebare care se pune oricum.
    update public.credits_config set gift_users_granted = gift_users_granted + 1 where id = 1;
  end if;
  return new;
end; $function$;
