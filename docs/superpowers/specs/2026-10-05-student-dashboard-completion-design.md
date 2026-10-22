# Student Dashboard Completion

## Purpose

Make the existing student experience coherent and dependable from starting a story through reading it, taking its quiz, finding it later, and managing the learner account. Every visible control should have a clear outcome, and saved progress should survive navigation and reloads.

## Users and scope

This work is for signed-in learners using the existing student dashboard and its story, history, and profile screens. Keep the current Fibonacci visual style, supported English/Russian/Kazakh interface, and existing product capabilities. Improve action labels and state feedback where the current behavior is unclear.

The work may add or adjust authenticated API behavior where needed to make the interface correct, while preserving existing public response shapes wherever possible. Server-owned data is authoritative; browser storage may help resume a session but must not be the only copy of saved progress.

## Learner flows

### Create and edit a story

- A learner can begin a story, edit its topic and other existing inputs, and see whether the draft is saving, saved, or needs attention.
- Saved drafts can be resumed after reload. The saved values shown in the editor must match the values sent for rendering.
- Starting another story while an editable draft exists asks whether to discard it. Confirming discards that specific draft on the server; canceling leaves it intact. A draft that has already been rendered or otherwise changed state cannot be discarded as an editable draft.
- If a save or render conflicts with another action, preserve the learner's local text, explain that the draft changed, and offer a safe recovery. Never silently replace newer server data with stale edits.
- Rendering claims and snapshots the editable draft once. The story record, generation job, and displayed inputs all use that same snapshot. A competing edit or duplicate render receives a clear conflict state instead of creating mismatched or duplicate work.

### Follow story generation and read

- Show distinct queued, generating, ready, and failed states, with understandable progress or next steps and a way to return to the learner's other work.
- Refreshing or reopening an in-progress story resumes watching the same job rather than starting another generation.
- The generated story supports its existing playback controls with clear play, pause/resume, loading, and error states. Playback failure does not block reading or quiz use.
- Preserve the current story content and avoid introducing a new provider or generation mode.

### Take and revisit a quiz

- Quiz questions, choices, selected answers, submission, and results have clear states. Submission is unavailable until the current quiz's required answers are present, and repeated clicks cannot create duplicate submissions.
- After successful submission, show the saved score and answer review. Reopening or refreshing the story restores the saved result for that learner and story instead of presenting an apparently unsubmitted quiz.
- The existing one-result-per-learner-per-story storage model remains the source of truth. This design does not add a separate attempt history or retake policy.

### Browse history

- Separate initial loading, empty history, initial-load failure, and loaded history states.
- Loading more stories does not hide stories already shown. If a later page fails, keep existing items visible and offer a retry for that page.
- Prevent duplicate pagination requests and stop offering “load more” when there are no further results.

### Manage the learner account

- Profile, sign-out, and existing account actions clearly report loading, success, and recoverable failure.
- Destructive account deletion retains its existing confirmation and privacy guarantees. Account switching must not display the previous learner's draft, quiz, history, or profile data.

## Privacy and failure handling

- Every draft, story, quiz result, history entry, and profile operation remains authenticated and owner-scoped on the server.
- Client state is partitioned by learner identity and cleared or replaced when the account changes or signs out.
- Network and server failures explain what the learner can do next. Retryable actions must be safe against duplicate saves, renders, quiz submissions, and history pages.
- Do not expose internal error details or another account's content in learner-facing messages.

## Visual and interaction direction

- Keep the current brand, colors, and typography system. Do not redesign the teacher dashboard or public marketing pages.
- Make primary and secondary actions distinguishable through wording, hierarchy, and disabled/loading states.
- Keep layouts usable on mobile and desktop, with keyboard-operable controls, visible focus, readable status/error messages, and reduced-motion support.

## Out of scope

- New student features such as streaks, leaderboards, subscriptions, social sharing, or a new content generator.
- Teacher lesson-preparation and source-library changes.
- New authentication providers, database vendors, or changes to the existing language set.
- A redesigned quiz-attempt model or a new retake policy.

## Acceptance criteria

- A learner can save a draft, reload, resume it, discard it intentionally, and start a different story without leaving an invisible editable draft behind.
- Editing and rendering races do not lose edits, create a story from a different snapshot than its job, or create duplicate renders.
- An in-progress generation survives navigation and reload; success and failure states lead to sensible next actions.
- A learner can read and play a story, submit its quiz once, and see the same saved score and answer review after reopening it.
- History pagination failure is recoverable without losing already loaded stories.
- Account switching and sign-out do not reveal cached data from the prior learner; server access remains owner-checked.
- All visible student-dashboard controls have a defined working outcome or are clearly presented as unavailable.

## Assumptions

- The existing `quiz_results` unique key per story and learner represents the intended single saved result.
- A learner explicitly confirms before an editable draft is permanently discarded.
- Existing authentication and generation providers remain configured separately; this work improves the student experience around their existing behavior.
