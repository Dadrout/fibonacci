# Student Dashboard Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the existing learner flow so drafts, generation, playback, quizzes, history, and account actions behave reliably and clearly.

**Architecture:** Keep the current Next.js student screens and FastAPI API. Use Supabase-backed, owner-scoped operations as the source of truth, add conditional draft deletion and quiz-result retrieval, then update the client state machines and feedback around those contracts.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, FastAPI, Python, Supabase PostgREST, existing pytest API suite.

**Spec:** `docs/superpowers/specs/2026-10-05-student-dashboard-completion-design.md`

## Global Constraints

- Keep the current TaleSpark visual style, supported English/Russian/Kazakh interface, and existing product capabilities.
- Server-owned data is authoritative; browser storage may help resume a session but must not be the only copy of saved progress.
- Every draft, story, quiz result, history entry, and profile operation remains authenticated and owner-scoped on the server.
- Preserve existing public response shapes wherever possible.
- The existing one-result-per-learner-per-story storage model remains the source of truth; do not add attempt history or a retake policy.
- Do not introduce a new content generator, authentication provider, or database vendor.
- Keep layouts usable on mobile and desktop, with keyboard-operable controls, visible focus, readable status/error messages, and reduced-motion support.
- Keep the existing account-deletion confirmation and privacy guarantees.

## File Map

- `wizetale-api/app/services/story_repository.py` — owner-scoped conditional draft removal and quiz-result reads/idempotent writes.
- `wizetale-api/app/api/v1/stories.py` — authenticated draft-delete and quiz-result read contracts; preserve current render claim behavior.
- `wizetale-api/app/api/v1/tests/test_story_routes.py` — route-level ownership, conflict, and quiz contract coverage.
- `wizetale-api/app/api/v1/tests/test_story_repository.py` — PostgREST request-filter and idempotent persistence coverage.
- `wizetale-app/app/api/v1/story-drafts/[draftId]/route.ts` — forward authenticated DELETE for a draft.
- `wizetale-app/app/api/v1/stories/[storyId]/quiz-results/route.ts` — forward authenticated GET while preserving POST.
- `wizetale-app/hooks/use-story-generator.ts` — persist explicit discard, serialize saves, expose save state, preserve local edits on failure.
- `wizetale-app/app/create/dashboard-client.tsx` — preserve “Save and start new,” add confirmed discard, show save state, and report sign-out failures.
- `wizetale-app/scripts/student-draft-lifecycle.test.cjs` — regression coverage for save ordering and server-backed discard using the app's existing Node test pattern.
- `wizetale-app/app/story/[taskId]/page.tsx` — restore saved quiz answers and score, gate submission while loading, and show playback failures.
- `wizetale-app/app/history/page.tsx` — separate first-page and later-page errors; retain existing stories and make either page retryable.
- `wizetale-app/app/profile/page.tsx` — report sign-out progress and recoverable errors alongside existing delete-account state.

## Review Focus

- A draft save already in flight when discard or render begins must not resurrect deleted data or replace newer text. Pin in Task 2 with an ordered-save/discard scenario and in Task 1 with a delete-versus-render status-filter scenario.
- Two quiz submissions for the same learner/story must preserve one original result; a different learner must not read it. Pin in Task 3 with duplicate-submit and owner-filter cases.
- A quiz-result read failure must not look like “not submitted” or enable a new submission. Pin in Task 4 by checking the UI stays in a retryable result-loading state.
- A later history page failure must preserve the first page and retry the same offset. Pin in Task 5 by checking append failure and retry behavior in the running learner view.
- Playback and sign-out failures must leave story reading/quiz access available and keep the learner on a recoverable screen. Pin playback in Task 4 and sign-out in Task 6 with local browser walkthroughs.

---

### Task 1: Add conditional, owner-scoped draft discard

**Files:**
- Modify: `wizetale-api/app/services/story_repository.py`
- Modify: `wizetale-api/app/api/v1/stories.py`
- Modify: `wizetale-api/app/api/v1/tests/test_story_repository.py`
- Modify: `wizetale-api/app/api/v1/tests/test_story_routes.py`
- Modify: `wizetale-app/app/api/v1/story-drafts/[draftId]/route.ts`

**Interfaces:**
- Produces: `delete_draft_if_editable(draft_id: str, user_id: str) -> dict[str, Any] | None`. It deletes only the matching owner row with `status='draft'` and returns the deleted row when the conditional delete succeeds.
- Produces: `DELETE /api/v1/story-drafts/{draft_id}` through the Next proxy. Return `204` when deleted, `404` when no owned draft exists, and `409` when an owned draft exists but is no longer editable.

- [x] **Step 1: Add failing repository coverage** in `test_delete_draft_if_editable_filters_by_owner_and_status` for the owner, id, and `status=draft` filters; assert a nonmatching response returns `None`.
- [x] **Step 2: Add failing route coverage** in `test_delete_story_draft_returns_no_content_to_owner`, `test_delete_story_draft_hides_missing_or_foreign_drafts`, and `test_delete_story_draft_returns_conflict_after_render_claim`.
- [x] **Step 3: Implement the conditional repository delete** with PostgREST `return=representation`; after a zero-row result, perform an owner-scoped lookup only to distinguish `404` from `409` without exposing foreign rows.
- [x] **Step 4: Add the API DELETE route** and Next proxy handler. Keep all existing GET and PATCH behavior unchanged.
- [x] **Step 5: Run the focused API checks** with `cd wizetale-api && pytest app/api/v1/tests/test_story_routes.py app/api/v1/tests/test_story_repository.py -q`.

### Task 2: Make draft autosave and discard safe in the learner workspace

**Files:**
- Modify: `wizetale-app/hooks/use-story-generator.ts`
- Modify: `wizetale-app/app/create/dashboard-client.tsx`
- Create: `wizetale-app/scripts/student-draft-lifecycle.test.cjs`

**Interfaces:**
- Consumes: Task 1's authenticated `DELETE /api/v1/story-drafts/{draft_id}` contract.
- Keeps: `clearDraft(): void` as the existing local active-pointer clear used after a draft is saved to the learner's draft shelf. It does not delete the server draft.
- Produces: `discardDraft(): Promise<boolean>`; it waits for already queued saves, deletes the current owned editable draft, clears the learner-keyed active pointer only on success or confirmed absence, and keeps the current draft/text on conflict.
- Produces: `draftSaveStatus: 'saved' | 'saving' | 'error'` from `useStoryGenerator`.

- [x] **Step 1: Add failing Node regression tests** in `student-draft-lifecycle.test.cjs` for ordered saves, render waiting for autosave and using its final script snapshot, discard waiting for an in-flight save, successful server discard, `409` preservation, and local pointer clearing that leaves an explicitly saved server draft available.
- [x] **Step 2: Run `node --test scripts/student-draft-lifecycle.test.cjs`** and confirm each failure identifies the missing queue or discard behavior.
- [x] **Step 3: Serialize draft PATCH requests** in `useStoryGenerator` so an older save cannot complete after and overwrite a newer save; keep a failed save from clearing or replacing the current draft.
- [x] **Step 4: Implement `discardDraft(): Promise<boolean>`** using the owner-scoped DELETE, waiting for already queued PATCH operations and preserving state on `409` or network failure. Keep `clearDraft()` local for drafts explicitly saved to the shelf.
- [x] **Step 5: Add save-status feedback** in the review panel: show unsaved changes during the debounce, saving while a PATCH is pending, saved after persistence, and a recoverable message on failure.
- [x] **Step 6: Sync editor fields only when the draft identity changes.** A PATCH response for the same draft must not replace text the learner edited while that request was in flight.
- [x] **Step 7: Preserve “Save and start new”** and add a clearly labeled “Discard draft and start new” choice to the existing confirmation group. Cancel keeps the draft; confirmed discard removes that draft from both the server and saved-drafts shelf. Disable edits/autosave during deletion, reset the editor only on success, and preserve it with a conflict message if the draft has left `draft` state.
- [ ] **Step 8: Re-run the Node regression script** and confirm save/discard behavior in the local learner view, including typing during a pending save, keeping a saved draft, and explicitly discarding it. Scripted regressions pass; the account-free preview opens and creates a sample draft, but authenticated save/discard needs the API and auth services and remains unverified.

### Task 3: Restore quiz results through an owner-scoped API

**Files:**
- Modify: `wizetale-api/app/services/story_repository.py`
- Modify: `wizetale-api/app/api/v1/stories.py`
- Modify: `wizetale-api/app/api/v1/tests/test_story_repository.py`
- Modify: `wizetale-api/app/api/v1/tests/test_story_routes.py`
- Modify: `wizetale-app/app/api/v1/stories/[storyId]/quiz-results/route.ts`

**Interfaces:**
- Produces: `get_quiz_result(story_id: str, user_id: str) -> dict[str, Any] | None`, filtering by both `story_id` and `user_id`.
- Produces: authenticated `GET /api/v1/stories/{story_id}/quiz-results` returning `{ "result": null }` when no result exists or `{ "result": { "answers": ..., "score": ..., "total": ... } }` for the owner's saved result. A non-owned or incomplete story returns `404`.
- Refines: quiz submission to be first-write-wins for the existing `(story_id, user_id)` unique key. Repeated submissions return the original saved answers and score rather than replacing them. Add `answers` to the existing POST response so the client can display the persisted result even if another tab submitted first.

- [x] **Step 1: Add failing repository tests** named `test_get_quiz_result_filters_by_story_and_user`, `test_get_quiz_result_returns_none_without_a_saved_row`, and `test_save_quiz_result_keeps_the_first_result_on_conflict`.
- [x] **Step 2: Add failing route tests** named `test_get_quiz_result_returns_only_the_owned_completed_story_result`, `test_get_quiz_result_returns_null_when_not_submitted`, `test_get_quiz_result_hides_another_users_result`, and `test_quiz_submission_returns_the_existing_result_on_repeat`.
- [x] **Step 3: Implement quiz-result lookup** and change the save operation to ignore a duplicate unique key, then fetch and return the original row when the insert created no row.
- [x] **Step 4: Add authenticated GET** to `stories.py`, resolve the completed story under the current user, return only answers/score/total, and expose GET from the Next proxy. Add `answers` to the POST response while retaining its existing `score` and `total` fields.
- [x] **Step 5: Run the focused API checks** with `cd wizetale-api && pytest app/api/v1/tests/test_story_routes.py app/api/v1/tests/test_story_repository.py -q`.

### Task 4: Restore quiz state and clarify story playback outcomes

**Files:**
- Modify: `wizetale-app/app/story/[taskId]/page.tsx`

**Interfaces:**
- Consumes: Task 3's quiz-result GET response and current `useStoryPoller` result, including `story_id`, `quiz`, and media URLs.
- Produces: quiz loading, submitted, and load-error UI states. The score and answers are restored from the server; submission stays disabled until the saved-result lookup finishes.

- [x] **Step 1: Fetch the saved quiz result** when a completed result with `story_id` and quiz questions becomes available. Treat `{result:null}` as not yet submitted; restore `answers` and `score` when a row exists.
- [x] **Step 2: Keep submission locked during result lookup** and after an existing result is restored. On lookup failure, show a retry action and do not present the quiz as unanswered.
- [x] **Step 3: Keep submission idempotent in the UI.** Disable answer controls and submit while saving; after success, display the persisted answers and score returned by the API.
- [x] **Step 4: Add a video playback error state** that leaves recap, narration, sources, and quiz available, with a clear message that the learner can continue reading.
- [ ] **Step 5: Walk through new result, saved result after reload, result-load retry, and media failure** in the local learner view. Scripted tests pass; the local account-free preview has no completed API story or quiz result, and auth/API/media integration remains unverified.

### Task 5: Preserve history and recover pagination failures

**Files:**
- Modify: `wizetale-app/app/history/page.tsx`

**Interfaces:**
- Produces: distinct initial-load and load-more error states with retry actions. Existing story records stay visible after an append failure; retry uses the same `offset`.

- [x] **Step 1: Separate initial-load and append errors** so an append failure cannot hide loaded stories or remove the load-more action.
- [x] **Step 2: Add explicit initial-page retry** while retaining the empty-history state only after a successful empty response.
- [x] **Step 3: Guard page requests synchronously** against duplicate clicks and clear only the relevant error after a successful retry.
- [ ] **Step 4: Walk through first-page failure, later-page failure, retry, and end-of-history** in the local learner view. Reducer regression tests pass; history requires the authenticated API and remains unverified without those services.

### Task 6: Finish feedback for sign-out and account actions

**Files:**
- Modify: `wizetale-app/app/create/dashboard-client.tsx`
- Modify: `wizetale-app/app/profile/page.tsx`

**Interfaces:**
- Consumes: the existing `logout(scope?: 'global' | 'local'): Promise<void>` behavior from `useAuth`.
- Produces: sign-out controls with an in-progress state, navigation after success, and an accessible recoverable error on failure. Keep profile account-deletion behavior and its existing confirmation.

- [x] **Step 1: Add sign-out state and error handling** to the dashboard header and profile page. Prevent duplicate clicks while `logout()` is pending; flush latest draft edits before exit.
- [x] **Step 2: Keep account deletion feedback intact** and ensure successful deletion still clears learner-keyed draft/job pointers before redirecting.
- [ ] **Step 3: Verify sign-out success and failure states** in the local learner view; confirm account deletion remains explicitly confirmed and busy while pending. Hook-level save-before-exit regression tests pass; sign-out and account deletion require live auth/API services and remain unverified.
- [ ] **Step 4: Check added controls and feedback at mobile width and with keyboard navigation**; preserve visible focus, accessible status/error announcements, and the existing reduced-motion behavior. Responsive behavior was not visually inspected.

### Task 7: Run the project acceptance checks

**Files:**
- No additional product files; resolve any issues in the files above.

- [x] **Step 1: Run API route/repository coverage** with `cd wizetale-api && pytest app/api/v1/tests/test_story_routes.py app/api/v1/tests/test_story_repository.py -q`. Full API suite: 167 passed.
- [x] **Step 2: Run frontend type-checking** with `cd wizetale-app && npm run typecheck`.
- [x] **Step 3: Run the production frontend build** with `cd wizetale-app && npm run build`. Build passed in an isolated temporary copy so the preview's build output was untouched.
- [ ] **Step 4: Complete a local end-to-end learner walkthrough**: sign in, create/edit/save/discard a draft, start and revisit generation, read/play a story, submit/reload its quiz result, retry history pagination, switch accounts, and sign out. Partial: the local account-free student preview at `http://localhost:3001/create?preview=1` was opened, a sample question created a draft editor, and the tab was left available. The full checklist requires configured auth/API/worker/storage services; Docker service startup is unavailable because access to the Docker socket is denied.
- [x] **Step 5: Record service-dependent gates** if local auth, worker, or media storage prevents a flow from completing; do not claim that blocked flow is verified.
