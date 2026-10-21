'use client'

import { useEffect, useState } from 'react'
import { ArrowUpRight, GitBranch } from 'lucide-react'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainGraph, ConceptDetail } from '@/lib/brain-types'
import { useCopy } from '@/hooks/use-copy'
import { BrainDialog } from './brain-dialog'
import { CitationChip } from './source-viewer'
import type { GraphNode } from './brain-graph-layout'

export function BrainConceptPanel({ node, graph, api, onClose, onNavigate, presentation }: {
  node: GraphNode | null; graph: BrainGraph; api: BrainApi; onClose: () => void; onNavigate: (id: string) => void; presentation: boolean
}) {
  const c = useCopy()
  const [detail, setDetail] = useState<ConceptDetail | null>(null)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  const conceptId = node?.kind === 'concept' ? node.entityId : null
  useEffect(() => {
    setDetail(null); setError(false)
    if (!conceptId) return
    let active = true
    const timeout = window.setTimeout(() => { if (active) { active = false; setError(true) } }, 12000)
    api.concept(conceptId).then(result => { if (active) setDetail(result) }, () => { if (active) setError(true) }).finally(() => window.clearTimeout(timeout))
    return () => { active = false; window.clearTimeout(timeout) }
  }, [api, conceptId, retry])
  const course = graph.courses.find(course => course.id === node?.courseId)
  const current = detail?.concept.id === conceptId ? detail : null
  const children = node ? graph.concepts.filter(concept => node.kind === 'course' ? concept.course_id === node.entityId : concept.topic_id === node.entityId) : []
  return <BrainDialog open={Boolean(node)} onClose={onClose} title={node?.label ?? c('Concepts')} description={current ? `${current.course.title}${current.topic ? ` → ${current.topic.title}` : ''}` : course?.title ?? c('Across your courses')} sheet presentation={presentation}>
    {node?.kind === 'concept' ? error ? <div className="brain-panel-error" role="alert"><p>{c('This concept could not load. Try again.')}</p><button className="brain-secondary-button" onClick={() => setRetry(value => value + 1)}>{c('Retry')}</button></div> : !current ? <div className="brain-panel-skeleton" aria-busy="true" aria-label={c('Loading concept')}><span /><span /><span /></div> : <>
      <p className="brain-concept-summary">{current.concept.summary}</p>
      <section className="brain-panel-section"><h3>{c('Sources behind this idea')}</h3><div className="brain-citation-list">{current.sources.map(source => <div key={source.chunk_id}><CitationChip source={source} presentation={presentation} /><span>{source.item_title}</span></div>)}</div>{!current.sources.length && <p>{c('No source passages are available yet.')}</p>}</section>
      <section className="brain-panel-section"><h3>{c('Connected ideas')}</h3><ul className="brain-linked-concepts">{[...current.linked].sort((a, b) => Number(b.link.cross_course) - Number(a.link.cross_course)).map(({ concept, course: linkedCourse, link }) => <li key={link.id}><button type="button" onClick={() => onNavigate(`concept:${concept.id}`)}><span>{link.cross_course && <GitBranch size={17} aria-hidden="true" />}<strong>{concept.name}</strong><ArrowUpRight size={17} aria-hidden="true" /></span><small>{linkedCourse.title}{link.cross_course ? ` · ${c('Across courses')}` : ''}</small><span className="brain-link-rationale">{link.rationale}</span></button></li>)}</ul>{!current.linked.length && <p>{c('Connections will appear as your Brain grows.')}</p>}</section>
    </> : <section className="brain-panel-section"><h3>{c('Concepts')}</h3><ul className="brain-linked-concepts">{children.map(concept => <li key={concept.id}><button type="button" onClick={() => onNavigate(`concept:${concept.id}`)}><strong>{concept.name}</strong><span className="brain-link-rationale">{concept.summary}</span></button></li>)}</ul>{!children.length && <p>{c('Concepts will appear when sources are filed.')}</p>}</section>}
  </BrainDialog>
}
