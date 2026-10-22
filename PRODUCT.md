# Fibonacci

Fibonacci is a second brain for students that builds itself. Students send anything they study with (a slide photo, a lecture link, a PDF, a web page, a voice note, pasted notes) through the web app, drag-and-drop, paste, or the Telegram bot. Fibonacci reads it, files it as Course → Topic → Concept with a confidence score, and links concepts across courses into one knowledge graph.

From that brain, one tap ("Exam in 3 days") builds a day-by-day plan, notes, flashcards and a quiz. Every generated line cites its source (page, slide photo, or video timestamp). A wrong quiz answer opens the exact moment in the student's own material that explains it, and gap alerts show what is missing ("Week 7 is missing").

The Brain is one calm home screen: a capture bar, what is arriving now, and the student's courses (as cards or as a map), with drill-down to a course and its exam. The interface and generated material work in English, Russian and Kazakh; the two languages can differ.

Principles:

- **Zero-effort capture.** No "upload and choose a folder" step.
- **Honest output.** Every AI result shows its sources; uncertainty is shown, not hidden.
- **Private by default.** Each student's material is visible only to them, enforced in the database.
- **Works on stage.** Every AI call has a timeout, a retry, and a recorded fallback, so the demo runs on bad Wi-Fi.

Product and design details: `docs/brain/DESIGN_BRAIN.md`. Team board and decisions: `docs/brain/COLLAB.md`. Demo: `docs/brain/DEMO_SCRIPT.md`.
