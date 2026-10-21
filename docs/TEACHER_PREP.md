# Teacher preparation setup

## Database and services

1. Apply `supabase/schema.sql`, then `supabase/teacher_prep.sql` and `supabase/relationship_indexes.sql` through your reviewed Supabase SQL workflow. The additive teacher file creates private teacher profiles, lessons and resources; enables owner-only reads; reserves writes for the validated API; and allows Kazakh story drafts. Back up the database before production schema changes.
2. Configure the API's existing Supabase service credential, Gemini provider and Redis. Teacher generation uses the existing Gemini structured provider and requires no new AI account.
3. For Kazakh story audio, set `ELEVENLABS_API_KEY`, `ELEVENLABS_KK_FEMALE_VOICE_ID`, and `ELEVENLABS_KK_MALE_VOICE_ID` in the API and worker environment. Configure voices available to your account. English/Russian continue through the configured default narration provider. Restart API/worker after configuration changes. Missing Kazakh credentials fail narration with a configuration error.
4. Configure the frontend public Supabase URL/key and server-only `BACKEND_API_URL`. No service credential goes to the browser.

## Teacher workflow

Choose teacher at signup, or open Teacher prep from an existing account and enable teacher mode. This is a self-selected role; authorization uses the server's persisted teacher profile. Create a private lesson with a subject, K–12 grade, topic and output language. Objectives and pasted reference text are optional. Generate one resource at a time: objectives, 45-minute plan, 10-question quiz, 20-point test with key/rubric, 12 flashcards, worksheet/activity, 3-question exit ticket, or 5-task homework.

For illustrated topic videos, apply `supabase/teacher_video_renders.sql` after `teacher_prep.sql` and `study_tools.sql`, then deploy the API and worker before enabling the lesson editor. Teachers choose a 3, 4, or 5 minute target and narration voice, review and edit the grade-tailored script, then render it as a private video resource saved with that lesson. Topic video generation uses the lesson topic, subject, grade and language; attached documents and pasted reference text are not used. Existing presentation-to-video remains available separately. See `supabase/tests/teacher_video_renders_rls.test.sql` for owner access and account deletion checks.

Review the AI draft before classroom use. Edit and save all structured fields. Edits can change the default item counts. Lesson-context edits affect future generation; saved resources keep the original context snapshot. Simultaneous saves return a conflict rather than overwriting newer content. Print a saved student or teacher copy and choose the browser's Save as PDF option. Student copies omit teacher notes and answer keys; flashcard backs are study content and remain visible. Page length depends on content, edits, printer paper size, and browser settings.

Lessons are deleted with their resources. Deleting the Supabase Auth account cascades through teacher records. Pasted references are private stored lesson data and are sent to the configured generation provider when a resource is requested. Do not paste learner personal information. This feature does not certify curriculum alignment or factual correctness.

## Release checks requiring configured services

- Run `supabase/teacher_prep_test.sql` as a staging database administrator; it rolls back fixtures and checks owner isolation, client grants, cross-owner constraints and deletion cascades. Also verify RLS policies in staging; authenticated users may read only their own rows and cannot directly write teacher tables. Verify anonymous access fails and an owner cannot read another owner's lessons/resources.
- With two test teacher accounts, create, reload, edit, generate each resource kind, and confirm cross-account requests fail. Repeat one request UUID and confirm one generation only. Submit two saves at the same revision; one must return 409.
- Exercise generation failure and account deletion during generation; no resource may survive deletion. Confirm deleting a test account removes its teacher records.
- Inspect student/teacher PDFs in all three languages and on A4/Letter. Check keys and rubrics only appear in teacher copies.
- Generate and play a Kazakh story with each configured voice. Exercise missing provider credentials in staging and confirm no false success. Sign-in, existing story generation/playback/quiz and account deletion remain release gates.

Local automated tests use simulated provider/persistence responses and do not replace these staging checks. Deployment, credential rotation, legal/child-safety decisions, and Git history cleanup remain owner launch gates.

## Private document library and source-based generation

Apply `supabase/teacher_documents.sql` after the teacher schema. It creates the private `teacher-documents` bucket, owner-readable document/passages tables, searchable English/Russian/Kazakh passages, guarded publication, revision-checked attachments, and resource provenance. Writes and original downloads go through the authenticated API; direct browser storage access and ingestion/search RPC execution are denied. Upgrade the API/worker and restart both before rolling out the frontend source library. Local Supabase migrations have been applied; production application deployment remains separate.

Open **My sources** to upload a PDF, DOCX, UTF-8 TXT, or paste text. Wait for Ready, then select up to five sources in a lesson and save the selection. Each account has 50 source slots; pending removals retain a slot until storage cleanup succeeds. The upload limit is 10 MB, PDF limit 200 pages, and extracted text limit 200,000 characters. PDFs must contain searchable text; encrypted PDFs and malformed/empty documents fail with a message. OCR is not included. Retries use a new attempt token, and late jobs cannot recreate deleted sources. A failed deletion stays visible as Removal pending; use Retry removal to complete cleanup.

Selected sources enable strict source-based generation. Saved topic/objectives become a keyword query (English/Russian stemming, Kazakh simple tokens). Retrieval is limited to selected ready documents, eight passages and 16,000 characters. Pasted lesson text is separately identified within that context. No matches, inadequate model coverage, or invented passage identifiers fail explicitly. Documents are untrusted reference data, and embedded instructions must not change generation rules. Without selected documents, the previous lesson generation flow remains available.

PDF references retain page numbers. DOCX/TXT use paragraph or table-row locations, without invented pagination. Saved resources include source identifiers, titles and locations; references appear in the teacher view and teacher printout, separated from student questions and answers. Deleting a source immediately stops retrieval and detaches it from lessons, then removes storage and passages. Generated resources stay saved and show Source removed. Account deletion stops ingestion and removes original files before deleting Auth records.

### Document release verification

Run `supabase/teacher_documents_test.sql` in a reviewed database session; it rolls back fictional fixtures and checks publication tokens, EN/RU/KK retrieval, selected-source filtering, RLS, attachment conflicts, quota, deletion exclusion and account cascades. API tests cover extraction/locations, scans, malformed documents, limits, bounded retrieval, citation validation, guarded workers, multipart limits and account cleanup. Frontend checks cover localization, teacher-only references, pagination state and unsaved source selection.

Use fictional, nonpersonal teaching content for live Gemini free-tier checks. References help a teacher review the draft; they do not prove correctness. Before public release, also verify account switching in an authenticated browser, printed A4/Letter output, deployment ordering, service monitoring, and the existing sign-in/story/playback/quiz gates. Privacy, retention decisions, credential rotation and Gemini under-18 restrictions remain owner launch gates.

For a repeatable live local check, start the three services and run `wizetale-api/.venv/bin/python wizetale-api/scripts/verify_teacher_sources.py` from the repository root. It creates two fictional confirmed accounts, consumes quiz/flashcard text generations, checks the upload-to-delete workflow, and removes its Auth/storage fixtures in a finally block. It never uses learner records. Inspect its final cleanup result before repeating after a service outage.
