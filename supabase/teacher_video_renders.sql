-- Additive teacher topic-video support. Apply after teacher_prep.sql and study_tools.sql.
alter table public.teacher_resources drop constraint if exists teacher_resources_kind_check;
alter table public.teacher_resources add constraint teacher_resources_kind_check
  check(kind in ('objectives','lesson_plan','quiz','test_paper','flashcards','worksheet','exit_ticket','homework','presentation','video'));

create table if not exists public.teacher_video_renders (
  id uuid primary key,
  resource_id uuid not null,
  user_id uuid not null references public.teacher_profiles(user_id) on delete cascade,
  resource_revision integer not null check(resource_revision > 0),
  status text not null default 'queued' check(status in ('queued','processing','ready','failed','cancelled')),
  progress integer not null default 0 check(progress between 0 and 100),
  stage text not null default 'queued',
  message text not null default 'Waiting to render your video.',
  video_object text,
  duration_sec numeric(8,2),
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key(resource_id, user_id) references public.teacher_resources(id, user_id) on delete cascade,
  check(status <> 'ready' or video_object is not null),
  check(video_object is null or starts_with(video_object,user_id::text || '/'))
);

create index if not exists teacher_video_renders_owner_created
  on public.teacher_video_renders(user_id, created_at desc);
create index if not exists teacher_video_renders_active
  on public.teacher_video_renders(user_id, status) where status in ('queued','processing');
create unique index if not exists teacher_video_renders_one_active_resource
  on public.teacher_video_renders(user_id, resource_id) where status in ('queued','processing');

alter table public.teacher_video_renders enable row level security;
revoke all on public.teacher_video_renders from public, anon, authenticated;
grant select on public.teacher_video_renders to authenticated;
grant all on public.teacher_video_renders to service_role;

drop policy if exists teacher_video_renders_read on public.teacher_video_renders;
create policy teacher_video_renders_read on public.teacher_video_renders
  for select to authenticated using ((select auth.uid()) = user_id);

drop trigger if exists teacher_video_renders_updated on public.teacher_video_renders;
create trigger teacher_video_renders_updated before update on public.teacher_video_renders
  for each row execute function public.set_updated_at();
