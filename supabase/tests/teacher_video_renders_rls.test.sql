begin;
select plan(8);

insert into auth.users(id,email) values
 ('00000000-0000-4000-8000-000000000131','teacher-video-a@example.test'),
 ('00000000-0000-4000-8000-000000000132','teacher-video-b@example.test');
insert into public.teacher_profiles(user_id) values
 ('00000000-0000-4000-8000-000000000131'),
 ('00000000-0000-4000-8000-000000000132');
insert into public.teacher_lessons(id,user_id,subject,grade,topic,language) values
 ('00000000-0000-4000-8000-000000000141','00000000-0000-4000-8000-000000000131','science','6','Fractions','en-US'),
 ('00000000-0000-4000-8000-000000000142','00000000-0000-4000-8000-000000000132','science','7','Water','kk-KZ');
insert into public.teacher_resources(id,lesson_id,user_id,kind,status,content,lesson_snapshot) values
 ('00000000-0000-4000-8000-000000000151','00000000-0000-4000-8000-000000000141','00000000-0000-4000-8000-000000000131','video','ready','{"script":{"title":"Fractions"},"target_duration_sec":180,"voice":"female"}','{}'),
 ('00000000-0000-4000-8000-000000000152','00000000-0000-4000-8000-000000000142','00000000-0000-4000-8000-000000000132','video','ready','{"script":{"title":"Water"},"target_duration_sec":180,"voice":"female"}','{}');
insert into public.teacher_video_renders(id,resource_id,user_id,resource_revision,status,progress,stage,message,video_object) values
 ('00000000-0000-4000-8000-000000000161','00000000-0000-4000-8000-000000000151','00000000-0000-4000-8000-000000000131',1,'ready',100,'complete','Ready','00000000-0000-4000-8000-000000000131/00000000-0000-4000-8000-000000000161/video.mp4'),
 ('00000000-0000-4000-8000-000000000162','00000000-0000-4000-8000-000000000152','00000000-0000-4000-8000-000000000132',1,'ready',100,'complete','Ready','00000000-0000-4000-8000-000000000132/00000000-0000-4000-8000-000000000162/video.mp4');

insert into public.teacher_video_renders(id,resource_id,user_id,resource_revision,status)
values ('00000000-0000-4000-8000-000000000163','00000000-0000-4000-8000-000000000151','00000000-0000-4000-8000-000000000131',1,'queued');
select throws_ok(
  $$insert into public.teacher_video_renders(id,resource_id,user_id,resource_revision,status)
    values ('00000000-0000-4000-8000-000000000164','00000000-0000-4000-8000-000000000151','00000000-0000-4000-8000-000000000131',1,'processing')$$,
  '23505', null, 'one queued or processing render is allowed per owner and resource');

select ok((select relrowsecurity from pg_class where oid='public.teacher_video_renders'::regclass),
  'row-level security is enabled on teacher video renders');
select ok(has_table_privilege('authenticated','public.teacher_video_renders','select'),
  'authenticated teachers may read render rows subject to owner policies');
select ok(not has_table_privilege('authenticated','public.teacher_video_renders','insert'),
  'render rows can only be created by the validated API');
select ok(not has_table_privilege('authenticated','public.teacher_video_renders','update'),
  'render progress can only be changed by the API and worker');

set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000131',true);
select is((select count(*)::integer from public.teacher_video_renders),2,
  'a teacher only reads their own video render');
select is((select count(*)::integer from public.teacher_video_renders where user_id='00000000-0000-4000-8000-000000000132'),0,
  'a teacher cannot read another account video render');
reset role;

delete from auth.users where id='00000000-0000-4000-8000-000000000131';
select is((select count(*)::integer from public.teacher_video_renders where user_id='00000000-0000-4000-8000-000000000131'),0,
  'account deletion cascades to teacher video renders');

select * from finish();
rollback;
