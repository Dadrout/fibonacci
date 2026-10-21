# TaleSpark

TaleSpark turns humanities topics into illustrated learning stories and helps teachers prepare private K–12 lesson materials in English, Russian, and Kazakh.

## Architecture

- `wizetale-app/`: Next.js frontend, deployed to Vercel.
- `wizetale-api/`: FastAPI API and Celery worker, deployed on a Docker host.
- Supabase: Auth, Postgres, and optionally private media storage.
- Cloudflare R2: optional private media storage provider.
- Redis: private queue, cache, and per-user request limits.
- Nginx + Certbot: HTTPS ingress for `api.wizetale.com`.

The browser calls Next.js route handlers. Those handlers forward authenticated requests to the server-only `BACKEND_API_URL`; the browser never receives the API host configuration or Supabase service role key.

## Local development

1. Create a Supabase project and apply [`supabase/schema.sql`](supabase/schema.sql), then [`supabase/knowledge_seed.sql`](supabase/knowledge_seed.sql) and [`supabase/teacher_prep.sql`](supabase/teacher_prep.sql), then [`supabase/relationship_indexes.sql`](supabase/relationship_indexes.sql).
2. Copy `.env.example` to `.env` at the repository root, set `ENVIRONMENT=development`, and fill in local Supabase and provider settings. Keep credentials out of source control.
3. Start Redis and the API/worker with `docker compose up --build redis api celery-worker`.
4. In `wizetale-app`, copy `.env.example` to `.env.local`, set the public Supabase URL/key and `BACKEND_API_URL=http://localhost:8000`, then run `npm ci` and `npm run dev`.
5. Open `http://localhost:3001`. API docs are enabled only outside production at `http://localhost:8000/docs`.

## Image generation

The API and Celery worker support Gemini, fal.ai, and Cloudflare Workers AI through the same image-provider interface. To use Cloudflare FLUX.2 Dev, set these server-only values in the repository-root `.env` for Docker, or `wizetale-api/.env` when running the API directly:

```dotenv
IMAGE_PROVIDER=cloudflare
CLOUDFLARE_ACCOUNT_ID=<your Cloudflare account ID>
CLOUDFLARE_API_TOKEN=<your Cloudflare API token>
CLOUDFLARE_IMAGE_MODEL=@cf/black-forest-labs/flux-1-schnell
CLOUDFLARE_IMAGE_TIMEOUT_SECONDS=180
IMAGE_GENERATION_CONCURRENCY=3
```

Keep the Cloudflare token out of frontend environment files and source control. A custom token needs `Workers AI - Read` and `Workers AI - Edit` permissions. Workers AI uses a direct authenticated request and returns the generated image; selected scenes run concurrently while the existing image budget, prompts, scene order, and placeholder fallback remain in effect.

Cloudflare FLUX.2 Dev accepts multipart form data, even for text-only prompts, and returns image data as base64. Restart or rebuild both the API and worker after changing provider settings. Set `IMAGE_PROVIDER=gemini` or `IMAGE_PROVIDER=fal` to select those providers instead.

## Production deployment

Follow [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). The production checklist is in [`docs/DEPLOYMENT_CHECKLIST.md`](docs/DEPLOYMENT_CHECKLIST.md); owner-supplied privacy and child-safety decisions are listed in [`docs/PUBLIC_LAUNCH_GATES.md`](docs/PUBLIC_LAUNCH_GATES.md).

Production API startup intentionally stops when required credentials, Redis, provider configuration, or the paid Gemini billing tier are missing. Account deletion removes a learner's media, revokes sessions, and deletes the Supabase Auth user; it is available from the account page.

## Verification

- API: `cd wizetale-api && python -m pip install -e ".[dev]" && python -m pytest -q`.
- Frontend: `cd wizetale-app && npm ci && npm run build`.
- Compose syntax: copy `.env.example` to `.env`, then `docker compose config --quiet`.

CI runs the API suite, frontend type-check, typography, teacher-content, localization and proxy checks, production build, and Compose validation.

## Teacher preparation

See [teacher setup and release checks](docs/TEACHER_PREP.md). Teacher mode is available at `/teacher` for existing accounts and as a signup preference. Saved lessons and resources belong to the authenticated account.
