'use client'

/*
 * Course view (board row A7). Built by Claude while Codex was paused; Astra owns the design.
 * List of courses → course detail with topics in sequence order, their sources, inline gap
 * alerts, one-tap re-file (via BrainItemCard), and the "Exam in N days" entry.
 */
import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, BookOpen, ChevronRight, FilePlus2, GraduationCap, TriangleAlert } from 'lucide-react'
import { BrainItemCard } from '@/components/brain/brain-item-card'
import { useCopy } from '@/hooks/use-copy'
import './brain-courses.css'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainGraph, BrainItem, CourseDetail, GapAlert, SequenceKind } from '@/lib/brain-types'

type Props = {
  api: BrainApi
  graph: BrainGraph | null
  /** Bumps when live events change the brain, so an open course refreshes. */
  version: number
  onStartExam: (courseId: string) => void
}

const SEQUENCE_LABEL: Record<SequenceKind, string> = { week: 'Week {n}', lecture: 'Lecture {n}', chapter: 'Chapter {n}', module: 'Module {n}' }
const MISSING_LABEL: Record<SequenceKind, string> = {
  week: 'Week {n} is missing', lecture: 'Lecture {n} is missing', chapter: 'Chapter {n} is missing', module: 'Module {n} is missing',
}

function openPicker() {
  window.dispatchEvent(new Event('brain:open-picker'))
}

export function BrainCourses({ api, graph, version, onStartExam }: Props) {
  const c = useCopy()
  const [openCourse, setOpenCourse] = useState<string | null>(null)

  if (!graph) {
    return <div className="brain-source-skeletons" aria-busy="true" aria-label={c('Loading courses')}>
      {[0, 1, 2].map(n => <div className="brain-source-skeleton" key={n}><span /><div><i /><i /><i /></div></div>)}
    </div>
  }
  if (openCourse) {
    return <CourseDetailView api={api} courseId={openCourse} version={version} onBack={() => setOpenCourse(null)} onStartExam={onStartExam} />
  }
  if (graph.courses.length === 0) {
    return <section className="brain-coming-soon" aria-labelledby="brain-courses-empty">
      <div className="brain-coming-icon"><BookOpen size={27} aria-hidden="true" /></div>
      <h2 id="brain-courses-empty">{c('No courses yet.')}</h2>
      <p>{c('Send your first lecture photo, PDF, or link — Fibonacci creates the course for you.')}</p>
      <button type="button" className="brain-primary-button" onClick={openPicker}><FilePlus2 size={18} aria-hidden="true" />{c('Add a file')}</button>
    </section>
  }
  return <section aria-labelledby="brain-courses-title">
    <div className="brain-inbox-heading">
      <div>
        <p className="brain-section-kicker">{c('Course by course')}</p>
        <h2 id="brain-courses-title">{c('Your courses')}</h2>
        <p>{c('Every source you send lands in a course. Open one to see its topics, what is missing, and what to study.')}</p>
      </div>
    </div>
    <ul className="brain-course-grid">
      {graph.courses.map(course => <li key={course.id}>
        <button type="button" className="brain-course-card" data-course-color={course.color_index} onClick={() => setOpenCourse(course.id)}>
          <span className="brain-course-card-top">
            <span className="brain-course-swatch" aria-hidden="true" />
            {course.code && <span className="brain-course-code">{course.code}</span>}
          </span>
          <strong>{course.title}</strong>
          <span className="brain-course-counts">
            <span><b>{course.item_count}</b> {c('sources')}</span>
            <span><b>{course.topic_count}</b> {c('topics')}</span>
            <span><b>{course.concept_count}</b> {c('concepts')}</span>
          </span>
          <span className="brain-course-open">{c('Open course')}<ChevronRight size={16} aria-hidden="true" /></span>
        </button>
      </li>)}
    </ul>
  </section>
}

function CourseDetailView({ api, courseId, version, onBack, onStartExam }: {
  api: BrainApi; courseId: string; version: number; onBack: () => void; onStartExam: (courseId: string) => void
}) {
  const c = useCopy()
  const [detail, setDetail] = useState<CourseDetail | null>(null)
  const [error, setError] = useState(false)

  const load = useCallback(async () => {
    setError(false)
    try {
      setDetail(await api.course(courseId))
    } catch {
      setError(true)
    }
  }, [api, courseId])

  useEffect(() => { void load() }, [load, version])

  const replaceItem = useCallback((next: BrainItem) => {
    if (next.course_id !== courseId) {
      void load() // moved to another course by a re-file
      return
    }
    setDetail(current => current && {
      ...current,
      topics: current.topics.map(entry => ({ ...entry, items: entry.items.map(item => item.id === next.id ? next : item) })),
      loose_items: current.loose_items.map(item => item.id === next.id ? next : item),
    })
  }, [courseId, load])

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
    <button type="button" className="brain-text-button brain-course-back" onClick={onBack}><ArrowLeft size={16} aria-hidden="true" />{c('All courses')}</button>
    <header className="brain-course-header">
      <div>
        <p className="brain-section-kicker">{course.code ?? c('Course')}</p>
        <h2 id="brain-course-title">{course.title}</h2>
        <p className="brain-course-counts">
          <span><b>{course.item_count}</b> {c('sources')}</span>
          <span><b>{course.topic_count}</b> {c('topics')}</span>
          <span><b>{course.concept_count}</b> {c('concepts')}</span>
        </p>
      </div>
      <button type="button" className="brain-primary-button" onClick={() => onStartExam(course.id)}>
        <GraduationCap size={18} aria-hidden="true" />{c('Exam in 3 days')}
      </button>
    </header>

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
            </header>
            {items.length > 0
              ? <div className="brain-item-list">{items.map(item => <BrainItemCard key={item.id} item={item} api={api} courseColor={course.color_index} onItemChange={replaceItem} />)}</div>
              : <p className="brain-no-recent">{c('No sources in this topic yet.')}</p>}
          </section>
        </li>
      })}
      {detail.gaps.filter(gap => !shownGaps.has(gap.id)).map(gap => <li key={gap.id}><GapRow gap={gap} /></li>)}
    </ol>

    {detail.loose_items.length > 0 && <section className="brain-topic" aria-labelledby="brain-loose-title">
      <header><h3 id="brain-loose-title">{c('Not in a topic yet')}</h3></header>
      <div className="brain-item-list">{detail.loose_items.map(item => <BrainItemCard key={item.id} item={item} api={api} courseColor={course.color_index} onItemChange={replaceItem} />)}</div>
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

