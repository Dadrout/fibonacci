-- Fibonacci learner story storage. Apply in the Supabase SQL editor.
-- Video objects belong in the private `story-videos` bucket.

-- A durable lock keeps in-flight and queued workers from creating media while
-- account deletion is stopping jobs and removing the user's assets.
create table if not exists public.account_deletion_locks (
  user_id uuid primary key references auth.users(id) on delete cascade,
  requested_at timestamptz not null default now()
);
revoke all on table public.account_deletion_locks from public, anon, authenticated;
grant all on table public.account_deletion_locks to service_role;
alter table public.account_deletion_locks enable row level security;

create table if not exists public.story_drafts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  subject text not null check (subject in ('history', 'language_arts', 'math', 'science', 'history_social_studies', 'geography', 'philosophy')),
  topic text not null check (char_length(topic) between 1 and 200),
  grade_band text not null check (grade_band in ('10-12', '13-15', '16-18')),
  target_duration_sec integer not null check (target_duration_sec between 60 and 300),
  language text not null check (language in ('en-US', 'ru-RU')),
  voice text not null check (voice in ('female', 'male')),
  script jsonb not null,
  recap text not null,
  quiz jsonb not null,
  sources jsonb not null default '[]'::jsonb check (jsonb_typeof(sources) = 'array'),
  knowledge_status text not null default 'none' check (knowledge_status in ('grounded', 'partial', 'none')),
  status text not null default 'draft' check (status in ('draft', 'rendering', 'complete')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.stories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  draft_id uuid not null references public.story_drafts(id) on delete cascade,
  task_id text not null unique,
  subject text not null,
  topic text not null,
  title text not null,
  grade_band text not null,
  target_duration_sec integer not null,
  language text not null,
  voice text not null,
  status text not null default 'PENDING' check (status in ('PENDING', 'PROGRESS', 'SUCCESS', 'FAILURE')),
  progress integer not null default 0 check (progress between 0 and 100),
  stage text not null default 'queued',
  message text not null default 'Waiting to start',
  result jsonb,
  sources jsonb not null default '[]'::jsonb check (jsonb_typeof(sources) = 'array'),
  knowledge_status text not null default 'none' check (knowledge_status in ('grounded', 'partial', 'none')),
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists stories_user_created_idx on public.stories(user_id, created_at desc);
create index if not exists drafts_user_updated_idx on public.story_drafts(user_id, updated_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists story_drafts_set_updated_at on public.story_drafts;
create trigger story_drafts_set_updated_at
before update on public.story_drafts
for each row execute function public.set_updated_at();

drop trigger if exists stories_set_updated_at on public.stories;
create trigger stories_set_updated_at
before update on public.stories
for each row execute function public.set_updated_at();

create table if not exists public.quiz_results (
  id uuid primary key default gen_random_uuid(),
  story_id uuid not null references public.stories(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  answers jsonb not null,
  score integer not null check (score >= 0),
  total integer not null check (total > 0),
  created_at timestamptz not null default now(),
  unique(story_id, user_id)
);

-- PostgreSQL requires immutable functions inside generated columns. The generic
-- array_to_string(anyarray, text) is stable because arbitrary element output can
-- depend on session settings. This helper only accepts text[]; joining text has
-- no session-dependent conversion and is safe to declare immutable.
create or replace function public.knowledge_alias_text(values_to_join text[])
returns text
language sql
immutable
parallel safe
security invoker
set search_path = pg_catalog
as $$ select array_to_string(values_to_join, ' '); $$;
revoke all on function public.knowledge_alias_text(text[]) from public, anon, authenticated;
grant execute on function public.knowledge_alias_text(text[]) to service_role;

-- Shared, reviewed facts used to ground story drafts. Learners may read approved
-- entries, while all writes are performed by the server using its secret key.
create table if not exists public.knowledge_entries (
  id uuid primary key default gen_random_uuid(),
  subject text not null check (subject in ('history', 'language_arts', 'math', 'science', 'history_social_studies', 'geography', 'philosophy')),
  canonical_topic text not null,
  aliases text[] not null default '{}',
  grade_bands text[] not null default array['10-12', '13-15', '16-18'],
  facts jsonb not null check (jsonb_typeof(facts) = 'array' and jsonb_array_length(facts) > 0),
  sources jsonb not null check (jsonb_typeof(sources) = 'array' and jsonb_array_length(sources) > 0),
  reviewed_at timestamptz not null default now(),
  is_approved boolean not null default false,
  search_document tsvector generated always as (
    setweight(to_tsvector('simple', coalesce(canonical_topic, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(public.knowledge_alias_text(aliases), '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(facts::text, '')), 'B')
  ) stored,
  unique(subject, canonical_topic)
);

create index if not exists knowledge_entries_search_idx
  on public.knowledge_entries using gin(search_document);
create index if not exists knowledge_entries_subject_grade_idx
  on public.knowledge_entries(subject, is_approved);

-- Additive upgrades for projects where the learner tables already exist.
alter table public.story_drafts
  add column if not exists sources jsonb not null default '[]'::jsonb
  check (jsonb_typeof(sources) = 'array');
alter table public.story_drafts
  add column if not exists knowledge_status text not null default 'none'
  check (knowledge_status in ('grounded', 'partial', 'none'));
alter table public.stories
  add column if not exists sources jsonb not null default '[]'::jsonb
  check (jsonb_typeof(sources) = 'array');
alter table public.stories
  add column if not exists knowledge_status text not null default 'none'
  check (knowledge_status in ('grounded', 'partial', 'none'));

-- Existing installations may have user foreign keys without cascade behavior.
-- Recreate those constraints so account deletion removes owned rows reliably.
do $$
declare
  fk record;
begin
  for fk in
    select conname
    from pg_constraint
    where conrelid = 'public.story_drafts'::regclass
      and contype = 'f'
      and (select attnum from pg_attribute
           where attrelid = 'public.story_drafts'::regclass and attname = 'user_id') = any(conkey)
  loop
    execute format('alter table public.story_drafts drop constraint %I', fk.conname);
  end loop;
  alter table public.story_drafts
    add constraint story_drafts_user_id_fkey
    foreign key (user_id) references auth.users(id) on delete cascade;

  for fk in
    select conname
    from pg_constraint
    where conrelid = 'public.stories'::regclass
      and contype = 'f'
      and (select attnum from pg_attribute
           where attrelid = 'public.stories'::regclass and attname = 'user_id') = any(conkey)
  loop
    execute format('alter table public.stories drop constraint %I', fk.conname);
  end loop;
  alter table public.stories
    add constraint stories_user_id_fkey
    foreign key (user_id) references auth.users(id) on delete cascade;

  for fk in
    select conname
    from pg_constraint
    where conrelid = 'public.quiz_results'::regclass
      and contype = 'f'
      and (select attnum from pg_attribute
           where attrelid = 'public.quiz_results'::regclass and attname = 'user_id') = any(conkey)
  loop
    execute format('alter table public.quiz_results drop constraint %I', fk.conname);
  end loop;
  alter table public.quiz_results
    add constraint quiz_results_user_id_fkey
    foreign key (user_id) references auth.users(id) on delete cascade;
end;
$$;

create or replace function public.search_knowledge_entries(
  query_text text,
  subject_filter text,
  grade_band_filter text,
  result_limit integer default 3
)
returns table (
  id uuid,
  subject text,
  canonical_topic text,
  aliases text[],
  grade_bands text[],
  facts jsonb,
  sources jsonb,
  reviewed_at timestamptz,
  rank real,
  match_type text
)
language sql
stable
security invoker
set search_path = public, pg_temp
as $$
  with search_terms as (
    select
      lower(trim(coalesce(query_text, ''))) as normalized_query,
      websearch_to_tsquery('simple', coalesce(query_text, '')) as parsed_query
  )
  select
    entry.id,
    entry.subject,
    entry.canonical_topic,
    entry.aliases,
    entry.grade_bands,
    entry.facts,
    entry.sources,
    entry.reviewed_at,
    ts_rank_cd(entry.search_document, search_terms.parsed_query)::real as rank,
    case
      when lower(trim(entry.canonical_topic)) = search_terms.normalized_query
        or exists (
          select 1 from unnest(entry.aliases) as alias_value(value)
          where lower(trim(alias_value.value)) = search_terms.normalized_query
        ) then 'exact'
      else 'partial'
    end as match_type
  from public.knowledge_entries entry
  cross join search_terms
  where entry.is_approved
    and entry.subject = subject_filter
    and grade_band_filter = any(entry.grade_bands)
    and (
      lower(trim(entry.canonical_topic)) = search_terms.normalized_query
      or exists (
        select 1 from unnest(entry.aliases) as alias_value(value)
        where lower(trim(alias_value.value)) = search_terms.normalized_query
      )
      or entry.search_document @@ search_terms.parsed_query
    )
  order by
    case when lower(trim(entry.canonical_topic)) = search_terms.normalized_query
      or exists (
        select 1 from unnest(entry.aliases) as alias_value(value)
        where lower(trim(alias_value.value)) = search_terms.normalized_query
      ) then 1 else 0 end desc,
    ts_rank_cd(entry.search_document, search_terms.parsed_query) desc,
    entry.canonical_topic
  limit greatest(1, least(coalesce(result_limit, 3), 3));
$$;

revoke all on table public.knowledge_entries from public, anon, authenticated;
grant select on table public.knowledge_entries to authenticated;
grant select, insert, update, delete on table public.knowledge_entries to service_role;
alter table public.knowledge_entries enable row level security;
drop policy if exists "Learners read approved knowledge entries" on public.knowledge_entries;
create policy "Learners read approved knowledge entries" on public.knowledge_entries
  for select to authenticated
  using (is_approved);

revoke all on function public.search_knowledge_entries(text, text, text, integer) from public, anon;
grant execute on function public.search_knowledge_entries(text, text, text, integer)
  to authenticated, service_role;

-- Apply the reviewed seed set with: psql <connection> -f supabase/knowledge_seed.sql

-- Reads follow owner RLS; all writes pass server-side validation.
revoke all on table public.story_drafts, public.stories, public.quiz_results from public, anon, authenticated;
grant select on table public.story_drafts, public.stories, public.quiz_results to authenticated;
grant all on table public.story_drafts, public.stories, public.quiz_results to service_role;

alter table public.story_drafts enable row level security;
alter table public.stories enable row level security;
alter table public.quiz_results enable row level security;

drop policy if exists "Learners manage their own drafts" on public.story_drafts;
drop policy if exists "Learners read their own drafts" on public.story_drafts;
create policy "Learners read their own drafts" on public.story_drafts
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Learners read their own stories" on public.stories;
create policy "Learners read their own stories" on public.stories
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Learners read their own quiz results" on public.quiz_results;
create policy "Learners read their own quiz results" on public.quiz_results
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Learners save their own quiz results" on public.quiz_results;

insert into storage.buckets (id, name, public)
values ('story-videos', 'story-videos', false)
on conflict (id) do update set public = false;

drop policy if exists "Learners read their own story videos" on storage.objects;
create policy "Learners read their own story videos" on storage.objects
  for select to authenticated
  using (bucket_id = 'story-videos' and (storage.foldername(name))[1] = (select auth.uid()::text));
