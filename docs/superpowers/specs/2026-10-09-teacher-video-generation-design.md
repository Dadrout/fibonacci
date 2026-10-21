# Teacher Video Generation

## Purpose

Let teachers create an illustrated, narrated video for a lesson topic and keep the editable script and finished MP4 with that lesson's other private resources. The feature supports every teacher grade from K through 12. The existing narrated presentation renderer remains available and unchanged.

## Users and scope

This feature is for signed-in accounts with teacher mode enabled. A teacher starts from an existing lesson; subject, topic, school grade, and language come from that lesson. Teachers can choose the existing story-video durations (3, 4, or 5 minutes) and narration voices (female or male). Defaults are 3 minutes and the female voice.

The first version does not use documents attached to a lesson. It uses the existing topic validation and approved topic knowledge lookup, then creates a grade-specific story script for teacher review. The exact K–12 grade must reach script and scene-planning prompts; existing student age-band behavior remains unchanged.

## Teacher flow

1. Add **Video** to the lesson resource picker.
2. Generate a script from the lesson subject, topic, grade, and language, with duration and voice settings.
3. Save and edit the script as a private teacher resource. The teacher reviews it before starting a render.
4. Queue an asynchronous illustrated-video render. Show progress, then provide playback and MP4 download from the same lesson resource.
5. If rendering fails, keep the saved script and allow a retry. A script edit increments its resource revision; a video rendered from an older revision must not be presented as current.

## API and data flow

- Extend the teacher resource kind and frontend `ResourceKind` with `video`. A video resource uses `VideoResourceContent = {script: VideoScript, target_duration_sec: 180 | 240 | 300, voice: "female" | "male"}`; its display title is `script.title`. `POST /api/v1/teacher/lessons/{lesson_id}/resources` accepts `{kind: "video", request_id, target_duration_sec, voice}` and returns that editable content. Script edits use `PATCH /api/v1/teacher/lessons/{lesson_id}/resources/{resource_id}` with the resource revision.
- Add `POST` and `GET /api/v1/teacher/lessons/{lesson_id}/resources/{resource_id}/video-renders` to start a render or fetch the latest render. A start request returns the active job when one is queued or processing; after a terminal failure, a new request creates a new job. Add `GET /api/v1/teacher/video-renders/{render_id}` for polling and `GET /api/v1/teacher/video-renders/{render_id}/video` for authenticated MP4 download. A job response contains `id`, `status`, `progress`, `stage`, and `message`, plus `video_url` and `duration_sec` when ready. Keep all presentation-render endpoints and behavior intact.
- Add a private `teacher_video_renders` table linked by `(resource_id, user_id)` to `teacher_resources`. Store job status, progress, message, resource revision, video object path, duration, and error code. Add an index that permits only one queued or processing render per user/resource pair. Enable RLS with owner-only reads; API/worker service credentials perform writes.
- The render worker uses the shared topic-video media pipeline for scene planning, narration, images, and MP4 creation, but skips learner quiz-outcome generation and does not create a learner story/history row. Store the private MP4 under the authenticated user's asset prefix and return signed playback URLs only after checking ownership and the resource revision.
- Every generation, edit, status, retry, and download request verifies teacher mode and lesson/resource ownership. Use teacher resource generation rate limits for script creation and a limit of three render attempts per user per hour.
- Resource or lesson deletion cancels active jobs, removes associated render rows, and deletes stored video assets. A script edit invalidates older renders and deletes their assets. Account deletion cancels active teacher video renders and retains the existing user-asset cleanup behavior.

## Grade targeting and compatibility

Add an optional `school_grade` target to the shared internal video-generation request. Teacher generation calls the existing topic validation and uses the exact lesson grade (`K` or `1`–`12`) in script and scene-planning prompts; when `school_grade` is present, those prompts must use it instead of learner age-band wording. Student requests omit it and keep their current age-band behavior. Teacher script generation and rendering both skip learner-only recap/quiz generation. When approved-knowledge lookup requires an age band, map K–6 to `10-12`, grades 7–9 to `13-15`, and grades 10–12 to `16-18` for lookup only; the exact school grade remains authoritative for generated content.

Add `supabase/teacher_video_renders.sql` after `teacher_prep.sql` and `study_tools.sql` in setup instructions. It adds the `video` resource kind and creates the render table with its owner policies, indexes, and resource foreign key. Apply this additive database change before deploying the API/worker, then deploy the frontend. Existing teacher resources, student story APIs, and presentation renders remain compatible.

## Failure handling and acceptance

- Script-generation errors leave the lesson and existing resources intact and offer a retry. Render-queue or worker errors leave the editable script intact and expose a clear retry state.
- Duplicate requests while a render is queued or processing return the active job instead of queuing another render. A stale resource revision cannot publish or serve a video as current.
- Test grade-aware prompt behavior at K, a middle grade, and 12; preserve student age-band generation; verify teacher-profile enforcement and cross-account isolation for every new route.
- Verify resource creation/editing, render progress and success, retry after failure, signed playback, download, stale-revision invalidation, lesson/resource deletion cleanup, and account-deletion cancellation.
- Verify the lesson UI supports script review/editing, progress, playback, download, and recoverable errors in English, Russian, and Kazakh, while the existing presentation-to-video flow still works.

## Out of scope

- Generating video from attached teacher documents or source-grounded lesson passages.
- Replacing or redesigning the current presentation-to-video renderer.
- Adding teacher-generated videos to the learner story history or learner quiz workflow.
- New AI providers, languages, or sharing/publication behavior.

## Assumptions

- Video resources use the same 3/4/5-minute and female/male narration choices as the existing story-video flow.
- A video remains private to its owning teacher and appears in the lesson where it was created.
- The workspace contains no usable Git repository metadata, so this design file cannot be committed from the current checkout.
