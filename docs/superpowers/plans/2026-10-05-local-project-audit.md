# Whole local project verification plan

> **For agentic workers:** Use superpowers:executing-plans. Track evidence below; reproduce confirmed bugs and add failing regression tests before implementation.

**Goal:** Verify and repair the complete local teacher and learner workflows before any deployment.
**Architecture:** Next frontend/proxy → authenticated FastAPI → Supabase persistence/private storage and Redis/Celery → Gemini/TTS/FFmpeg → saved results/UI. Preserve all local changes and use disposable fictional accounts/content for live checks.
**Tech stack:** Next/React/TypeScript, Python/FastAPI/Celery, Redis, Supabase, Gemini, Edge/ElevenLabs, FFmpeg.
**Spec:** User's 2026-10-05 whole-project local audit request; existing functional contracts in domain models, schemas and docs/TEACHER_PREP.md.

## Constraints
- No deployment, Git rewrite, credential deletion/rotation, or unrelated containers changed.
- No exposed secrets/document contents in logs or artifacts.
- Free-tier Gemini checks use nonpersonal fictional material; image billing remains disabled.
- Git metadata was unavailable previously; recheck and preserve work in place if unavailable.
- Execute audit/fixes inline under existing authorization; one independent Bugbot reviewer may review code.

## Review focus
- Provider/network failure must show an honest retryable failure, not endless loading or silent fallback.
- All owner data must disappear from mounted UI on account changes.
- Worker retries/failures/deletion races must not publish stale records or leak originals.
- Teacher print must separate references/keys from student content in all interface languages.
- Video/audio encoding and signed URLs must actually play, and saved quizzes must submit/reload.

## Checklist and evidence
- [x] Inventory routes, dependencies, service configuration and existing tests without revealing secrets.
- [x] Fresh baseline: bare API pytest; all frontend test scripts/typecheck; production build; Compose validation; installed dependency checks.
- [x] Review authentication/recovery/profile/account paths and exercise disposable-account browser flows.
- [x] Exercise teacher lesson CRUD, every generation kind and localized print rendering; source library upload/attach/search/deletion and insufficient-source errors.
- [x] Exercise real story draft/edit/render → worker → private assets → playback → quiz → history/reload with configured local services.
- [x] Verify cancellation, duplicate actions, owner isolation and retry/recovery through targeted regression tests/SQL.
- [x] Fix each confirmed failure after a failing test, then rerun its flow and full suites.
- [x] Independent Bugbot review; fix confirmed findings and recheck.
- [x] Remove disposable fixtures; save a report with passed, failed, and unverified gates; keep deployment blocked if required flows fail.

## Final evidence

See [local audit report](../../LOCAL_PROJECT_AUDIT_2026-10-05.md): 154 API tests on host and container, 42 frontend checks, clean install/typecheck/build, both container builds, health/media smoke, Compose, live Supabase rollback checks, real provider flows, account switching, fixture cleanup and final Bugbot review. Physical printing, real inbox delivery, broader devices, load/operational checks and owner launch gates remain explicitly unverified. These gates prevent claiming universal 100% readiness.
