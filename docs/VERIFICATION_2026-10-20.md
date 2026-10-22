# Fibonacci verification — 20 October 2026

> Follow-up: [expanded verification and latest status](FULL_VERIFICATION_2026-10-20.md). The formerly failing camera assertion is resolved there; Google OAuth is confirmed disabled.

Scope: verify the redesigned frontend and the actual local application flow through Next.js, FastAPI, Redis/Celery, Supabase, and the configured generation providers. This is local verification, not a production deployment.

## Confirmed checks

- Fresh TypeScript check and production frontend build pass.
- All 17 frontend regression test files pass.
- Backend suite after the encoder correction: 320 tests pass, one existing camera-motion expectation fails.
- Existing local API, Redis, and Celery containers are healthy. Worker inspection returned `pong`.
- Private story, learner-material, lesson, and document endpoints reject unauthenticated requests with 401 at both frontend and backend boundaries.
- An invalid test token initially produced the same 503 authentication-unavailable error through the direct backend and frontend proxy, confirming the real forwarding path.
- Normal-mode browser entry routes to registration, with preview disabled. Login validation focuses its linked error summary.

## Supabase restoration

The configured Fibonacci project initially reported `INACTIVE`; its API hostname did not resolve. The user explicitly approved restoring it. The restore operation succeeded and the project reached `ACTIVE_HEALTHY`.

Auth and database services recovered at different times: an early attempt reached a gateway 502, and a later temporary schema-cache 404 produced a teacher-profile 500. Once restoration completed, the required tables were available without database schema changes. The known fixture from the failed attempt was confirmed absent through Auth admin lookup.

A disposable fictional learner account subsequently passed password authentication through the actual browser and opened `/create`. Test credentials were stored only in a private temporary file and are excluded from these artifacts.

## Confirmed compatibility fix

A real host rendering check failed because the OpenH264 encoder does not accept the `baseline` profile name used for x264. The installed encoder's own help lists `constrained_baseline` instead.

- Added an encoder-specific regression that failed before the change.
- Updated `FFmpegService.build_command` to select `constrained_baseline` for `libopenh264`, preserving `baseline` for `libx264`.
- All three encoder-selection tests pass.
- Actual host story and presentation fixtures render as 1280×720 H.264/AAC MP4s, each 2.00 seconds.
- The running API container independently rendered both variants with x264, H.264 video and AAC audio, each 1.96 seconds. Temporary container fixtures were removed automatically.

The local API and Celery worker were subsequently rebuilt and restarted with this correction and the speech-library update below. No production deployment was performed.

## Remaining test failure

`wizetale-api/app/api/v1/tests/test_teacher_presentation_video.py:142` expects `zoompan` in ordinary story renders. The current renderer, last modified before this redesign, uses a full foreground image over a blurred background without zoom. Actual MP4 encoding succeeds, but the camera-motion expectation does not match current behavior.

Neither that assertion nor the rendering style was changed merely to make the suite pass. Resolving whether camera motion should return or the contract should be updated remains open.

## Live workflow results

Passed against real services:

- Password sign-in through the normal browser UI, with preview disabled.
- Learner flashcards (12), quiz (10), and presentation (8): real generation, save/reload, and quiz scoring. Initial learner quiz responses did not leak correct-answer fields.
- Story draft generation, title editing, save confirmation, and persistence after reload.
- A full story-video retry through the browser, API, Celery, Gemini, Edge TTS, Cloudflare image generation, FFmpeg, and Supabase Storage.
- Downloaded MP4: H.264/AAC, 1280×720, 147.8 seconds, 4,632,904 bytes. Browser media metadata reports readyState 4 and no media error.
- Story quiz scoring and persisted 3/3 result, also visible in the browser.
- Teacher TXT upload through the frontend, worker ingestion, original download, PDF/DOCX/paste ingestion, malformed-document failure and retry.
- Teacher cross-account isolation, revision-conflict handling, source-grounded quiz/flashcard generation, citations, idempotent request IDs, saves/reloads, and source removal retaining removed-source references.
- Fresh teacher-account deletion after the migration: Auth account removed and owned storage empty.

### Approved database repair

Live account deletion initially failed with 503 because `teacher_video_renders` was missing. The user explicitly approved applying `supabase/teacher_video_renders.sql`. After connector timeouts, the migration returned success. A fresh database query confirms the table, authenticated SELECT permission, no authenticated INSERT permission, RLS enabled, and the owner-only SELECT policy.

The existing eight-assertion transactional SQL test could not be executed through the connector: repeated attempts returned expired-request or transport errors. It is not counted as passing. The live account-deletion retest did pass.

### Speech-provider compatibility repair

The first real video failed at the Edge TTS WebSocket handshake with HTTP 403 while pinned to 7.2.8. The upstream maintainer confirms this issue was resolved in 7.3.0: https://github.com/rany2/edge-tts/issues/490 (maintainer comment on October 13).

Updated `wizetale-api/constraints.txt` to official PyPI release 7.3.1, upgraded the project virtual environment, and rebuilt/restarted only the local API and worker. A real speech sample then succeeded (4.896 seconds), six targeted speech/encoder tests passed, and the full 147.8-second video completed successfully.

The browser once displayed a transient progress-service error during the run; its Refresh control recovered and loaded the completed video and persisted quiz score. This does not establish resilience to every provider outage or verify all voices/languages, teacher video rendering, OAuth, or production infrastructure.

The Gemini primary model has returned temporary 503 errors and a timeout. Its configured fallback successfully produced learner flashcards and a quiz. This fallback behavior is being tested as part of the real requests, without changing model configuration.

## Evidence

Logs, generated synthetic rendering fixtures, authenticated test screenshots, and sanitized results are stored in `artifacts/verification-2026-10-20`. No test account credentials or access tokens are included. Earlier October 5 live audit results are historical evidence and are not counted as results of this run.

## Final result

Core learner and teacher-source workflows are verified live after the fixes above. The project does not have an entirely green test suite: the final backend rerun remains 320 passed / 1 failed on the camera-motion contract described above. Frontend checks are green. This report makes no claim that every feature, language, provider, or deployment is fully verified.

## Fixture cleanup

All fictional teacher and learner accounts created for this verification were removed. The final learner cleanup verified Auth 404 and empty owned storage prefixes, then removed the private temporary credential file. A database aggregate found zero recent `rag-` or `verify-` fixture accounts. The browser was signed out and returned to `/login`. Local, nonpersonal evidence (including the MP4 and screenshots) remains in the artifact directory. Supabase remains active as approved.
