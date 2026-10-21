# Local project audit — 2026-10-05

## Result

The tested local teacher and learner workflows pass after the fixes below. This is evidence of the tested configuration, not a guarantee that every browser, provider outage, workload or future model response will work. No deployment was performed. Existing workspace work and the older containers were preserved. This workspace has no Git metadata; remote comparison, history secret scanning, commits and branch review could not be verified here.

## Fresh verification

| Check | Result |
| --- | --- |
| API suite, local Python 3.14 | 154 passed |
| API suite inside production Python 3.11 image | 154 passed |
| Frontend regression scripts | 42 passed across 9 scripts |
| TypeScript checking | Passed |
| Clean frontend install and production build | Passed, Next 16.3.8 |
| API and frontend Docker production builds | Passed; frontend container served HTTP 200 as UID 1001 |
| Non-root API image startup, Redis connection and health | Passed |
| Container media encoding | H.264 / yuv420p video and AAC audio passed |
| Production and local Compose validation | Passed |
| npm, installed Python and exact production API dependency scans | No known vulnerabilities reported; private project package is not a PyPI audit target |
| Supabase document policy/retrieval rollback checks | Passed against configured project |
| Atomic story render/recovery rollback checks | Passed against configured project |
| Final independent Bugbot review | No actionable material findings |

The dependency scans are point-in-time advisory checks, not a complete security certification. The optional legacy gTTS fallback is excluded from the default runtime: its Click constraint prevents using the patched Click version. Do not enable that extra for production without a separate dependency review.

## Real service and browser flows

- Fictional learner: authenticated draft creation, editing, render queue, worker processing, private audio/video download, quiz scoring, history and reload passed. English, Russian and Kazakh stories completed. Russian transient speech failures were reproduced and the repaired retry completed successfully.
- Real Gemini preparation: all eight kinds passed generation, persistence, reload and duplicate prevention: objectives, lesson plan, quiz, test paper, flashcards, worksheet, exit ticket and homework. Russian and Kazakh teacher quizzes also passed validated generation.
- Source library passed again after dependency upgrades: PDF, DOCX, TXT through the frontend proxy and pasted text; accurate locations; malformed input failure/retry; private original download; ownership and attachment revision checks; source-based Gemini quiz/flashcards with validated citations; save/reload; deletion, detachment and retained “Source removed” references; account and storage cleanup.
- Production frontend on localhost used an HTTPS API endpoint with certificate verification enabled. Browser sign-in, history, teacher flashcard editing/save/reload, newly generated story preview and rendering, ready video media and a saved 3-of-3 quiz passed.
- Browser account switching: account B had no history and received “Story job not found” for account A’s job; signing back into A restored its saved draft. Hook regression tests cover responses arriving after identity changes.
- Narrow 390px learner workspace had no horizontal overflow. Desktop teacher styling was inspected after the Tailwind upgrade.
- All disposable audit accounts were deleted through the application, with missing Auth users and empty story/document storage prefixes verified. No real user accounts were deleted.

Browser screenshots are in `artifacts/local-audit/`. Real provider checks used fictional nonpersonal material. Paid Gemini images remain disabled, so videos use the configured scene-card fallback. Selected story length is approximate: the latest one-minute request produced a 41.96-second video. This audit does not claim exact duration or illustrated output.

## Repairs

- Atomic draft-and-story render claim with one snapshot; duplicate render prevention and stale queue/worker recovery. Workers cannot publish success or failures over another attempt or a deleted account. Completed media remains available even if final draft metadata fails.
- Thirty-minute recovery for interrupted teacher resource generation, with guarded late completion.
- Strict quiz option/answer validation; scene assignment and fallback fixes preserve all narration paragraphs.
- Three bounded Edge speech attempts with fresh requests and partial-file cleanup for transient transport/no-audio failures.
- Account-keyed learner mounts, token checks, storage keys and asynchronous guards; restored drafts survive account switching without crossing accounts.
- Polling transport errors refresh the existing job; actual generation failures retry the saved draft. Quiz controls stay consistent with submitted answers.
- Private document parser diagnostics are suppressed even after worker logging is reconfigured.
- Patched frontend and API dependency trees; reproducible Python constraints used by CI and Docker. Tailwind 4 uses its PostCSS plugin and compatible class merger. Confirmed orphan calendar and its dependencies were removed.
- Updated vulnerable pip/setuptools tools from the Python base image; the final production dependency scan is clear.
- Nested stale virtual environments excluded from container and wheel packaging. Container build and Python 3.11 compatibility were verified rather than inferred from the local Python version.
- Corrected frontend draft quiz type to match the existing API response. Added regression checks to CI.

## Database rollout prerequisite

`supabase/story_render_recovery.sql` was applied to the configured project as `atomic_story_render_and_recovery`. Any other environment must apply this migration before running the updated API/worker. Apply the existing teacher/document migrations in their documented order as well. The rollback checks are `supabase/story_render_recovery_test.sql` and `supabase/teacher_documents_test.sql`.

## Remaining release gates

1. Rotate Supabase, Gemini and ElevenLabs keys shared in chat. Rotate the three preserved legacy Google private keys before removing their JSON files. No credentials or Git history were rewritten in this audit.
2. Choose the new production domain and configure HTTPS, exact Auth callbacks, deployment environment, operational monitoring, backups and rollback. Local test TLS is temporary and must not be deployed.
3. Verify actual email confirmation, password-recovery delivery and callbacks with a controlled real inbox. The disposable tests used confirmed Auth-admin fixtures. Google OAuth is not configured; configure it before offering it as a working sign-in option.
4. Owner/legal approval for privacy, terms, retention, age/parental consent, incident response and Gemini under-18/free-tier data restrictions. Review Supabase’s disabled leaked-password protection.
5. Human review of Kazakh pronunciation and generated teaching content. Citations do not certify correctness.
6. Physical A4/Letter printing and browser/device coverage, including Safari and real phones. Print content separation is covered by automated checks; the native print dialog prevented reliable automated paper-layout inspection.
7. Capacity/load, prolonged soak, backup restore, production networking and provider-outage exercises are not covered by these local checks.

## Reproduce

API: install `.[dev]` with `-c constraints.txt`, then run `python -m pytest -q`. Frontend: `npm ci`, `npm run typecheck`, run each `scripts/*.test.*` directly with Node, then `npm run build`. Validate both Compose configurations and build both Docker images. The opt-in `wizetale-api/scripts/verify_teacher_sources.py` requires running local API/frontend/worker and consumes two real text generations using disposable accounts.

Dependency upgrade references: [Next 16 guide](https://nextjs.org/docs/app/guides/upgrading/version-16), [Tailwind 4 guide and browser requirements](https://tailwindcss.com/docs/upgrade-guide), [Firebase release notes](https://firebase.google.com/support/release-notes/js). The Tailwind browser minimums should be included in the supported-browser policy.
