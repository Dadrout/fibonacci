begin;
select plan(18);

insert into auth.users(id,email) values
 ('00000000-0000-4000-8000-000000000021','learner-a@example.test'),
 ('00000000-0000-4000-8000-000000000022','learner-b@example.test');

insert into public.teacher_profiles(user_id) values
 ('00000000-0000-4000-8000-000000000021'),
 ('00000000-0000-4000-8000-000000000022');
insert into public.teacher_lessons(id,user_id,subject,grade,topic,language) values
 ('00000000-0000-4000-8000-000000000041','00000000-0000-4000-8000-000000000021','science','6','Fractions','en-US'),
 ('00000000-0000-4000-8000-000000000042','00000000-0000-4000-8000-000000000022','science','7','Water','kk-KZ');
insert into public.teacher_resources(id,lesson_id,user_id,kind,status,content,lesson_snapshot) values
 ('00000000-0000-4000-8000-000000000051','00000000-0000-4000-8000-000000000041','00000000-0000-4000-8000-000000000021','presentation','ready','{"title":"Fractions","slides":[]}','{}'),
 ('00000000-0000-4000-8000-000000000052','00000000-0000-4000-8000-000000000042','00000000-0000-4000-8000-000000000022','presentation','ready','{"title":"Water","slides":[]}','{}');
insert into public.teacher_presentation_renders(id,resource_id,user_id,resource_revision,status,progress,stage,message,video_object) values
 ('00000000-0000-4000-8000-000000000061','00000000-0000-4000-8000-000000000051','00000000-0000-4000-8000-000000000021',1,'ready',100,'complete','Ready','00000000-0000-4000-8000-000000000021/render/video.mp4'),
 ('00000000-0000-4000-8000-000000000062','00000000-0000-4000-8000-000000000052','00000000-0000-4000-8000-000000000022',1,'ready',100,'complete','Ready','00000000-0000-4000-8000-000000000022/render/video.mp4');

insert into public.student_study_materials(id,user_id,kind,subject,grade,topic,language,context,content,status)
values
 ('00000000-0000-4000-8000-000000000031','00000000-0000-4000-8000-000000000021','flashcards','math','6','Fractions','en-US','{}','{"title":"Fractions"}','ready'),
 ('00000000-0000-4000-8000-000000000032','00000000-0000-4000-8000-000000000022','quiz','science','7','Water','kk-KZ','{}','{"title":"Water"}','ready');
insert into public.presentation_slide_visuals(id,user_id,deck_type,deck_id,student_material_id,teacher_resource_id,slide_index,status,kind,alt_text,caption,prompt)
values
 ('00000000-0000-4000-8000-000000000071','00000000-0000-4000-8000-000000000021','student','00000000-0000-4000-8000-000000000031','00000000-0000-4000-8000-000000000031',null,1,'pending','diagram','A number line divided into equal parts.','Fractions','Create a number line.'),
 ('00000000-0000-4000-8000-000000000072','00000000-0000-4000-8000-000000000022','teacher','00000000-0000-4000-8000-000000000052',null,'00000000-0000-4000-8000-000000000052',3,'pending','image','Water flowing through a stream.','Water cycle','Create a water cycle image.');

select ok((select relrowsecurity from pg_class where oid='public.student_study_materials'::regclass),
  'row-level security is enabled on learner study materials');
select ok((select relrowsecurity from pg_class where oid='public.presentation_slide_visuals'::regclass),
  'row-level security is enabled on private slide visuals');
select ok(not has_table_privilege('authenticated','public.presentation_slide_visuals','select'),
  'learners read signed visuals through the owner-scoped API');
select ok(has_table_privilege('service_role','public.presentation_slide_visuals','select'),
  'the server can hydrate visual job state');
select ok(has_table_privilege('authenticated','public.student_study_materials','select'),
  'authenticated learners may read study materials subject to owner policies');
select ok(not has_table_privilege('anon','public.student_study_materials','select'),
  'unauthenticated users cannot read study materials');
select ok(not has_table_privilege('authenticated','public.student_study_materials','insert'),
  'study material writes pass through the validated API');
select ok(not has_table_privilege('authenticated','public.student_study_materials','update'),
  'study material edits pass through the validated API');
select ok(not has_table_privilege('authenticated','public.student_study_materials','delete'),
  'study material removal passes through the validated API');

set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000021',true);
select is((select count(*)::integer from public.student_study_materials),1,
  'a learner only reads their own study materials');
select ok((select relrowsecurity from pg_class where oid='public.teacher_presentation_renders'::regclass),
  'row-level security is enabled on private teacher video renders');
select ok(has_table_privilege('authenticated','public.teacher_presentation_renders','select'),
  'teachers may read their render progress subject to owner policies');
select ok(not has_table_privilege('authenticated','public.teacher_presentation_renders','insert'),
  'render jobs can only be created by the validated API');
select is((select count(*)::integer from public.teacher_presentation_renders),1,
  'a teacher only reads their own video render');
select is((select count(*)::integer from public.teacher_presentation_renders where user_id='00000000-0000-4000-8000-000000000022'),0,
  'a teacher cannot read another account video render');
reset role;

delete from auth.users where id='00000000-0000-4000-8000-000000000021';
select is((select count(*)::integer from public.student_study_materials where user_id='00000000-0000-4000-8000-000000000021'),0,
  'account deletion cascades to private study materials');
select is((select count(*)::integer from public.teacher_presentation_renders where user_id='00000000-0000-4000-8000-000000000021'),0,
  'account deletion cascades to teacher render progress');
select is((select count(*)::integer from public.presentation_slide_visuals where user_id='00000000-0000-4000-8000-000000000021'),0,
  'account deletion cascades to private slide visuals');

select * from finish();
rollback;
