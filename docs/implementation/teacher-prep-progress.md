# Teacher prep implementation ledger
Approved scope: private K–12 lesson workspaces; objectives, lesson plans, quizzes, test papers, flashcards, worksheets/activities, exit tickets, homework; EN/RU/KK interface and resources; ElevenLabs Kazakh narration.
Tasks: backend contracts/storage/generation; teacher UI/onboarding/printing; localization/narration; verification/review.
Ruling: workspace has no .git; preserve existing source and implement in place. Git branch isolation/history comparison are unavailable.
Ruling: use structured resource fields with separate teacher keys; teachers can change generated counts through editing. Generation presets follow the approved defaults.

Completed implementation:
- Server-validated contracts, owner-filtered teacher CRUD, revision conflicts, atomic idempotent generation and saved lesson snapshots.
- Additive database schema with RLS, grants, owner/parent constraints and account deletion cascades; rollback staging SQL regression script.
- Teacher signup/onboarding, private library, context form, eight individually generated resource types, full structured editor, save protections and separate student/teacher print views.
- EN/RU/KK interface copy, locale picker and Cyrillic font support; Kazakh story contract and ElevenLabs routing/settings.
- CI runs frontend type-check, typography, resource and localization tests alongside API/build/Compose checks.

Verification (2026-10-03):
- API suite: 106 passed (two existing slowapi deprecation warnings).
- Frontend type-check passed; typography 14, resource helpers 3, localization 2 and backend proxy 1 tests passed.
- Next production build passed; Compose configuration validation passed using example environment.
- Browser checks with simulated accounts/provider responses passed: onboarding, create, generate, edit/save/reload, print content separation, unsaved navigation warning, visible generation failure, Kazakh mobile layout without horizontal overflow and account-switch privacy. Desktop dark and mobile layouts inspected.
- Bugbot file-based review found one P1: private lesson state persisted across account changes. Fixed by identity-keyed authenticated workspace mounts on both teacher routes; browser check confirmed previous editor/print content disappears after account switch. No other confirmed finding from Bugbot. A subsequent proxy regression test reproduced successful deletes returning 503; the shared proxy now uses a null body for empty-response statuses, and the regression passes.

Unverified release gates:
- Supabase SQL application/RLS integration, live Gemini resource generation, ElevenLabs voices and existing learner end-to-end flows require staging services and test accounts. Database script has not been executed here (no local Supabase/PostgreSQL runtime).
- No deployment, Git history comparison/rewrite, live credential rotation or root credential deletion. This checkout lacks .git metadata. Existing owner/legal/credential launch gates remain.

2026-10-04 live Supabase setup: user approved Fibonacci (`nsrhlhbpnkxmzgveingy`) initialization. Applied learner/teacher migrations, approved knowledge seed (15 rows), private video bucket and three relationship indexes. Both SQL regression scripts passed with rollback; all 8 application tables enable RLS, cross-owner constraints and account deletion cascades verified. Security advisor has only the intentional server-only lock/no-policy informational notice; performance notices only unused indexes before traffic. Live Gemini/ElevenLabs/Auth/API smoke tests remain outstanding; server credential is not configured. See SUPABASE_SETUP_REVIEW.md for migration records and remaining configuration.
