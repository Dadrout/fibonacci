-- LOCAL DEVELOPMENT ONLY — never apply to the hosted project.
-- With BRAIN_STORE=local, accounts still sign in with hosted Supabase Auth (or the demo
-- session), but the brain lives in this local database. Mirror the account id into the
-- local auth.users so the brain tables' foreign keys hold.
create or replace function public.brain_local_ensure_user(p_uid uuid, p_email text)
returns void language sql security definer set search_path = auth, pg_catalog as $$
  insert into auth.users (id, email, aud, role, created_at, updated_at)
  values (p_uid, p_email, 'authenticated', 'authenticated', now(), now())
  on conflict (id) do nothing;
$$;
revoke all on function public.brain_local_ensure_user(uuid, text) from public, anon, authenticated;
grant execute on function public.brain_local_ensure_user(uuid, text) to service_role;
notify pgrst, 'reload schema';
