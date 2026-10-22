'use client'

/*
 * Exam mode + mistake → source moment (board rows A5, A6).
 * Setup (course, days, language, earlier plans) → generating (plan.progress events with a
 * 2-second polling fallback) → ready plan (brain-exam-plan.tsx) or a localized failure.
 * Pure state and formatting live in brain-exam-logic.ts.
 */
import { useCallback, useEffect, useReducer, useRef, useState, type FormEvent } from 'react'
import { BookOpen, Check, ChevronRight, FilePlus2, GraduationCap, Minus, Plus, RefreshCw, TriangleAlert } from 'lucide-react'
import { useBrainEvents } from '@/hooks/use-brain-api'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainCourse, BrainGraph, BrainLanguage, StudyPlan } from '@/lib/brain-types'
import './brain-exam.css'
import { BrainExamPlan } from './brain-exam-plan'
import {
  DEFAULT_DAYS, FAILURE_COPY, MAX_DAYS, MIN_DAYS, PLAN_LANGUAGES, PLAN_STAGES, STAGE_LABEL,
  activeStageIndex, clampDays, examDateFor, examReducer, failureFromError, formatCreatedAt, formatPlanDate,
  initialExamState, newRequestId, parseDays, planLanguageFor, shouldStopPolling, sortPlansNewest, stageProgress,
  type ExamView, type PlanParams, type PlanStage,
} from './brain-exam-logic'

export type BrainExamProps = {
  api: BrainApi
  graph: BrainGraph | null
  /** Course chosen from the course view's "Exam in N days" button (null = let the student choose). */
  courseId: string | null
  presentation: boolean
}

const LAST_PLAN_KEY = 'fibonacci:brain:exam:last-plan:v1'
const POLL_MS = 2000

function readLastPlan(): string | null {
  try { return window.sessionStorage.getItem(LAST_PLAN_KEY) } catch { return null }
}
function writeLastPlan(planId: string | null) {
  try {
    if (planId) window.sessionStorage.setItem(LAST_PLAN_KEY, planId)
    else window.sessionStorage.removeItem(LAST_PLAN_KEY)
  } catch { /* Restoring the last plan is a convenience only. */ }
}

function openPicker() {
  window.dispatchEvent(new Event('brain:open-picker'))
}

export function BrainExam({ api, graph, courseId, presentation }: BrainExamProps) {
  const [state, dispatch] = useReducer(examReducer, initialExamState)
  const { view } = state
  const courses = useCourses(api, graph)

  // Reopen the plan from earlier in this session when the Exam tab is opened directly.
  useEffect(() => {
    if (courseId) return
    const last = readLastPlan()
    if (!last) return
    dispatch({ type: 'restore', planId: last })
    let alive = true
    api.plan(last).then(
      plan => { if (alive) dispatch({ type: 'polled', plan }) },
      () => { if (alive) { writeLastPlan(null); dispatch({ type: 'reset' }) } },
    )
    return () => { alive = false }
    // Only on mount: later plans are chosen in this view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const activePlanId = view.phase === 'generating' ? view.planId : view.phase === 'ready' ? view.plan.id : null
  useEffect(() => { if (activePlanId) writeLastPlan(activePlanId) }, [activePlanId])

  useBrainEvents(useCallback(event => dispatch({ type: 'event', event }), []))

  // Polling fallback: events can be missed while the stream reconnects.
  const pollId = view.phase === 'generating' ? view.planId : null
  useEffect(() => {
    if (!pollId) return
    let alive = true
    let inFlight = false
    let failures = 0
    const timer = window.setInterval(() => {
      if (inFlight) return
      inFlight = true
      api.plan(pollId).then(
        plan => { failures = 0; if (alive) dispatch({ type: 'polled', plan }) },
        error => {
          failures += 1
          const failure = failureFromError(error)
          if (alive && shouldStopPolling(failure, failures)) dispatch({ type: 'error', failure, retry: 'poll', planId: pollId })
        },
      ).finally(() => { inFlight = false })
    }, POLL_MS)
    return () => { alive = false; window.clearInterval(timer) }
  }, [api, pollId])

  const create = useCallback(async (request: PlanParams, requestId: string) => {
    dispatch({ type: 'start', request, requestId })
    try {
      const plan = await api.createExamPlan(request.courseId, { days: request.days, language: request.language, request_id: requestId })
      dispatch({ type: 'created', requestId, plan })
    } catch (error) {
      dispatch({ type: 'error', failure: failureFromError(error), retry: 'create', requestId })
    }
  }, [api])

  const reset = useCallback(() => { writeLastPlan(null); dispatch({ type: 'reset' }) }, [])

  const retry = useCallback((failed: Extract<ExamView, { phase: 'failed' }>) => {
    if (failed.retry === 'poll' && failed.planId) dispatch({ type: 'resume', planId: failed.planId })
    else if (failed.request) void create(failed.request, failed.retry === 'create' && failed.requestId ? failed.requestId : newRequestId())
    else reset()
  }, [create, reset])

  const courseTitle = (id: string | null | undefined) => courses.list?.find(course => course.id === id)?.title ?? ''

  return <section className={`brain-exam${presentation ? ' is-presentation' : ''}`} aria-labelledby="brain-exam-title">
    {view.phase === 'setup' ? <ExamSetup api={api} courses={courses} initialCourseId={courseId} onStart={request => void create(request, newRequestId())} onOpen={plan => dispatch({ type: 'open', plan })} />
      : view.phase === 'restoring' ? <ExamProgress title="" stage={null} restoring />
      : view.phase === 'generating' ? <ExamProgress title={courseTitle(view.request.courseId)} stage={view.stage} />
      : view.phase === 'ready' ? <BrainExamPlan api={api} plan={view.plan} course={courses.list?.find(course => course.id === view.plan.course_id) ?? null} presentation={presentation} onNewPlan={reset} />
      : <ExamFailure view={view} courseTitle={courseTitle(view.request?.courseId)} onRetry={() => retry(view)} onBack={reset} />}
  </section>
}

type CourseState = { list: BrainCourse[] | null; error: boolean; reload: () => void }

/** Courses come from the workspace graph; fetch them here only if the graph is unavailable. */
function useCourses(api: BrainApi, graph: BrainGraph | null): CourseState {
  const [own, setOwn] = useState<BrainCourse[] | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (graph) return
    let alive = true
    setError(false)
    api.graph().then(result => { if (alive) setOwn(result.courses) }, () => { if (alive) setError(true) })
    return () => { alive = false }
  }, [api, graph, attempt])
  return { list: graph?.courses ?? own, error: !graph && !own && error, reload: () => setAttempt(value => value + 1) }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

function ExamSetup({ api, courses, initialCourseId, onStart, onOpen }: {
  api: BrainApi; courses: CourseState; initialCourseId: string | null; onStart: (request: PlanParams) => void; onOpen: (plan: StudyPlan) => void
}) {
  const c = useCopy()
  const { language } = useLanguage()
  const [selected, setSelected] = useState<string | null>(initialCourseId)
  const [days, setDays] = useState(DEFAULT_DAYS)
  const [daysText, setDaysText] = useState(String(DEFAULT_DAYS))
  const [chosenLanguage, setChosenLanguage] = useState<BrainLanguage | null>(null)
  const planLanguage = chosenLanguage ?? planLanguageFor(language)
  const list = courses.list

  useEffect(() => {
    if (!list?.length) return
    setSelected(current => current && list.some(course => course.id === current) ? current
      : initialCourseId && list.some(course => course.id === initialCourseId) ? initialCourseId : list[0].id)
  }, [list, initialCourseId])

  const setDayCount = (value: number) => { const next = clampDays(value); setDays(next); setDaysText(String(next)) }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (selected) onStart({ courseId: selected, days, language: planLanguage })
  }

  const heading = <div className="brain-inbox-heading">
    <div>
      <p className="brain-section-kicker">{c('Built from your sources')}</p>
      <h2 id="brain-exam-title">{c('Exam mode')}</h2>
      <p>{c('Choose a course and how many days you have. Fibonacci builds a day-by-day plan, notes, flashcards, and a quiz — every line cited to your own material.')}</p>
    </div>
  </div>

  if (courses.error) {
    return <>{heading}<div className="brain-load-error" role="alert"><TriangleAlert size={24} aria-hidden="true" />
      <div><strong>{c('Your courses could not load.')}</strong><p>{c('Check your connection and try again.')}</p></div>
      <button type="button" className="brain-secondary-button" onClick={courses.reload}>{c('Try again')}</button>
    </div></>
  }
  if (!list) {
    return <>{heading}<div className="brain-source-skeletons" aria-busy="true" aria-label={c('Loading courses')}>
      {[0, 1].map(n => <div className="brain-source-skeleton" key={n}><span /><div><i /><i /><i /></div></div>)}
    </div></>
  }
  if (list.length === 0) {
    return <>{heading}<div className="brain-exam-empty">
      <BookOpen size={26} aria-hidden="true" />
      <div><strong>{c('Add some material first.')}</strong><p>{c('Exam plans are built only from your own sources. Send a lecture photo, PDF, or link and Fibonacci files it into a course.')}</p></div>
      <button type="button" className="brain-primary-button" onClick={openPicker}><FilePlus2 size={18} aria-hidden="true" />{c('Add a file')}</button>
    </div></>
  }

  const examDate = formatPlanDate(examDateFor(days), language)
  return <>
    {heading}
    <form className="brain-exam-setup" onSubmit={submit}>
      <fieldset className="brain-exam-field">
        <legend>{c('Course')}</legend>
        <div className="brain-exam-courses">
          {list.map(course => <label key={course.id} className="brain-exam-course" data-course-color={course.color_index}>
            <input type="radio" name="brain-exam-course" value={course.id} checked={selected === course.id} onChange={() => setSelected(course.id)} />
            <span className="brain-exam-course-swatch" aria-hidden="true" />
            <span className="brain-exam-course-copy">
              <strong>{course.title}</strong>
              <span>{course.code ? `${course.code} · ` : ''}{c('{n} sources').replace('{n}', String(course.item_count))} · {c('{n} topics').replace('{n}', String(course.topic_count))}</span>
            </span>
            <Check className="brain-exam-course-check" size={20} aria-hidden="true" />
          </label>)}
        </div>
      </fieldset>

      <div className="brain-exam-setup-row">
        <div className="brain-exam-field">
          <label htmlFor="brain-exam-days">{c('Days until the exam')}</label>
          <div className="brain-exam-days">
            <button type="button" className="brain-icon-button" aria-label={c('Fewer days')} disabled={days <= MIN_DAYS} onClick={() => setDayCount(days - 1)}><Minus size={18} aria-hidden="true" /></button>
            <input id="brain-exam-days" type="number" inputMode="numeric" min={MIN_DAYS} max={MAX_DAYS} step={1} value={daysText} aria-describedby="brain-exam-date"
              onChange={event => { setDaysText(event.target.value); setDays(current => parseDays(event.target.value, current)) }}
              onBlur={() => setDaysText(String(days))} />
            <button type="button" className="brain-icon-button" aria-label={c('More days')} disabled={days >= MAX_DAYS} onClick={() => setDayCount(days + 1)}><Plus size={18} aria-hidden="true" /></button>
          </div>
          <p id="brain-exam-date" className="brain-exam-hint">{c('Exam on {date} · 1–14 days').replace('{date}', examDate)}</p>
        </div>
        <div className="brain-exam-field">
          <label htmlFor="brain-exam-language">{c('Plan language')}</label>
          <select id="brain-exam-language" className="brain-exam-select" value={planLanguage} onChange={event => setChosenLanguage(event.target.value as BrainLanguage)}>
            {PLAN_LANGUAGES.map(option => <option key={option.id} value={option.id} lang={option.id}>{option.label}</option>)}
          </select>
          <p className="brain-exam-hint">{c('Notes, flashcards, and the quiz are written in this language.')}</p>
        </div>
      </div>

      <button type="submit" className="brain-primary-button brain-exam-build" disabled={!selected}>
        <GraduationCap size={22} aria-hidden="true" />{c('Build my exam plan')}
      </button>
    </form>
    {selected && <EarlierPlans key={selected} api={api} courseId={selected} onOpen={onOpen} />}
  </>
}

function EarlierPlans({ api, courseId, onOpen }: { api: BrainApi; courseId: string; onOpen: (plan: StudyPlan) => void }) {
  const c = useCopy()
  const { language } = useLanguage()
  const [plans, setPlans] = useState<StudyPlan[] | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    setError(false)
    api.coursePlans(courseId).then(result => { if (alive) setPlans(sortPlansNewest(result).slice(0, 6)) }, () => { if (alive) setError(true) })
    return () => { alive = false }
  }, [api, courseId, attempt])

  // Secondary content: stay quiet while loading and when there is nothing to reopen.
  if (!error && !plans?.length) return null
  return <section className="brain-exam-earlier" aria-labelledby="brain-exam-earlier-title">
    <h3 id="brain-exam-earlier-title">{c('Earlier plans for this course')}</h3>
    {error ? <p className="brain-exam-inline-error" role="alert"><TriangleAlert size={16} aria-hidden="true" />{c('Earlier plans could not load.')}
      <button type="button" className="brain-text-button" onClick={() => setAttempt(value => value + 1)}><RefreshCw size={15} aria-hidden="true" />{c('Try again')}</button></p>
      : <ul>
        {(plans ?? []).map(plan => {
          const status = plan.status === 'ready' ? c('Ready') : plan.status === 'generating' ? c('Building…') : c('Failed')
          const title = plan.content?.title ?? c('Exam in {n} days').replace('{n}', String(plan.days))
          return <li key={plan.id}>
            <button type="button" onClick={() => onOpen(plan)}>
              <span className="brain-exam-earlier-copy">
                <strong>{title}</strong>
                <span>{c('Exam on {date}').replace('{date}', formatPlanDate(plan.exam_date, language))} · {c('created {date}').replace('{date}', formatCreatedAt(plan.created_at, language))}</span>
              </span>
              <span className={`brain-exam-status is-${plan.status}`}>{status}</span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </li>
        })}
      </ul>}
  </section>
}

// ---------------------------------------------------------------------------
// Generating
// ---------------------------------------------------------------------------

function ExamProgress({ title, stage, restoring = false }: { title: string; stage: PlanStage | null; restoring?: boolean }) {
  const c = useCopy()
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 25_000)
    return () => window.clearTimeout(timer)
  }, [])
  const current = activeStageIndex(stage)
  const progress = stageProgress(stage)
  const headingRef = useRef<HTMLHeadingElement>(null)
  // After "Build", the button is gone: keep keyboard focus in the view. Not on a restore at page load.
  useEffect(() => { if (!restoring) headingRef.current?.focus({ preventScroll: true }) }, [restoring])
  const stageText = c(STAGE_LABEL[PLAN_STAGES[current]])

  return <div className="brain-exam-progress" aria-busy="true">
    <div className="brain-inbox-heading">
      <div>
        <p className="brain-section-kicker">{title || c('Exam mode')}</p>
        <h2 id="brain-exam-title" ref={headingRef} tabIndex={-1}>{restoring ? c('Opening your plan…') : c('Building your exam plan…')}</h2>
        {!restoring && <p>{c('Reading everything you filed for this course. This usually takes 10–15 seconds.')}</p>}
      </div>
    </div>
    {!restoring && <div className="brain-exam-pipeline">
      <div className="brain-exam-rail" role="progressbar" aria-label={c('Exam plan progress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} aria-valuetext={stageText}>
        <span style={{ transform: `scaleX(${progress})` }} />
      </div>
      <ol className="brain-exam-stages">
        {PLAN_STAGES.map((entry, index) => <li key={entry} className={index < current ? 'is-done' : index === current ? 'is-current' : ''} aria-current={index === current ? 'step' : undefined}>
          <span className="brain-exam-stage-dot" aria-hidden="true">{index < current ? <Check size={14} /> : index + 1}</span>
          <span>{c(STAGE_LABEL[entry])}</span>
        </li>)}
      </ol>
      <p className="brain-exam-sr-only" role="status" aria-live="polite">{stageText}</p>
      {slow && <p className="brain-exam-hint" role="status">{c('Taking a little longer than usual. Still working…')}</p>}
    </div>}
    <div className="brain-exam-skeleton" aria-hidden="true">
      {[0, 1, 2].map(day => <div key={day} className="brain-exam-skeleton-day">
        <i className="is-short" /><i className="is-title" />
        {[0, 1, 2].map(task => <div key={task} className="brain-exam-skeleton-task"><i /><i /><b /></div>)}
      </div>)}
    </div>
  </div>
}

// ---------------------------------------------------------------------------
// Failure
// ---------------------------------------------------------------------------

function ExamFailure({ view, courseTitle, onRetry, onBack }: {
  view: Extract<ExamView, { phase: 'failed' }>; courseTitle: string; onRetry: () => void; onBack: () => void
}) {
  const c = useCopy()
  const copy = FAILURE_COPY[view.failure]
  const canRetry = Boolean(view.request || view.planId) && view.failure !== 'not_found'
  // The control the student used is gone; land on the way forward.
  const actionRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { actionRef.current?.focus({ preventScroll: true }) }, [])
  return <div className="brain-exam-failure">
    <p className="brain-section-kicker">{courseTitle || c('Exam mode')}</p>
    <div className="brain-load-error" role="alert">
      <TriangleAlert size={26} aria-hidden="true" />
      <div>
        <h2 id="brain-exam-title">{c(copy.title)}</h2>
        <p>{c(copy.body)}</p>
      </div>
    </div>
    <div className="brain-exam-failure-actions">
      {canRetry && <button type="button" ref={actionRef} className="brain-primary-button" onClick={onRetry}><RefreshCw size={18} aria-hidden="true" />{c('Try again')}</button>}
      {view.failure === 'not_enough_material' && <button type="button" className="brain-secondary-button" onClick={openPicker}><FilePlus2 size={17} aria-hidden="true" />{c('Add a file')}</button>}
      <button type="button" ref={canRetry ? undefined : actionRef} className="brain-secondary-button" onClick={onBack}>{c('Back to exam setup')}</button>
    </div>
  </div>
}
