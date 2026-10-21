# Teacher Video Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let teachers generate, review, edit, and render illustrated narrated videos from a lesson topic, then keep each private video with that lesson's resources.

**Architecture:** Add `video` as a teacher resource with a grade-aware editable script, and save render jobs in a separate owner-scoped table. Reuse the existing topic-video pipeline for scenes, images, narration, subtitles, and MP4 rendering, while skipping learner outcomes and story persistence. Add a lesson UI for script review, render progress, playback, download, and retry; leave presentation rendering and student flows intact.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, FastAPI, Pydantic, Celery, Supabase PostgREST/RLS, existing topic-video media pipeline, existing English/Russian/Kazakh copy system.

**Spec:** `docs/superpowers/specs/2026-10-09-teacher-video-generation-design.md`

## Global Constraints

- Support teacher grades `K` and `1`–`12`; exact school grade is authoritative for generated content.
- When approved-topic lookup needs an age band, map K–6 to `10-12`, grades 7–9 to `13-15`, and grades 10–12 to `16-18` for lookup only.
- Student requests omit `school_grade` and keep the current age-band behavior.
- Use the existing video pipeline and the existing 3/4/5-minute and female/male choices; default to 3 minutes and female voice.
- Teacher videos do not use lesson attachments, create learner story/history rows, or generate learner recap/quiz outcomes.
- Every teacher operation verifies teacher mode and lesson/resource ownership; render rate limit is three attempts per user per hour.
- A script edit invalidates renders from older resource revisions; resource, lesson, and account deletion cancel work and clean up private video assets.
- Preserve all presentation-render endpoints and behavior, and preserve current student generation behavior.
- Localize teacher-facing video UI in English, Russian, and Kazakh; keep controls keyboard accessible and status/error messages announced.
- Before editing Next.js frontend code, read the relevant guide under `wizetale-app/node_modules/next/dist/docs/` as required by `wizetale-app/AGENTS.md`.
- The checkout has no usable Git metadata, so do not include worktree or commit steps.

## Review Focus

- A render request racing with another request must return or create only one active job for the same teacher/resource; pin this in Task 3 with `test_start_teacher_video_render_returns_active_job` and `test_active_teacher_video_render_unique_index_rejects_duplicate`.
- A teacher editing a script while a worker is rendering must never see or download the old-revision video as current; pin this in Task 3 with `test_stale_video_render_cannot_publish_or_download`.
- A lesson with attached documents must still generate a topic-and-grade video without reading, citing, or requiring those documents; pin this in Task 2 with `test_video_resource_generation_ignores_attached_documents`.
- A non-teacher or a different teacher must not read, render, poll, or download another user's video; pin this in Task 3 with ownership cases for each route.
- Account deletion during an active teacher render must stop the worker before user asset cleanup; pin this in Task 3 with `test_account_deletion_cancels_teacher_video_renders`.

---

### Task 1: Add teacher video resource contracts and the private render schema

**Files:**
- Modify: `wizetale-api/app/domain/teacher.py`
- Modify: `wizetale-app/lib/teacher-content.ts`
- Create: `supabase/teacher_video_renders.sql`
- Modify: `supabase/README.md`
- Modify: `docs/TEACHER_PREP.md`
- Test: `wizetale-api/app/api/v1/tests/test_teacher_prep.py`
- Test: `wizetale-app/scripts/teacher-video-content.contract.ts`
- Test: `supabase/tests/teacher_video_renders_rls.test.sql`

**Interfaces:**
- Produces Python `VideoResourceContent` with `script: VideoScript`, `target_duration_sec: Literal[180, 240, 300] = 180`, and `voice: Literal['female', 'male'] = 'female'`.
- Produces `ResourceKind` including `video`; `ResourceGenerate` accepts the duration and voice fields with those defaults; `ResourceUpdate.content` accepts either `ResourceContent` or `VideoResourceContent`.
- Produces TypeScript `VideoResourceContent` with the same fields and `VideoScript` matching `app/domain/models.py`'s title, hook, `sections: {heading, summary}[]`, full narration, and estimated duration. Task 4 widens `Resource.content` when the lesson UI handles both content variants.
- Produces an additive `teacher_video_renders` table with a composite `(resource_id, user_id)` foreign key, the same job status/progress fields as presentation renders, owner-only RLS, an owner/created index, and one-active-render-per-resource partial unique index.

- [ ] **Step 1: Add domain contract coverage** named `test_video_resource_model_accepts_supported_options`, `test_video_resource_model_rejects_invalid_options`, and `test_resource_update_accepts_video_content`; cover valid K–12 grades, 180/240/300 seconds, female/male voice, defaults, and video script content.
- [ ] **Step 2: Implement the video resource models and kind** in `app/domain/teacher.py`; keep non-video `ResourceContent` validation unchanged and reject mismatched resource content.
- [ ] **Step 3: Add a compile-time contract fixture** in `scripts/teacher-video-content.contract.ts` that assigns `video` to `ResourceKind` and constructs `VideoResourceContent`; run `npm run typecheck` and confirm it fails on the missing types.
- [ ] **Step 4: Add matching frontend types** in `lib/teacher-content.ts`; keep `Resource.content` unchanged until Task 4 updates its consumers.
- [ ] **Step 5: Create the additive migration** with the video kind constraint update, `teacher_video_renders` table, owner-scoped foreign key, checks, partial active-job index, RLS read policy, service-role write grants, and updated-at trigger.
- [ ] **Step 6: Add SQL policy coverage** proving an authenticated owner can read their render but another account cannot, and run the RLS SQL check in the configured Supabase test environment.
- [ ] **Step 7: Document setup order** in `supabase/README.md` and `docs/TEACHER_PREP.md`: run `teacher_video_renders.sql` after `teacher_prep.sql` and `study_tools.sql`, then deploy API/worker, then frontend.

### Task 2: Generate grade-specific teacher scripts without changing learner generation

**Files:**
- Modify: `wizetale-api/app/domain/models.py`
- Modify: `wizetale-api/app/services/pipeline/script_service.py`
- Modify: `wizetale-api/app/services/pipeline/scene_service.py`
- Modify: `wizetale-api/app/services/pipeline/job_orchestrator.py`
- Create: `wizetale-api/app/services/teacher_video_generation.py`
- Modify: `wizetale-api/app/api/v1/teacher.py`
- Test: `wizetale-api/app/api/v1/tests/test_teacher_video_generation.py`
- Test: `wizetale-api/app/api/v1/tests/test_teacher_generation_prompts.py`
- Test: `wizetale-api/app/api/v1/tests/test_generate.py`

**Interfaces:**
- Produces optional `GenerationRequest.school_grade: str | None`, validated as `K` or `1`–`12`. `grade_band` remains unchanged for existing callers.
- Produces `teacher_video_generation_service.generate(lesson: dict, target_duration_sec: int, voice: str, user_id: str) -> VideoResourceContent`; it validates the lesson topic, maps the grade to an age band only for approved-knowledge lookup, then passes the exact grade to script generation.
- Produces `JobOrchestrator.run(..., generate_learning_outcomes: bool = True)`. When false, it does not call `generate_learning_outcomes`, uses empty recap/quiz output in its render result and manifest, and still renders the video.
- Refines scene planning to accept `school_grade: str | None`; teacher prompts use the exact school grade, while existing requests retain the current age-band prompt language.

- [ ] **Step 1: Add prompt coverage** named `test_teacher_script_prompt_uses_exact_school_grade`, `test_teacher_scene_prompt_uses_exact_school_grade`, and `test_student_script_prompt_keeps_existing_age_band`; parameterize the teacher prompt cases for `K`, a middle grade, and `12`, asserting exact grade wording and no learner age-band wording.
- [ ] **Step 2: Add orchestrator coverage** named `test_orchestrator_skips_learning_outcomes_for_teacher_video` and `test_orchestrator_generates_learning_outcomes_by_default`; assert that false skips outcome generation, writes empty recap/quiz data, and still calls scene, narration, image, and video stages.
- [ ] **Step 3: Add teacher resource route coverage** named `test_video_resource_generation_ignores_attached_documents`; assert generation only consumes lesson subject, topic, grade, and language (not `source_document_ids`, `source_material`, or objectives), then persists the selected duration and voice.
- [ ] **Step 4: Add `school_grade` to `GenerationRequest`** with the K–12 constraint; add one grade-to-lookup-band helper used only for knowledge lookup, not script or scene prompts.
- [ ] **Step 5: Update script and scene prompts** to use `school_grade` when supplied and otherwise retain current age-band instructions. Keep ordinary learner request serialization unchanged.
- [ ] **Step 6: Add the teacher video script service** that calls existing topic validation and script generation, creates no learner outcomes, and returns the strict video resource content.
- [ ] **Step 7: Branch `generate_resource` for `kind == 'video'` before the attached-document context branch**; preserve existing resource claim, rate limit, retry, ownership, and persistence behavior.
- [ ] **Step 8: Run focused API checks** with `cd wizetale-api && pytest app/api/v1/tests/test_teacher_video_generation.py app/api/v1/tests/test_teacher_generation_prompts.py app/api/v1/tests/test_generate.py -q`; expected: teacher grade cases pass and existing student age-band cases remain unchanged.

### Task 3: Add private asynchronous render lifecycle and cleanup

**Files:**
- Modify: `wizetale-api/app/services/story_repository.py`
- Create: `wizetale-api/app/api/v1/teacher_video_renders.py`
- Create: `wizetale-api/app/services/teacher_video_render.py`
- Modify: `wizetale-api/app/api/v1/teacher.py`
- Modify: `wizetale-api/app/services/account_deletion.py`
- Modify: `wizetale-api/app/main.py`
- Modify: `wizetale-api/app/celery_utils.py`
- Modify: `wizetale-api/worker.py`
- Test: `wizetale-api/app/api/v1/tests/test_teacher_video_renders.py`
- Test: `wizetale-api/app/api/v1/tests/test_teacher_video_render.py`
- Test: `wizetale-api/app/api/v1/tests/test_account_deletion.py`
- Test: `wizetale-api/app/api/v1/tests/test_teacher_presentation_renders.py`

**Interfaces:**
- Produces repository methods `create_teacher_video_render(record)`, `teacher_video_render(render_id, user_id)`, `active_teacher_video_render(resource_id, user_id)`, `latest_teacher_video_render(resource_id, user_id)`, `update_teacher_video_render(render_id, user_id, changes)`, `list_active_teacher_video_renders(user_id)`, `cancel_active_teacher_video_renders(user_id)`, and `invalidate_teacher_video_renders(resource_id, user_id, current_revision)`.
- Produces the teacher render routes from the spec: start/latest at `/lessons/{lesson_id}/resources/{resource_id}/video-renders`, poll at `/video-renders/{render_id}`, and authenticated download at `/video-renders/{render_id}/video`.
- Produces Celery task `render_teacher_video_task(render_id, user_id, resource_id, resource_revision, content, lesson_snapshot)` in `app/services/teacher_video_render.py`; it uses the shared `JobOrchestrator` with `script_override` and `generate_learning_outcomes=False`, stores only the private teacher render row and MP4, and publishes only if the resource still has the captured revision.
- Render response contains `id`, `status`, `progress`, `stage`, `message`, plus `video_url` and `duration_sec` when ready. Every lookup filters by owner; a download additionally checks that the render revision matches the current ready video resource.

- [ ] **Step 1: Add repository coverage** named `test_teacher_video_render_queries_filter_by_owner`, `test_active_teacher_video_render_unique_index_rejects_duplicate`, `test_latest_teacher_video_render_is_owner_scoped`, and `test_invalidating_teacher_video_renders_cancels_and_deletes_assets`; assert owner/id filters, active/latest selection, status transitions, revision invalidation, and object cleanup.
- [ ] **Step 2: Implement owner-scoped teacher video render repository methods** in `story_repository.py`; reuse existing media-storage and signed-URL helpers without changing presentation render methods.
- [ ] **Step 3: Add route coverage** named `test_start_teacher_video_render_returns_active_job`, `test_start_teacher_video_render_retries_after_failure`, `test_teacher_video_render_routes_enforce_teacher_and_resource_ownership`, and `test_video_download_rejects_stale_resource_revision`; cover teacher-mode enforcement, lesson/resource ownership, progress polling, and cross-account hiding on every route.
- [ ] **Step 4: Implement `teacher_video_renders.py`** with the exact routes above, shared `_uid`/`_lesson`/`_resource` authorization, the three-per-hour `teacher-video-render` limit, active job reuse, race recovery, and private streaming download headers.
- [ ] **Step 5: Add worker coverage** named `test_teacher_video_render_skips_story_history_and_outcomes`, `test_teacher_video_render_checks_revision_before_publish`, and `test_teacher_video_render_marks_failure_retryable`; cover progress updates, private MP4 storage under `<user_id>/<render_id>/`, cancellation, no learner story/history writes, and stale revision cleanup. Add the Celery task that builds `GenerationRequest` from the saved lesson snapshot and video options.
- [ ] **Step 6: Register the router and worker module** in `main.py`, `celery_utils.py`, and `worker.py`.
- [ ] **Step 7: Invalidate renders on script edits** in the existing PATCH handler after revision-guarded save; delete older video objects and make old render responses unavailable as current.
- [ ] **Step 8: Cancel and clean resources on deletion** before deleting a video resource or lesson; add `test_account_deletion_cancels_teacher_video_renders`, then extend account deletion to cancel/revoke active teacher-video render jobs and wait for them to stop before existing user-asset cleanup.
- [ ] **Step 9: Run focused API checks** with `cd wizetale-api && pytest app/api/v1/tests/test_teacher_video_renders.py app/api/v1/tests/test_teacher_video_render.py app/api/v1/tests/test_account_deletion.py app/api/v1/tests/test_teacher_presentation_renders.py -q`; expected: new lifecycle and deletion cases pass while presentation coverage stays green.

### Task 4: Add the lesson video workflow and localized review/render UI

**Files:**
- Modify: `wizetale-app/lib/teacher-content.ts`
- Modify: `wizetale-app/hooks/use-teacher-api.ts`
- Modify: `wizetale-app/lib/copy.ts`
- Modify: `wizetale-app/app/teacher/lessons/[lessonId]/page.tsx`
- Modify: `wizetale-app/components/teacher/resource-editor.tsx`
- Create: `wizetale-app/components/teacher/video-script-editor.tsx`
- Create: `wizetale-app/components/teacher/video-resource-render.tsx`
- Modify: `wizetale-app/app/teacher/teacher.css`
- Test: `wizetale-app/scripts/teacher-video-resource.test.cjs`

**Interfaces:**
- Consumes Task 1's `VideoResourceContent` contract and Task 3's render routes.
- Produces `Resource.content: ResourceContent | VideoResourceContent | null` after the lesson screen has a video-specific editor branch.
- Produces lesson picker option “Video”; duration controls (3, 4, 5 minutes) and voice controls (female, male) appear for video generation, defaulting to 3 minutes/female.
- Produces `VideoScriptEditor` that edits `script.title`, `hook`, section headings/summaries, and `full_narration`; its parent saves through the existing revision-guarded resource PATCH.
- Produces `VideoResourceRender` that accepts `{lessonId, resourceId, revision, disabled}`, loads latest render, starts/retries render, polls status, and shows current playback and MP4 download only when the returned revision matches.

- [ ] **Step 1: Read the relevant installed Next.js guides** under `wizetale-app/node_modules/next/dist/docs/` before making frontend edits.
- [ ] **Step 2: Add frontend lifecycle coverage** named `test_video_resource_title_comes_from_script`, `test_video_generation_sends_selected_duration_and_voice`, and `test_video_render_is_hidden_after_script_revision_changes`; cover content parsing, title derivation, request payload, and stale-render suppression.
- [ ] **Step 3: Update `use-teacher-api.ts`** so resource generation can send `target_duration_sec` and `voice`, and add typed start/latest/poll/download methods for video renders through the existing teacher catchall proxy.
- [ ] **Step 4: Add picker settings and video generation** in the lesson page; display a video resource's title from `script.title`, and route video content to its own editor instead of the printable generic resource editor.
- [ ] **Step 5: Build `VideoScriptEditor`** for all editable script fields and save state; keep the saved resource revision as the concurrency guard and disable rendering while script changes are unsaved.
- [ ] **Step 6: Build `VideoResourceRender`** for latest state, progress, stage/message, retry after failure, inline playback, authenticated download, and stale revision suppression.
- [ ] **Step 7: Add English, Russian, and Kazakh copy** for video selection, settings, script fields, render progress, failures, retry, playback, and download; add responsive and keyboard-focus styling in `teacher.css`.
- [ ] **Step 8: Keep presentation behavior distinct** by leaving `PresentationRender` mounted only for presentations and hiding print controls for video resources.
- [ ] **Step 9: Run frontend checks** with `cd wizetale-app && npm run typecheck && npm run build`; expected: both complete without errors.

### Task 5: Complete compatibility and acceptance review

**Files:**
- No planned new product files; resolve findings in the files above.
- Review: `wizetale-api/app/api/v1/tests/test_teacher_prep.py`
- Review: `wizetale-api/app/api/v1/tests/test_teacher_presentation_renders.py`
- Review: `wizetale-api/app/api/v1/tests/test_teacher_presentation_video.py`
- Review: `wizetale-api/app/api/v1/tests/test_generate.py`

**Interfaces:**
- Consumes all prior tasks and the rollout sequence in `supabase/README.md`.
- Produces a release checklist confirming additive database migration first, then API/worker deployment, then frontend deployment; video resources stay lesson-private and the presentation-to-video feature remains available.

- [ ] **Step 1: Run the full API suite** with `cd wizetale-api && pytest app/api/v1/tests -q`; expected: all teacher, student-generation, media, and account-deletion tests pass.
- [ ] **Step 2: Walk through the teacher flow**: create a K and grade-12 lesson video, review/edit/save its script, start render, poll progress, play/download the result, retry a failed render, edit the script during an active render, and delete the resource.
- [ ] **Step 3: Walk through ownership and cleanup** with a second teacher and account deletion while rendering; confirm no cross-account metadata or signed URL is exposed and no worker can upload after cleanup begins.
- [ ] **Step 4: Walk through English, Russian, and Kazakh UI states** at mobile and desktop widths with keyboard navigation; confirm script editing, progress, retry, playback, and download are usable.
- [ ] **Step 5: Confirm student and presentation behavior** with the existing learner generation and presentation render flows; verify student prompts still use age bands and slide-to-video remains unchanged.
