# Fibonacci Brain — finale demo script (90 seconds)

Owner: Claude (backend, setup, backups) · Astra (screens, choreography — see `DESIGN_BRAIN.md`).
Status: **rehearsed — 3 full UI runs in a row passed (R7–R9), plus an offline run (R10)**. All steps work in the app (verified 2026-10-22 in a browser on live data). The Brain is one home screen — capture bar, what's arriving now, your courses (Courses | Map) — with drill-down to a course and its exam. Finalize timings after the three full rehearsals.

---

## 0. Before you go on stage (T − 30 min)

1. **Laptop on power, notifications off, browser zoom 100%, presentation mode on** (Brain header → *Presentation mode*).
2. Start the stack (from `~/Fibonacci`):
   ```
   docker compose -p fibonacci-local -f docker-compose.yml -f docker-compose.local.yml -f docker-compose.brain.yml \
     up -d redis brain-db brain-rest api celery-worker telegram-bot
   cd wizetale-app && npm run dev        # http://localhost:3001
   ```
3. **Fresh demo brain:** `docker exec fibonacci-local-api-1 python -m app.services.brain.demo.seed`
   → expect `{"courses": 3, "topics": 16, "concepts": 35, "items": 38, ... "missing_embeddings": 0}`.
   The seed keeps the Telegram link, so you don't need to re-link the phone.
4. Open **http://localhost:3001** (it opens the Brain) — the demo student loads (badge *Demo*). Check: 3 courses, the Econometrics card shows "Week 6 is missing · Week 7 is missing", *Live* is on.
5. Telegram: open the chat with **@eduhack2026_bot** on the presenter's phone; the three hero files are ready to forward (below). Send `/start` once — the bot must answer within 2 s.
6. Confirm `DEMO_MODE=true` in `.env.brain` (recorded AI outputs replay first; live AI only for anything new).

### Hero inputs (in `demo/hero/`, also saved on the phone)
| # | Item | File / link | What it becomes |
|---|---|---|---|
| 1 | Blurry slide photo | `slide7-heteroskedasticity.jpg` | Econometrics → Week 6 Heteroskedasticity, slide 7 |
| 2 | YouTube lecture | `https://youtu.be/2xcUup_-K6c` (zedstatistics, "What is Heteroskedasticity?") | same topic, transcript with timestamps |
| 3 | PDF lecture notes | `ECON301_Week6_Heteroskedasticity.pdf` | same topic, 6 pages |

---

## 1. The 90 seconds

| Time | Presenter does | Screen shows | Say |
|---|---|---|---|
| 0:00 | Brain inbox on the projector | Demo student's brain: 3 courses, 38 sources | "This is Aruzhan's second brain. She never organized any of it." |
| 0:08 | Forwards the **slide photo, YouTube link, PDF** to the bot (one after another) | Three cards appear instantly (*Reading → Filing → Linking*) | "I'm forwarding a blurry photo of a slide, a lecture link, and a PDF — straight from Telegram." |
| 0:15 | — | Each card lands on **Econometrics → Heteroskedasticity** with confidence; the bot replies "Filed under Econometrics → Heteroskedasticity ✓" | "No folders. It read the slide, transcribed the lecture, and filed all three under Week 6." |
| 0:25 | Under *Your courses*, switch **Courses → Map** | New Week 6 cluster; a **cross-course link** lights up Econometrics ↔ Probability (e.g. Heteroskedasticity ↔ Variance / Standard error) | "And it noticed that this is the same variance she learned in Probability." |
| 0:40 | Back to **Courses**, tap **Exam in 3 days** on the Econometrics card (one tap — the plan builds immediately) | Day-by-day plan + quiz; every line has a source chip (slide 7, page 4, 14:32) | "One tap: a three-day plan and a quiz built only from her own material — every line cites where it came from." |
| 0:55 | Open **Quiz**, answer a question **wrong** (pick "coefficients become biased") | *See where this was explained* → **slide 7** of her photo opens (or the video at the cited timestamp) | "Wrong answer? It takes her to the exact slide — the one she photographed — that explains it." |
| 1:10 | Back to your Brain; point at the Econometrics card | **"Week 7 is missing"** chip on the card (and in the plan's coverage line) | "And it knows what's missing: she has weeks 1 to 8 — except 7." |
| 1:20 | — | — | "NotebookLM makes you organize your sources. Fibonacci organizes them for you, connects them, and makes sure you learned them." |

Measured backend timings (local stack, 2026-10-22): three items filed in **7.7–9.8 s live** (parallel), **2.6 s from recordings**; exam plan **10–15 s live**, **1 s from recordings**; wrong answer → moment **32 ms**.

---

## 2. Backup plans

| If… | Then… |
|---|---|
| **Venue Wi-Fi is slow or down** | Nothing changes for the hero inputs: with `DEMO_MODE=true` the recorded outputs replay (verified with the Gemini key removed). Use the phone's hotspot for Telegram; if Telegram itself is unreachable, use the next row. |
| **Telegram doesn't deliver** (no internet, bot down) | Drag the three files from `demo/hero/` onto the browser window (global drop zone) and paste the YouTube link (Ctrl/Cmd+V). Same pipeline, same result. Say: "Same thing from the web app — drop anything anywhere." |
| **A card says "failed"** | Press *Retry* on the card. If it fails again, continue — the other two items carry the story. |
| **YouTube transcript blocked** | Handled: captions → Gemini clip transcription → recorded transcript. Worst case the video files by its title (no timestamps); use slide 7 for the mistake → moment step. |
| **Exam plan slow** | It streams progress (*Gathering → Planning → Citing*). Live it takes 10–15 s; from recordings ~1 s. Fill with: "It's reading everything she filed for Econometrics." |
| **Laptop/browser crash** | Restart the browser → `localhost:3001/brain`. Data is in the local database; nothing is lost. |
| **Need a clean slate between rehearsals** | Re-run the seed command (step 0.3). |

---

## 3. Rehearsal log

| # | Date | Live / recorded | Result | Notes |
|---|---|---|---|---|
| R0 | 2026-10-22 00:4x | API only (no UI) | ✅ hero items filed 9.8 s; plan 12 s (en/ru/kk); offline replay 2.6 s + 1 s | UI rehearsals pending Astra's screens |
| R1–R5 | 2026-10-22 03:5x–04:4x | Full UI, recorded | ✅ ×5 (filing 1.7–20.9 s) | Browser rehearsals (`rehearse.py`): capture → filed → Map → Exam in 3 days → wrong answer → moment |
| R6 | 2026-10-22 04:49 | Full UI, recorded | ❌ | Home was replaced by "Your Brain could not load." Two causes, both fixed: the live-updates connection dropped every 5 s (Redis client timeout shorter than the 15 s wait), and a failed background refresh wiped a working screen. Now the screen stays and quietly retries. |
| **R7** | 2026-10-22 05:0x | Full UI, recorded | ✅ filed 1.8 s · 5 new links · Week 7 gap · plan 0.6 s · moment opened · 0 page errors | Screenshots `artifacts/brain/rehearsal-r7-*` |
| **R8** | 2026-10-22 05:0x | Full UI, recorded | ✅ filed 1.8 s · 5 new links · Week 7 gap · plan 0.9 s · moment opened · 0 page errors | `rehearsal-r8-*` |
| **R9** | 2026-10-22 05:0x | Full UI, recorded | ✅ filed 1.8 s · 5 new links · Week 7 gap · plan 0.4 s · moment opened · 0 page errors | `rehearsal-r9-*` — three in a row ✅ |
| **R10** | 2026-10-22 05:1x | Full UI, **no AI key**, AI cache cleared | ✅ filed 1.9 s · 5 new links · Week 7 gap · plan 0.6 s · moment opened | Proves the "Wi-Fi down" backup: recorded outputs alone carry the whole demo |

Not yet rehearsed: forwarding through Telegram from the presenter's phone (needs the phone linked once — see §4). The rehearsals above send the same three files through the web capture path, which runs the same pipeline.

---

## 4. One-time owner setup still needed

1. ~~Telegram bot token~~ — done: **@eduhack2026_bot**, token in `.env.brain`. **Link the presenter's phone once:** Brain → Telegram → Connect Telegram → scan the QR (or open the bot and press Start). The link survives re-seeding.
2. **Gemini key tier:** the current key is on the free tier and hits per-minute limits when several items process at once. A paid key (`GEMINI_BILLING_TIER=paid`) makes live (non-recorded) captures reliable.
3. *(Only if you want the hosted Supabase project instead of the local brain database)*: paste `supabase/brain.sql` into the Supabase SQL editor once, and set `BRAIN_STORE=supabase`.
