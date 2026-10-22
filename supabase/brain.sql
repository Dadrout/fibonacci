-- Fibonacci Brain: captures that organize themselves into courses → topics → concepts.
-- Additive upgrade. Apply after schema.sql (needs account_deletion_locks and set_updated_at).
--
-- Security model (same as student_study_materials):
--   * every row has user_id → auth.users, deleted with the account;
--   * RLS on every table; authenticated users may only SELECT their own rows;
--   * all writes go through the validated API with the service role;
--   * composite (id, user_id) foreign keys stop rows from pointing at another user's data;
--   * answer keys and Telegram codes are server-only (no client grants at all).

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists public.brain_courses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(trim(title)) between 1 and 120),
  code text check (code is null or char_length(code) between 1 and 32),
  color_index smallint not null default 0 check (color_index between 0 and 7),
  created_by text not null default 'auto' check (created_by in ('auto', 'user')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id)
);
create unique index if not exists brain_courses_owner_title on public.brain_courses (user_id, lower(title));

create table if not exists public.brain_topics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  course_id uuid not null,
  title text not null check (char_length(trim(title)) between 1 and 160),
  sequence integer check (sequence between 0 and 400),
  sequence_kind text check (sequence_kind in ('week', 'lecture', 'chapter', 'module')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id),
  foreign key (course_id, user_id) references public.brain_courses (id, user_id) on delete cascade,
  check ((sequence is null) = (sequence_kind is null))
);
create unique index if not exists brain_topics_owner_title on public.brain_topics (user_id, course_id, lower(title));
create index if not exists brain_topics_course on public.brain_topics (user_id, course_id, sequence);

create table if not exists public.brain_concepts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  course_id uuid not null,
  topic_id uuid,
  name text not null check (char_length(trim(name)) between 1 and 120),
  summary text not null default '' check (char_length(summary) <= 600),
  embedding extensions.vector(768),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id),
  foreign key (course_id, user_id) references public.brain_courses (id, user_id) on delete cascade,
  foreign key (topic_id, user_id) references public.brain_topics (id, user_id) on delete set null (topic_id)
);
create unique index if not exists brain_concepts_owner_name on public.brain_concepts (user_id, course_id, lower(name));
create index if not exists brain_concepts_owner_course on public.brain_concepts (user_id, course_id);

create table if not exists public.brain_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('photo', 'pdf', 'document', 'youtube', 'web', 'audio', 'text')),
  channel text not null check (channel in ('web_drop', 'web_paste', 'web_picker', 'telegram', 'seed')),
  status text not null default 'queued' check (status in ('queued', 'extracting', 'classifying', 'linking', 'filed', 'failed')),
  progress real not null default 0 check (progress between 0 and 1),
  title text not null check (char_length(trim(title)) between 1 and 300),
  summary text check (summary is null or char_length(summary) <= 1000),
  language text check (language is null or language in ('en-US', 'ru-RU', 'kk-KZ')),
  course_id uuid,
  topic_id uuid,
  confidence real check (confidence is null or confidence between 0 and 1),
  alternatives jsonb not null default '[]'::jsonb check (jsonb_typeof(alternatives) = 'array'),
  source_url text check (source_url is null or char_length(source_url) <= 2048),
  youtube_id text check (youtube_id is null or youtube_id ~ '^[A-Za-z0-9_-]{11}$'),
  object_path text check (object_path is null or char_length(object_path) <= 300),
  thumbnail_path text check (thumbnail_path is null or char_length(thumbnail_path) <= 300),
  mime_type text check (mime_type is null or char_length(mime_type) <= 100),
  byte_count integer check (byte_count is null or byte_count between 0 and 26214400),
  content_hash text check (content_hash is null or content_hash ~ '^[0-9a-f]{64}$'),
  duration_sec real check (duration_sec is null or duration_sec >= 0),
  page_count integer check (page_count is null or page_count between 0 and 2000),
  failure_code text check (failure_code is null or failure_code in
    ('unsupported_type', 'too_large', 'unreadable', 'fetch_failed', 'transcript_unavailable', 'ai_unavailable', 'internal')),
  task_id uuid not null default gen_random_uuid(),
  request_id uuid,
  timings_ms jsonb not null default '{}'::jsonb check (jsonb_typeof(timings_ms) = 'object'),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  captured_at timestamptz not null default now(),
  filed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id),
  foreign key (course_id, user_id) references public.brain_courses (id, user_id) on delete set null (course_id),
  foreign key (topic_id, user_id) references public.brain_topics (id, user_id) on delete set null (topic_id),
  check (status <> 'filed' or course_id is not null),
  check (status <> 'failed' or failure_code is not null)
);
create unique index if not exists brain_items_request on public.brain_items (user_id, request_id) where request_id is not null;
create index if not exists brain_items_owner_captured on public.brain_items (user_id, captured_at desc);
create index if not exists brain_items_owner_course on public.brain_items (user_id, course_id, topic_id);
create index if not exists brain_items_active on public.brain_items (user_id, status) where status not in ('filed', 'failed');

create table if not exists public.brain_chunks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  item_id uuid not null,
  ordinal integer not null check (ordinal between 0 and 5000),
  anchor_kind text not null check (anchor_kind in ('page', 'slide', 'timestamp', 'paragraph', 'section')),
  page integer check (page is null or page >= 1),
  slide integer check (slide is null or slide >= 1),
  start_sec real check (start_sec is null or start_sec >= 0),
  end_sec real check (end_sec is null or end_sec >= 0),
  paragraph integer check (paragraph is null or paragraph >= 1),
  heading text check (heading is null or char_length(heading) <= 200),
  body text not null check (char_length(body) between 1 and 8000),
  embedding extensions.vector(768),
  search_document tsvector generated always as (to_tsvector('simple'::regconfig, body)) stored,
  created_at timestamptz not null default now(),
  unique (id, user_id),
  unique (item_id, ordinal),
  foreign key (item_id, user_id) references public.brain_items (id, user_id) on delete cascade,
  check (anchor_kind <> 'page' or page is not null),
  check (anchor_kind <> 'timestamp' or (start_sec is not null and end_sec is not null and end_sec >= start_sec)),
  check (anchor_kind <> 'paragraph' or paragraph is not null),
  check (anchor_kind <> 'section' or heading is not null)
);
create index if not exists brain_chunks_owner_item on public.brain_chunks (user_id, item_id, ordinal);
create index if not exists brain_chunks_fts on public.brain_chunks using gin (search_document);
-- Exact (sequential) cosine search per user is fast at personal-brain scale and never
-- drops rows the way a global approximate index would after the per-user filter.

create table if not exists public.brain_chunk_concepts (
  chunk_id uuid not null,
  concept_id uuid not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  weight real not null default 1 check (weight between 0 and 1),
  primary key (chunk_id, concept_id),
  foreign key (chunk_id, user_id) references public.brain_chunks (id, user_id) on delete cascade,
  foreign key (concept_id, user_id) references public.brain_concepts (id, user_id) on delete cascade
);
create index if not exists brain_chunk_concepts_concept on public.brain_chunk_concepts (user_id, concept_id);

create table if not exists public.brain_concept_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_concept_id uuid not null,
  target_concept_id uuid not null,
  strength real not null check (strength between 0 and 1),
  relation text not null check (relation in ('same_idea', 'builds_on', 'applies', 'contrasts')),
  rationale text not null default '' check (char_length(rationale) <= 400),
  method text not null check (method in ('embedding', 'verified', 'user')),
  created_at timestamptz not null default now(),
  foreign key (source_concept_id, user_id) references public.brain_concepts (id, user_id) on delete cascade,
  foreign key (target_concept_id, user_id) references public.brain_concepts (id, user_id) on delete cascade,
  check (source_concept_id <> target_concept_id),
  -- Machine-made links must clear a floor; the API applies a stricter threshold.
  check (method = 'user' or strength >= 0.5)
);
-- One link per unordered pair; direction is kept for "A builds on B".
create unique index if not exists brain_concept_links_pair on public.brain_concept_links
  (user_id, least(source_concept_id, target_concept_id), greatest(source_concept_id, target_concept_id));
create index if not exists brain_concept_links_target on public.brain_concept_links (user_id, target_concept_id);

create table if not exists public.brain_study_plans (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  course_id uuid not null,
  days smallint not null check (days between 1 and 14),
  exam_date date not null,
  language text not null check (language in ('en-US', 'ru-RU', 'kk-KZ')),
  status text not null default 'generating' check (status in ('generating', 'ready', 'failed')),
  failure_code text check (failure_code is null or failure_code in ('not_enough_material', 'ai_unavailable', 'internal')),
  content jsonb check (content is null or jsonb_typeof(content) = 'object'),
  coverage jsonb check (coverage is null or jsonb_typeof(coverage) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id),
  foreign key (course_id, user_id) references public.brain_courses (id, user_id) on delete cascade,
  check (status <> 'ready' or content is not null)
);
create index if not exists brain_study_plans_course on public.brain_study_plans (user_id, course_id, created_at desc);

-- Correct answers and grounding stay server-side, even from the plan owner's direct reads.
create table if not exists public.brain_plan_secrets (
  plan_id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  answer_key jsonb not null check (jsonb_typeof(answer_key) = 'object'),
  foreign key (plan_id, user_id) references public.brain_study_plans (id, user_id) on delete cascade
);

create table if not exists public.brain_quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_id uuid not null,
  question_id text not null check (char_length(question_id) between 1 and 40),
  chosen_option text not null check (chosen_option in ('a', 'b', 'c', 'd')),
  correct boolean not null,
  moment jsonb check (moment is null or jsonb_typeof(moment) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (plan_id, user_id) references public.brain_study_plans (id, user_id) on delete cascade
);
create index if not exists brain_quiz_attempts_plan on public.brain_quiz_attempts (user_id, plan_id, created_at desc);

-- Corrections the classifier learns from (titles are copied so examples survive deletions).
create table if not exists public.brain_todos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 300),
  due text check (due is null or char_length(due) <= 80),
  done boolean not null default false,
  source text not null default 'web' check (source in ('web', 'telegram')),
  created_at timestamptz not null default now()
);
create index if not exists brain_todos_owner on public.brain_todos (user_id, done, created_at desc);

create table if not exists public.brain_refile_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  item_id uuid,
  item_title text not null check (char_length(item_title) <= 300),
  item_summary text not null default '' check (char_length(item_summary) <= 1000),
  from_course_title text check (from_course_title is null or char_length(from_course_title) <= 120),
  from_topic_title text check (from_topic_title is null or char_length(from_topic_title) <= 160),
  to_course_title text not null check (char_length(to_course_title) <= 120),
  to_topic_title text check (to_topic_title is null or char_length(to_topic_title) <= 160),
  created_at timestamptz not null default now(),
  foreign key (item_id, user_id) references public.brain_items (id, user_id) on delete set null (item_id)
);
create index if not exists brain_refile_events_owner on public.brain_refile_events (user_id, created_at desc);

create table if not exists public.brain_telegram_links (
  user_id uuid primary key references auth.users(id) on delete cascade,
  chat_id bigint not null unique,
  telegram_user_id bigint,
  telegram_username text check (telegram_username is null or char_length(telegram_username) <= 64),
  linked_at timestamptz not null default now()
);

create table if not exists public.brain_telegram_codes (
  code_hash text primary key check (code_hash ~ '^[0-9a-f]{64}$'),
  user_id uuid not null references auth.users(id) on delete cascade,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists brain_telegram_codes_owner on public.brain_telegram_codes (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Row-level security and grants
-- ---------------------------------------------------------------------------

do $$
declare t text;
begin
  foreach t in array array[
    'brain_courses', 'brain_topics', 'brain_concepts', 'brain_items', 'brain_chunks',
    'brain_chunk_concepts', 'brain_concept_links', 'brain_study_plans', 'brain_plan_secrets',
    'brain_quiz_attempts', 'brain_refile_events', 'brain_telegram_links', 'brain_telegram_codes', 'brain_todos'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from public, anon, authenticated', t);
    execute format('grant all on public.%I to service_role', t);
  end loop;
  -- Owner read access; server-only tables (plan secrets, Telegram codes) get none.
  foreach t in array array[
    'brain_courses', 'brain_topics', 'brain_concepts', 'brain_items', 'brain_chunks',
    'brain_chunk_concepts', 'brain_concept_links', 'brain_study_plans', 'brain_quiz_attempts',
    'brain_refile_events', 'brain_telegram_links', 'brain_todos'
  ] loop
    execute format('grant select on public.%I to authenticated', t);
    execute format('drop policy if exists %I on public.%I', t || '_owner_read', t);
    execute format('create policy %I on public.%I for select to authenticated using ((select auth.uid()) = user_id)', t || '_owner_read', t);
  end loop;
  foreach t in array array['brain_courses', 'brain_topics', 'brain_concepts', 'brain_items', 'brain_study_plans'] loop
    execute format('drop trigger if exists %I on public.%I', t || '_updated', t);
    execute format('create trigger %I before update on public.%I for each row execute function public.set_updated_at()', t || '_updated', t);
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- Server-only functions (SECURITY INVOKER; executed by the API with the service role)
-- ---------------------------------------------------------------------------

-- Whole brain for the graph screen in one round trip.
create or replace function public.brain_graph(p_uid uuid)
returns jsonb language sql stable security invoker set search_path = public, extensions, pg_catalog as $$
  with
  mention_counts as (
    select concept_id, count(*) as n from public.brain_chunk_concepts where user_id = p_uid group by concept_id
  )
  select jsonb_build_object(
    'courses', coalesce((select jsonb_agg(jsonb_build_object(
        'id', c.id, 'title', c.title, 'code', c.code, 'color_index', c.color_index, 'created_by', c.created_by,
        'item_count', (select count(*) from public.brain_items i where i.user_id = p_uid and i.course_id = c.id and i.status = 'filed'),
        'topic_count', (select count(*) from public.brain_topics t where t.user_id = p_uid and t.course_id = c.id),
        'concept_count', (select count(*) from public.brain_concepts k where k.user_id = p_uid and k.course_id = c.id),
        'created_at', c.created_at) order by c.created_at)
      from public.brain_courses c where c.user_id = p_uid), '[]'::jsonb),
    'topics', coalesce((select jsonb_agg(jsonb_build_object(
        'id', t.id, 'course_id', t.course_id, 'title', t.title, 'sequence', t.sequence, 'sequence_kind', t.sequence_kind,
        'item_count', (select count(*) from public.brain_items i where i.user_id = p_uid and i.topic_id = t.id and i.status = 'filed'),
        'concept_count', (select count(*) from public.brain_concepts k where k.user_id = p_uid and k.topic_id = t.id),
        'created_at', t.created_at) order by t.course_id, t.sequence nulls last, t.created_at)
      from public.brain_topics t where t.user_id = p_uid), '[]'::jsonb),
    'concepts', coalesce((select jsonb_agg(jsonb_build_object(
        'id', k.id, 'course_id', k.course_id, 'topic_id', k.topic_id, 'name', k.name, 'summary', k.summary,
        'mention_count', coalesce(m.n, 0), 'created_at', k.created_at) order by k.created_at)
      from public.brain_concepts k left join mention_counts m on m.concept_id = k.id where k.user_id = p_uid), '[]'::jsonb),
    'links', coalesce((select jsonb_agg(jsonb_build_object(
        'id', l.id, 'source_concept_id', l.source_concept_id, 'target_concept_id', l.target_concept_id,
        'cross_course', a.course_id <> b.course_id, 'strength', l.strength, 'relation', l.relation,
        'rationale', l.rationale, 'method', l.method, 'created_at', l.created_at) order by l.created_at)
      from public.brain_concept_links l
      join public.brain_concepts a on a.id = l.source_concept_id
      join public.brain_concepts b on b.id = l.target_concept_id
      where l.user_id = p_uid), '[]'::jsonb),
    'generated_at', now()
  );
$$;

-- Nearest passages to an embedding, optionally limited to courses or items.
create or replace function public.brain_match_chunks(
  p_uid uuid, p_embedding extensions.vector(768), p_limit integer default 12,
  p_course_ids uuid[] default null, p_item_ids uuid[] default null
) returns table (chunk_id uuid, item_id uuid, course_id uuid, similarity real)
language sql stable security invoker set search_path = public, extensions, pg_catalog as $$
  select c.id, c.item_id, i.course_id, (1 - (c.embedding <=> p_embedding))::real
  from public.brain_chunks c
  join public.brain_items i on i.id = c.item_id and i.user_id = c.user_id
  where c.user_id = p_uid and c.embedding is not null and i.status = 'filed'
    and (p_course_ids is null or i.course_id = any (p_course_ids))
    and (p_item_ids is null or c.item_id = any (p_item_ids))
  order by c.embedding <=> p_embedding
  limit least(greatest(p_limit, 1), 100);
$$;

-- Candidate concepts for linking (other concepts of the same user, best first).
create or replace function public.brain_match_concepts(
  p_uid uuid, p_embedding extensions.vector(768), p_exclude uuid[] default '{}',
  p_limit integer default 8, p_min_similarity real default 0.5
) returns table (concept_id uuid, course_id uuid, name text, summary text, similarity real)
language sql stable security invoker set search_path = public, extensions, pg_catalog as $$
  select k.id, k.course_id, k.name, k.summary, (1 - (k.embedding <=> p_embedding))::real as similarity
  from public.brain_concepts k
  where k.user_id = p_uid and k.embedding is not null and not (k.id = any (coalesce(p_exclude, '{}')))
    and 1 - (k.embedding <=> p_embedding) >= p_min_similarity
  order by k.embedding <=> p_embedding
  limit least(greatest(p_limit, 1), 50);
$$;

-- Keyword search over passages (complements vector search in the API).
create or replace function public.brain_search_chunks(p_uid uuid, p_query text, p_limit integer default 20)
returns table (chunk_id uuid, item_id uuid, rank real)
language sql stable security invoker set search_path = public, pg_catalog as $$
  select c.id, c.item_id, ts_rank_cd(c.search_document, q)::real
  from public.brain_chunks c
  join public.brain_items i on i.id = c.item_id and i.user_id = c.user_id,
       websearch_to_tsquery('simple'::regconfig, left(p_query, 400)) q
  where c.user_id = p_uid and i.status = 'filed' and c.search_document @@ q
  order by 3 desc, c.item_id, c.ordinal
  limit least(greatest(p_limit, 1), 50);
$$;

create or replace function public.brain_vector(p_value jsonb)
returns extensions.vector language sql immutable set search_path = public, extensions, pg_catalog as $$
  select case when p_value is null or jsonb_typeof(p_value) <> 'array' then null else (p_value::text)::extensions.vector(768) end;
$$;

-- Find-or-create a course by title (case-insensitive). Returns (id, created).
create or replace function public.brain_ensure_course(p_uid uuid, p_title text, p_code text, p_created_by text default 'auto')
returns table (id uuid, created boolean) language plpgsql security invoker set search_path = public, pg_catalog as $$
declare v_id uuid; v_color smallint;
begin
  select c.id into v_id from public.brain_courses c where c.user_id = p_uid and lower(c.title) = lower(trim(p_title));
  if found then return query select v_id, false; return; end if;
  select (count(*) % 8)::smallint into v_color from public.brain_courses c where c.user_id = p_uid;
  insert into public.brain_courses (user_id, title, code, color_index, created_by)
  values (p_uid, trim(p_title), nullif(trim(coalesce(p_code, '')), ''), v_color, p_created_by)
  on conflict (user_id, lower(title)) do nothing
  returning brain_courses.id into v_id;
  if v_id is null then
    select c.id into v_id from public.brain_courses c where c.user_id = p_uid and lower(c.title) = lower(trim(p_title));
    return query select v_id, false; return;
  end if;
  return query select v_id, true;
end $$;

-- Find-or-create a topic in a course; sequence (week/lecture number) wins over title when present.
create or replace function public.brain_ensure_topic(p_uid uuid, p_course uuid, p_title text, p_sequence integer, p_kind text)
returns table (id uuid, created boolean) language plpgsql security invoker set search_path = public, pg_catalog as $$
declare v_id uuid;
begin
  if p_sequence is not null then
    select t.id into v_id from public.brain_topics t
    where t.user_id = p_uid and t.course_id = p_course and t.sequence = p_sequence and t.sequence_kind = p_kind
    order by t.created_at limit 1;
  end if;
  if v_id is null then
    select t.id into v_id from public.brain_topics t
    where t.user_id = p_uid and t.course_id = p_course and lower(t.title) = lower(trim(p_title));
  end if;
  if v_id is not null then
    -- Learn a missing sequence number from new evidence.
    if p_sequence is not null then
      update public.brain_topics t set sequence = p_sequence, sequence_kind = p_kind
      where t.id = v_id and t.sequence is null
        and not exists (select 1 from public.brain_topics o where o.user_id = p_uid and o.course_id = p_course and o.sequence = p_sequence and o.sequence_kind = p_kind);
    end if;
    return query select v_id, false; return;
  end if;
  insert into public.brain_topics (user_id, course_id, title, sequence, sequence_kind)
  values (p_uid, p_course, trim(p_title), p_sequence, case when p_sequence is null then null else p_kind end)
  on conflict (user_id, course_id, lower(title)) do nothing
  returning brain_topics.id into v_id;
  if v_id is null then
    select t.id into v_id from public.brain_topics t where t.user_id = p_uid and t.course_id = p_course and lower(t.title) = lower(trim(p_title));
    return query select v_id, false; return;
  end if;
  return query select v_id, true;
end $$;

-- Atomically file an extracted + classified item. Guarded by the item's task token so a
-- stale worker (after retry/refile/delete) can never overwrite newer state.
-- p_payload: { course:{id?,title,code?}, topic:{id?,title,sequence?,sequence_kind?}|null,
--              item:{title,summary,language,confidence,alternatives,page_count?,duration_sec?,timings_ms?},
--              chunks:[{ordinal,anchor_kind,page?,slide?,start_sec?,end_sec?,paragraph?,heading?,body,embedding?}],
--              concepts:[{name,summary,embedding?,chunk_ordinals:[...]}] }
create or replace function public.brain_publish_item(p_uid uuid, p_item uuid, p_task uuid, p_payload jsonb)
returns jsonb language plpgsql security invoker set search_path = public, extensions, pg_catalog as $$
declare
  v_item public.brain_items;
  v_course uuid; v_course_new boolean := false;
  v_topic uuid; v_topic_new boolean := false;
  v_concepts jsonb := '[]'::jsonb;
  v_concept uuid;
  c jsonb;
begin
  select * into v_item from public.brain_items where id = p_item and user_id = p_uid for update;
  if not found or v_item.task_id <> p_task or v_item.status in ('filed', 'failed')
     or exists (select 1 from public.account_deletion_locks where user_id = p_uid) then
    return null;
  end if;
  if jsonb_array_length(coalesce(p_payload->'chunks', '[]')) = 0 then raise exception 'An item needs at least one passage'; end if;

  -- Course
  if nullif(p_payload#>>'{course,id}', '') is not null then
    select id into v_course from public.brain_courses where id = (p_payload#>>'{course,id}')::uuid and user_id = p_uid;
    if v_course is null then raise exception 'Unknown course'; end if;
  else
    select e.id, e.created into v_course, v_course_new
    from public.brain_ensure_course(p_uid, p_payload#>>'{course,title}', p_payload#>>'{course,code}') e;
  end if;

  -- Topic (optional)
  if p_payload->'topic' is not null and jsonb_typeof(p_payload->'topic') = 'object' then
    if nullif(p_payload#>>'{topic,id}', '') is not null then
      select id into v_topic from public.brain_topics where id = (p_payload#>>'{topic,id}')::uuid and user_id = p_uid and course_id = v_course;
      if v_topic is null then raise exception 'Unknown topic'; end if;
    else
      select e.id, e.created into v_topic, v_topic_new
      from public.brain_ensure_topic(p_uid, v_course, p_payload#>>'{topic,title}',
        nullif(p_payload#>>'{topic,sequence}', '')::integer, nullif(p_payload#>>'{topic,sequence_kind}', '')) e;
    end if;
  end if;

  -- Passages (replace any partial set from an earlier attempt)
  delete from public.brain_chunks where item_id = p_item and user_id = p_uid;
  insert into public.brain_chunks (user_id, item_id, ordinal, anchor_kind, page, slide, start_sec, end_sec, paragraph, heading, body, embedding)
  select p_uid, p_item, (x->>'ordinal')::integer, x->>'anchor_kind', nullif(x->>'page', '')::integer, nullif(x->>'slide', '')::integer,
         nullif(x->>'start_sec', '')::real, nullif(x->>'end_sec', '')::real, nullif(x->>'paragraph', '')::integer,
         nullif(x->>'heading', ''), x->>'body', public.brain_vector(x->'embedding')
  from jsonb_array_elements(p_payload->'chunks') x;

  -- Concepts: merge by name within the course; attach mentions.
  for c in select * from jsonb_array_elements(coalesce(p_payload->'concepts', '[]')) loop
    v_concept := null;
    select id into v_concept from public.brain_concepts
    where user_id = p_uid and course_id = v_course and lower(name) = lower(trim(c->>'name'));
    if v_concept is null then
      insert into public.brain_concepts (user_id, course_id, topic_id, name, summary, embedding)
      values (p_uid, v_course, v_topic, trim(c->>'name'), left(coalesce(c->>'summary', ''), 600), public.brain_vector(c->'embedding'))
      returning id into v_concept;
      v_concepts := v_concepts || jsonb_build_object('id', v_concept, 'new', true);
    else
      update public.brain_concepts set
        embedding = coalesce(embedding, public.brain_vector(c->'embedding')),
        summary = case when summary = '' then left(coalesce(c->>'summary', ''), 600) else summary end,
        topic_id = coalesce(topic_id, v_topic)
      where id = v_concept;
      v_concepts := v_concepts || jsonb_build_object('id', v_concept, 'new', false);
    end if;
    insert into public.brain_chunk_concepts (chunk_id, concept_id, user_id)
    select ch.id, v_concept, p_uid from public.brain_chunks ch
    where ch.item_id = p_item and ch.user_id = p_uid
      and ch.ordinal in (select (o)::integer from jsonb_array_elements_text(coalesce(c->'chunk_ordinals', '[]')) o)
    on conflict do nothing;
    -- A concept with no explicit passage still gets the first passage, so it is always citable.
    if not exists (select 1 from public.brain_chunk_concepts where concept_id = v_concept and user_id = p_uid) then
      insert into public.brain_chunk_concepts (chunk_id, concept_id, user_id)
      select ch.id, v_concept, p_uid from public.brain_chunks ch where ch.item_id = p_item and ch.user_id = p_uid order by ch.ordinal limit 1
      on conflict do nothing;
    end if;
  end loop;

  update public.brain_items set
    status = 'linking', progress = greatest(progress, 0.8),
    course_id = v_course, topic_id = v_topic,
    title = left(coalesce(nullif(trim(p_payload#>>'{item,title}'), ''), title), 300),
    summary = left(p_payload#>>'{item,summary}', 1000),
    language = coalesce(nullif(p_payload#>>'{item,language}', ''), language),
    confidence = nullif(p_payload#>>'{item,confidence}', '')::real,
    alternatives = coalesce(p_payload#>'{item,alternatives}', '[]'::jsonb),
    page_count = coalesce(nullif(p_payload#>>'{item,page_count}', '')::integer, page_count),
    duration_sec = coalesce(nullif(p_payload#>>'{item,duration_sec}', '')::real, duration_sec),
    timings_ms = timings_ms || coalesce(p_payload#>'{item,timings_ms}', '{}'::jsonb)
  where id = p_item;

  return jsonb_build_object('course_id', v_course, 'course_created', v_course_new,
    'topic_id', v_topic, 'topic_created', v_topic_new, 'concepts', v_concepts);
end $$;

-- Store verified links; duplicates (either direction) are ignored. Returns inserted ids.
create or replace function public.brain_add_links(p_uid uuid, p_links jsonb)
returns setof uuid language plpgsql security invoker set search_path = public, pg_catalog as $$
begin
  return query
  insert into public.brain_concept_links (user_id, source_concept_id, target_concept_id, strength, relation, rationale, method)
  select p_uid, (x->>'source_concept_id')::uuid, (x->>'target_concept_id')::uuid, (x->>'strength')::real,
         x->>'relation', left(coalesce(x->>'rationale', ''), 400), coalesce(x->>'method', 'verified')
  from jsonb_array_elements(p_links) x
  where exists (select 1 from public.brain_concepts k where k.id = (x->>'source_concept_id')::uuid and k.user_id = p_uid)
    and exists (select 1 from public.brain_concepts k where k.id = (x->>'target_concept_id')::uuid and k.user_id = p_uid)
  on conflict (user_id, least(source_concept_id, target_concept_id), greatest(source_concept_id, target_concept_id)) do nothing
  returning id;
end $$;

-- Remove concepts nobody mentions any more (after a delete or re-file).
create or replace function public.brain_prune_concepts(p_uid uuid)
returns integer language sql security invoker set search_path = public, pg_catalog as $$
  with gone as (
    delete from public.brain_concepts k
    where k.user_id = p_uid and not exists (select 1 from public.brain_chunk_concepts m where m.concept_id = k.id)
    returning 1
  ) select count(*)::integer from gone;
$$;

-- One-tap fix. Moves the item, carries its concepts along (merging by name in the target
-- course), drops an auto-created course/topic that ends up empty, and records the correction.
create or replace function public.brain_refile_item(
  p_uid uuid, p_item uuid, p_course uuid, p_new_course_title text,
  p_topic uuid, p_new_topic_title text, p_auto_topic boolean
) returns jsonb language plpgsql security invoker set search_path = public, pg_catalog as $$
declare
  v_item public.brain_items;
  v_from_course public.brain_courses; v_from_topic public.brain_topics;
  v_course uuid; v_topic uuid; v_course_title text; v_topic_title text;
  r record; v_target uuid;
begin
  select * into v_item from public.brain_items where id = p_item and user_id = p_uid for update;
  if not found or v_item.status <> 'filed' then return null; end if;
  select * into v_from_course from public.brain_courses where id = v_item.course_id;
  select * into v_from_topic from public.brain_topics where id = v_item.topic_id;

  if p_course is not null then
    select id into v_course from public.brain_courses where id = p_course and user_id = p_uid;
    if v_course is null then raise exception 'Unknown course'; end if;
  elsif nullif(trim(coalesce(p_new_course_title, '')), '') is not null then
    select e.id into v_course from public.brain_ensure_course(p_uid, p_new_course_title, null, 'user') e;
  else
    raise exception 'Choose a course';
  end if;

  if p_topic is not null then
    select id into v_topic from public.brain_topics where id = p_topic and user_id = p_uid and course_id = v_course;
    if v_topic is null then raise exception 'Unknown topic'; end if;
  elsif nullif(trim(coalesce(p_new_topic_title, '')), '') is not null then
    select e.id into v_topic from public.brain_ensure_topic(p_uid, v_course, p_new_topic_title, null, null) e;
  elsif p_auto_topic and v_from_topic.id is not null then
    -- Keep a same-named topic if the target course has one.
    select t.id into v_topic from public.brain_topics t
    where t.user_id = p_uid and t.course_id = v_course and lower(t.title) = lower(v_from_topic.title);
  end if;

  -- Concepts mentioned by this item's passages.
  for r in
    select distinct k.* from public.brain_concepts k
    join public.brain_chunk_concepts m on m.concept_id = k.id
    join public.brain_chunks ch on ch.id = m.chunk_id
    where ch.item_id = p_item and k.user_id = p_uid and k.course_id <> v_course
  loop
    select id into v_target from public.brain_concepts
    where user_id = p_uid and course_id = v_course and lower(name) = lower(r.name);
    if v_target is null and not exists (
      select 1 from public.brain_chunk_concepts m join public.brain_chunks ch on ch.id = m.chunk_id
      where m.concept_id = r.id and ch.item_id <> p_item
    ) then
      -- Only this item knew the concept: move it.
      update public.brain_concepts set course_id = v_course, topic_id = v_topic where id = r.id;
    else
      if v_target is null then
        insert into public.brain_concepts (user_id, course_id, topic_id, name, summary, embedding)
        values (p_uid, v_course, v_topic, r.name, r.summary, r.embedding) returning id into v_target;
      end if;
      insert into public.brain_chunk_concepts (chunk_id, concept_id, user_id, weight)
      select m.chunk_id, v_target, p_uid, m.weight from public.brain_chunk_concepts m
      join public.brain_chunks ch on ch.id = m.chunk_id
      where m.concept_id = r.id and ch.item_id = p_item
      on conflict do nothing;
      delete from public.brain_chunk_concepts m using public.brain_chunks ch
      where m.chunk_id = ch.id and m.concept_id = r.id and ch.item_id = p_item;
    end if;
  end loop;

  update public.brain_items set course_id = v_course, topic_id = v_topic, confidence = 1, alternatives = '[]'::jsonb
  where id = p_item;

  select title into v_course_title from public.brain_courses where id = v_course;
  select title into v_topic_title from public.brain_topics where id = v_topic;
  insert into public.brain_refile_events (user_id, item_id, item_title, item_summary, from_course_title, from_topic_title, to_course_title, to_topic_title)
  values (p_uid, p_item, v_item.title, coalesce(v_item.summary, ''), v_from_course.title, v_from_topic.title, v_course_title, v_topic_title);

  perform public.brain_prune_concepts(p_uid);
  -- Drop an auto-created topic/course the correction emptied.
  if v_from_topic.id is not null and v_from_topic.id is distinct from v_topic
     and not exists (select 1 from public.brain_items where topic_id = v_from_topic.id)
     and not exists (select 1 from public.brain_concepts where topic_id = v_from_topic.id) then
    delete from public.brain_topics where id = v_from_topic.id;
  end if;
  if v_from_course.id is not null and v_from_course.id <> v_course and v_from_course.created_by = 'auto'
     and not exists (select 1 from public.brain_items where course_id = v_from_course.id)
     and not exists (select 1 from public.brain_concepts where course_id = v_from_course.id) then
    delete from public.brain_courses where id = v_from_course.id;
  end if;

  return jsonb_build_object('course_id', v_course, 'topic_id', v_topic,
    'removed_course_id', case when not exists (select 1 from public.brain_courses where id = v_from_course.id) then v_from_course.id end);
end $$;

-- Delete an item and anything only it supported.
create or replace function public.brain_delete_item(p_uid uuid, p_item uuid)
returns jsonb language plpgsql security invoker set search_path = public, pg_catalog as $$
declare v_item public.brain_items;
begin
  delete from public.brain_items where id = p_item and user_id = p_uid returning * into v_item;
  if not found then return null; end if;
  perform public.brain_prune_concepts(p_uid);
  return jsonb_build_object('id', v_item.id, 'object_path', v_item.object_path, 'thumbnail_path', v_item.thumbnail_path);
end $$;

-- Redeem a one-time Telegram code (hash only) and bind the chat to the account.
create or replace function public.brain_redeem_telegram_code(
  p_code_hash text, p_chat_id bigint, p_telegram_user_id bigint, p_username text
) returns uuid language plpgsql security invoker set search_path = public, pg_catalog as $$
declare v_uid uuid;
begin
  update public.brain_telegram_codes set used_at = now()
  where code_hash = p_code_hash and used_at is null and expires_at > now()
  returning user_id into v_uid;
  if v_uid is null or exists (select 1 from public.account_deletion_locks where user_id = v_uid) then return null; end if;
  -- A chat belongs to one account; re-linking moves it.
  delete from public.brain_telegram_links where chat_id = p_chat_id and user_id <> v_uid;
  insert into public.brain_telegram_links (user_id, chat_id, telegram_user_id, telegram_username, linked_at)
  values (v_uid, p_chat_id, p_telegram_user_id, left(p_username, 64), now())
  on conflict (user_id) do update set chat_id = excluded.chat_id, telegram_user_id = excluded.telegram_user_id,
    telegram_username = excluded.telegram_username, linked_at = now();
  delete from public.brain_telegram_codes where user_id = v_uid and code_hash <> p_code_hash;
  return v_uid;
end $$;

do $$
declare f text;
begin
  foreach f in array array[
    'public.brain_graph(uuid)',
    'public.brain_match_chunks(uuid, extensions.vector, integer, uuid[], uuid[])',
    'public.brain_match_concepts(uuid, extensions.vector, uuid[], integer, real)',
    'public.brain_search_chunks(uuid, text, integer)',
    'public.brain_vector(jsonb)',
    'public.brain_ensure_course(uuid, text, text, text)',
    'public.brain_ensure_topic(uuid, uuid, text, integer, text)',
    'public.brain_publish_item(uuid, uuid, uuid, jsonb)',
    'public.brain_add_links(uuid, jsonb)',
    'public.brain_prune_concepts(uuid)',
    'public.brain_refile_item(uuid, uuid, uuid, text, uuid, text, boolean)',
    'public.brain_delete_item(uuid, uuid)',
    'public.brain_redeem_telegram_code(text, bigint, bigint, text)'
  ] loop
    execute format('revoke all on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;

-- Private bucket for originals (photos, PDFs, audio) and thumbnails, when Supabase Storage is
-- the blob store. Objects live under <user_id>/<item_id>/; the API serves them via signed URLs.
do $$
begin
  if exists (select 1 from information_schema.tables where table_schema = 'storage' and table_name = 'buckets') then
    insert into storage.buckets (id, name, public, file_size_limit)
    values ('brain-captures', 'brain-captures', false, 26214400)
    on conflict (id) do nothing;
  end if;
end $$;
notify pgrst, 'reload schema';
