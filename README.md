# Fibonacci

**A second brain for students that builds itself.**

Students lose their study material everywhere: slide photos in the camera roll, closed tabs, PDFs in Downloads. With Fibonacci they just send it, from the web app or the Telegram bot, and Fibonacci does the rest:

1. **Reads it.** Text from blurry slide photos, transcripts with timestamps from lecture videos, pages from PDFs.
2. **Files it.** Course → Topic → Concept, with a confidence score and a one-tap fix if it guessed wrong.
3. **Connects it.** Links the same idea across courses, such as *Variance* in Probability and *Heteroskedasticity* in Econometrics.
4. **Turns it into study material.** *Exam in 3 days* builds a day-by-day plan, notes, flashcards and a quiz from the student's own material. Every line cites its source: slide, page or video timestamp.
5. **Traces mistakes.** A wrong quiz answer opens the exact slide or video moment that explains it.
6. **Spots gaps.** "You have weeks 1–6 and 8, but nothing from week 7."

> NotebookLM makes you organize your sources. Fibonacci organizes them for you, connects them, and makes sure you learned them.

English, Russian and Kazakh · light and dark · phone, desktop and projector.

## Run it locally

You need Docker (with Compose) and Node.js 20+.

1. Put a `.env` with `GEMINI_API_KEY` in the repository root (see `.env.example`).
2. Create the local secrets once: `supabase/local/setup.sh` (writes the git-ignored `.env.brain`). Add `DEMO_MODE=true`, and `TELEGRAM_BOT_TOKEN` if you use the bot.
3. Start the backend and load the demo student:
   ```sh
   docker compose -p fibonacci-local -f docker-compose.yml -f docker-compose.local.yml -f docker-compose.brain.yml \
     up -d redis brain-db brain-rest api celery-worker telegram-bot
   docker exec fibonacci-local-api-1 python -m app.services.brain.demo.seed
   ```
4. Start the web app. In `wizetale-app/.env.development.local` set `NEXT_PUBLIC_BRAIN_DEMO=1` and `BRAIN_DEMO_TOKEN` (the same value as in `.env.brain`), then:
   ```sh
   cd wizetale-app && npm ci && npm run dev    # http://localhost:3001
   ```

With `DEMO_MODE=true`, recorded AI outputs for the demo inputs replay first, so the demo also works without internet.

## Repository

| Path | What it is |
|---|---|
| `wizetale-app/` | Web app. The Brain lives in `components/brain/` and `app/brain/`. |
| `wizetale-api/` | API and background workers. The Brain lives in `app/services/brain/` and `app/api/brain/`. |
| `supabase/brain.sql` | Data model with row-level security on every table; tests in `supabase/tests/`. |
| `demo/hero/` | The three demo inputs: a slide photo, a PDF, and a lecture link. |
| `docs/brain/` | Design, team board, and the demo script. |

## Tests

- API: `cd wizetale-api && python -m pytest -q`
- Web app: `cd wizetale-app && npm run typecheck && node --experimental-strip-types --no-warnings --test scripts/*.test.mjs && npm run build`
- Database security: `supabase/tests/run_brain_tests.sh`

CI runs all three on every push.

## Deployment

See `docs/DEPLOYMENT.md`. In production the API refuses to start in demo mode or without its media signing secret.
