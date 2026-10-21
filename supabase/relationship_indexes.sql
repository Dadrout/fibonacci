-- Cover relationship lookups and cascading deletes as user data grows.
create index if not exists stories_draft_id_idx on public.stories(draft_id);
create index if not exists quiz_results_user_id_idx on public.quiz_results(user_id);
create index if not exists teacher_resources_lesson_owner_idx on public.teacher_resources(lesson_id, user_id);
