'use client'

import { useId, useState } from 'react'
import { useCopy } from '@/hooks/use-copy'
import type { SourceRef } from '@/lib/brain-types'
import { CitationChip } from './source-viewer'
import { uniqueSources } from './brain-exam-logic'

/** Opens the shared source viewer; `reason` is set for a quiz mistake's source moment. */
export type OpenSource = (source: SourceRef, reason?: string) => void

export function SourceChips({ sources, onOpen, presentation, label, limit, inline = false }: { sources: SourceRef[]; onOpen: OpenSource; presentation: boolean; label?: string; limit?: number; inline?: boolean }) {
  const c = useCopy()
  const [expanded, setExpanded] = useState(false)
  const overflowId = useId()
  const unique = uniqueSources(sources)
  const count = limit ?? unique.length
  const visible = unique.slice(0, count)
  const overflow = unique.slice(count)
  if (!unique.length) return <span className="brain-exam-no-source">{c('No source cited')}</span>
  return <span className={`brain-exam-chips${inline ? " is-inline" : ""}`} role="group" aria-label={label ?? c('Sources')}>
    {visible.map(source => <CitationChip key={`${source.item_id}:${source.chunk_id}`} source={source} onOpen={() => onOpen(source)} presentation={presentation} />)}
    {overflow.length > 0 && <>
      <button type="button" className="brain-citation-chip brain-exam-chips-more" aria-expanded={expanded} aria-controls={overflowId} onClick={() => setExpanded(value => !value)}>
        {expanded ? c('Show fewer sources') : c('+{n} more').replace('{n}', String(overflow.length))}
      </button>
      <span id={overflowId} className="brain-exam-chips-overflow" hidden={!expanded}>
        {overflow.map(source => <CitationChip key={`${source.item_id}:${source.chunk_id}`} source={source} onOpen={() => onOpen(source)} presentation={presentation} />)}
      </span>
    </>}
  </span>
}
