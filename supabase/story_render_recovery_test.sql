begin;
do $$
declare uid uuid; d public.story_drafts; claim jsonb; test_id uuid; job text := 'rollback-render-' || gen_random_uuid()::text;
begin
 select id into uid from auth.users where email like 'local-audit-%@example.test' limit 1;
 if uid is null then raise exception 'Create a disposable local-audit learner fixture before this check'; end if;
 insert into public.story_drafts(user_id,subject,topic,grade_band,target_duration_sec,language,voice,script,recap,quiz)
 values(uid,'geography','Fictional river check','10-12',60,'en-US','female','{"title":"River","full_narration":"River facts"}','River recap','[]') returning * into d;
 claim := public.claim_story_render(d.id,uid,job);
 if claim->'draft'->>'status' <> 'rendering' or claim->'story'->>'task_id' <> job then raise exception 'Atomic claim failed'; end if;
 if public.claim_story_render(d.id,uid,job||'-duplicate') is not null then raise exception 'Duplicate claim succeeded'; end if;
 if public.claim_story_render(d.id,gen_random_uuid(),job||'-other') is not null then raise exception 'Cross-owner claim succeeded'; end if;
 perform public.recover_story_render(d.id,uid);
 if (select status from public.story_drafts where id=d.id) <> 'rendering' then raise exception 'Active queued draft was reclaimed'; end if;
 -- A stale pending row models an API crash after commit and before broker send.
 insert into public.story_drafts(user_id,subject,topic,grade_band,target_duration_sec,language,voice,script,recap,quiz,status)
 values(uid,'geography','Queue interruption','10-12',60,'en-US','female','{"title":"River"}','Recap','[]','rendering') returning id into test_id;
 insert into public.stories(user_id,draft_id,task_id,subject,topic,title,grade_band,target_duration_sec,language,voice,updated_at)
 values(uid,test_id,job||'-interrupted','geography','Queue interruption','River','10-12',60,'en-US','female',now()-interval '11 minutes');
 perform public.recover_story_render(test_id,gen_random_uuid());
 if (select status from public.story_drafts where id=test_id) <> 'rendering' then raise exception 'Cross-owner recovery changed a draft'; end if;
 perform public.recover_story_render(test_id,uid);
 if (select status from public.story_drafts where id=test_id) <> 'draft' or (select status from public.stories where draft_id=test_id) <> 'FAILURE' then raise exception 'Interrupted queue did not recover'; end if;
 -- Insertion failure must undo the claim as one transaction.
 begin
   perform public.claim_story_render(test_id,uid,job);
   raise exception 'Expected duplicate task error';
 exception when unique_violation then null;
 end;
 if (select status from public.story_drafts where id=test_id) <> 'draft' then raise exception 'Insertion failure stranded a draft'; end if;
 if has_function_privilege('authenticated','public.claim_story_render(uuid,uuid,text)','execute') or has_function_privilege('anon','public.recover_story_render(uuid,uuid)','execute') then raise exception 'Render mutation exposed to browser roles'; end if;
 raise notice 'Atomic claim, snapshot, rollback, duplicate, owner isolation and interrupted queue recovery passed';
end $$;
rollback;
