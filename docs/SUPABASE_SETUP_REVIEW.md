# Supabase setup completed

Target: TalesPark (`nsrhlhbpnkxmzgveingy`), API `https://nsrhlhbpnkxmzgveingy.supabase.co`.

Read-only inspection on 2026-10-04: project healthy; public schema has no application tables or migrations; security advisor reports no notices. Local frontend/API environment files now use the project's URL and active publishable key. No server secret has been obtained or exposed.

## Applied live setup

Applied with explicit user approval on 2026-10-04:

1. `supabase/schema.sql`: learner drafts/stories/quiz results, account deletion locks, shared knowledge table/search, owner read policies, server-only writes and the private `story-videos` bucket. The generated alias search expression now uses a text-only immutable helper to meet PostgreSQL generated-column requirements; account deletion locks enable RLS; learner grants are explicit.
2. `supabase/teacher_prep.sql`: teacher profiles, private lessons/resources, owner reads/server-only writes, cascades, revision fields, context snapshots, and Kazakh story language.
3. `supabase/knowledge_seed.sql`: existing reviewed subject facts and source links for story grounding.

4. `supabase/relationship_indexes.sql`: three covering indexes for story/draft, quiz/owner and resource/lesson relationships.

Both rollback-only SQL test scripts passed on the project: generated alias search, grants, teacher owner isolation, cross-owner constraints and account-deletion cascades. Eight application tables have RLS enabled. `story-videos` is private. Fifteen approved knowledge entries are present; test teacher fixtures left no records.

Recorded migration names: `initialize_learner_storage` (20261004154016), `initialize_teacher_preparation` (20261004154040), `index_owner_and_lesson_relationships` (20261004154225). The seed was applied as a data update.

Security advisor has no warning/error findings. One [informational notice](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) is intentional: account deletion locks have no client policy because only the server role may access them. Performance advisor no longer flags missing foreign-key indexes. [Unused index notices](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index) are expected before application traffic; retain the indexes for their intended queries.

## Remaining configuration

- Server credential is now configured privately under `SUPABASE_SERVICE_ROLE_KEY`; database, private bucket and Auth admin read checks returned 200. Rotate the key shared in chat before public launch. The browser only has the publishable key.
- Auth now uses localhost:3001 with four exact local callbacks; email sign-in is enabled. A future production URL and Google OAuth credentials remain owner configuration.
- Password-protected local Redis/API/worker are connected and Supabase media storage is selected. Gemini generation is blocked by depleted prepayment credits; ElevenLabs credentials are missing. See LOCAL_SETUP.md. Existing credential rotation and public launch gates remain.

The approved schema, seed and private bucket are now live. Local Auth settings have since been configured. Production deployment, server-key rotation, provider billing and ElevenLabs configuration remain outstanding. No website/API deployment was performed.

## Teacher document library verification (2026-10-04)

Applied teacher document schema/private bucket, source publication/attachment/finalization guards, pending-removal quota and covering foreign-key index. Rollback checks pass owner policies, denied client writes/RPCs, selected-document search, English/Russian stemming, Kazakh tokens, stale attempts/revisions, quota, duplicate finalization and deletion guards. Fictional live accounts verified uploads, processing, downloads, quiz/flashcards, provenance and account/storage deletion; fixtures removed.

Security advisor still reports leaked-password protection disabled in Auth. Review availability and enable it before public release: [Supabase password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection). The account-deletion table's no-policy INFO is intentional because it is server-only. Unused-index INFO notices are retained pending real workload measurements.

## October 5 local audit

Applied `supabase/story_render_recovery.sql` as `atomic_story_render_and_recovery`. Atomic draft/story claims and stale-job recovery are server-only operations; rollback checks passed against the configured project. Document policy/retrieval rollback checks passed again. See [the local audit report](LOCAL_PROJECT_AUDIT_2026-10-05.md) for actual service verification and remaining launch gates.
