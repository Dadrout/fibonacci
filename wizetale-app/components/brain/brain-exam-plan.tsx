'use client'

/*
 * A ready exam plan: coverage, day-by-day tasks, notes, flashcards and the quiz.
 * Every claim keeps its citation chips; all chips share one SourceViewer. A wrong quiz
 * answer opens that viewer at the returned source moment, with the reason shown inside it.
 */
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { ArrowLeft, BookOpen, CalendarDays, CirclePlay, Clock3, FilePlus2, Layers, ListChecks, PencilLine, RotateCcw, TriangleAlert, type LucideIcon } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainCourse, Flashcard, PlanDay, PlanTaskKind, SourceRef, StudyPlan, StudyPlanContent } from '@/lib/brain-types'
import { SourceViewer } from './source-viewer'
import { SourceChips, type OpenSource } from './brain-exam-chips'
import { BrainExamQuiz } from './brain-exam-quiz'
import { MISSING_LABEL, TASK_KIND_LABEL, coverageGaps, dayMinutes, formatPlanDate, type AnswerState } from './brain-exam-logic'

type Section = 'days' | 'notes' | 'cards' | 'quiz'
const SECTIONS: Section[] = ['days', 'notes', 'cards', 'quiz']
const SECTION_LABEL: Record<Section, string> = { days: 'Day by day', notes: 'Notes', cards: 'Flashcards', quiz: 'Quiz' }

const TASK_ICON: Record<PlanTaskKind, LucideIcon> = {
  read: BookOpen, watch: CirclePlay, review: RotateCcw, flashcards: Layers, quiz: ListChecks, practice: PencilLine,
}

export function BrainExamPlan({ api, plan, course, presentation, onNewPlan }: {
  api: BrainApi; plan: StudyPlan; course: BrainCourse | null; presentation: boolean; onNewPlan: () => void
}) {
  const c = useCopy()
  const { language } = useLanguage()
  const content = plan.content as StudyPlanContent
  const [section, setSection] = useState<Section>('days')
  const [viewing, setViewing] = useState<{ source: SourceRef; reason?: string } | null>(null)
  const [answers, setAnswers] = useState<Record<string, AnswerState>>({})
  const [questionIndex, setQuestionIndex] = useState(0)
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => { headingRef.current?.focus({ preventScroll: true }) }, [plan.id])

  const openSource: OpenSource = (source, reason) => setViewing({ source, reason })
  const counts: Record<Section, number> = { days: content.days.length, notes: content.notes.length, cards: content.flashcards.length, quiz: content.quiz.length }
  const gaps = coverageGaps(plan.coverage?.missing)

  const tabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const index = SECTIONS.indexOf(section)
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? SECTIONS.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + SECTIONS.length) % SECTIONS.length
    setSection(SECTIONS[nextIndex])
    document.getElementById(`brain-exam-tab-${SECTIONS[nextIndex]}`)?.focus()
  }

  return <div className="brain-exam-plan" data-course-color={course?.color_index ?? 0}>
    <header className="brain-exam-plan-header">
      <div>
        <p className="brain-section-kicker"><span className="brain-exam-course-dot" aria-hidden="true" />{course?.title ?? c('Exam plan')}</p>
        <h2 id="brain-exam-title" ref={headingRef} tabIndex={-1}>{content.title}</h2>
        <p className="brain-exam-plan-meta">
          <span><CalendarDays size={16} aria-hidden="true" />{c('Exam on {date}').replace('{date}', formatPlanDate(plan.exam_date, language))}</span>
          <span>{c(plan.days === 1 ? '1 day' : '{n} days').replace('{n}', String(plan.days))}</span>
        </p>
      </div>
      <button type="button" className="brain-secondary-button" onClick={onNewPlan}><ArrowLeft size={17} aria-hidden="true" />{c('New plan')}</button>
    </header>

    {plan.coverage && <div className="brain-exam-coverage">
      <p className="brain-exam-coverage-line">
        <strong>{c('Built from {cited} of {total} sources').replace('{cited}', String(plan.coverage.cited_item_count)).replace('{total}', String(plan.coverage.item_count))}</strong>
        <span>{c('Every line below cites where it came from.')}</span>
      </p>
      {gaps.length > 0 && <aside className="brain-gap-alert brain-exam-gap">
        <span className="brain-gap-icon"><TriangleAlert size={19} aria-hidden="true" /></span>
        <div>
          <strong>{gaps.map(gap => c(MISSING_LABEL[gap.sequence_kind]).replace('{n}', String(gap.missing))).join(' · ')}</strong>
          <span>{c('This plan cannot cover material you do not have yet. Add it, then build a new plan.')}</span>
        </div>
        <button type="button" className="brain-text-button" onClick={() => window.dispatchEvent(new Event('brain:open-picker'))}><FilePlus2 size={16} aria-hidden="true" />{c('Add it')}</button>
      </aside>}
    </div>}

    <div className="brain-exam-sections" role="tablist" aria-label={c('Exam plan sections')} onKeyDown={tabKeyDown}>
      {SECTIONS.map(id => <button key={id} id={`brain-exam-tab-${id}`} type="button" role="tab" aria-selected={section === id} aria-controls={`brain-exam-panel-${id}`} tabIndex={section === id ? 0 : -1} onClick={() => setSection(id)}>
        <span>{c(SECTION_LABEL[id])}</span><span className="brain-exam-count">{counts[id]}</span>
      </button>)}
    </div>

    {SECTIONS.map(id => <div key={id} id={`brain-exam-panel-${id}`} role="tabpanel" aria-labelledby={`brain-exam-tab-${id}`} hidden={section !== id} className="brain-exam-panel">
      {id === 'days' ? <PlanDays days={content.days} onOpen={openSource} presentation={presentation} onStartQuiz={content.quiz.length ? () => { setSection('quiz'); document.getElementById('brain-exam-tab-quiz')?.focus() } : undefined} />
        : id === 'notes' ? <PlanNotes content={content} onOpen={openSource} presentation={presentation} />
        : id === 'cards' ? <PlanFlashcards cards={content.flashcards} onOpen={openSource} presentation={presentation} />
        : <BrainExamQuiz api={api} planId={plan.id} questions={content.quiz} answers={answers} setAnswers={setAnswers} index={questionIndex} setIndex={setQuestionIndex} onOpen={openSource} presentation={presentation} />}
    </div>)}

    <SourceViewer source={viewing?.source ?? null} onClose={() => setViewing(null)} presentation={presentation} />
    {viewing?.reason && <MomentNote key={`${viewing.source.chunk_id}:${viewing.reason}`} reason={viewing.reason} />}
  </div>
}

/**
 * Shows why the moment explains the answer inside the shared source viewer, right under its
 * heading. SourceViewer has no slot for it, so this attaches a node to the open dialog.
 */
function MomentNote({ reason }: { reason: string }) {
  const c = useCopy()
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useEffect(() => {
    let frame = 0
    let tries = 0
    let node: HTMLElement | null = null
    const attach = () => {
      const headings = document.querySelectorAll('.brain-dialog .brain-dialog-heading')
      const heading = headings[headings.length - 1]
      if (!heading) {
        if (++tries < 120) frame = window.requestAnimationFrame(attach)
        return
      }
      node = document.createElement('div')
      node.className = 'brain-exam-moment-note'
      heading.insertAdjacentElement('afterend', node)
      setSlot(node)
    }
    attach()
    return () => { window.cancelAnimationFrame(frame); node?.remove() }
  }, [])
  if (!slot) return null
  return createPortal(<><p>{c('Why this moment')}</p><strong>{reason}</strong></>, slot)
}

function PlanDays({ days, onOpen, presentation, onStartQuiz }: { days: PlanDay[]; onOpen: OpenSource; presentation: boolean; onStartQuiz?: () => void }) {
  const c = useCopy()
  const { language } = useLanguage()
  if (!days.length) return <p className="brain-no-recent">{c('This plan has no days.')}</p>
  return <>
    <ol className="brain-exam-days-grid">
      {days.map(day => {
        const minutes = dayMinutes(day)
        return <li key={day.day} className="brain-exam-day">
          <article aria-labelledby={`brain-exam-day-${day.day}`}>
            <header>
              <p className="brain-exam-day-label"><span>{c('Day {n}').replace('{n}', String(day.day))}</span>{day.date && <time dateTime={day.date}>{formatPlanDate(day.date, language)}</time>}</p>
              <h3 id={`brain-exam-day-${day.day}`}>{day.focus}</h3>
              <p className="brain-exam-day-meta"><Clock3 size={15} aria-hidden="true" />{c('{n} min').replace('{n}', String(minutes))} · {c(day.tasks.length === 1 ? '1 task' : '{n} tasks').replace('{n}', String(day.tasks.length))}</p>
            </header>
            <ol className="brain-exam-tasks">
              {day.tasks.map(task => {
                const Icon = TASK_ICON[task.kind] ?? BookOpen
                return <li key={task.id} className="brain-exam-task">
                  <p className="brain-exam-task-kind"><span><Icon size={16} aria-hidden="true" />{c(TASK_KIND_LABEL[task.kind] ?? 'Recap')}</span><span>{c('{n} min').replace('{n}', String(task.minutes))}</span></p>
                  <p className="brain-exam-task-title">{task.title}</p>
                  <SourceChips sources={task.sources} onOpen={onOpen} presentation={presentation} label={c('Sources for this task')} />
                </li>
              })}
            </ol>
          </article>
        </li>
      })}
    </ol>
    {onStartQuiz && <div className="brain-exam-next"><button type="button" className="brain-primary-button" onClick={onStartQuiz}><ListChecks size={19} aria-hidden="true" />{c('Start the quiz')}</button></div>}
  </>
}

function PlanNotes({ content, onOpen, presentation }: { content: StudyPlanContent; onOpen: OpenSource; presentation: boolean }) {
  const c = useCopy()
  if (!content.notes.length) return <p className="brain-no-recent">{c('This plan has no notes.')}</p>
  return <div className="brain-exam-notes">
    {content.notes.map(note => <section key={note.id} className="brain-exam-note" aria-labelledby={`brain-exam-note-${note.id}`}>
      <h3 id={`brain-exam-note-${note.id}`}>{note.heading}</h3>
      <ul>
        {note.bullets.map((bullet, index) => <li key={index}>
          <p>{bullet.text}</p>
          <SourceChips sources={bullet.sources} onOpen={onOpen} presentation={presentation} />
        </li>)}
      </ul>
    </section>)}
  </div>
}

function PlanFlashcards({ cards, onOpen, presentation }: { cards: Flashcard[]; onOpen: OpenSource; presentation: boolean }) {
  const c = useCopy()
  const [flipped, setFlipped] = useState<Record<string, boolean>>({})
  const [announcement, setAnnouncement] = useState('')
  if (!cards.length) return <p className="brain-no-recent">{c('This plan has no flashcards.')}</p>
  const flip = (card: Flashcard) => {
    const next = !flipped[card.id]
    setFlipped(current => ({ ...current, [card.id]: next }))
    setAnnouncement(next ? `${c('Answer')}: ${card.back}` : `${c('Question')}: ${card.front}`)
  }
  return <>
    <p className="brain-exam-hint">{c('Select a card to flip it. Enter and Space work too.')}</p>
    <ul className="brain-exam-cards">
      {cards.map((card, index) => {
        const isFlipped = Boolean(flipped[card.id])
        return <li key={card.id}>
          <button type="button" className="brain-exam-card" data-flipped={isFlipped}
            aria-label={`${c('Flashcard {n}').replace('{n}', String(index + 1))}. ${isFlipped ? `${c('Answer')}: ${card.back}` : `${c('Question')}: ${card.front}`}`}
            onClick={() => flip(card)}>
            <span className="brain-exam-card-inner">
              <span className="brain-exam-card-face is-front" aria-hidden="true">
                <small>{c('Question')}</small><span>{card.front}</span><em>{c('Show answer')}</em>
              </span>
              <span className="brain-exam-card-face is-back" aria-hidden="true">
                <small>{c('Answer')}</small><span>{card.back}</span><em>{c('Show question')}</em>
              </span>
            </span>
          </button>
          <SourceChips sources={card.sources} onOpen={onOpen} presentation={presentation} />
        </li>
      })}
    </ul>
    <p className="brain-exam-sr-only" role="status" aria-live="polite">{announcement}</p>
  </>
}
