'use client'

import Image from 'next/image'
import { useState } from 'react'
import { AudioLines, Check, ChevronDown, FileText, Image as ImageIcon, Link2, RotateCw } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { courseColorSlot } from './brain-ui-state'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainItem, ItemStatus } from '@/lib/brain-types'

type BrainItemCardProps = {
  item: BrainItem
  api: BrainApi
  recentlyFiled?: boolean
  courseColor?: number
  onItemChange: (item: BrainItem) => void
}

const stages: Array<{ status: Exclude<ItemStatus, 'failed'>; label: string }> = [
  { status: 'queued', label: 'Queued' },
  { status: 'extracting', label: 'Reading' },
  { status: 'classifying', label: 'Filing' },
  { status: 'linking', label: 'Linking' },
  { status: 'filed', label: 'Filed' },
]

function kindLabel(kind: BrainItem['kind']) {
  const labels: Record<BrainItem['kind'], string> = {
    photo: 'Photo', pdf: 'PDF', document: 'Document', youtube: 'YouTube video', web: 'Web page', audio: 'Audio', text: 'Text',
  }
  return labels[kind]
}

function kindIcon(kind: BrainItem['kind']) {
  if (kind === 'photo') return <ImageIcon size={17} aria-hidden="true" />
  if (kind === 'audio') return <AudioLines size={17} aria-hidden="true" />
  if (kind === 'youtube' || kind === 'web') return <Link2 size={17} aria-hidden="true" />
  return <FileText size={17} aria-hidden="true" />
}

function failureText(code: BrainItem['failure_code'], c: (text: string) => string) {
  switch (code) {
    case 'unsupported_type': return c('This file type is not supported.')
    case 'too_large': return c('This source is over the 20 MB limit.')
    case 'unreadable': return c('Fibonacci could not read this source.')
    case 'fetch_failed': return c('This link could not be opened. Check it and retry.')
    case 'transcript_unavailable': return c('No transcript was available for this video.')
    case 'ai_unavailable': return c('Filing is temporarily unavailable. Retry in a moment.')
    default: return c('This source could not be filed. Retry in a moment.')
  }
}

function requestForAlternative(alt: BrainItem['alternatives'][number]) {
  return {
    ...(alt.course_id ? { course_id: alt.course_id } : { new_course_title: alt.course_title }),
    topic_id: alt.topic_id,
    ...(alt.topic_id ? {} : { new_topic_title: alt.topic_title }),
  }
}

export function BrainItemCard({ item, api, recentlyFiled = false, courseColor, onItemChange }: BrainItemCardProps) {
  const c = useCopy()
  const { language } = useLanguage()
  const [action, setAction] = useState<'retry' | 'refile' | null>(null)
  const [actionError, setActionError] = useState('')
  const [showAlternatives, setShowAlternatives] = useState(false)
  const imageUrl = item.thumbnail_url ?? (item.kind === 'photo' ? item.media_url : null)
  const progress = Math.max(0, Math.min(1, item.progress || 0))
  const percent = Math.round(progress * 100)
  const activeStageIndex = item.status === 'filed' ? stages.length - 1 : stages.findIndex((stage) => stage.status === item.status)
  const confidence = item.confidence === null ? null : Math.max(0, Math.min(100, Math.round(item.confidence * 100)))
  const needsReview = item.needs_review || (confidence !== null && confidence < 70)

  const retry = async () => {
    setAction('retry')
    setActionError('')
    try {
      const updated = await api.retryItem(item.id)
      onItemChange(updated)
    } catch {
      setActionError(c('Retry could not start. Check your connection and try again.'))
    } finally {
      setAction(null)
    }
  }

  const refile = async (alternative: BrainItem['alternatives'][number]) => {
    setAction('refile')
    setActionError('')
    try {
      const result = await api.refile(item.id, requestForAlternative(alternative))
      onItemChange(result.item)
      setShowAlternatives(false)
    } catch {
      setActionError(c('Could not update this filing. Try again.'))
    } finally {
      setAction(null)
    }
  }

  return <article className={`brain-item${recentlyFiled ? ' is-newly-filed' : ''}${item.status === 'filed' ? ' is-filed' : ''}${item.status === 'failed' ? ' is-failed' : ''}`} data-course-color={courseColorSlot(courseColor)} aria-label={`${c(kindLabel(item.kind))}: ${item.title}`}>
    <div className="brain-item-main">
      <div className="brain-item-preview" aria-hidden={imageUrl ? undefined : true}>
        {imageUrl ? <Image src={imageUrl} alt={`${c('Preview of source')}: ${item.title}`} fill unoptimized sizes="(max-width: 700px) 68px, 88px" className="brain-item-image" /> : kindIcon(item.kind)}
      </div>
      <div className="brain-item-content">
        <div className="brain-item-overline"><span className="brain-kind">{kindIcon(item.kind)}{c(kindLabel(item.kind))}</span><time dateTime={item.captured_at}>{new Intl.DateTimeFormat(language, { month: 'short', day: 'numeric' }).format(new Date(item.captured_at))}</time></div>
        <h2>{item.status === 'filed' && item.source_url ? <a href={item.source_url} target="_blank" rel="noopener noreferrer" aria-label={`${item.title} · ${c('Open original source')}`}>{item.title}<span aria-hidden="true"> ↗</span></a> : item.title}</h2>
        {item.status !== 'filed' && item.summary && <p className="brain-item-summary">{item.summary}</p>}
        {item.status !== 'filed' && item.source_url && <a className="brain-source-link" href={item.source_url} target="_blank" rel="noopener noreferrer">{c('Open original source')}<span aria-hidden="true">↗</span></a>}
      </div>
      {item.status === 'filed' && <span className="brain-filed-mark" aria-label={c('Filed')}><Check size={19} aria-hidden="true" /></span>}
    </div>

    {item.status === 'failed' ? <div className="brain-failure" role="group" aria-label={c('Capture failed')}>
      <p>{failureText(item.failure_code, c)}</p>
      <button type="button" className="brain-secondary-button" disabled={action !== null} onClick={() => void retry()}><RotateCw size={16} aria-hidden="true" />{action === 'retry' ? c('Retrying…') : c('Retry')}</button>
    </div> : item.status !== 'filed' ? <div className="brain-pipeline">
      <div className="brain-progress-heading"><strong>{c(stages[Math.max(0, activeStageIndex)]?.label ?? 'Queued')}</strong><span>{percent}%</span></div>
      <div className="brain-progress-track" role="progressbar" aria-label={c('Processing progress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <span style={{ transform: `scaleX(${progress})` }} />
      </div>
      <ol className="brain-stage-list" aria-label={c('Capture stages')}>
        {stages.map((stage, index) => {
          const done = activeStageIndex >= 0 && index < activeStageIndex
          const current = index === activeStageIndex
          return <li key={stage.status} className={`${done ? 'is-done' : ''}${current ? ' is-current' : ''}`} aria-current={current ? 'step' : undefined}>
            <span className="brain-stage-dot">{done ? <Check size={12} aria-hidden="true" /> : index + 1}</span>
            <span>{c(stage.label)}</span>
          </li>
        })}
      </ol>
    </div> : null}

    {item.status === 'filed' && <div className="brain-filing-result">
      <div className="brain-filing-path" role={recentlyFiled ? 'status' : undefined}><span><Check size={14} aria-hidden="true" />{c('Filed under')}</span><strong>{item.course_title || c('Course not identified')} <span aria-hidden="true">→</span> {item.topic_title || c('No topic yet')}</strong></div>
      {confidence !== null && <div className={`brain-confidence${needsReview ? ' needs-review' : ''}`}>
        <span>{needsReview ? c('Please review this match') : c('Filing confidence')}</span>
        <strong aria-label={`${c('Filing confidence')}: ${confidence}%`}>{confidence}%</strong>
      </div>}
      <details className="brain-refile" open={showAlternatives} onToggle={(event) => setShowAlternatives(event.currentTarget.open)}>
        <summary><span>{c('Not right?')}</span><ChevronDown size={16} aria-hidden="true" /></summary>
        <div className="brain-alternatives">
          {item.alternatives.length ? item.alternatives.map((alt, index) => <button type="button" key={`${alt.course_id ?? alt.course_title}-${alt.topic_id ?? alt.topic_title}-${index}`} disabled={action !== null} onClick={() => void refile(alt)}>
            <span>{alt.course_title}<span aria-hidden="true"> → </span>{alt.topic_title}</span><small>{Math.round(alt.confidence * 100)}% {c('match')}</small>
          </button>) : <p>{c('No other filing suggestions yet.')}</p>}
        </div>
      </details>
    </div>}
    {actionError && <p className="brain-item-action-error" role="alert">{actionError}</p>}
  </article>
}
