/**
 * Fibonacci Brain — shared API contract between the FastAPI backend (Claude)
 * and the web app (Astra). Owner: Claude. Change requests go to
 * docs/brain/COLLAB.md → Questions.
 *
 * Conventions
 * - All ids are UUID strings; all timestamps are ISO-8601 UTC strings.
 * - Every route lives under `/api/v1/brain/...` on the Next.js origin, which
 *   proxies to the API. Use `lib/brain-api.ts` instead of calling fetch directly.
 * - Errors: HTTP status + `{ detail: string, code: BrainErrorCode }`. Show copy
 *   from `code` (localized), never the English `detail`.
 * - AI text (titles, summaries, plans, quizzes) comes back in the language
 *   the user asked for or, for filing, the language of the source material.
 * - Field names are snake_case, matching the API JSON exactly.
 */

export type UUID = string
export type IsoDateTime = string
/** Calendar date, `YYYY-MM-DD`. */
export type IsoDate = string

export type BrainLanguage = 'en-US' | 'ru-RU' | 'kk-KZ'

// ---------------------------------------------------------------------------
// Capture
// ---------------------------------------------------------------------------

/** What an item is, detected by the server. */
export type CaptureKind =
  | 'photo' // image of a slide, whiteboard, or notes (OCR)
  | 'pdf' // PDF, text by page
  | 'document' // DOCX or plain-text file
  | 'youtube' // YouTube link, transcript with timestamps
  | 'web' // any other web page, readable text
  | 'audio' // audio file or Telegram voice note, transcript with timestamps
  | 'text' // pasted or messaged text

/** Where the item came from. */
export type CaptureChannel = 'web_drop' | 'web_paste' | 'web_picker' | 'telegram' | 'seed'

/**
 * Pipeline status, in order. `filed` is terminal success, `failed` terminal failure.
 * queued → extracting → classifying → linking → filed
 */
export type ItemStatus = 'queued' | 'extracting' | 'classifying' | 'linking' | 'filed' | 'failed'

/** Why a capture failed. Localize these in the UI. */
export type CaptureFailureCode =
  | 'unsupported_type' // file type we cannot read
  | 'too_large' // over the size limit (20 MB files, 2 h media)
  | 'unreadable' // corrupt, encrypted, or no readable text/speech
  | 'fetch_failed' // link could not be downloaded
  | 'transcript_unavailable' // video has no captions and transcription failed
  | 'ai_unavailable' // model provider down and no cached result
  | 'internal'

/** Server timings per pipeline stage in milliseconds (for the demo HUD / debugging). */
export type PipelineStage = 'extract' | 'classify' | 'link' | 'total'

/** Where inside a source a passage lives. Discriminated by `kind`. */
export type SourceAnchor =
  | { kind: 'page'; page: number } // PDF/DOCX page, 1-based
  | { kind: 'slide'; slide: number | null } // photo of a slide; slide number if visible on the photo
  | { kind: 'timestamp'; start_sec: number; end_sec: number } // video/audio window
  | { kind: 'paragraph'; paragraph: number } // pasted text / text file, 1-based
  | { kind: 'section'; heading: string } // web page heading

/** Another place this item could belong, for the one-tap fix. */
export interface FilingAlternative {
  course_id: UUID | null // null = would create a new course
  course_title: string
  topic_id: UUID | null // null = would create a new topic
  topic_title: string
  confidence: number // 0..1
}

export interface BrainItem {
  id: UUID
  kind: CaptureKind
  channel: CaptureChannel
  status: ItemStatus
  /** 0..1 progress across the whole pipeline; monotonic while processing. */
  progress: number
  /** Detected title (e.g. "Lecture 6 — Heteroskedasticity") or file name until extraction finishes. */
  title: string
  /** One or two sentences, null until classified. */
  summary: string | null
  language: BrainLanguage | null
  course_id: UUID | null
  course_title: string | null
  topic_id: UUID | null
  topic_title: string | null
  /** Filing confidence 0..1, null until classified. */
  confidence: number | null
  /** True when confidence is low; show the fix control prominently. */
  needs_review: boolean
  alternatives: FilingAlternative[]
  concept_ids: UUID[]
  /** Original link for youtube/web items. */
  source_url: string | null
  youtube_id: string | null
  /** Short-lived same-origin URL; usable directly in <img src>. Null if none. */
  thumbnail_url: string | null
  /** Short-lived same-origin URL to the original photo/PDF/audio. Null for links/text. */
  media_url: string | null
  duration_sec: number | null
  page_count: number | null
  failure_code: CaptureFailureCode | null
  captured_at: IsoDateTime
  filed_at: IsoDateTime | null
  timings_ms: Partial<Record<PipelineStage, number>>
}

/** A passage of an item, used in detail views. */
export interface BrainChunk {
  id: UUID
  item_id: UUID
  ordinal: number
  anchor: SourceAnchor
  text: string
}

export interface BrainItemDetail {
  item: BrainItem
  chunks: BrainChunk[] // first 50 passages in order
  concepts: BrainConcept[]
}

/** POST /brain/captures — links and text. Files use POST /brain/captures/upload (multipart). */
export interface CaptureCreateRequest {
  /** A URL (YouTube or web) or free text. Exactly one of url/text. */
  url?: string
  text?: string
  /** Optional title for pasted text. */
  title?: string
  channel: Extract<CaptureChannel, 'web_drop' | 'web_paste' | 'web_picker'>
  /** Client-generated UUID; repeating it returns the same item (idempotent). */
  request_id: UUID
}

/** Multipart fields for POST /brain/captures/upload. */
export interface CaptureUploadFields {
  file: File // image/*, application/pdf, .docx, .txt, audio/*; ≤ 20 MB
  channel: Extract<CaptureChannel, 'web_drop' | 'web_picker'>
  request_id: UUID
}

// ---------------------------------------------------------------------------
// The brain: courses → topics → concepts, and links between concepts
// ---------------------------------------------------------------------------

export interface BrainCourse {
  id: UUID
  title: string
  /** e.g. "ECON 301" when detected; null otherwise. */
  code: string | null
  /** Stable palette slot 0..7 assigned at creation. Map to design tokens in the UI. */
  color_index: number
  created_by: 'auto' | 'user'
  item_count: number
  topic_count: number
  concept_count: number
  created_at: IsoDateTime
}

export type SequenceKind = 'week' | 'lecture' | 'chapter' | 'module'

export interface BrainTopic {
  id: UUID
  course_id: UUID
  title: string
  /** Week/lecture number when the material states one; drives ordering and gap alerts. */
  sequence: number | null
  sequence_kind: SequenceKind | null
  item_count: number
  concept_count: number
  created_at: IsoDateTime
}

export interface BrainConcept {
  id: UUID
  course_id: UUID
  topic_id: UUID | null
  name: string
  /** One sentence, grounded in the user's material. */
  summary: string
  /** How many passages mention it; use for node size. */
  mention_count: number
  created_at: IsoDateTime
}

export type LinkRelation = 'same_idea' | 'builds_on' | 'applies' | 'contrasts'

export interface ConceptLink {
  id: UUID
  source_concept_id: UUID
  target_concept_id: UUID
  /** True when the two concepts live in different courses — the signature edge. */
  cross_course: boolean
  /** 0..1. Links below the server threshold are never created. */
  strength: number
  relation: LinkRelation
  /** One sentence explaining the connection, in the user's material's language. */
  rationale: string
  method: 'embedding' | 'verified' | 'user'
  created_at: IsoDateTime
}

/** GET /brain/graph — the whole brain for the graph screen (few hundred nodes max). */
export interface BrainGraph {
  courses: BrainCourse[]
  topics: BrainTopic[]
  concepts: BrainConcept[]
  links: ConceptLink[]
  generated_at: IsoDateTime
}

/** GET /brain/concepts/{id} — side panel when a node is clicked. */
export interface ConceptDetail {
  concept: BrainConcept
  course: BrainCourse
  topic: BrainTopic | null
  /** Where this concept appears in the user's material, best first. */
  sources: SourceRef[]
  linked: Array<{ link: ConceptLink; concept: BrainConcept; course: BrainCourse }>
}

/** GET /brain/courses/{id} — course view. Topics are ordered by sequence, then creation. */
export interface CourseDetail {
  course: BrainCourse
  topics: Array<{ topic: BrainTopic; items: BrainItem[] }>
  /** Filed to this course but without a topic. */
  loose_items: BrainItem[]
  gaps: GapAlert[]
}

/** GET /brain/overview — home/inbox header. */
export interface BrainOverview {
  /** items = filed sources; processing = still being read or filed; failed = need a retry. */
  counts: { items: number; courses: number; concepts: number; cross_links: number; processing: number; failed?: number }
  recent_items: BrainItem[] // newest 20
  gaps: GapAlert[]
  telegram: TelegramStatus
  demo_mode: boolean
}

// ---------------------------------------------------------------------------
// Citations
// ---------------------------------------------------------------------------

/**
 * A citation: the exact place in the user's own material that supports a claim.
 * Every generated claim (plan task, note bullet, flashcard, quiz question) carries ≥ 1.
 */
export interface SourceRef {
  item_id: UUID
  chunk_id: UUID
  item_kind: CaptureKind
  item_title: string
  /** Course of the cited item — may differ from the plan's course (cross-course pull). */
  course_id: UUID | null
  anchor: SourceAnchor
  /** Verbatim excerpt from the passage, ≤ 280 chars. */
  quote: string
  captured_at: IsoDateTime
  /** Same-origin, short-lived; photo or page thumbnail. */
  thumbnail_url: string | null
  /** For youtube: watch URL with `t=` at anchor start. For web: page URL. Else null (use media_url). */
  open_url: string | null
  youtube_id: string | null
  media_url: string | null
}

// ---------------------------------------------------------------------------
// Gap alerts
// ---------------------------------------------------------------------------

export interface GapAlert {
  /** Stable id: `${course_id}:${sequence_kind}:${missing}`. */
  id: string
  course_id: UUID
  course_title: string
  sequence_kind: SequenceKind
  /** The missing number, e.g. 7 → "Week 7 is missing". */
  missing: number
  /** Numbers the user does have in this course, sorted. */
  present: number[]
}

// ---------------------------------------------------------------------------
// Exam mode: plan, notes, flashcards, quiz
// ---------------------------------------------------------------------------

/** POST /brain/courses/{course_id}/exam-plan */
export interface ExamPlanRequest {
  days: number // 1..14
  /** Defaults to today + days. */
  exam_date?: IsoDate
  language: BrainLanguage
  request_id: UUID // idempotency
}

export type PlanStatus = 'generating' | 'ready' | 'failed'

export interface CitedText {
  text: string
  sources: SourceRef[]
}

export type PlanTaskKind = 'read' | 'watch' | 'review' | 'flashcards' | 'quiz' | 'practice'

export interface PlanTask {
  id: string
  kind: PlanTaskKind
  title: string
  minutes: number
  topic_id: UUID | null
  sources: SourceRef[]
}

export interface PlanDay {
  day: number // 1-based
  date: IsoDate | null
  focus: string
  tasks: PlanTask[]
}

export interface PlanNote {
  id: string
  heading: string
  topic_id: UUID | null
  bullets: CitedText[]
}

export interface Flashcard {
  id: string
  front: string
  back: string
  sources: SourceRef[]
}

export type QuizOptionId = 'a' | 'b' | 'c' | 'd'

/** The correct answer is never sent before the user answers. */
export interface QuizQuestion {
  id: string
  prompt: string
  options: Array<{ id: QuizOptionId; text: string }>
  concept_ids: UUID[]
  sources: SourceRef[]
}

export interface StudyPlanContent {
  title: string
  days: PlanDay[]
  notes: PlanNote[]
  flashcards: Flashcard[]
  quiz: QuizQuestion[]
}

export interface PlanCoverage {
  item_count: number // items in the course
  cited_item_count: number // items cited somewhere in the plan
  /** Topics with no material at all (feeds the honest "not covered" note). */
  missing: GapAlert[]
}

export interface StudyPlan {
  id: UUID
  course_id: UUID
  days: number
  exam_date: IsoDate
  language: BrainLanguage
  status: PlanStatus
  failure_code: 'not_enough_material' | 'ai_unavailable' | 'internal' | null
  content: StudyPlanContent | null
  coverage: PlanCoverage | null
  created_at: IsoDateTime
}

/** POST /brain/plans/{plan_id}/quiz/{question_id}/answer */
export interface QuizAnswerRequest {
  option_id: QuizOptionId
}

/** The exact place to go back to after a mistake. */
export interface SourceMoment {
  source: SourceRef
  /** Why this moment explains the answer (one sentence, plan language). */
  reason: string
  confidence: number // 0..1
}

export interface QuizAnswerResult {
  question_id: string
  correct: boolean
  correct_option_id: QuizOptionId
  explanation: CitedText
  /** Best source moment for this question; present for wrong answers, may be present for right ones. */
  moment: SourceMoment | null
  attempt_id: UUID
}

// ---------------------------------------------------------------------------
// One-tap re-file
// ---------------------------------------------------------------------------

/** POST /brain/items/{item_id}/refile — choose an existing course/topic or name a new one. */
export interface RefileRequest {
  course_id?: UUID
  new_course_title?: string
  /** null = no topic. Omit to let the server pick the best topic in the target course. */
  topic_id?: UUID | null
  new_topic_title?: string
}

export interface RefileResult {
  item: BrainItem
  course: BrainCourse
  topic: BrainTopic | null
  /** The correction was stored and will steer future filing for this user. */
  learned: boolean
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export type SearchHit =
  | { kind: 'concept'; score: number; concept: BrainConcept }
  | { kind: 'passage'; score: number; source: SourceRef }

/** GET /brain/search?q=...&limit=20 */
export interface SearchResponse {
  query: string
  hits: SearchHit[]
}

// ---------------------------------------------------------------------------
// Telegram
// ---------------------------------------------------------------------------

export interface TelegramStatus {
  bot_configured: boolean
  bot_username: string | null
  linked: boolean
  telegram_username: string | null
  linked_at: IsoDateTime | null
}

/** POST /brain/telegram/link-code */
export interface TelegramLinkCode {
  /** Six digits; the user sends `/start 123456` or opens deep_link. */
  code: string
  /** `https://t.me/<bot>?start=<code>` — render as QR. */
  deep_link: string
  expires_at: IsoDateTime
  bot_username: string
}

// ---------------------------------------------------------------------------
// Demo tools — only while DEMO_MODE is on (overview.demo_mode); the API answers 404 otherwise
// ---------------------------------------------------------------------------

/** POST /brain/demo/hero → 202. The three demo inputs (slide photo, lecture video, PDF) go
 *  through the normal capture pipeline; their progress arrives over events like any capture. */
export interface DemoHeroResponse {
  items: BrainItem[]
}

/** POST /brain/demo/reset → 200. Demo student only: back to the starting Brain. Telegram stays linked. */
export interface DemoResetResponse {
  courses: number
  items: number
}

// ---------------------------------------------------------------------------
// Realtime events — GET /brain/events (Server-Sent Events, via subscribeBrainEvents)
// ---------------------------------------------------------------------------

interface EventBase {
  /** Monotonic per user; used for resume. */
  id: string
  at: IsoDateTime
}

export type BrainEvent =
  | (EventBase & { type: 'item.created'; item: BrainItem })
  | (EventBase & { type: 'item.progress'; item_id: UUID; status: ItemStatus; progress: number; title: string })
  | (EventBase & {
      type: 'item.filed'
      item: BrainItem
      course: BrainCourse
      topic: BrainTopic | null
      new_course: boolean
      new_topic: boolean
      concepts: BrainConcept[]
    })
  | (EventBase & { type: 'item.failed'; item_id: UUID; failure_code: CaptureFailureCode })
  | (EventBase & { type: 'item.refiled'; item: BrainItem })
  | (EventBase & { type: 'item.deleted'; item_id: UUID })
  | (EventBase & {
      type: 'link.created'
      link: ConceptLink
      source: BrainConcept
      target: BrainConcept
      /** Courses of the two concepts (same object twice when the link is within one course). */
      source_course: BrainCourse
      target_course: BrainCourse
    })
  | (EventBase & { type: 'gap.detected'; gap: GapAlert })
  | (EventBase & { type: 'gap.resolved'; gap_id: string })
  | (EventBase & { type: 'plan.progress'; plan_id: UUID; stage: 'gathering' | 'planning' | 'citing' })
  | (EventBase & { type: 'plan.ready'; plan: StudyPlan })
  | (EventBase & { type: 'plan.failed'; plan_id: UUID; failure_code: NonNullable<StudyPlan['failure_code']> })
  | (EventBase & { type: 'telegram.linked'; telegram: TelegramStatus })

export type BrainEventType = BrainEvent['type']

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export type BrainErrorCode =
  | 'unauthorized'
  | 'not_found'
  | 'invalid_input'
  | 'unsupported_type'
  | 'too_large'
  | 'rate_limited'
  | 'conflict'
  | 'not_enough_material'
  | 'telegram_not_configured'
  | 'unavailable'
  | 'internal'

export interface BrainErrorBody {
  detail: string
  code: BrainErrorCode
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

/** GET /brain/items?status=&course_id=&limit=&cursor= */
export interface ItemPage {
  items: BrainItem[]
  next_cursor: string | null
}
