# Expanded Fibonacci verification — 20 October 2026

**Status:** automated and tested local workflows pass. Google sign-in is blocked by Supabase configuration; real email delivery remains pending owner verification. No production deployment or universal readiness claim is made.

This extends [the earlier verification](VERIFICATION_2026-10-20.md). Tests use the normal application, fictional accounts, real Gemini/Cloudflare/Edge/ElevenLabs services, Next.js proxy, FastAPI, Celery, Redis, and Supabase. Preview mode is disabled. Earlier results are explicitly identified below rather than counted as new tests.

## Final automated results

| Check | Result |
|---|---|
| API suite, host Python 3.14 | 321 passed, 0 failed; two SlowAPI deprecation warnings |
| API suite, production Python 3.11 image | 321 passed, 0 failed |
| Frontend regression suite | 81 tests in 17 files passed, 0 failed |
| TypeScript | Passed |
| Final production frontend build | Passed |
| Installed Python requirement consistency | No broken requirements |
| Final npm production dependency audit | 0 known vulnerabilities reported |

The Python 3.11 test environment was disposable and removed. Its first bind-mount attempt failed on host permissions; copying the current tests and SQL fixtures into the disposable container worked. A thread-based TestClient production-CORS probe stalled; an ASGI transport probe subsequently verified the behavior directly. These harness failures are not counted as product failures or successful checks.

## Live workflow coverage

- Two fictional users passed real password sign-in and teacher onboarding. Incorrect passwords were rejected, and refresh-token exchange succeeded.
- All ten teacher resource kinds generated and passed their actual content models and preset rules: objectives, lesson plan, quiz, test paper, flashcards, worksheet, exit ticket, homework, presentation, and topic video.
- Every teacher kind passed save/reload, stale-revision conflict rejection, and cross-account resource isolation. A repeated generation request reused its original ID.
- Teacher lessons were created in English, Russian, and Kazakh. Kazakh objectives and Russian homework were generated; other teacher kinds used English.
- Learner Russian flashcards (12), Kazakh quiz (10), and English presentation (8) passed real generation, ownership checks, persistence or scoring. Initial quiz responses omitted correct-answer fields. Presentation and flashcard stale revisions returned 409.
- Teacher presentation video: 108.04 seconds, 3,677,216 bytes, H.264/AAC, 1280×720. Teacher topic video: 154.32 seconds, 4,245,537 bytes, H.264/AAC, 1280×720. Both completed via the actual worker and downloaded through the authenticated frontend proxy; another user received 404.
- Repeating an active render reused its job. Editing the teacher topic-video script invalidated its old render and blocked the stale download with 409.
- Both teacher and learner presentations generated three slide visuals. Signed image downloads loaded, foreign-user retries returned 404, retries completed, and removals persisted. Teacher visual changes intentionally invalidate previously rendered presentation videos.
- Direct database requests used the publishable key and real user JWTs, never the service credential: eight tables returned only owned rows, foreign-owner queries returned zero rows, client updates returned 403, and anonymous reads were denied. Direct reads of server-only slide visuals returned 403. Metadata additionally confirmed RLS and revoked client writes on all nine tables.
- Actual boundary requests verified anonymous 401s, invalid input 422s, private/no-store responses, and the onboarding 429 limit with a forwarded Retry-After header.
- Production CORS accepted a configured origin (200) and rejected an untrusted origin (400). Development intentionally adds a wildcard; its preflight allows other origins. No production CORS policy was relaxed.
- English and Kazakh male/female speech and Russian female speech succeeded on the host. Russian male speech succeeded in the actual API container after a retry; see intermittency below.
- Browser checks at 390×844 found no horizontal overflow in learner and teacher workspaces. Teacher light/dark themes and English/Russian/Kazakh UI text were inspected. A real teacher quiz title edit survived reload. The learner library loaded the generated formats; presentation controls advanced slides, keyboard ArrowRight navigation worked, and presentation mode exited correctly. The browser console had no application errors in the inspected session, but did log a Next.js smooth-scrolling warning.

The earlier run additionally verified learner story draft generation/editing, a 147.8-second learner story video, persisted story quiz scoring, all four document source types, worker ingestion and original downloads, source-grounded teacher generation/citations, account isolation, source removal, and account/storage deletion. Those were not needlessly regenerated in this pass.

## Changes made during expanded testing

1. **Teacher topic-video downloads were being decoded as text by the Next.js proxy.** Added a failing binary regression, extended the existing MP4 streaming branch to teacher topic-video endpoints, and verified the real downloaded MP4 with ffprobe. Presentation streaming remains covered.
2. **The proxy dropped Retry-After.** Added a failing regression and preserved that response header for normal JSON and document-upload proxy responses. A real 429 now includes the API's retry delay. A type-check caught an overly broad inferred helper return type during implementation; the final helper explicitly returns string headers and final type/build checks pass.
3. **An old camera-motion assertion mismatched current rendering.** Replaced the zoom-specific assertion with meaningful coverage that the foreground preserves the entire image over a separately cropped blurred backdrop. Presentation fade/steady-frame checks remain. No renderer behavior was changed in this pass.
4. **npm reported one high-severity transitive advisory.** Updated only source-map-js 1.2.1 → 1.2.2 in the lockfile. The final audit reports zero vulnerabilities. [Advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

## Confirmed blockers and remaining limits

- **Google OAuth is disabled in Fibonacci Supabase.** The public Auth settings return google=false; authorization returns HTTP 400, `Unsupported provider: provider is not enabled`. Browser sign-in cannot complete until the owner configures/enables the Google provider. The owner opted to handle external-account steps. No OAuth credentials or provider settings were changed. Follow the [official Google provider setup](https://supabase.com/docs/guides/auth/social-login/auth-google), including the Google client, Supabase callback, and the app callback allowlist. Keep the client secret in the provider dashboard.
- **Real email delivery and email-link completion are unverified.** No personal inbox was accessed or password/verification code requested. Signup confirmation, reset-email arrival, real Google consent, and final OAuth callback still need owner testing.
- **Provider intermittency remains visible.** One worksheet request produced a business-validation ValueError and a recoverable 503; a direct reproduction and fresh API generation passed. The failed model output was not retained, so its exact invalid field is unknown. Russian male speech twice exhausted host retries despite appearing in the live voice catalog, then succeeded in the API container after a retry. These are recorded as failures/recoveries, not universal reliability.
- No load/soak test, physical printing, full PDF pagination export, Safari/Firefox/device matrix, OS reduced-motion emulation, adversarial security audit, production deployment, or production failover testing was performed. The earlier transactional SQL test connector failures remain documented; the real JWT/RLS checks above provide additional evidence without claiming those SQL assertions passed.

## Cleanup and handoff

Both fictional full-verification users were deleted through the real account endpoint. Admin lookups returned Auth 404; owned story/document storage prefixes were empty; the private credentials file was deleted. A database count confirmed zero `full-verify-…@example.test` accounts remain. The browser was signed out, language/theme restored, and the viewport override reset. The normal login tab was left visible for the owner's external-account tests. No real user account was deleted.

Evidence is in `artifacts/full-verification-2026-10-20`, including per-layer logs, sanitized JSON results, MP4/MP3 files, and screenshots. Passwords, bearer tokens, refresh tokens, signed media URLs, and provider keys are excluded from the saved result files.
