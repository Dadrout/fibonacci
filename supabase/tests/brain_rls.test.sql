-- Fibonacci Brain: access rules and server functions. Run with `supabase test db`
-- or `supabase/tests/run_brain_tests.sh` (local Docker database).
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select plan(42);

-- Unit vector e_i in 768 dimensions, as the JSON the API sends.
create function pg_temp.vec(i integer) returns jsonb language sql immutable as $$
  select jsonb_agg(case when g = i then 1.0 else 0.0 end order by g) from generate_series(1, 768) g;
$$;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-0000000000a1', 'brain-a@example.test'),
  ('00000000-0000-4000-8000-0000000000b1', 'brain-b@example.test');

-- ---------------------------------------------------------------- privileges
select is((select count(*)::integer from pg_class where relnamespace = 'public'::regnamespace and relname like 'brain\_%' and relkind = 'r' and relrowsecurity), 13,
  'row-level security is on for all 13 brain tables');
select is((select count(*)::integer from pg_class c where relnamespace = 'public'::regnamespace and relname like 'brain\_%' and relkind = 'r'
  and (has_table_privilege('authenticated', c.oid, 'insert') or has_table_privilege('authenticated', c.oid, 'update') or has_table_privilege('authenticated', c.oid, 'delete'))), 0,
  'clients cannot write any brain table directly');
select is((select count(*)::integer from pg_class c where relnamespace = 'public'::regnamespace and relname like 'brain\_%' and relkind = 'r'
  and has_table_privilege('anon', c.oid, 'select')), 0, 'signed-out visitors cannot read any brain table');
select ok(has_table_privilege('authenticated', 'public.brain_items', 'select'), 'learners may read their items subject to owner policies');
select ok(not has_table_privilege('authenticated', 'public.brain_plan_secrets', 'select'), 'quiz answer keys are server-only');
select ok(not has_table_privilege('authenticated', 'public.brain_telegram_codes', 'select'), 'Telegram link codes are server-only');
select ok(not has_function_privilege('authenticated', 'public.brain_publish_item(uuid, uuid, uuid, jsonb)', 'execute'), 'clients cannot call the filing function');
select ok(not has_function_privilege('anon', 'public.brain_redeem_telegram_code(text, bigint, bigint, text)', 'execute'), 'visitors cannot redeem Telegram codes');
select ok(has_function_privilege('service_role', 'public.brain_publish_item(uuid, uuid, uuid, jsonb)', 'execute'), 'the API can file items');

-- ---------------------------------------------------------------- filing
insert into public.brain_items (id, user_id, kind, channel, title, task_id, status) values
  ('00000000-0000-4000-8000-00000000c001', '00000000-0000-4000-8000-0000000000a1', 'photo', 'telegram', 'IMG_4182.jpg', '00000000-0000-4000-8000-00000000d001', 'classifying'),
  ('00000000-0000-4000-8000-00000000c002', '00000000-0000-4000-8000-0000000000a1', 'pdf', 'web_drop', 'week6.pdf', '00000000-0000-4000-8000-00000000d002', 'classifying'),
  ('00000000-0000-4000-8000-00000000c003', '00000000-0000-4000-8000-0000000000a1', 'youtube', 'web_paste', 'Variance video', '00000000-0000-4000-8000-00000000d003', 'classifying'),
  ('00000000-0000-4000-8000-00000000c009', '00000000-0000-4000-8000-0000000000b1', 'text', 'web_paste', 'B note', '00000000-0000-4000-8000-00000000d009', 'classifying');

select is(public.brain_publish_item('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c001', '00000000-0000-4000-8000-00000000dead',
  '{"course":{"title":"Econometrics"},"chunks":[{"ordinal":0,"anchor_kind":"slide","slide":7,"body":"x"}]}'::jsonb), null,
  'a stale worker (wrong task token) cannot file an item');

create temp table filed1 as select public.brain_publish_item('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c001', '00000000-0000-4000-8000-00000000d001',
  jsonb_build_object(
    'course', jsonb_build_object('title', 'Econometrics', 'code', 'ECON 301'),
    'topic', jsonb_build_object('title', 'Heteroskedasticity', 'sequence', 6, 'sequence_kind', 'week'),
    'item', jsonb_build_object('title', 'Slide 7 — Heteroskedasticity', 'summary', 'Var(u|x) is not constant.', 'language', 'en-US', 'confidence', 0.94,
      'alternatives', '[]'::jsonb, 'timings_ms', jsonb_build_object('extract', 1200)),
    'chunks', jsonb_build_array(
      jsonb_build_object('ordinal', 0, 'anchor_kind', 'slide', 'slide', 7, 'body', 'Heteroskedasticity: Var(u|x) depends on x.', 'embedding', pg_temp.vec(1))),
    'concepts', jsonb_build_array(
      jsonb_build_object('name', 'Heteroskedasticity', 'summary', 'Non-constant error variance.', 'embedding', pg_temp.vec(1), 'chunk_ordinals', '[0]'::jsonb)))) as r;

select ok((select (r->>'course_created')::boolean and (r->>'topic_created')::boolean from filed1), 'filing creates a new course and topic when nothing fits');
select is((select status from public.brain_items where id = '00000000-0000-4000-8000-00000000c001'), 'linking', 'a filed item moves on to linking');
select is((select anchor_kind || ':' || slide from public.brain_chunks where item_id = '00000000-0000-4000-8000-00000000c001'), 'slide:7', 'passages keep their source anchor');

create temp table filed2 as select public.brain_publish_item('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c002', '00000000-0000-4000-8000-00000000d002',
  jsonb_build_object(
    'course', jsonb_build_object('title', 'econometrics'),
    'topic', jsonb_build_object('title', 'Week 6 notes', 'sequence', 6, 'sequence_kind', 'week'),
    'item', jsonb_build_object('title', 'Week 6 notes', 'confidence', 0.9),
    'chunks', jsonb_build_array(
      jsonb_build_object('ordinal', 0, 'anchor_kind', 'page', 'page', 2, 'body', 'Usual standard errors are biased.', 'embedding', pg_temp.vec(2)),
      jsonb_build_object('ordinal', 1, 'anchor_kind', 'page', 'page', 4, 'body', 'White test uses squared residuals.', 'embedding', pg_temp.vec(3))),
    'concepts', jsonb_build_array(
      jsonb_build_object('name', 'heteroskedasticity', 'summary', '', 'chunk_ordinals', '[0]'::jsonb),
      jsonb_build_object('name', 'White test', 'summary', 'A test for heteroskedasticity.', 'embedding', pg_temp.vec(3), 'chunk_ordinals', '[1]'::jsonb)))) as r;

select ok((select not (r->>'course_created')::boolean from filed2), 'course titles match case-insensitively');
select is((select r->>'topic_id' from filed2), (select r->>'topic_id' from filed1), 'the same week number lands in the same topic');
select is((select count(*)::integer from public.brain_concepts where user_id = '00000000-0000-4000-8000-0000000000a1' and lower(name) = 'heteroskedasticity'), 1,
  'concepts merge by name within a course');

select public.brain_publish_item('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c003', '00000000-0000-4000-8000-00000000d003',
  jsonb_build_object(
    'course', jsonb_build_object('title', 'Probability & Statistics'),
    'topic', jsonb_build_object('title', 'Expectation and variance', 'sequence', 2, 'sequence_kind', 'lecture'),
    'item', jsonb_build_object('title', 'Variance video', 'confidence', 0.88),
    'chunks', jsonb_build_array(jsonb_build_object('ordinal', 0, 'anchor_kind', 'timestamp', 'start_sec', 262, 'end_sec', 330, 'body', 'Variance is E[X^2] minus the mean squared.', 'embedding', pg_temp.vec(1))),
    'concepts', jsonb_build_array(jsonb_build_object('name', 'Variance', 'summary', 'Spread around the mean.', 'embedding', pg_temp.vec(1), 'chunk_ordinals', '[0]'::jsonb))));
select public.brain_publish_item('00000000-0000-4000-8000-0000000000b1', '00000000-0000-4000-8000-00000000c009', '00000000-0000-4000-8000-00000000d009',
  jsonb_build_object('course', jsonb_build_object('title', 'Biology'), 'item', jsonb_build_object('title', 'B note'),
    'chunks', jsonb_build_array(jsonb_build_object('ordinal', 0, 'anchor_kind', 'paragraph', 'paragraph', 1, 'body', 'Cells.', 'embedding', pg_temp.vec(1))),
    'concepts', jsonb_build_array(jsonb_build_object('name', 'Cell', 'embedding', pg_temp.vec(1)))));
update public.brain_items set status = 'filed', filed_at = now() where status = 'linking';

select throws_ok($$ insert into public.brain_chunks (user_id, item_id, ordinal, anchor_kind, page, body)
  values ('00000000-0000-4000-8000-0000000000b1', '00000000-0000-4000-8000-00000000c001', 9, 'page', 1, 'injected') $$,
  '23503', null, 'a row cannot point at another user''s item');
select throws_ok($$ insert into public.brain_chunks (user_id, item_id, ordinal, anchor_kind, body)
  values ('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c001', 9, 'timestamp', 'no times') $$,
  '23514', null, 'timestamp anchors need start and end');

-- ---------------------------------------------------------------- matching and links
select is((select count(*)::integer from public.brain_match_chunks('00000000-0000-4000-8000-0000000000a1', (pg_temp.vec(1)::text)::vector, 10)), 4,
  'vector search returns only the caller''s passages');
select is((select name from public.brain_match_concepts('00000000-0000-4000-8000-0000000000a1', (pg_temp.vec(1)::text)::vector,
  array[(select id from public.brain_concepts where name = 'Heteroskedasticity')], 5, 0.9) limit 1), 'Variance',
  'concept matching finds the closest other concept above the threshold');
select is((select count(*)::integer from public.brain_match_concepts('00000000-0000-4000-8000-0000000000a1', (pg_temp.vec(5)::text)::vector, '{}', 5, 0.9)), 0,
  'nothing is matched below the similarity threshold');

create temp table k as select
  (select id from public.brain_concepts where name = 'Heteroskedasticity') as het,
  (select id from public.brain_concepts where name = 'Variance') as var,
  (select id from public.brain_concepts where name = 'White test') as white;
select is((select count(*)::integer from public.brain_add_links('00000000-0000-4000-8000-0000000000a1', jsonb_build_array(
  jsonb_build_object('source_concept_id', (select het from k), 'target_concept_id', (select var from k), 'strength', 0.89, 'relation', 'builds_on', 'rationale', 'Conditional variance.')))), 1,
  'a verified link is stored');
select is((select count(*)::integer from public.brain_add_links('00000000-0000-4000-8000-0000000000a1', jsonb_build_array(
  jsonb_build_object('source_concept_id', (select var from k), 'target_concept_id', (select het from k), 'strength', 0.9, 'relation', 'builds_on')))), 0,
  'the reverse direction of an existing link is not duplicated');
select throws_ok($$ select public.brain_add_links('00000000-0000-4000-8000-0000000000a1', jsonb_build_array(jsonb_build_object(
  'source_concept_id', (select het from k), 'target_concept_id', (select white from k), 'strength', 0.3, 'relation', 'applies'))) $$,
  '23514', null, 'machine links below the confidence floor are rejected');
select is((select count(*)::integer from public.brain_add_links('00000000-0000-4000-8000-0000000000b1', jsonb_build_array(
  jsonb_build_object('source_concept_id', (select het from k), 'target_concept_id', (select white from k), 'strength', 0.9, 'relation', 'applies')))), 0,
  'a user cannot link another user''s concepts');
select ok((select bool_and((l->>'cross_course')::boolean) from jsonb_array_elements(public.brain_graph('00000000-0000-4000-8000-0000000000a1')->'links') l),
  'the graph marks Econometrics ↔ Probability as a cross-course link');
select is((select jsonb_array_length(public.brain_graph('00000000-0000-4000-8000-0000000000a1')->'courses')), 2, 'the graph lists the user''s courses');

-- ---------------------------------------------------------------- owner reads
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-0000000000a1', true);
select is((select count(*)::integer from public.brain_items), 3, 'a learner reads only their own items');
select is((select count(*)::integer from public.brain_concepts where user_id = '00000000-0000-4000-8000-0000000000b1'), 0, 'another learner''s concepts are invisible');
select throws_ok($$ select * from public.brain_plan_secrets $$, '42501', null, 'answer keys cannot be read even by the owner');
select throws_ok($$ insert into public.brain_courses (user_id, title) values ('00000000-0000-4000-8000-0000000000a1', 'Sneaky') $$, '42501', null,
  'learners cannot create courses directly');
reset role;

-- ---------------------------------------------------------------- re-file and delete
-- Move the slide to a brand-new course; its concept is shared with the PDF, so a copy is made.
create temp table refiled as select public.brain_refile_item('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c001', null, 'Statistics Seminar', null, null, true) as r;
select is((select c.title from public.brain_items i join public.brain_courses c on c.id = i.course_id where i.id = '00000000-0000-4000-8000-00000000c001'),
  'Statistics Seminar', 're-filing moves the item to the chosen course');
select is((select count(*)::integer from public.brain_concepts where user_id = '00000000-0000-4000-8000-0000000000a1' and name = 'Heteroskedasticity'), 2,
  'a concept shared with other items is copied, not stolen');
select is((select to_course_title from public.brain_refile_events where item_id = '00000000-0000-4000-8000-00000000c001'), 'Statistics Seminar',
  'the correction is recorded for the classifier to learn from');
-- Move the variance video into Econometrics: its course becomes empty and was auto-created, so it goes.
select public.brain_refile_item('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c003',
  (select course_id from public.brain_items where id = '00000000-0000-4000-8000-00000000c002'), null, null, null, true);
select is((select count(*)::integer from public.brain_courses where user_id = '00000000-0000-4000-8000-0000000000a1' and title = 'Probability & Statistics'), 0,
  'an auto-created course emptied by a correction is removed');
select is((select count(*)::integer from public.brain_concept_links), 1, 'links follow a concept that moved with its only item');

select ok(public.brain_delete_item('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-00000000c001') is not null, 'an item can be deleted');
select is((select count(*)::integer from public.brain_concepts c join public.brain_courses s on s.id = c.course_id where s.title = 'Statistics Seminar'), 0,
  'concepts only that item supported are pruned');

-- ---------------------------------------------------------------- Telegram codes
insert into public.brain_telegram_codes (code_hash, user_id, expires_at) values
  (encode(sha256('483921'::bytea), 'hex'), '00000000-0000-4000-8000-0000000000a1', now() + interval '10 minutes'),
  (encode(sha256('111111'::bytea), 'hex'), '00000000-0000-4000-8000-0000000000b1', now() - interval '1 minute');
select is(public.brain_redeem_telegram_code(encode(sha256('483921'::bytea), 'hex'), 777001, 42, 'aruzhan_s'), '00000000-0000-4000-8000-0000000000a1'::uuid,
  'a valid code links the chat to its account');
select is(public.brain_redeem_telegram_code(encode(sha256('483921'::bytea), 'hex'), 777002, 43, 'intruder'), null, 'a code works only once');
select is(public.brain_redeem_telegram_code(encode(sha256('111111'::bytea), 'hex'), 777003, 44, 'late'), null, 'an expired code is refused');

-- ---------------------------------------------------------------- account deletion
delete from auth.users where id = '00000000-0000-4000-8000-0000000000a1';
select is((select count(*)::integer from public.brain_items where user_id = '00000000-0000-4000-8000-0000000000a1')
  + (select count(*)::integer from public.brain_concepts where user_id = '00000000-0000-4000-8000-0000000000a1')
  + (select count(*)::integer from public.brain_telegram_links where user_id = '00000000-0000-4000-8000-0000000000a1'), 0,
  'deleting the account removes the whole brain and the Telegram link');

select * from finish();
rollback;
