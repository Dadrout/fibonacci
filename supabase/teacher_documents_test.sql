-- Rollback-only regression checks; reserved fictional accounts.
begin;
insert into auth.users(id,email) values
('00000000-0000-4000-8000-000000000101','rag-a@example.test'),('00000000-0000-4000-8000-000000000102','rag-b@example.test');
insert into public.teacher_profiles(user_id) values('00000000-0000-4000-8000-000000000101'),('00000000-0000-4000-8000-000000000102');
insert into public.teacher_lessons(id,user_id,subject,grade,topic,language) values('00000000-0000-4000-8000-000000000111','00000000-0000-4000-8000-000000000101','science','5','Water','en-US');
select * from public.reserve_teacher_document('{"id":"00000000-0000-4000-8000-000000000121","user_id":"00000000-0000-4000-8000-000000000101","title":"Water","kind":"txt","language":"en-US","object_path":"fixture/water.txt","byte_count":20,"task_id":"00000000-0000-4000-8000-000000000131"}');
insert into public.teacher_documents(id,user_id,title,kind,language,object_path,byte_count,task_id,status) values('00000000-0000-4000-8000-000000000122','00000000-0000-4000-8000-000000000102','Other','txt','en-US','fixture/other.txt',20,'00000000-0000-4000-8000-000000000132','ready');
update public.teacher_documents set status='processing' where id='00000000-0000-4000-8000-000000000121';
do $$ begin
 if public.publish_teacher_document('00000000-0000-4000-8000-000000000121','00000000-0000-4000-8000-000000000101','00000000-0000-4000-8000-000000000132','[{"ordinal":0,"location":"Paragraph 1","text":"Water evaporates."}]') then raise exception 'Old task published'; end if;
 if not public.publish_teacher_document('00000000-0000-4000-8000-000000000121','00000000-0000-4000-8000-000000000101','00000000-0000-4000-8000-000000000131','[{"ordinal":0,"location":"Paragraph 1","text":"Water evaporates. Clouds form from condensation."}]') then raise exception 'Current task failed'; end if;
 if (select count(*) from public.search_teacher_passages('00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000121'::uuid],'evaporating OR cloud'))<>1 then raise exception 'English stemming failed'; end if;
 if (select count(*) from public.search_teacher_passages('00000000-0000-4000-8000-000000000102',array['00000000-0000-4000-8000-000000000121'::uuid],'Water'))<>0 then raise exception 'Cross-owner retrieval'; end if;
 if has_function_privilege('authenticated','public.search_teacher_passages(uuid,uuid[],text)','execute') or has_table_privilege('authenticated','public.teacher_document_chunks','insert') then raise exception 'Client write/search privilege leak'; end if;
 begin
  perform public.set_teacher_lesson_sources('00000000-0000-4000-8000-000000000111','00000000-0000-4000-8000-000000000101',1,array['00000000-0000-4000-8000-000000000122'::uuid]);
  raise exception 'Cross-owner attachment accepted';
 exception when raise_exception then
  if sqlerrm='Cross-owner attachment accepted' then raise; end if;
 end;
end $$;
select * from public.set_teacher_lesson_sources('00000000-0000-4000-8000-000000000111','00000000-0000-4000-8000-000000000101',1,array['00000000-0000-4000-8000-000000000121'::uuid]);
do $$ begin
 if exists(select 1 from public.set_teacher_lesson_sources('00000000-0000-4000-8000-000000000111','00000000-0000-4000-8000-000000000101',1,'{}')) then raise exception 'Stale attachment accepted'; end if;
end $$;
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000101',true);
do $$ begin
 if (select count(*) from public.teacher_documents)<>1 or (select count(*) from public.teacher_document_chunks)<>1 then raise exception 'Document RLS isolation failed'; end if;
end $$;
reset role;
-- Russian stemming and Kazakh simple tokens, scoped to selected ready sources.
insert into public.teacher_documents(id,user_id,title,kind,language,object_path,byte_count,task_id,status) values
('00000000-0000-4000-8000-000000000123','00000000-0000-4000-8000-000000000101','Russian','txt','ru-RU','fixture/ru.txt',20,gen_random_uuid(),'ready'),
('00000000-0000-4000-8000-000000000124','00000000-0000-4000-8000-000000000101','Kazakh','txt','kk-KZ','fixture/kk.txt',20,gen_random_uuid(),'ready');
insert into public.teacher_document_chunks(document_id,user_id,ordinal,location,body,language) values
('00000000-0000-4000-8000-000000000123','00000000-0000-4000-8000-000000000101',0,'Paragraph 1','Облака образуются при охлаждении пара.','ru-RU'),
('00000000-0000-4000-8000-000000000124','00000000-0000-4000-8000-000000000101',0,'Paragraph 1','Су буы бұлтқа айналады.','kk-KZ');
do $$ begin
 if (select count(*) from public.search_teacher_passages('00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000123'::uuid],'облако'))<>1 then raise exception 'Russian stemming failed'; end if;
 if (select count(*) from public.search_teacher_passages('00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000124'::uuid],'СУ'))<>1 then raise exception 'Kazakh token failed'; end if;
 if exists(select 1 from public.search_teacher_passages('00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000121'::uuid],'облако')) then raise exception 'Unselected document retrieved'; end if;
end $$;
insert into public.teacher_resources(id,lesson_id,user_id,kind,lesson_snapshot) values
('00000000-0000-4000-8000-000000000141','00000000-0000-4000-8000-000000000111','00000000-0000-4000-8000-000000000101','quiz','{"topic":"Water"}'),
('00000000-0000-4000-8000-000000000142','00000000-0000-4000-8000-000000000111','00000000-0000-4000-8000-000000000101','quiz','{"topic":"Water"}');
do $$ begin
 if not exists(select 1 from public.finish_sourced_teacher_resource('00000000-0000-4000-8000-000000000141','00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000121'::uuid],'{"title":"Water"}','{"status":"source_based","sources":[]}')) then raise exception 'Ready sources did not finalize'; end if;
 if exists(select 1 from public.finish_sourced_teacher_resource('00000000-0000-4000-8000-000000000141','00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000121'::uuid],'{"title":"Duplicate"}','{}')) then raise exception 'Duplicate finalization accepted'; end if;
end $$;
select * from public.mark_teacher_document_deleting('00000000-0000-4000-8000-000000000121','00000000-0000-4000-8000-000000000101');
do $$ begin
 if exists(select 1 from public.search_teacher_passages('00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000121'::uuid],'Water')) then raise exception 'Deleting source retrieved'; end if;
 if (select cardinality(source_document_ids) from public.teacher_lessons where id='00000000-0000-4000-8000-000000000111')<>0 then raise exception 'Source not detached'; end if;
 if public.publish_teacher_document('00000000-0000-4000-8000-000000000121','00000000-0000-4000-8000-000000000101','00000000-0000-4000-8000-000000000131','[{"ordinal":0,"location":"Paragraph 1","text":"Water"}]') then raise exception 'Deleted source republished'; end if;
end $$;
do $$ begin
 if exists(select 1 from public.finish_sourced_teacher_resource('00000000-0000-4000-8000-000000000142','00000000-0000-4000-8000-000000000101',array['00000000-0000-4000-8000-000000000121'::uuid],'{"title":"Late"}','{}')) then raise exception 'Deleted source finalized resource'; end if;
 if (select status from public.teacher_resources where id='00000000-0000-4000-8000-000000000141')<>'ready' then raise exception 'Saved resource lost on source deletion'; end if;
end $$;
-- Pending removals occupy a slot until their retained originals are cleaned up.
insert into public.teacher_documents(id,user_id,title,kind,language,object_path,byte_count,task_id,status)
select gen_random_uuid(),'00000000-0000-4000-8000-000000000101','Quota fixture','txt','en-US','fixture/quota.txt',1,gen_random_uuid(),'ready' from generate_series(1,47);
do $$ begin
 begin
  perform public.reserve_teacher_document('{"id":"00000000-0000-4000-8000-000000000125","user_id":"00000000-0000-4000-8000-000000000101","title":"Over quota","kind":"txt","language":"en-US","object_path":"fixture/q.txt","byte_count":1,"task_id":"00000000-0000-4000-8000-000000000135"}');
  raise exception 'Quota accepted pending-deletion overflow';
 exception when raise_exception then
  if sqlerrm<>'Source limit reached' then raise; end if;
 end;
end $$;
delete from auth.users where id='00000000-0000-4000-8000-000000000101';
do $$ begin
 if exists(select 1 from public.teacher_documents where user_id='00000000-0000-4000-8000-000000000101') or exists(select 1 from public.teacher_document_chunks where user_id='00000000-0000-4000-8000-000000000101') then raise exception 'Account cascade failed'; end if;
end $$;
rollback;
