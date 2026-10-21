/**
 * Pure helpers for Brain UI state. Owner: Claude. No runtime imports, so they are
 * easy to test (scripts/brain-mocks.test.mjs) and safe in any component.
 */
import type { BrainEvent, BrainGraph, BrainItem } from './brain-types'

/** "14:32" or "1:02:05". */
export function formatTimestamp(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

/** YouTube embed URL that starts at the anchor (end is advisory; the player API enforces it). */
export function youtubeEmbedUrl(youtubeId: string, startSec = 0, endSec?: number): string {
  const params = new URLSearchParams({ start: String(Math.floor(startSec)), rel: '0', modestbranding: '1', enablejsapi: '1' })
  if (endSec && endSec > startSec) params.set('end', String(Math.ceil(endSec)))
  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(youtubeId)}?${params}`
}

/** Apply a BrainEvent to a list of items (newest first) — handy for inbox state. */
export function reduceItems(items: BrainItem[], event: BrainEvent): BrainItem[] {
  switch (event.type) {
    case 'item.created':
      return [event.item, ...items.filter((item) => item.id !== event.item.id)]
    case 'item.progress':
      return items.map((item) => (item.id === event.item_id ? { ...item, status: event.status, progress: event.progress, title: event.title || item.title } : item))
    case 'item.filed':
    case 'item.refiled':
      return items.some((item) => item.id === event.item.id)
        ? items.map((item) => (item.id === event.item.id ? event.item : item))
        : [event.item, ...items]
    case 'item.failed':
      return items.map((item) => (item.id === event.item_id ? { ...item, status: 'failed', failure_code: event.failure_code } : item))
    case 'item.deleted':
      return items.filter((item) => item.id !== event.item_id)
    default:
      return items
  }
}

/** Apply a BrainEvent to a graph snapshot so the graph screen stays live without refetching. */
export function reduceGraph(graph: BrainGraph, event: BrainEvent): BrainGraph {
  if (event.type === 'item.filed') {
    const courses = graph.courses.some((c) => c.id === event.course.id)
      ? graph.courses.map((c) => (c.id === event.course.id ? event.course : c))
      : [...graph.courses, event.course]
    const topics = event.topic
      ? graph.topics.some((t) => t.id === event.topic?.id)
        ? graph.topics.map((t) => (t.id === event.topic?.id ? (event.topic as typeof t) : t))
        : [...graph.topics, event.topic]
      : graph.topics
    const known = new Set(graph.concepts.map((c) => c.id))
    const concepts = [
      ...graph.concepts.map((c) => event.concepts.find((n) => n.id === c.id) ?? c),
      ...event.concepts.filter((c) => !known.has(c.id)),
    ]
    return { ...graph, courses, topics, concepts }
  }
  if (event.type === 'link.created') {
    if (graph.links.some((l) => l.id === event.link.id)) return graph
    const known = new Set(graph.concepts.map((c) => c.id))
    const extra = [event.source, event.target].filter((c) => !known.has(c.id))
    return { ...graph, concepts: [...graph.concepts, ...extra], links: [...graph.links, event.link] }
  }
  return graph
}
