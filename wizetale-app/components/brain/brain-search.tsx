'use client'

/*
 * Search across the whole brain (P1). Built by Claude. Concepts jump to the graph;
 * passages open the shared source viewer at the exact anchor.
 */
import { useEffect, useId, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainCourse, SearchHit, SourceRef } from '@/lib/brain-types'
import { CitationChip, SourceViewer } from './source-viewer'
import './brain-courses.css'

type Props = {
  api: BrainApi
  courses: BrainCourse[]
  onOpenConcept: (conceptId: string) => void
  presentation?: boolean
}

export function BrainSearch({ api, courses, onOpenConcept, presentation = false }: Props) {
  const c = useCopy()
  const listId = useId()
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [failed, setFailed] = useState(false)
  const [open, setOpen] = useState(false)
  const [viewing, setViewing] = useState<SourceRef | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const request = useRef(0)

  useEffect(() => {
    const text = query.trim()
    if (text.length < 2) { setHits(null); setSearching(false); return }
    const id = ++request.current
    setSearching(true)
    const timer = window.setTimeout(async () => {
      try {
        const result = await api.search(text, 12)
        if (id === request.current) { setHits(result.hits); setFailed(false) }
      } catch {
        if (id === request.current) setFailed(true)
      } finally {
        if (id === request.current) setSearching(false)
      }
    }, 280)
    return () => window.clearTimeout(timer)
  }, [api, query])

  useEffect(() => {
    const close = (event: MouseEvent) => { if (!boxRef.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const courseOf = (id: string | null) => courses.find(course => course.id === id)
  const showPanel = open && query.trim().length >= 2

  return <div className="brain-search" ref={boxRef}>
    <label className="brain-search-field">
      <Search size={17} aria-hidden="true" />
      <span className="sr-only">{c('Search your Brain')}</span>
      <input type="search" value={query} placeholder={c('Search your Brain')} autoComplete="off"
        aria-controls={listId} aria-expanded={showPanel}
        onChange={event => { setQuery(event.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={event => { if (event.key === 'Escape') { setOpen(false); (event.target as HTMLInputElement).blur() } }} />
      {query && <button type="button" aria-label={c('Clear search')} onClick={() => { setQuery(''); setHits(null) }}><X size={15} aria-hidden="true" /></button>}
    </label>
    {showPanel && <div className="brain-search-panel" id={listId} role="region" aria-live="polite" aria-label={c('Search results')}>
      {searching && !hits ? <p className="brain-search-note">{c('Searching…')}</p>
        : failed ? <p className="brain-search-note">{c('Search is unavailable right now. Try again.')}</p>
        : hits && hits.length === 0 ? <p className="brain-search-note">{c('Nothing in your Brain matches that yet.')}</p>
        : <ul>
          {(hits ?? []).map(hit => hit.kind === 'concept'
            ? <li key={`k-${hit.concept.id}`}>
              <button type="button" className="brain-search-hit" data-course-color={courseOf(hit.concept.course_id)?.color_index ?? 0}
                onClick={() => { setOpen(false); onOpenConcept(hit.concept.id) }}>
                <span className="brain-search-kind">{c('Concept')}</span>
                <strong>{hit.concept.name}</strong>
                <span className="brain-search-meta">{courseOf(hit.concept.course_id)?.title}</span>
                <span className="brain-search-summary">{hit.concept.summary}</span>
              </button>
            </li>
            : <li key={`p-${hit.source.chunk_id}`} className="brain-search-passage" data-course-color={courseOf(hit.source.course_id)?.color_index ?? 0}>
              <span className="brain-search-kind">{courseOf(hit.source.course_id)?.title ?? c('Source')}</span>
              <strong>{hit.source.item_title}</strong>
              <span className="brain-search-summary">“{hit.source.quote}”</span>
              <CitationChip source={hit.source} onOpen={setViewing} presentation={presentation} />
            </li>)}
        </ul>}
    </div>}
    <SourceViewer source={viewing} onClose={() => setViewing(null)} presentation={presentation} />
  </div>
}
