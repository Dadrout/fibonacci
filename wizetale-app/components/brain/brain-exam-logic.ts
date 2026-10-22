/*
 * Exam mode state and formatting (board rows A5, A6). Pure: no runtime imports, so
 * scripts/brain-ui-exam.test.mjs can load it with `node --experimental-strip-types`.
 */
import type { BrainEvent, BrainLanguage, GapAlert, PlanDay, PlanTaskKind, QuizAnswerResult, QuizOptionId, SequenceKind, SourceRef, StudyPlan } from '@/lib/brain-types'

export type UiLanguage = 'en' | 'ru' | 'kk'

export const MIN_DAYS = 1
export const MAX_DAYS = 14
export const DEFAULT_DAYS = 3

/** Endonyms: each language is named in itself, so they need no translation. */
export const PLAN_LANGUAGES: ReadonlyArray<{ id: BrainLanguage; label: string }> = [
  { id: 'en-US', label: 'English' },
  { id: 'ru-RU', label: 'Русский' },
  { id: 'kk-KZ', label: 'Қазақша' },
]

export function planLanguageFor(language: string): BrainLanguage {
  if (language === 'ru') return 'ru-RU'
  if (language === 'kk') return 'kk-KZ'
  return 'en-US'
}

export function clampDays(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_DAYS
  return Math.min(MAX_DAYS, Math.max(MIN_DAYS, Math.round(value)))
}

/** Parse what the student typed; empty or invalid input keeps the previous value. */
export function parseDays(text: string, previous: number): number {
  const value = Number.parseInt(text, 10)
  return Number.isNaN(value) ? previous : clampDays(value)
}

const pad = (value: number) => String(value).padStart(2, '0')

/** Local calendar date `days` from now, as YYYY-MM-DD. */
export function examDateFor(days: number, now: Date = new Date()): string {
  const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + days)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** "Wed, Oct 21" for an ISO calendar date, independent of the viewer's time zone. */
export function formatPlanDate(isoDate: string | null, locale: string, weekday = true): string {
  if (!isoDate) return ''
  const date = new Date(`${isoDate.slice(0, 10)}T00:00:00Z`)
  if (Number.isNaN(date.valueOf())) return ''
  return new Intl.DateTimeFormat(locale, { ...(weekday ? { weekday: 'short' } : {}), month: 'short', day: 'numeric', timeZone: 'UTC' }).format(date)
}

export function formatCreatedAt(isoDateTime: string, locale: string): string {
  const date = new Date(isoDateTime)
  if (Number.isNaN(date.valueOf())) return ''
  return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

export function newRequestId(): string {
  const crypto = globalThis.crypto
  if (crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    return (ch === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

// ---------------------------------------------------------------------------
// Generation progress
// ---------------------------------------------------------------------------

export const PLAN_STAGES = ['gathering', 'planning', 'citing'] as const
export type PlanStage = (typeof PLAN_STAGES)[number]

export const STAGE_LABEL: Record<PlanStage, string> = {
  gathering: 'Gathering your sources',
  planning: 'Planning the days',
  citing: 'Citing every line',
}

/** Stages only move forward: a replayed or late event never rewinds the rail. */
export function advanceStage(current: PlanStage | null, next: PlanStage): PlanStage {
  if (!current) return next
  return PLAN_STAGES.indexOf(next) > PLAN_STAGES.indexOf(current) ? next : current
}

/** The first stage is active as soon as the request is accepted. */
export function activeStageIndex(stage: PlanStage | null): number {
  return stage ? PLAN_STAGES.indexOf(stage) : 0
}

export function stageProgress(stage: PlanStage | null): number {
  return [0.18, 0.5, 0.82][activeStageIndex(stage)]
}

// ---------------------------------------------------------------------------
// Failures
// ---------------------------------------------------------------------------

export type PlanFailure = NonNullable<StudyPlan['failure_code']> | 'network' | 'rate_limited' | 'not_found'

export const FAILURE_COPY: Record<PlanFailure, { title: string; body: string }> = {
  not_enough_material: { title: 'There is not enough material for a plan yet.', body: 'Add a few more sources to this course — slides, notes, or a lecture video — then try again.' },
  ai_unavailable: { title: 'The study assistant is busy right now.', body: 'Your sources are safe. Try again in a moment.' },
  internal: { title: 'Something went wrong while building your plan.', body: 'Your sources are safe. Try again.' },
  network: { title: 'Fibonacci could not be reached.', body: 'Check your connection and try again.' },
  rate_limited: { title: 'Too many requests at once.', body: 'Wait a few seconds and try again.' },
  not_found: { title: 'This plan could not be found.', body: 'Choose a course and build a new plan.' },
}

/** Map a thrown BrainApiError (or anything else) to localized failure copy. */
export function failureFromError(error: unknown): PlanFailure {
  const code = (error as { code?: unknown } | null)?.code
  if (code === 'not_enough_material') return 'not_enough_material'
  if (code === 'rate_limited') return 'rate_limited'
  if (code === 'not_found') return 'not_found'
  if (code === 'unavailable') return 'network'
  if (error instanceof TypeError) return 'network'
  return 'internal'
}

/** Polling tolerates brief network blips; other errors stop it at once. */
export function shouldStopPolling(failure: PlanFailure, consecutiveFailures: number): boolean {
  return failure !== 'network' || consecutiveFailures >= 4
}

// ---------------------------------------------------------------------------
// Exam state machine
// ---------------------------------------------------------------------------

export type PlanParams = { courseId: string; days: number; language: BrainLanguage }
/** create = repeat the same idempotent request; poll = keep waiting for this plan; restart = new request. */
export type RetryKind = 'create' | 'poll' | 'restart'

export type ExamView =
  | { phase: 'setup' }
  | { phase: 'restoring'; planId: string }
  | { phase: 'generating'; request: PlanParams; requestId: string; planId: string | null; stage: PlanStage | null }
  | { phase: 'ready'; plan: StudyPlan }
  | { phase: 'failed'; failure: PlanFailure; retry: RetryKind; request: PlanParams | null; requestId: string | null; planId: string | null; stage: PlanStage | null }

export type ExamState = { view: ExamView; early: PlanEvent[] }

export type PlanEvent = Extract<BrainEvent, { type: 'plan.progress' | 'plan.ready' | 'plan.failed' }>

export type ExamAction =
  | { type: 'start'; request: PlanParams; requestId: string }
  | { type: 'created'; requestId: string; plan: StudyPlan }
  | { type: 'polled'; plan: StudyPlan }
  | { type: 'event'; event: BrainEvent }
  | { type: 'error'; failure: PlanFailure; retry: RetryKind; requestId?: string; planId?: string }
  | { type: 'resume'; planId: string }
  | { type: 'restore'; planId: string }
  | { type: 'open'; plan: StudyPlan }
  | { type: 'reset' }

export const initialExamState: ExamState = { view: { phase: 'setup' }, early: [] }

export function isPlanEvent(event: BrainEvent): event is PlanEvent {
  return event.type === 'plan.progress' || event.type === 'plan.ready' || event.type === 'plan.failed'
}

function planEventId(event: PlanEvent): string {
  return event.type === 'plan.ready' ? event.plan.id : event.plan_id
}

function paramsOf(plan: StudyPlan): PlanParams {
  return { courseId: plan.course_id, days: plan.days, language: plan.language }
}

/** The view a plan snapshot belongs in (also used to reopen an earlier plan). */
export function viewForPlan(plan: StudyPlan, stage: PlanStage | null = null, requestId: string | null = null): ExamView {
  if (plan.status === 'ready') {
    return plan.content
      ? { phase: 'ready', plan }
      : { phase: 'failed', failure: 'internal', retry: 'restart', request: paramsOf(plan), requestId: null, planId: plan.id, stage }
  }
  if (plan.status === 'failed') {
    return { phase: 'failed', failure: plan.failure_code ?? 'internal', retry: 'restart', request: paramsOf(plan), requestId: null, planId: plan.id, stage }
  }
  return { phase: 'generating', request: paramsOf(plan), requestId: requestId ?? plan.id, planId: plan.id, stage }
}

function applyEvent(view: Extract<ExamView, { phase: 'generating' }>, event: PlanEvent): ExamView {
  if (event.type === 'plan.progress') return { ...view, stage: advanceStage(view.stage, event.stage) }
  if (event.type === 'plan.ready') return viewForPlan(event.plan, view.stage, view.requestId)
  return { phase: 'failed', failure: event.failure_code, retry: 'restart', request: view.request, requestId: null, planId: view.planId, stage: view.stage }
}

export function examReducer(state: ExamState, action: ExamAction): ExamState {
  const { view } = state
  switch (action.type) {
    case 'start':
      return { view: { phase: 'generating', request: action.request, requestId: action.requestId, planId: null, stage: null }, early: [] }
    case 'created': {
      if (view.phase !== 'generating' || view.requestId !== action.requestId) return state
      let next: ExamView = viewForPlan(action.plan, view.stage, view.requestId)
      if (next.phase === 'generating') next = { ...next, request: view.request }
      // Events that raced ahead of the POST response.
      for (const event of state.early) {
        if (next.phase !== 'generating') break
        if (planEventId(event) === action.plan.id) next = applyEvent(next, event)
      }
      return { view: next, early: [] }
    }
    case 'polled': {
      if (view.phase === 'restoring' && view.planId === action.plan.id) return { view: viewForPlan(action.plan), early: [] }
      if (view.phase !== 'generating' || view.planId !== action.plan.id || action.plan.status === 'generating') return state
      return { ...state, view: viewForPlan(action.plan, view.stage, view.requestId) }
    }
    case 'event': {
      const event = action.event
      if (view.phase !== 'generating' || !isPlanEvent(event)) return state
      if (view.planId === null) return { ...state, early: [...state.early, event].slice(-30) }
      if (planEventId(event) !== view.planId) return state
      return { ...state, view: applyEvent(view, event) }
    }
    case 'error': {
      if (view.phase === 'restoring') return initialExamState
      if (view.phase !== 'generating') return state
      if (action.requestId && action.requestId !== view.requestId) return state
      if (action.planId && action.planId !== view.planId) return state
      return { ...state, view: { phase: 'failed', failure: action.failure, retry: action.retry, request: view.request, requestId: view.requestId, planId: view.planId, stage: view.stage } }
    }
    case 'resume': {
      if (view.phase !== 'failed' || view.planId !== action.planId || !view.request) return state
      return { ...state, view: { phase: 'generating', request: view.request, requestId: view.requestId ?? action.planId, planId: action.planId, stage: view.stage } }
    }
    case 'restore':
      return { view: { phase: 'restoring', planId: action.planId }, early: [] }
    case 'open':
      return { view: viewForPlan(action.plan), early: [] }
    case 'reset':
      return initialExamState
  }
}

// ---------------------------------------------------------------------------
// Plan content
// ---------------------------------------------------------------------------

export const TASK_KIND_LABEL: Record<PlanTaskKind, string> = {
  read: 'Read', watch: 'Watch', review: 'Recap', flashcards: 'Flashcards', quiz: 'Quiz', practice: 'Practice',
}

export const MISSING_LABEL: Record<SequenceKind, string> = {
  week: 'Week {n} is missing', lecture: 'Lecture {n} is missing', chapter: 'Chapter {n} is missing', module: 'Module {n} is missing',
}

export function dayMinutes(day: PlanDay): number {
  return day.tasks.reduce((sum, task) => sum + Math.max(0, task.minutes || 0), 0)
}

/** One chip per passage, in the order the plan cites them. */
export function uniqueSources(sources: SourceRef[] | null | undefined): SourceRef[] {
  const seen = new Set<string>()
  return (sources ?? []).filter((source) => {
    const key = `${source.item_id}:${source.chunk_id}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

/** Missing material, one entry per gap, in course order. */
export function coverageGaps(gaps: GapAlert[] | null | undefined): GapAlert[] {
  const byId = new Map<string, GapAlert>()
  for (const gap of gaps ?? []) byId.set(gap.id, gap)
  return [...byId.values()].sort((a, b) => a.sequence_kind.localeCompare(b.sequence_kind) || a.missing - b.missing)
}

export function sortPlansNewest(plans: StudyPlan[]): StudyPlan[] {
  return [...plans].sort((a, b) => b.created_at.localeCompare(a.created_at))
}

// ---------------------------------------------------------------------------
// Quiz
// ---------------------------------------------------------------------------

export type AnswerState =
  | { status: 'checking'; selected: QuizOptionId }
  | { status: 'error'; selected: QuizOptionId }
  | { status: 'answered'; selected: QuizOptionId; result: QuizAnswerResult }

export type OptionStatus = 'idle' | 'checking' | 'correct' | 'wrong' | 'muted'

/** Correct and wrong options also carry a text label in the UI, never color alone. */
export function optionStatus(optionId: QuizOptionId, answer: AnswerState | undefined): OptionStatus {
  if (!answer || answer.status === 'error') return 'idle'
  if (answer.status === 'checking') return optionId === answer.selected ? 'checking' : 'muted'
  if (optionId === answer.result.correct_option_id) return 'correct'
  if (optionId === answer.selected) return 'wrong'
  return 'muted'
}

export function quizScore(answers: Record<string, AnswerState>): { answered: number; correct: number } {
  let answered = 0
  let correct = 0
  for (const answer of Object.values(answers)) {
    if (answer.status !== 'answered') continue
    answered += 1
    if (answer.result.correct) correct += 1
  }
  return { answered, correct }
}

export function optionLetter(optionId: QuizOptionId): string {
  return optionId.toUpperCase()
}
