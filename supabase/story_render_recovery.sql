-- Apply after schema.sql. Server-only atomic render submission and recovery.
create or replace function public.claim_story_render(p_draft_id uuid, p_user_id uuid, p_task_id text)
returns jsonb language plpgsql security invoker set search_path = public, pg_temp as $$
declare d public.story_drafts; s public.stories;
begin
  if exists(select 1 from public.account_deletion_locks where user_id=p_user_id) then return null; end if;
  select * into d from public.story_drafts where id=p_draft_id and user_id=p_user_id for update;
  if not found or d.status <> 'draft' then return null; end if;
  update public.story_drafts set status='rendering' where id=d.id returning * into d;
  insert into public.stories(user_id,draft_id,task_id,subject,topic,title,grade_band,target_duration_sec,language,voice,sources,knowledge_status)
  values(d.user_id,d.id,p_task_id,d.subject,d.topic,d.script->>'title',d.grade_band,d.target_duration_sec,d.language,d.voice,d.sources,d.knowledge_status)
  returning * into s;
  return jsonb_build_object('draft',to_jsonb(d),'story',to_jsonb(s));
end; $$;
revoke all on function public.claim_story_render(uuid,uuid,text) from public, anon, authenticated;
grant execute on function public.claim_story_render(uuid,uuid,text) to service_role;

create or replace function public.recover_story_render(p_draft_id uuid,p_user_id uuid)
returns void language plpgsql security invoker set search_path = public, pg_temp as $$
declare d public.story_drafts; s public.stories;
begin
  select * into d from public.story_drafts where id=p_draft_id and user_id=p_user_id for update;
  if not found or d.status <> 'rendering' then return; end if;
  if exists(select 1 from public.account_deletion_locks where user_id=p_user_id) then return; end if;
  select * into s from public.stories where draft_id=d.id and user_id=p_user_id order by created_at desc limit 1 for update;
  if not found then
    -- Repair old submissions made before atomic claim/create was introduced.
    if d.updated_at < now()-interval '10 minutes' then update public.story_drafts set status='draft' where id=d.id; end if;
    return;
  end if;
  if s.status='SUCCESS' then update public.story_drafts set status='complete' where id=d.id; return; end if;
  if (s.status='PENDING' and s.updated_at < now()-interval '10 minutes')
     or (s.status='PROGRESS' and s.updated_at < now()-interval '30 minutes') then
    update public.stories set status='FAILURE',progress=0,stage='interrupted',message='Generation was interrupted. Your draft is ready to retry.',error='Generation was interrupted. Your draft is ready to retry.' where id=s.id;
    s.status := 'FAILURE';
  end if;
  if s.status='FAILURE' then update public.story_drafts set status='draft' where id=d.id; end if;
end; $$;
revoke all on function public.recover_story_render(uuid,uuid) from public, anon, authenticated;
grant execute on function public.recover_story_render(uuid,uuid) to service_role;
