import type { BrainEvent, BrainGraph, BrainItem, BrainOverview, GapAlert, SequenceKind } from '@/lib/brain-types'

export type NewConnection = Extract<BrainEvent, { type: 'link.created' }>

/** Preserve totals outside the recent-items window, applying only the visible delta. */
export function updateOverview(current: BrainOverview, event: BrainEvent, items: BrainItem[], graph: BrainGraph | null): BrainOverview {
  const processing = (rows: BrainItem[]) => rows.filter(item => item.status !== 'filed' && item.status !== 'failed').length
  const filed = (rows: BrainItem[]) => rows.filter(item => item.status === 'filed').length
  let gaps = current.gaps
  if (event.type === 'gap.detected') gaps = [...gaps.filter(gap => gap.id !== event.gap.id), event.gap]
  if (event.type === 'gap.resolved') gaps = gaps.filter(gap => gap.id !== event.gap_id)
  return {
    ...current,
    recent_items: items,
    gaps,
    telegram: event.type === 'telegram.linked' ? event.telegram : current.telegram,
    counts: {
      ...current.counts,
      items: Math.max(0, current.counts.items + filed(items) - filed(current.recent_items)),
      processing: Math.max(0, current.counts.processing + processing(items) - processing(current.recent_items)),
      ...(graph ? { courses: graph.courses.length, concepts: graph.concepts.length, cross_links: graph.links.filter(link => link.cross_course).length } : {}),
    },
  }
}

export function addConnection(current: NewConnection[], event: BrainEvent): NewConnection[] {
  if (event.type !== 'link.created' || !event.link.cross_course || current.some(entry => entry.link.id === event.link.id)) return current
  return [event, ...current].slice(0, 3)
}

export function groupGaps(gaps: GapAlert[]) {
  const courses = new Map<string, { id: string; title: string; sequences: Array<{ kind: SequenceKind; missing: number[] }> }>()
  for (const gap of gaps) {
    let course = courses.get(gap.course_id)
    if (!course) {
      course = { id: gap.course_id, title: gap.course_title, sequences: [] }
      courses.set(gap.course_id, course)
    }
    let sequence = course.sequences.find(entry => entry.kind === gap.sequence_kind)
    if (!sequence) { sequence = { kind: gap.sequence_kind, missing: [] }; course.sequences.push(sequence) }
    if (!sequence.missing.includes(gap.missing)) sequence.missing.push(gap.missing)
  }
  for (const course of courses.values()) for (const sequence of course.sequences) sequence.missing.sort((a, b) => a - b)
  return [...courses.values()]
}

export function courseColorSlot(index = 0) { return ((Math.trunc(index) % 8) + 8) % 8 }

/** Bound loading UI even if the underlying transport never settles. */
export function withUiTimeout<T>(request: Promise<T>, milliseconds = 15000): Promise<T> {
  let timer: ReturnType<typeof setTimeout>
  const timeout = new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error('Brain request timed out')), milliseconds) })
  return Promise.race([request, timeout]).finally(() => clearTimeout(timer))
}
