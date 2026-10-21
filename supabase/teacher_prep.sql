-- Additive teacher preparation upgrade. Apply after schema.sql.
create table if not exists public.teacher_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);
create table if not exists public.teacher_lessons (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.teacher_profiles(user_id) on delete cascade,
  subject text not null check(subject in ('language_arts','math','science','history_social_studies','geography')),
  grade text not null check(grade ~ '^(K|[1-9]|1[0-2])$'),
  topic text not null check(char_length(trim(topic)) between 1 and 200),
  language text not null check(language in ('en-US','ru-RU','kk-KZ')),
  objectives text not null default '' check(char_length(objectives) <= 3000),
  source_material text not null default '' check(char_length(source_material) <= 20000),
  revision integer not null default 1 check(revision > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id, user_id)
);
create table if not exists public.teacher_resources (
  id uuid primary key default gen_random_uuid(),
  lesson_id uuid not null,
  user_id uuid not null references public.teacher_profiles(user_id) on delete cascade,
  kind text not null check(kind in ('objectives','lesson_plan','quiz','test_paper','flashcards','worksheet','exit_ticket','homework','presentation')),
  status text not null default 'generating' check(status in ('generating','ready','failed')),
  content jsonb check(content is null or jsonb_typeof(content) = 'object'),
  lesson_snapshot jsonb not null check(jsonb_typeof(lesson_snapshot) = 'object'),
  revision integer not null default 1 check(revision > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key(lesson_id, user_id) references public.teacher_lessons(id, user_id) on delete cascade,
  check(status <> 'ready' or content is not null)
);
alter table public.teacher_resources drop constraint if exists teacher_resources_kind_check;
alter table public.teacher_resources add constraint teacher_resources_kind_check
  check(kind in ('objectives','lesson_plan','quiz','test_paper','flashcards','worksheet','exit_ticket','homework','presentation'));
create index if not exists teacher_lessons_owner_updated on public.teacher_lessons(user_id, updated_at desc);
create index if not exists teacher_resources_owner_lesson on public.teacher_resources(user_id, lesson_id, created_at desc);
-- API writes use a server credential and always scope records by verified user.
-- Direct authenticated access is read-only; writes must pass API validation.
alter table public.teacher_profiles enable row level security;
alter table public.teacher_lessons enable row level security;
alter table public.teacher_resources enable row level security;
revoke all on public.teacher_profiles, public.teacher_lessons, public.teacher_resources from public, anon, authenticated;
grant select on public.teacher_profiles, public.teacher_lessons, public.teacher_resources to authenticated;
grant all on public.teacher_profiles, public.teacher_lessons, public.teacher_resources to service_role;
drop policy if exists teacher_profile_read on public.teacher_profiles;
create policy teacher_profile_read on public.teacher_profiles for select to authenticated using((select auth.uid()) = user_id);
drop policy if exists teacher_lesson_read on public.teacher_lessons;
create policy teacher_lesson_read on public.teacher_lessons for select to authenticated using((select auth.uid()) = user_id);
drop policy if exists teacher_resource_read on public.teacher_resources;
create policy teacher_resource_read on public.teacher_resources for select to authenticated using((select auth.uid()) = user_id);
drop trigger if exists teacher_lessons_updated on public.teacher_lessons;
create trigger teacher_lessons_updated before update on public.teacher_lessons for each row execute function public.set_updated_at();
drop trigger if exists teacher_resources_updated on public.teacher_resources;
create trigger teacher_resources_updated before update on public.teacher_resources for each row execute function public.set_updated_at();
-- Add Kazakh to the existing story-language constraint.
alter table public.story_drafts drop constraint if exists story_drafts_language_check;
alter table public.story_drafts add constraint story_drafts_language_check check(language in ('en-US','ru-RU','kk-KZ'));
