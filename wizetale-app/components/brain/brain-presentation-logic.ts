/** Slide navigation never wraps: boundaries keep the presenter on the current slide. */
export function clampSlideIndex(index: number, count: number): number {
  if (!Number.isFinite(index) || !Number.isFinite(count) || count < 1) return 0
  return Math.max(0, Math.min(Math.trunc(count) - 1, Math.trunc(index)))
}

export type SlideKeyContext = {
  presenting?: boolean
  interactive?: boolean
  modified?: boolean
}

/** null means leave the browser's key behavior alone (especially buttons and dialogs). */
export function slideIndexForKey(key: string, index: number, count: number, context: SlideKeyContext = {}): number | null {
  if (context.interactive || context.modified || count < 1) return null
  if (key === 'ArrowRight' || (key === ' ' && context.presenting)) return clampSlideIndex(index + 1, count)
  if (key === 'ArrowLeft') return clampSlideIndex(index - 1, count)
  if (key === 'Home') return 0
  if (key === 'End') return clampSlideIndex(count - 1, count)
  return null
}
