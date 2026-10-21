-- Additive upgrade after teacher_prep.sql. RPCs are server-only and SECURITY INVOKER.
create table public.teacher_documents (
 id uuid primary key, user_id uuid not null references public.teacher_profiles(user_id) on delete cascade,
 title text not null check(char_length(trim(title)) between 1 and 200),
 kind text not null check(kind in ('pdf','docx','txt')),
 language text not null check(language in ('en-US','ru-RU','kk-KZ')),
 status text not null default 'uploading' check(status in ('uploading','processing','ready','failed','deleting')),
 object_path text not null, byte_count integer not null check(byte_count between 1 and 10485760),
 task_id uuid not null, error_message text, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(id,user_id)
);
create table public.teacher_document_chunks (
 id uuid primary key default gen_random_uuid(), document_id uuid not null, user_id uuid not null,
 ordinal integer not null check(ordinal>=0), location text not null, body text not null check(char_length(body) between 1 and 8000),
 language text not null check(language in ('en-US','ru-RU','kk-KZ')),
 search_document tsvector generated always as (
 case language when 'en-US' then to_tsvector('english'::regconfig,body)
 when 'ru-RU' then to_tsvector('russian'::regconfig,body) else to_tsvector('simple'::regconfig,body) end) stored,
 foreign key(document_id,user_id) references public.teacher_documents(id,user_id) on delete cascade,
 unique(document_id,ordinal)
);
create index teacher_documents_owner_status on public.teacher_documents(user_id,status);
create index teacher_document_chunks_owner_document on public.teacher_document_chunks(user_id,document_id);
create index teacher_document_chunks_document_owner on public.teacher_document_chunks(document_id,user_id);
create index teacher_document_chunks_fts on public.teacher_document_chunks using gin(search_document);
alter table public.teacher_lessons add column source_document_ids uuid[] not null default '{}';
alter table public.teacher_resources add column provenance jsonb;
alter table public.teacher_documents enable row level security;
alter table public.teacher_document_chunks enable row level security;
revoke all on public.teacher_documents,public.teacher_document_chunks from public,anon,authenticated;
grant select on public.teacher_documents,public.teacher_document_chunks to authenticated;
grant all on public.teacher_documents,public.teacher_document_chunks to service_role;
create policy teacher_documents_read on public.teacher_documents for select to authenticated using((select auth.uid())=user_id and status <> 'deleting');
create policy teacher_chunks_read on public.teacher_document_chunks for select to authenticated using((select auth.uid())=user_id and exists(select 1 from public.teacher_documents d where d.id=document_id and d.status='ready'));
create trigger teacher_documents_updated before update on public.teacher_documents for each row execute function public.set_updated_at();

create function public.validate_teacher_sources() returns trigger language plpgsql security invoker set search_path=public,pg_catalog as $$
begin
 if cardinality(new.source_document_ids)>5 or cardinality(new.source_document_ids)<>(select count(distinct x) from unnest(new.source_document_ids) x) then raise exception 'Select at most five distinct sources'; end if;
 if (select count(*) from public.teacher_documents where id=any(new.source_document_ids) and user_id=new.user_id and status='ready') <> cardinality(new.source_document_ids) then raise exception 'Sources must be ready and belong to the lesson owner'; end if;
 return new;
end;$$;
create trigger teacher_sources_valid before insert or update of source_document_ids on public.teacher_lessons for each row execute function public.validate_teacher_sources();

create function public.reserve_teacher_document(p_record jsonb) returns setof public.teacher_documents language plpgsql security invoker set search_path=public,pg_catalog as $$
declare owner_id uuid := (p_record->>'user_id')::uuid;
begin
 perform 1 from public.teacher_profiles where user_id=owner_id for update;
 if not found or exists(select 1 from public.account_deletion_locks where user_id=owner_id) then raise exception 'Account unavailable'; end if;
 if (select count(*) from public.teacher_documents where user_id=owner_id)>=50 then raise exception 'Source limit reached'; end if;
 return query insert into public.teacher_documents(id,user_id,title,kind,language,object_path,byte_count,task_id)
 values((p_record->>'id')::uuid,owner_id,p_record->>'title',p_record->>'kind',p_record->>'language',p_record->>'object_path',(p_record->>'byte_count')::integer,(p_record->>'task_id')::uuid) returning *;
end;$$;

create function public.publish_teacher_document(p_id uuid,p_uid uuid,p_task uuid,p_chunks jsonb) returns boolean language plpgsql security invoker set search_path=public,pg_catalog as $$
declare doc public.teacher_documents;
begin
 select * into doc from public.teacher_documents where id=p_id and user_id=p_uid for update;
 if not found or doc.status<>'processing' or doc.task_id<>p_task or exists(select 1 from public.account_deletion_locks where user_id=p_uid) then return false; end if;
 if jsonb_array_length(p_chunks)=0 or (select sum(char_length(x->>'text')) from jsonb_array_elements(p_chunks) x)>250000 then raise exception 'Invalid extracted passages'; end if;
 delete from public.teacher_document_chunks where document_id=p_id and user_id=p_uid;
 insert into public.teacher_document_chunks(document_id,user_id,ordinal,location,body,language)
 select p_id,p_uid,(x->>'ordinal')::integer,x->>'location',x->>'text',doc.language from jsonb_array_elements(p_chunks) x;
 update public.teacher_documents set status='ready',error_message=null where id=p_id;
 return true;
end;$$;

create function public.set_teacher_lesson_sources(p_id uuid,p_uid uuid,p_revision integer,p_sources uuid[]) returns setof public.teacher_lessons language plpgsql security invoker set search_path=public,pg_catalog as $$
begin
 perform 1 from public.teacher_profiles where user_id=p_uid for update;
 if exists(select 1 from public.account_deletion_locks where user_id=p_uid) then return; end if;
 -- Serialize attachment validation with source deletion.
 perform 1 from public.teacher_documents where user_id=p_uid and id=any(p_sources) order by id for update;
 return query update public.teacher_lessons set source_document_ids=p_sources,revision=revision+1 where id=p_id and user_id=p_uid and revision=p_revision returning *;
end;$$;

create function public.mark_teacher_document_deleting(p_id uuid,p_uid uuid) returns setof public.teacher_documents language plpgsql security invoker set search_path=public,pg_catalog as $$
begin
 perform 1 from public.teacher_profiles where user_id=p_uid for update;
 perform 1 from public.teacher_documents where id=p_id and user_id=p_uid for update;
 if not found then return; end if;
 update public.teacher_lessons set source_document_ids=array_remove(source_document_ids,p_id),revision=revision+1 where user_id=p_uid and p_id=any(source_document_ids);
 return query update public.teacher_documents set status='deleting' where id=p_id and user_id=p_uid returning *;
end;$$;

create function public.search_teacher_passages(p_uid uuid,p_sources uuid[],p_query text) returns table(id uuid,document_id uuid,title text,location text,body text,rank real) language sql stable security invoker set search_path=public,pg_catalog as $$
 with queries as (select language,websearch_to_tsquery(case language when 'en-US' then 'english'::regconfig when 'ru-RU' then 'russian'::regconfig else 'simple'::regconfig end,left(p_query,4000)) q from (values('en-US'),('ru-RU'),('kk-KZ')) languages(language))
 select c.id,c.document_id,d.title,c.location,c.body,ts_rank_cd(c.search_document,q.q) as rank
 from public.teacher_document_chunks c join public.teacher_documents d on d.id=c.document_id and d.user_id=c.user_id join queries q on q.language=c.language
 where c.user_id=p_uid and d.status='ready' and c.document_id=any(p_sources) and c.search_document@@q.q
 order by rank desc,c.document_id,c.ordinal limit 8;
$$;

revoke all on function public.validate_teacher_sources(),public.reserve_teacher_document(jsonb),public.publish_teacher_document(uuid,uuid,uuid,jsonb),public.set_teacher_lesson_sources(uuid,uuid,integer,uuid[]),public.mark_teacher_document_deleting(uuid,uuid),public.search_teacher_passages(uuid,uuid[],text) from public,anon,authenticated;
grant execute on function public.validate_teacher_sources(),public.reserve_teacher_document(jsonb),public.publish_teacher_document(uuid,uuid,uuid,jsonb),public.set_teacher_lesson_sources(uuid,uuid,integer,uuid[]),public.mark_teacher_document_deleting(uuid,uuid),public.search_teacher_passages(uuid,uuid[],text) to service_role;
insert into storage.buckets(id,name,public,file_size_limit) values('teacher-documents','teacher-documents',false,10485760) on conflict(id) do nothing;
-- No client storage policy: originals are downloaded through the owner-checked API.

create function public.finish_sourced_teacher_resource(p_id uuid,p_uid uuid,p_sources uuid[],p_content jsonb,p_provenance jsonb) returns setof public.teacher_resources language plpgsql security invoker set search_path=public,pg_catalog as $$
begin
 perform 1 from public.teacher_documents where user_id=p_uid and id=any(p_sources) order by id for update;
 if exists(select 1 from public.account_deletion_locks where user_id=p_uid) or (select count(*) from public.teacher_documents where user_id=p_uid and id=any(p_sources) and status='ready')<>cardinality(p_sources) then return; end if;
 return query update public.teacher_resources set content=p_content,provenance=p_provenance,status='ready' where id=p_id and user_id=p_uid and status='generating' returning *;
end;$$;
revoke all on function public.finish_sourced_teacher_resource(uuid,uuid,uuid[],jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.finish_sourced_teacher_resource(uuid,uuid,uuid[],jsonb,jsonb) to service_role;
