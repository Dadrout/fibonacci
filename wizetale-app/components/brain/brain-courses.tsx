'use client'

/*
 * Course view (board row A7). Built by Claude while Codex was paused; Astra owns the design.
 * Course cards for the Brain home and the course page: topics in sequence order, their sources,
 * inline gap alerts, one-tap re-file (via BrainItemCard), and the "Exam in 3 days" entry.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ChevronRight, FilePlus2, GraduationCap, Layers, ListChecks, Presentation, Trash2, TriangleAlert } from 'lucide-react'
import { BrainDeleteConfirm } from './brain-delete-confirm'
import { BrainItemCard } from '@/components/brain/brain-item-card'
import { useCopy } from '@/hooks/use-copy'
import './brain-courses.css'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainCourse, BrainGraph, BrainItem, BrainTopic, CourseDetail, GapAlert, SequenceKind } from '@/lib/brain-types'

const SEQUENCE_LABEL: Record<SequenceKind, string> = { week: 'Week {n}', lecture: 'Lecture {n}', chapter: 'Chapter {n}', module: 'Module {n}' }
const MISSING_LABEL: Record<SequenceKind, string> = {
  week: 'Week {n} is missing', lecture: 'Lecture {n} is missing', chapter: 'Chapter {n} is missing', module: 'Module {n} is missing',
}

function openPicker() {
  window.dispatchEvent(new Event('brain:open-picker'))
}

/** Course cards for the Brain home: color, counts, missing weeks, and the two things a student does next. */
type StudyToolActions = { onFlashcards: (courseId: string) => void; onQuiz: (courseId: string) => void; onPresentation: (courseId: string) => void }

export function CourseGrid({ graph, gaps, onOpen, onExam, onChooseDate, onFlashcards, onQuiz, onPresentation }: {
  graph: BrainGraph | null; gaps: GapAlert[]; onOpen: (courseId: string) => void; onExam: (courseId: string) => void
} & StudyToolActions & { onChooseDate: (courseId: string) => void }) {
  const c = useCopy()
  if (!graph) {
    return <div className="brain-source-skeletons" aria-busy="true" aria-label={c('Loading courses')}>
      {[0, 1, 2].map(n => <div className="brain-source-skeleton" key={n}><span /><div><i /><i /><i /></div></div>)}
    </div>
  }
  if (graph.courses.length === 0) {
    return <p className="brain-no-recent">{c('Send your first lecture photo, PDF, or link — Fibonacci creates the course for you.')}</p>
  }
  return <ul className="brain-course-grid">
    {graph.courses.map(course => {
      const missing = gaps.filter(gap => gap.course_id === course.id)
      return <li key={course.id}>
        <article className="brain-course-card" data-course-color={course.color_index} aria-labelledby={`course-card-${course.id}`}>
          <h3 id={`course-card-${course.id}`}><span className="brain-course-swatch" aria-hidden="true" /><button type="button" className="brain-course-title" onClick={() => onOpen(course.id)}>{course.title}</button></h3>
          <span className="brain-course-counts">
            {course.code && <span className="brain-course-code">{course.code}</span>}
            <span><b>{course.item_count}</b> {c('sources')}</span>
            <span><b>{course.topic_count}</b> {c('topics')}</span>
            <span><b>{course.concept_count}</b> {c('concepts')}</span>
          </span>
          {missing.length > 0 && <span className="brain-course-gap"><TriangleAlert size={15} aria-hidden="true" />
            {missing.map(gap => c(MISSING_LABEL[gap.sequence_kind]).replace('{n}', String(gap.missing))).join(' · ')}</span>}
          <span className="brain-course-actions">
            <button type="button" className="brain-primary-button" onClick={() => onExam(course.id)}><GraduationCap size={17} aria-hidden="true" />{c('Exam in 3 days')}</button>
            <button type="button" className="brain-text-button brain-choose-date" onClick={() => onChooseDate(course.id)}>{c('Choose date')}</button>
            <button type="button" className="brain-secondary-button" onClick={() => onOpen(course.id)}>{c('Open course')}<ChevronRight size={16} aria-hidden="true" /></button>
          </span>
          <StudyTools courseId={course.id} compact onFlashcards={onFlashcards} onQuiz={onQuiz} onPresentation={onPresentation} />
        </article>
      </li>
    })}
  </ul>
}

/** Full course page: topics in order with their sources, inline gaps, and the exam entry. */
export function CourseDetailView({ api, catalog = null, courseId, version, onBack, onChanged, onStartExam, onChooseDate, onFlashcards, onQuiz, onPresentation }: {
  api: BrainApi; catalog?: { courses: BrainCourse[]; topics: BrainTopic[] } | null; courseId: string; version: number
  onBack: () => void; onChanged: () => void; onStartExam: (courseId: string) => void
} & StudyToolActions & { onChooseDate: (courseId: string) => void }) {
  const c = useCopy()
  const [detail, setDetail] = useState<CourseDetail | null>(null)
  const [error, setError] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState('')
  const [renameBusy, setRenameBusy] = useState(false)
  const [renameError, setRenameError] = useState<string | null>(null)
  const renameButton = useRef<HTMLButtonElement>(null)
  const renameInput = useRef<HTMLInputElement>(null)

  const [deleteTarget, setDeleteTarget] = useState<{ kind: 'course' } | { kind: 'topic'; id: string } | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const deleteTrigger = useRef<HTMLButtonElement | null>(null)
  const cancelDelete = () => {
    setDeleteTarget(null)
    setDeleteError(null)
    deleteTrigger.current?.focus()
  }
  const removeSource = (id: string) => {
    setDetail(current => current && {
      ...current,
      course: { ...current.course, item_count: Math.max(0, current.course.item_count - (current.loose_items.some(item => item.id === id) || current.topics.some(entry => entry.items.some(item => item.id === id)) ? 1 : 0)) },
      topics: current.topics.map(entry => ({ ...entry, items: entry.items.filter(item => item.id !== id) })),
      loose_items: current.loose_items.filter(item => item.id !== id),
    })
    onChanged()
  }
  const deleteSelection = async () => {
    if (!deleteTarget || deleteBusy) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      if (deleteTarget.kind === 'course') {
        await api.deleteCourse(courseId)
        onBack()
      } else {
        const id = deleteTarget.id
        await api.deleteTopic(id)
        setDetail(current => {
          if (!current) return current
          const removed = current.topics.find(entry => entry.topic.id === id)
          return {
            ...current,
            course: { ...current.course, topic_count: Math.max(0, current.course.topic_count - 1), item_count: Math.max(0, current.course.item_count - (removed?.items.length ?? 0)) },
            topics: current.topics.filter(entry => entry.topic.id !== id),
          }
        })
        // The deleted lesson's trigger is gone; return focus to the course heading.
        document.getElementById('brain-course-title')?.focus()
      }
      setDeleteTarget(null)
      onChanged()
    } catch {
      setDeleteError(c(deleteTarget.kind === 'course' ? 'Could not delete this course. Try again.' : 'Could not delete this lesson. Try again.'))
    } finally { setDeleteBusy(false) }
  }

  useEffect(() => {
    if (renaming) { renameInput.current?.focus(); renameInput.current?.select() }
  }, [renaming])

  const closeRename = () => {
    setRenaming(false)
    setRenameError(null)
    window.requestAnimationFrame(() => renameButton.current?.focus())
  }

  const saveTitle = async () => {
    if (renameBusy) return
    const nextTitle = title.trim()
    if (!nextTitle) {
      setRenameError('Enter a course title.')
      renameInput.current?.focus()
      return
    }
    setRenameBusy(true)
    setRenameError(null)
    try {
      const course = await api.renameCourse(courseId, nextTitle)
      setDetail(current => current && { ...current, course })
      closeRename()
    } catch {
      setRenameError('The course could not be renamed. Try again.')
      renameInput.current?.focus()
    } finally {
      setRenameBusy(false)
    }
  }

  const load = useCallback(async () => {
    setError(false)
    try {
      setDetail(await api.course(courseId))
    } catch {
      setError(true)
    }
  }, [api, courseId])

  useEffect(() => { void load() }, [load, version])

  const replaceItem = useCallback((_next: BrainItem) => {
    // Re-file can change topic, course, counts and gaps; reload the authoritative grouping.
    void load()
  }, [load])

  if (error) {
    return <div className="brain-load-error" role="alert"><TriangleAlert size={24} aria-hidden="true" />
      <div><strong>{c('This course could not load.')}</strong><p>{c('Check your connection and try again.')}</p></div>
      <button type="button" className="brain-secondary-button" onClick={() => void load()}>{c('Try again')}</button>
    </div>
  }
  if (!detail) {
    return <div className="brain-source-skeletons" aria-busy="true" aria-label={c('Loading course')}>
      {[0, 1].map(n => <div className="brain-source-skeleton" key={n}><span /><div><i /><i /><i /></div></div>)}
    </div>
  }

  const { course } = detail
  const gapsBefore = (sequence: number | null) => detail.gaps.filter(gap => sequence !== null && gap.missing < sequence)
  const shownGaps = new Set<string>()
  return <section className="brain-course-detail" data-course-color={course.color_index} aria-labelledby="brain-course-title">
    <button type="button" className="brain-text-button brain-course-back" onClick={onBack}><ArrowLeft size={16} aria-hidden="true" />{c('Back to your Brain')}</button>
    <header className="brain-course-header">
      <div>
        <div className="brain-course-title-row">
          <h2 id="brain-course-title" tabIndex={-1}>{course.title}</h2>
          {!renaming && <button ref={renameButton} type="button" className="brain-text-button" onClick={() => { setTitle(course.title); setRenameError(null); setRenaming(true) }}>{c('Rename')}</button>}
          <button type="button" className="brain-text-button brain-delete-trigger" disabled={deleteBusy} onClick={event => { deleteTrigger.current = event.currentTarget; setDeleteError(null); setDeleteTarget({ kind: 'course' }) }}>{c('Delete course')}</button>
        </div>
        {renaming && <form className="brain-course-rename" aria-busy={renameBusy} onSubmit={event => { event.preventDefault(); void saveTitle() }}>
          <label htmlFor="brain-course-rename-title">{c('Course title')}</label>
          <input ref={renameInput} id="brain-course-rename-title" value={title} readOnly={renameBusy}
            aria-invalid={Boolean(renameError)} aria-describedby={renameError ? 'brain-course-rename-error' : undefined}
            onChange={event => { setTitle(event.target.value); setRenameError(null) }}
            onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!renameBusy) closeRename() } }} />
          <div className="brain-course-rename-actions">
            <button type="submit" className="brain-secondary-button" disabled={renameBusy}>{c('Save course title')}</button>
            <button type="button" className="brain-text-button" disabled={renameBusy} onClick={closeRename}>{c('Cancel rename')}</button>
          </div>
          {renameError && <p id="brain-course-rename-error" className="brain-item-action-error" role="alert">{c(renameError)}</p>}
        </form>}
        <p className="brain-course-counts">
          {course.code && <span className="brain-course-code">{course.code}</span>}
          <span><b>{course.item_count}</b> {c('sources')}</span>
          <span><b>{course.topic_count}</b> {c('topics')}</span>
          <span><b>{course.concept_count}</b> {c('concepts')}</span>
        </p>
      </div>
      <div className="brain-course-study-actions">
        <button type="button" className="brain-primary-button" onClick={() => onStartExam(course.id)}>
          <GraduationCap size={18} aria-hidden="true" />{c('Exam in 3 days')}
        </button>
        <button type="button" className="brain-text-button brain-choose-date" onClick={() => onChooseDate(course.id)}>{c('Choose date')}</button>
        <StudyTools courseId={course.id} onFlashcards={onFlashcards} onQuiz={onQuiz} onPresentation={onPresentation} />
      </div>
    </header>

    {deleteTarget?.kind === 'course' && <BrainDeleteConfirm key={`delete-course-${course.id}`} 
      message={c('Delete {title}, its lessons and {count} sources?').replace('{title}', course.title).replace('{count}', String(course.item_count))}
      label={c('Delete course')} busy={deleteBusy} error={deleteError} onConfirm={() => void deleteSelection()} onCancel={cancelDelete} />}

    <ol className="brain-topic-list">
      {detail.topics.map(({ topic, items }) => {
        const gaps = gapsBefore(topic.sequence).filter(gap => !shownGaps.has(gap.id))
        gaps.forEach(gap => shownGaps.add(gap.id))
        return <li key={topic.id}>
          {gaps.map(gap => <GapRow key={gap.id} gap={gap} />)}
          <section className="brain-topic" aria-labelledby={`topic-${topic.id}`}>
            <header>
              {topic.sequence !== null && topic.sequence_kind && <span className="brain-topic-sequence">{c(SEQUENCE_LABEL[topic.sequence_kind]).replace('{n}', String(topic.sequence))}</span>}
              <h3 id={`topic-${topic.id}`}>{topic.title}</h3>
              <span className="brain-topic-meta">{items.length} {c('sources')} · {topic.concept_count} {c('concepts')}</span>
              <button type="button" className="brain-topic-delete brain-delete-trigger" aria-label={c('Delete lesson {title}').replace('{title}', topic.title)} disabled={deleteBusy}
                onClick={event => { deleteTrigger.current = event.currentTarget; setDeleteError(null); setDeleteTarget({ kind: 'topic', id: topic.id }) }}><Trash2 size={17} aria-hidden="true" /></button>
            </header>
            {deleteTarget?.kind === 'topic' && deleteTarget.id === topic.id && <BrainDeleteConfirm key={`delete-topic-${topic.id}`} 
              message={c('Delete "{title}" and its {count} sources?').replace('{title}', topic.title).replace('{count}', String(items.length))}
              label={c('Delete lesson')} busy={deleteBusy} error={deleteError} onConfirm={() => void deleteSelection()} onCancel={cancelDelete} />}
            {items.length > 0
              ? <div className="brain-item-list">{items.map(item => <BrainItemCard key={item.id} item={item} api={api} catalog={catalog} showPath={false} courseColor={course.color_index} onItemChange={replaceItem} onDeleted={removeSource} />)}</div>
              : <p className="brain-no-recent">{c('No sources in this topic yet.')}</p>}
          </section>
        </li>
      })}
      {detail.gaps.filter(gap => !shownGaps.has(gap.id)).map(gap => <li key={gap.id}><GapRow gap={gap} /></li>)}
    </ol>

    {detail.loose_items.length > 0 && <section className="brain-topic" aria-labelledby="brain-loose-title">
      <header><h3 id="brain-loose-title">{c('Not in a topic yet')}</h3></header>
      <div className="brain-item-list">{detail.loose_items.map(item => <BrainItemCard key={item.id} item={item} api={api} catalog={catalog} courseColor={course.color_index} onItemChange={replaceItem} onDeleted={removeSource} />)}</div>
    </section>}
  </section>
}

function GapRow({ gap }: { gap: GapAlert }) {
  const c = useCopy()
  return <aside className="brain-gap-alert brain-gap-inline">
    <span className="brain-gap-icon"><TriangleAlert size={19} aria-hidden="true" /></span>
    <div><strong>{c(MISSING_LABEL[gap.sequence_kind]).replace('{n}', String(gap.missing))}</strong>
      <span>{c('You have the material before and after it, but nothing from this one.')}</span></div>
    <button type="button" className="brain-text-button" onClick={openPicker}><FilePlus2 size={16} aria-hidden="true" />{c('Add it')}</button>
  </aside>
}


function StudyTools({ courseId, compact = false, onFlashcards, onQuiz, onPresentation }: StudyToolActions & { courseId: string; compact?: boolean }) {
  const c = useCopy()
  return <div className={`brain-course-tools${compact ? ' is-compact' : ''}`}>
    <button type="button" className={compact ? 'brain-text-button' : 'brain-secondary-button'} onClick={() => onFlashcards(courseId)}><Layers size={16} aria-hidden="true" />{c('Flashcards')}</button>
    <button type="button" className={compact ? 'brain-text-button' : 'brain-secondary-button'} onClick={() => onQuiz(courseId)}><ListChecks size={16} aria-hidden="true" />{c('Quiz')}</button>
    <button type="button" className={compact ? 'brain-text-button' : 'brain-secondary-button'} onClick={() => onPresentation(courseId)}><Presentation size={16} aria-hidden="true" />{c(compact ? 'Slides' : 'Presentation')}</button>
  </div>
}
