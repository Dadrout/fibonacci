begin;
select plan(13);

insert into public.knowledge_entries (
  id, subject, canonical_topic, aliases, grade_bands, facts, sources, is_approved
) values
  (
    '00000000-0000-4000-8000-000000000001', 'history', 'RLS approved fixture',
    array['approved fixture'], array['13-15'], jsonb_build_array('Reviewed fact.'),
    jsonb_build_array(jsonb_build_object('title', 'Fixture', 'url', 'https://example.org/fixture')), true
  ),
  (
    '00000000-0000-4000-8000-000000000002', 'history', 'RLS hidden fixture',
    array['hidden fixture'], array['13-15'], jsonb_build_array('Unreviewed fact.'),
    jsonb_build_array(jsonb_build_object('title', 'Fixture', 'url', 'https://example.org/hidden')), false
  );

select ok(
  (select relrowsecurity from pg_class where oid = 'public.knowledge_entries'::regclass),
  'row-level security is enabled on knowledge_entries'
);
select ok(has_table_privilege('authenticated', 'public.knowledge_entries', 'select'),
  'authenticated learners can select knowledge entries');
select ok(not has_table_privilege('anon', 'public.knowledge_entries', 'select'),
  'unauthenticated users have no table read grant');
select ok(not has_table_privilege('authenticated', 'public.knowledge_entries', 'insert'),
  'authenticated learners cannot insert knowledge entries');
select ok(not has_table_privilege('authenticated', 'public.knowledge_entries', 'update'),
  'authenticated learners cannot update knowledge entries');
select ok(not has_table_privilege('authenticated', 'public.knowledge_entries', 'delete'),
  'authenticated learners cannot delete knowledge entries');
select ok(has_function_privilege('authenticated',
  'public.search_knowledge_entries(text,text,text,integer)', 'execute'),
  'authenticated learners may use the read-only search function');
select ok(not has_function_privilege('anon',
  'public.search_knowledge_entries(text,text,text,integer)', 'execute'),
  'unauthenticated users cannot search the shared library');

set local role authenticated;
select is(
  (select count(*)::integer from public.knowledge_entries where id = '00000000-0000-4000-8000-000000000001'),
  1,
  'authenticated learners can read approved entries'
);
select is(
  (select count(*)::integer from public.knowledge_entries where id = '00000000-0000-4000-8000-000000000002'),
  0,
  'authenticated learners cannot read unapproved entries'
);
select is(
  (select match_type from public.search_knowledge_entries('approved fixture', 'history', '13-15', 3) limit 1),
  'exact',
  'database search labels an exact alias match as grounded'
);
select is(
  (select match_type from public.search_knowledge_entries('reviewed', 'history', '13-15', 3) limit 1),
  'partial',
  'database search labels a text match as partial'
);
select is(
  (select count(*)::integer from public.search_knowledge_entries('approved fixture', 'history', '10-12', 3)),
  0,
  'database search filters out unsupported grade bands'
);
reset role;

select * from finish();
rollback;
