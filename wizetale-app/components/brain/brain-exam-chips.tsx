'use client'

import { useCopy } from '@/hooks/use-copy'
import type { SourceRef } from '@/lib/brain-types'
import { CitationChip } from './source-viewer'
import { uniqueSources } from './brain-exam-logic'

/** Opens the shared source viewer; `reason` is set for a quiz mistake's source moment. */
export type OpenSource = (source: SourceRef, reason?: string) => void

export function SourceChips({ sources, onOpen, presentation, label }: { sources: SourceRef[]; onOpen: OpenSource; presentation: boolean; label?: string }) {
  const c = useCopy()
  const unique = uniqueSources(sources)
  if (!unique.length) return <p className="brain-exam-no-source">{c('No source cited')}</p>
  return <div className="brain-exam-chips" role="group" aria-label={label ?? c('Sources')}>
    {unique.map(source => <CitationChip key={`${source.item_id}:${source.chunk_id}`} source={source} onOpen={() => onOpen(source)} presentation={presentation} />)}
  </div>
}
