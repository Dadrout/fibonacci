# Fibonacci Brain — shared brief for both agents

You are one of two senior agents building the finale version of **Fibonacci**, an edtech product competing in a hackathon pitch finale. The other agent works in the same repo at the same time. Your job is to win the finale with a product that works live on stage, looks world-class, and clearly cannot be replaced by NotebookLM or ChatGPT.

**Agent 1 = Claude (Opus, Claude Code)** — lead engineer, backend, data, AI pipelines, integration.
**Agent 2 = Astra (Codex CLI)** — product designer and frontend engineer.

> Live coordination happens in `docs/brain/COLLAB.md`. Read it before every task. Its **Decisions log** refines the rules below (for example the git workflow); where they differ, the Decisions log wins.

## The product idea: "A second brain that builds itself"
Students lose their study material everywhere: slide photos rot in the camera roll, tabs get closed, PDFs sit in Downloads. NotebookLM makes you upload and organize everything by hand. Fibonacci does it automatically:

1. **Zero-effort capture.** Students throw anything at Fibonacci (a blurry photo of a slide, a YouTube/lecture link, a PDF, a web page, a voice note, pasted text) through the web app, drag-and-drop anywhere, or a **Telegram bot** (Telegram is the main messenger in Kazakhstan). No "upload and choose a folder" step.
2. **Auto-sorting.** Each item is cleaned (OCR for photos, transcript with timestamps for video/audio), then filed automatically as **Course → Topic → Concept**, with a confidence score and a one-tap fix if it guessed wrong.
3. **The Brain graph.** All concepts form one living knowledge graph. The system links concepts **across courses** (e.g. "variance" in Econometrics ↔ Probability) and pulls from other sections of the brain when answering or generating material.
4. **The brain turns into study material.** One tap — "Exam in 3 days" — builds a study plan, notes, flashcards, and a quiz from everything filed under a course. Every generated claim cites its source: page, slide photo, or video timestamp.
5. **Mistake → moment tracing.** A wrong quiz answer links to the exact source moment that explains it ("rewatch 14:32–15:10", "slide 7 of your photo from Oct 3").
6. **Gap alerts.** "You have lectures 1–6 and 8, but nothing from week 7." No other tool knows what is missing.

Pitch line: *"NotebookLM makes you organize your sources. Fibonacci organizes them for you, connects them, and makes sure you learned them."*

## Hero demo — this is the acceptance test
Everything is prioritized by whether it makes this 90-second demo flawless:
1. Presenter forwards 3 messy items to the Telegram bot live: a blurry slide photo, a YouTube lecture link, a PDF.
2. Within seconds, the web app shows them arriving and being auto-filed into the right course/topic, with a satisfying animation.
3. The Brain graph lights up a new **cross-course link**.
4. Presenter taps **"Exam in 3 days"** → a day-by-day plan + quiz appears, every item cited to its source.
5. Presenter answers one quiz question wrong → the app jumps to the exact video timestamp / slide that explains it.
6. A gap alert shows: "Week 7 is missing."

## Existing project — read before changing anything
Repo: `~/Fibonacci`. Start by reading: `README.md`, `PRODUCT.md`, `DESIGN.md`, `HOW_TO_RUN.md`, `design-system/fibonacci/MASTER.md`, `wizetale-app/AGENTS.md`, `docs/UI_REDESIGN.md`, `supabase/schema.sql`, `supabase/study_tools.sql`, `supabase/teacher_documents.sql`, and the `wizetale-api/app/` and `wizetale-app/app/` trees.
Known stack (verify, don't assume):
- Frontend: `wizetale-app/` — Next.js (App Router), TypeScript, Tailwind, Radix/shadcn UI, framer-motion, recharts/d3, i18n (ru / kk / en).
- Backend: `wizetale-api/` — Python FastAPI + Celery workers, edge-tts, Gemini.
- Data/auth: Supabase Postgres with RLS (+ Firebase auth pieces), Docker Compose + nginx.
Reuse what exists (auth, source library, study tools, presentation/video rendering, i18n). Extend; don't rewrite working systems.

## Collaboration protocol (mandatory)
- Shared board: `docs/brain/COLLAB.md`. Agent 1 creates it. Sections: **Plan**, **API contracts**, **Task board** (owner, status, files), **Questions**, **Decisions log**.
- **File ownership:** Agent 1 owns `wizetale-api/**`, `supabase/**`, `docker-compose*`, and `wizetale-app/lib/*api*` / `hooks/use-*-api.ts`. Agent 2 owns `wizetale-app/app/**`, `wizetale-app/components/**`, styles, copy, and design-system files. To touch the other agent's files, write a request in **Questions** and wait. (Exact paths, including exceptions, are listed in COLLAB.md.)
- **Contracts first:** Agent 1 publishes request/response JSON shapes and TypeScript types in `wizetale-app/lib/brain-types.ts` before implementing. Agent 2 builds against those types with realistic mock data, then swaps to the live API.
- Re-read `COLLAB.md` before each new task and after each finished task. Update your task status when you start and finish.
- Commit small and often with clear messages; only commit work whose tests and build pass. (Branch workflow: see COLLAB.md Decisions log.)
- Never delete or rewrite the other agent's work. If something looks wrong, write it in **Questions**.

## Quality bar
- **Demo-proof:** every AI call has a timeout, retry, and a cached/seeded fallback so the demo works on bad Wi-Fi. Add a `DEMO_MODE` flag with a seeded demo account and pre-warmed results.
- **Honest UI:** every AI output shows its sources; uncertainty is shown, not hidden.
- **Trilingual:** all new UI strings go through the existing i18n system in ru, kk, en.
- **Secure:** RLS on every new table; never log or commit secrets; validate all inputs.
- **Verified:** you are not done until you have run it. Typecheck, tests, production build, and a real click-through of the hero demo (screenshots in `artifacts/brain/`).
- Don't fake functionality in the product code. If a feature can't be finished, cut scope and tell the other agent in `COLLAB.md`.

## Priorities
- **P0 (must work live):** capture (web + Telegram) → auto-file → Brain graph with cross-course link → "Exam in N days" plan + quiz with citations → mistake → source moment.
- **P1:** gap alerts, one-tap re-file, search across the whole brain, mobile layout.
- **P2 (only if P0/P1 are flawless):** browser-extension capture, spaced-repetition forecast, class/teacher view.

## Final checklist for both agents (before you say "done")
- [ ] Hero demo runs end to end 3 times in a row on a fresh demo account, live API and `DEMO_MODE`.
- [ ] Works with Wi-Fi off in `DEMO_MODE`.
- [ ] Every AI output shows sources; no broken citation links.
- [ ] ru / kk / en all complete; light/dark both polished; phone + projector layouts checked.
- [ ] Typecheck, tests, and production build pass; RLS tests pass.
- [ ] `docs/brain/COLLAB.md` updated with what shipped, what was cut, and known issues.
- [ ] `docs/brain/DEMO_SCRIPT.md` with the exact clicks, inputs, and backup plan if something fails on stage.
