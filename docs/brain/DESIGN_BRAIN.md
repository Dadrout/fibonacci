# Fibonacci Brain — design direction

**Owner: Astra · H1 / H2**

## Product intent

The Brain should feel like a quiet place where scattered study material starts to find its shape. The student does not need to sort each source: they add it once, watch Fibonacci read and file it, then see the ideas connect. The live inbox is the proof surface for the finale demo. It must show what the system is doing, how certain it is, and where a learner can correct it.

## Visual direction: Seedhead, extended

Keep the existing Seedhead identity and its Literata / Golos Text pairing. Use the paper background, clean working surfaces, cobalt actions, pale cobalt context surfaces, and gold only for progress, sources, or cross-course emphasis. The seedhead mark stays a small brand cue. The Brain adds a slightly denser field-notes layout: a strong editorial page title, a live status line, a visible capture action, then source rows that resolve into Course → Topic. One border and one working surface are enough; avoid nested cards, ornamental gradients, stock art, and dashboard chrome that competes with the material.

Status needs more than color. The pipeline uses a numbered, labeled path—Queued → Reading → Filing → Linking → Filed—with a progress rail driven by the API's `progress` value. The active step is set in heavier type; completed steps use a check. Confidence is an explicit percentage with a review cue when `needs_review` is set or the match is weak. Failed sources keep their original place and show a localized reason with a retry action.

Use existing semantic CSS tokens (`--studio-paper`, `--studio-surface`, `--studio-ink`, `--studio-muted`, `--studio-line`, `--studio-green`, `--studio-accent`, and `--studio-sage`). Keep the global palette and logo. The graph adds eight scoped `--brain-course-N` categorical tokens (each with a dark counterpart) for the API’s stable `color_index`; labels, surfaces, actions, and gold emphasis retain the shared semantic tokens. A presentation mode may deepen contrast and scale type, but it uses these same materials and the existing theme setting.

## Screen direction

### Inbox — `/brain` default

The inbox is the first screen and the hero demo stage. At the top: Brain title, item/course/concept totals, a live connection indicator, the presentation toggle, and the persistent Add action. A compact tab row holds Inbox, Graph, Courses, Exam, and Telegram; only Inbox is fully implemented in H1. The inbox begins with any active cross-course connection and gap alerts, followed by newest captures.

Each source row shows a kind label, title, source thumbnail when one exists, stage, real progress, and—after filing—Course → Topic. The correction disclosure lists the server-provided alternatives and sends the selected course/topic to `refile`. The row keeps the distinction between a confident match and a guess that needs review. Errors use `failure_code` copy, never backend English detail, and offer Retry.

An empty brain uses one onboarding screen, not a multi-step wizard: “Just send us anything,” with drop, paste, Add, and Telegram as equally clear ways to start. It explains that the source will be sorted automatically. The mock-only “Simulate Telegram demo” control is visibly labeled as a developer control and is absent from live mode.

### Graph

The graph is the signature exploration view in H2 / A4. Group courses as readable clusters, place topics inside each course, and render concepts as the fine-grained nodes. Course clusters use the stable course palette slot, ordinary same-course links stay quiet, and verified cross-course links use a stronger gold-accented line and a short draw-on animation. Selecting a node opens a source panel with the concept summary and the exact passages, pages, slides, or timestamps behind it. Zoom should move from the whole-brain overview to one course without hiding labels or making edges the only way to understand a relationship.

#### H2 implementation direction and verification plan

1. Repair inbox state: apply event updates to counters immediately, reconcile totals with overview snapshots, and keep at most three dismissible connections using the course titles carried in each event. Filed sources lose the pipeline and secondary summary; their destination briefly lands on a course-colored strip. Group missing sequences into one alert per course.
2. Share `CitationChip` and a controlled `SourceViewer`. A Radix dialog keeps focus and Escape behavior. The quote and anchor remain visible independently of media. YouTube has a ready handshake and timeout with thumbnail fallback; audio seeks after metadata loads. Photo, PDF page, paragraph, and section anchors use the same readable source heading. All labels use `lib/copy.ts` and localized dates.
3. Lazy-load one SVG graph. D3 mutates a separate layout model, never API objects. A tick writes SVG coordinates through cached element refs, without React state updates or layout reads; the simulation cools and stops. Course anchors form clusters, topics orbit them, and concepts use a bounded square-root mention radius. Containment is dashed, within-course links are thin, and cross-course links are thick gold curves. A newly created cross-course edge draws once with endpoint rings; its named connection stays in the banner stack until dismissed.
4. Pointer drag/pinch, wheel zoom, arrow-key pan, +/- zoom, Home fit, and explicit controls share one camera. Course/topic activation focuses its cluster and shows a list of child concepts; concept activation loads `api.concept(id)` in a side sheet, with cross-course neighbors first. A hierarchical list toggle exposes the same concepts through native disclosures/buttons. Projector mode enlarges labels and edges. Reduced motion settles D3 before drawing and uses fades without movement.
5. Keep three named connection announcements stacked beside the map above 1080px; below that width they stack above it. The Graph tab uses a shorter page heading so a projector can show the map and announcements together. The simulation control stays available on both Inbox and Graph.
6. Add behavioral tests for event counts/replay, grouped gaps, retained connections, graph parent/link integrity, stable layout inputs, camera bounds, and citation anchors. Run the requested frontend typecheck and script suite. Claude owns production build, browser screenshots, media/offline checks, and timed performance/rehearsal review outside this sandbox.

H2 review focus: snapshots racing incoming events; duplicate/replayed events; disconnected media that fires iframe load but never becomes ready; stale concept requests after rapid navigation; zoom/drag cleanup and readable small-screen controls. — Astra

### Course

The course view orders topics by sequence and shows the item cards that support each topic. A detected gap appears inline where it belongs (“Week 7 is missing”) with an Add action. Loose items remain visible and can be re-filed. The student can rename a course without losing its items or links.

### Exam

The entry point is a direct action—“Exam in 3 days”—followed by a day-by-day plan. Study tasks, notes, flashcards, and quiz questions keep visible citation chips. A citation opens the exact source context: a timestamped video window, a slide/photo, or a PDF page. When an answer is wrong, show a kind explanation and a single “See where this was explained” action that opens the returned source moment.

### Telegram connect

Explain the handoff in one short paragraph, show the one-time code and a QR for the deep link, state the expiry, and make the linked state unmistakable. Keep the code selectable and the link available to keyboard and screen-reader users; QR is a convenience, not the only route.

## Capture everywhere

The app-wide capture layer appears only when `useBrainSession().canUse` is true. A compact Add control opens the native file picker. Dropped files and links are accepted anywhere in the app; paste accepts an image, URL, or text only when focus is outside an editable control. The client checks `BRAIN_ACCEPT`, rejects empty or over-20-MB files before upload, uses `captureFile` progress callbacks, and sends links/text through their existing API methods. A small live status surface confirms the action or explains how to recover from an error. The inbox stays authoritative through overview and the event stream.

## Motion and accessibility

Motion describes actual state changes: a new item enters the list, its progress rail advances as API events arrive, a filed row settles into its course, and a cross-course link draws once when created. Transitions stay short and use existing easing. No looping decoration is needed. Under `prefers-reduced-motion: reduce`, disable transforms and reveal changes immediately while retaining text, progress, and status semantics.

All controls are keyboard reachable, use native buttons/links/inputs, have visible focus rings, and meet 44px touch targets. The pipeline is labeled for assistive technology with `role="progressbar"` and polite live announcements for new connections and capture feedback. Thumbnails include useful alt text; decorative marks remain hidden from assistive technology. Long Kazakh copy may wrap and grow the row naturally rather than truncate.

## Projector mode

The presentation toggle is persisted in local storage on the current device. It enlarges body and status type, strengthens the paper/ink contrast, broadens the source-row and progress-rail spacing, and keeps meaningful actions visible without hover. The state does not change the data or the selected light/dark theme. On a phone it retains the regular responsive layout; on a projector, labels and progress remain readable from the back of the room.

## Hero demo choreography (90 seconds)

The event names below are the contract in `COLLAB.md` §2. The website is already open on Inbox; Telegram is already linked. Each capture is allowed to finish while the presenter sends the next one.

| Time | Presenter / screen | Event and response |
|---|---|---|
| 00–03 | Presenter opens with “I send it once; Fibonacci sorts it.” Inbox is visible. | Existing `overview()` gives the baseline and the Week 7 gap. The SSE indicator is connected. |
| 03–06 | Forward the blurry slide photo from Telegram. | `item.created` adds a queued photo row; `item.progress` advances through extracting, classifying, and linking. The visible rail follows the real `progress`. |
| 06–09 | Forward the YouTube lecture link. The photo finishes as the link arrives. | The link gets its own `item.created` row and stage events. First `item.filed` moves the photo to Econometrics → Heteroskedasticity. |
| 09–12 | Forward the PDF. | YouTube row advances through extract/classify/link and files under Econometrics → Heteroskedasticity; links connect its concepts to Probability & Statistics. PDF appears as a third queued row. |
| 12–18 | Let the three rows resolve. | PDF follows the same progress events and files. For each `item.filed`, the row settles into Course → Topic and reveals its confidence. Any weak match exposes “Not right?” and its alternatives. |
| 18–25 | Pause on the new connection. | `link.created` with `cross_course: true` raises a high-contrast “New connection” banner: Heteroskedasticity ↔ Variance · Probability & Statistics. The graph destination is highlighted for the next task. `gap.detected`/overview keeps “Week 7 is missing” visible. |
| 25–30 | Select the course and choose “Exam in 3 days.” | In A5, the exam request is sent with its selected course, three days, language, and idempotency ID. |
| 30–44 | Show the plan being assembled. | `plan.progress` moves through gathering → planning → citing. A skeleton has labeled work rather than a spinner. `plan.ready` replaces it with the returned plan. |
| 44–59 | Scan Day 1, Day 2, and Day 3; open one citation. | Each task and claim displays its `SourceRef`. The citation opens the exact PDF page, slide, paragraph, or video timestamp. |
| 59–72 | Answer one quiz question incorrectly. | The answer endpoint returns `correct: false`, cited explanation, and `moment`. The mistake state is clear and kind; it never invents a citation. |
| 72–82 | Choose “See where this was explained.” | Open the returned timestamp/source moment and make the relevant window obvious. |
| 82–90 | Close on the gap alert. | Return to the Week 7 gap: “You have lectures 1–6 and 8, but nothing from week 7.” End on the missing-coverage insight unique to the whole Brain. |

H1 implements the Inbox, global capture layer, onboarding, and projector toggle. H2 adds the Graph, its course/topic/concept panels, the shared source viewer, and the inbox review fixes. The gap action opens that course in the graph. Full Course, Exam, and Telegram workflows remain assigned to A5–A8; they are not part of H2. The canonical live timings, inputs, and backup plan are in `DEMO_SCRIPT.md` (Claude).
