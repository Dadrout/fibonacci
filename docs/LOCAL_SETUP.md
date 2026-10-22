# Local setup status — 2026-10-05

## Configured and verified

- Frontend: `http://localhost:3001`; backend proxy: `http://localhost:8001`.
- Supabase: Fibonacci (`nsrhlhbpnkxmzgveingy`). Auth Site URL is `http://localhost:3001`. Exact allowed callbacks are `/auth/callback`, `/auth/callback?next=/create`, `/auth/callback?next=/teacher`, and `/auth/callback?next=/reset-password/update`, all on localhost:3001. Verified saved in the Supabase dashboard.
- Email sign-in and email confirmation enabled; anonymous sign-in disabled. Google OAuth is not configured.
- API/worker use Gemini free-tier text, Edge speech for English/Russian, ElevenLabs v3 for Kazakh, and Supabase private video storage. Paid Gemini image calls are disabled; story rendering uses existing placeholder scene cards. Local runtime is development mode; no new production domain was configured.
- Separate Redis project `fibonacci-local`, published only at 127.0.0.1:6380, with a generated password in private environment files. API connects successfully; the worker responds to ping. Earlier containers remain running on their original ports.
- API health returned 200; the frontend teacher proxy correctly returned 401 without authentication.
- Replacement Gemini key: model listing and minimal primary/fallback text requests each returned 200. The actual teacher service generated validated objectives (4 objectives) and a quiz (10 questions / 10 answers) from fictional lesson data. Private settings declare the owner-reported free tier. API and worker were restarted with this configuration. See [Gemini free-tier review](GEMINI_FREE_TIER_REVIEW.md) for documentation, quota and release constraints.

## Owner actions still needed

1. The supplied modern Supabase secret key is now configured under the API's existing `SUPABASE_SERVICE_ROLE_KEY` setting in both private server environment files. Database, private storage and Auth admin read checks each returned 200. The key was absent from frontend configuration. Because the value was pasted into chat, replace it with a rotated server key before public launch; never put it in source or frontend variables.
2. The old Gemini key returned depleted-prepayment 402; the replacement key now successfully generates text. No credit purchase is needed for the verified local text checks. Confirm actual free quota/billing in AI Studio. Free-tier inputs must exclude personal/confidential data. Gemini's under-18 API-client restrictions remain a launch gate for the learner-facing product, even on a paid tier. Rotate the key shared in chat before public use.
3. ElevenLabs is configured privately for API/worker. Subscription, voices and model checks returned 200; Eleven v3 lists Kazakh support. Initial voices: Bella (female), George (male), both English-accent voice profiles. Two short Kazakh synthesis checks succeeded (2.80s / 2.72s); samples are in `artifacts/voice-checks/`. Have a Kazakh speaker review pronunciation before release. The account reported a free plan with 10,000 characters before these checks. Rotate the key shared in chat before public launch.
4. Configure Google OAuth client credentials in Supabase if Google sign-in is wanted. Email sign-in already has its provider configuration.
5. Core fictional-account flows now pass. Before release, verify real email delivery, physical printing, supported devices and the owner launch gates listed in [the local audit](LOCAL_PROJECT_AUDIT_2026-10-05.md).

## Start the local services again

The frontend, API and worker were started as local processes during setup. Redis runs as a separate container. Use the same ports and private configuration when restarting.

```bash
# From the repository root: isolated local Redis
 docker compose -p fibonacci-local -f docker-compose.yml -f docker-compose.local.yml up -d redis

# From wizetale-api: API and worker in separate terminals
 ./.venv/bin/python -m pip install -c constraints.txt -e '.[dev]'
 ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
 ./.venv/bin/celery -A worker.celery_app worker --loglevel=warning --concurrency=1

# From wizetale-app: frontend
 ./node_modules/.bin/next dev --webpack -H 127.0.0.1 -p 3001
```

The Compose overlay can also run the API and worker as containers after building the local image. Stop the host API/worker first to avoid port conflicts and duplicate workers, then use the same Compose project/files with `up -d --build redis api celery-worker`. Do not start nginx/certbot for this local workflow.

Private `.env` files have owner-only filesystem permissions. Old deployment domains remain historical deployment configuration and must be replaced when the owner supplies the new production domain.

## Document library upgrade

The private teacher document migration, covering foreign-key index, and pending-removal quota guard are applied to Fibonacci. Owner isolation and EN/RU/KK keyword retrieval were checked with rollback-only SQL. API/worker are running the new ingestion support locally. See [teacher preparation](TEACHER_PREP.md#private-document-library-and-source-based-generation) for limits, retry behavior and production rollout ordering.

The document workflow passed live with disposable fictional accounts: all four source formats, processing failure/retry, source attachments/revision conflicts, source-grounded Gemini quiz/flashcards, citations, duplicate prevention, save/reload, source removal references, and account/storage cleanup. Desktop-browser checks verified pasted-source Ready state and account-switch isolation. Latest audit: 154 API tests pass locally and inside the production Python 3.11 container; 42 frontend checks, type-checking, production builds, Compose and rollback database checks pass. Both dependency scans report no known vulnerabilities. See [the full audit](LOCAL_PROJECT_AUDIT_2026-10-05.md). Bugbot re-review has no remaining material findings. Teacher-only references are covered by rendering tests; physical A4/Letter print layout remains a release check. The security advisor reports leaked-password protection disabled; review that Auth setting before launch.

## October 5 recovery and dependency update

Apply `supabase/story_render_recovery.sql` before using the updated API in another environment. It is already applied to Fibonacci. Use the checked-in Python constraints for installation; the optional legacy gTTS fallback is excluded from the default verified runtime. Browser account switching, saved drafts and all three story languages passed. No deployment was performed.
