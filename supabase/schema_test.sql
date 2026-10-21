-- Run after schema.sql as a staging database administrator. Rolls back fixtures.
begin;
do $$ begin
 if not exists(select 1 from pg_class where oid='public.account_deletion_locks'::regclass and relrowsecurity) then
   raise exception 'Deletion locks require RLS';
 end if;
 if has_table_privilege('authenticated','public.story_drafts','INSERT') or
    has_table_privilege('authenticated','public.stories','UPDATE') or
    has_table_privilege('authenticated','public.quiz_results','INSERT') or
    has_table_privilege('anon','public.story_drafts','SELECT') then
   raise exception 'Learner table client permissions are too broad';
 end if;
end $$;
insert into public.knowledge_entries(subject,canonical_topic,aliases,facts,sources,is_approved)
values('history','Schema search regression',array['quartzmarigold'], '["A regression fixture."]','[{"title":"Test","url":"https://example.test"}]',true);
do $$ begin
 if not exists(select 1 from public.knowledge_entries
   where canonical_topic='Schema search regression' and search_document @@ to_tsquery('simple','quartzmarigold')) then
   raise exception 'Generated search vector lost alias text';
 end if;
end $$;
rollback;
