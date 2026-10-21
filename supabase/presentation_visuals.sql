-- Apply after schema.sql, teacher_prep.sql, teacher_documents.sql, and study_tools.sql.
-- Student subjects grow independently of teacher lesson subjects; retain legacy history stories.
alter table public.student_study_materials drop constraint if exists student_study_materials_subject_check;
alter table public.student_study_materials add constraint student_study_materials_subject_check
  check(subject in ('language_arts','math','science','history_social_studies','geography','philosophy'));
alter table public.story_drafts drop constraint if exists story_drafts_subject_check;
alter table public.story_drafts add constraint story_drafts_subject_check
  check(subject in ('history','language_arts','math','science','history_social_studies','geography','philosophy'));
alter table public.knowledge_entries drop constraint if exists knowledge_entries_subject_check;
alter table public.knowledge_entries add constraint knowledge_entries_subject_check
  check(subject in ('history','language_arts','math','science','history_social_studies','geography','philosophy'));

create unique index if not exists student_study_materials_id_owner_unique on public.student_study_materials(id,user_id);
create unique index if not exists teacher_resources_id_owner_unique on public.teacher_resources(id,user_id);

-- Visual updates have their own generation UUID and never change content/revision.
create table if not exists public.presentation_slide_visuals (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  deck_type text not null check(deck_type in ('student','teacher')),
  deck_id uuid not null,
  student_material_id uuid,
  teacher_resource_id uuid,
  -- Exactly three eligible concept slots bounds provider cost for every deck.
  slide_index integer not null check(slide_index in (1,3,5)),
  status text not null check(status in ('pending','processing','ready','failed')),
  kind text not null check(kind in ('image','diagram')),
  alt_text text not null check(char_length(alt_text) <= 1000),
  caption text not null check(char_length(caption) <= 1000),
  prompt text not null,
  image_object text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(deck_type,deck_id,user_id,slide_index),
  foreign key(student_material_id,user_id) references public.student_study_materials(id,user_id) on delete cascade,
  foreign key(teacher_resource_id,user_id) references public.teacher_resources(id,user_id) on delete cascade,
  check((deck_type='student' and student_material_id=deck_id and student_material_id is not null and teacher_resource_id is null)
     or (deck_type='teacher' and teacher_resource_id=deck_id and teacher_resource_id is not null and student_material_id is null)),
  check(status <> 'ready' or image_object is not null),
  check(image_object is null or starts_with(image_object,user_id::text || '/'))
);
create index if not exists presentation_slide_visuals_owner_active
  on public.presentation_slide_visuals(user_id,status) where status in ('pending','processing');
alter table public.presentation_slide_visuals enable row level security;
-- URLs and provider prompts are hydrated only by the owner-scoped server API.
revoke all on public.presentation_slide_visuals from public,anon,authenticated;
grant all on public.presentation_slide_visuals to service_role;
drop trigger if exists presentation_slide_visuals_updated on public.presentation_slide_visuals;
create trigger presentation_slide_visuals_updated before update on public.presentation_slide_visuals
  for each row execute function public.set_updated_at();
