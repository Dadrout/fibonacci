# TaleSpark Supabase setup

1. Create a Supabase project and copy its project URL and publishable key into `wizetale-app/.env.local`.
2. Set the same `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the API environment. Set `SUPABASE_SERVICE_ROLE_KEY` only on the API server; never add it to a `NEXT_PUBLIC_` variable.
3. Run `schema.sql` in the Supabase SQL editor. It creates the learner tables, account-deletion lock, shared source library, search function, row policies, and a private `story-videos` bucket.
4. For study tools, teacher preparation, teacher topic videos, and slide visuals, run `teacher_prep.sql`, `teacher_documents.sql`, `study_tools.sql`, `teacher_video_renders.sql`, then `presentation_visuals.sql` in that order. The video migration adds the `video` resource kind and private owner-scoped render jobs. Run `tests/student_study_materials_rls.test.sql` and `tests/teacher_video_renders_rls.test.sql` after those scripts to check access and account-cleanup behavior. For rollout, apply the database scripts first, deploy/restart the API and worker next, then deploy the teacher lesson UI.
5. Run `knowledge_seed.sql` after the schema. It inserts the reviewed starter facts and can be re-run to update those entries.
6. In Supabase Auth, configure the site URL and allowed redirects for the app origin, including `/auth/callback`.
7. Enable email confirmation and configure the email template to use the Supabase confirmation link. OAuth providers can be enabled in Supabase Auth when credentials are configured.
8. Start the API, Redis/Celery worker, and Next.js app. Video generation also requires the configured text, image, and narration providers.

The source library contains short original fact notes and links to the references; it does not copy complete articles. Authenticated learners can read approved entries, but only the API's server-side secret key can change them. Database access rules are covered by `tests/knowledge_entries_rls.test.sql` and can be run with `supabase test db` when the local Supabase CLI project is configured.

TaleSpark stores each media object under `<auth-user-id>/<job-id>/` in the private bucket. The API creates short-lived signed URLs after checking the requesting user's ownership. Keep the service role key private: it bypasses Supabase row policies, so API queries also include the authenticated owner ID explicitly.

The account page offers account deletion. The API first places a server-only deletion lock, cancels active generation jobs, and waits for running workers to stop. It then revokes the learner's sessions, removes their objects from the configured media provider, and deletes their Supabase Auth user. The schema's `ON DELETE CASCADE` foreign keys remove the lock, drafts, stories, and quiz results. Keep workers reachable when deleting an account with active jobs; deletion stops safely if workers cannot be confirmed stopped or media removal fails.

Firebase email/password credentials cannot be copied into Supabase as reusable passwords. Existing users need a Supabase account (and may use password reset if their email is transferred). This code switches the app to Supabase Auth but does not migrate Firebase users or existing Firebase stories.
