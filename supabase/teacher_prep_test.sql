-- Staging regression check. Run as database administrator after teacher_prep.sql.
-- Fixture writes are rolled back; uses reserved example.test accounts.
begin;
insert into auth.users(id,email) values
 ('00000000-0000-4000-8000-000000000001','teacher-a@example.test'),
 ('00000000-0000-4000-8000-000000000002','teacher-b@example.test');
insert into public.teacher_profiles(user_id) select id from auth.users where email in ('teacher-a@example.test','teacher-b@example.test');
insert into public.teacher_lessons(id,user_id,subject,grade,topic,language) values
 ('00000000-0000-4000-8000-000000000011','00000000-0000-4000-8000-000000000001','math','6','Fractions','kk-KZ'),
 ('00000000-0000-4000-8000-000000000012','00000000-0000-4000-8000-000000000002','science','K','Water','en-US');
insert into public.teacher_resources(lesson_id,user_id,kind,lesson_snapshot) values
 ('00000000-0000-4000-8000-000000000011','00000000-0000-4000-8000-000000000001','quiz','{}'),
 ('00000000-0000-4000-8000-000000000012','00000000-0000-4000-8000-000000000002','flashcards','{}');
do $$ begin
 if has_table_privilege('authenticated','public.teacher_lessons','INSERT')
 or has_table_privilege('authenticated','public.teacher_resources','UPDATE')
 or has_table_privilege('anon','public.teacher_lessons','SELECT') then
   raise exception 'Client access privileges are too broad';
 end if;
 begin
   insert into public.teacher_resources(lesson_id,user_id,kind,lesson_snapshot) values
   ('00000000-0000-4000-8000-000000000011','00000000-0000-4000-8000-000000000002','quiz','{}');
   raise exception 'Cross-owner resource was accepted';
 exception when foreign_key_violation then null;
 end;
end $$;
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
do $$ begin
 if (select count(*) from public.teacher_lessons) <> 1 or
    not exists(select 1 from public.teacher_lessons where topic='Fractions') then
   raise exception 'Lesson owner isolation failed';
 end if;
 if (select count(*) from public.teacher_resources) <> 1 then
   raise exception 'Resource owner isolation failed';
 end if;
 if (select count(*) from public.teacher_profiles) <> 1 then
   raise exception 'Profile owner isolation failed';
 end if;
end $$;
reset role;
delete from auth.users where id='00000000-0000-4000-8000-000000000001';
do $$ begin
 if exists(select 1 from public.teacher_lessons where id='00000000-0000-4000-8000-000000000011') or exists(select 1 from public.teacher_resources where user_id='00000000-0000-4000-8000-000000000001') then
   raise exception 'Account deletion did not cascade';
 end if;
end $$;
rollback;
