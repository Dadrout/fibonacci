-- Additive study tools upgrade. Apply after schema.sql and teacher_prep.sql.
create table if not exists public.student_study_materials (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check(kind in ('flashcards','quiz','presentation')),
  subject text not null check(subject in ('language_arts','math','science','history_social_studies','geography','philosophy')),
  grade text not null check(grade ~ '^(K|[1-9]|1[0-2])$'),
  topic text not null check(char_length(trim(topic)) between 1 and 200),
  language text not null check(language in ('en-US','ru-RU','kk-KZ')),
  context jsonb not null check(jsonb_typeof(context) = 'object'),
  status text not null default 'generating' check(status in ('generating','ready','failed')),
  content jsonb check(content is null or jsonb_typeof(content) = 'object'),
  revision integer not null default 1 check(revision > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check(status <> 'ready' or content is not null)
);
create index if not exists student_study_materials_owner_created
  on public.student_study_materials(user_id, created_at desc);

do $$ begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.teacher_resources'::regclass
      and conname = 'teacher_resources_id_user_unique'
  ) then
    alter table public.teacher_resources
      add constraint teacher_resources_id_user_unique unique(id, user_id);
  end if;
end $$;

create table if not exists public.teacher_presentation_renders (
  id uuid primary key,
  resource_id uuid not null,
  user_id uuid not null references public.teacher_profiles(user_id) on delete cascade,
  resource_revision integer not null check(resource_revision > 0),
  status text not null default 'queued' check(status in ('queued','processing','ready','failed','cancelled')),
  progress integer not null default 0 check(progress between 0 and 100),
  stage text not null default 'queued',
  message text not null default 'Waiting to start',
  video_object text,
  duration_sec numeric(8,2),
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key(resource_id, user_id) references public.teacher_resources(id, user_id) on delete cascade,
  check(status <> 'ready' or video_object is not null)
);
alter table public.teacher_presentation_renders
  add column if not exists resource_revision integer not null default 1 check(resource_revision > 0);
create index if not exists teacher_presentation_renders_owner_created
  on public.teacher_presentation_renders(user_id, created_at desc);
create index if not exists teacher_presentation_renders_active
  on public.teacher_presentation_renders(user_id, status) where status in ('queued','processing');
create unique index if not exists teacher_presentation_renders_one_active_resource
  on public.teacher_presentation_renders(user_id, resource_id) where status in ('queued','processing');

alter table public.student_study_materials enable row level security;
alter table public.teacher_presentation_renders enable row level security;
revoke all on public.student_study_materials, public.teacher_presentation_renders from public, anon, authenticated;
grant select on public.student_study_materials, public.teacher_presentation_renders to authenticated;
grant all on public.student_study_materials, public.teacher_presentation_renders to service_role;

drop policy if exists student_study_materials_read on public.student_study_materials;
create policy student_study_materials_read on public.student_study_materials
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists teacher_presentation_renders_read on public.teacher_presentation_renders;
create policy teacher_presentation_renders_read on public.teacher_presentation_renders
  for select to authenticated using ((select auth.uid()) = user_id);

drop trigger if exists student_study_materials_updated on public.student_study_materials;
create trigger student_study_materials_updated before update on public.student_study_materials
  for each row execute function public.set_updated_at();
drop trigger if exists teacher_presentation_renders_updated on public.teacher_presentation_renders;
create trigger teacher_presentation_renders_updated before update on public.teacher_presentation_renders
  for each row execute function public.set_updated_at();
