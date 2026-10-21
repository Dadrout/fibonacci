import type { SourceRef } from '@/lib/brain-types'

export function safeSourceUrl(value: string | null): string | null {
  if (!value) return null
  if (value.startsWith('/') && !value.startsWith('//') && !value.includes('\\')) return value
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? value : null } catch { return null }
}

export function sourceOpenUrl(source: SourceRef): string | null {
  const media = safeSourceUrl(source.media_url)
  if (source.anchor.kind === 'page' && media) return `${media.split('#')[0]}#page=${source.anchor.page}`
  return safeSourceUrl(source.open_url) ?? media
}

/** The timestamp is formatted by the shared API helper at the call site. */
export function sourceLabel(source: SourceRef, c: (text: string) => string, locale: string, windowLabel: string): string {
  const anchor = source.anchor
  const date = new Date(source.captured_at)
  const dateLabel = Number.isNaN(date.valueOf()) ? c('Unknown date') : new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' }).format(date)
  switch (anchor.kind) {
    case 'timestamp': return c(source.youtube_id || source.item_kind === 'youtube' ? '{window} · video' : '{window} · audio').replace('{window}', windowLabel)
    case 'slide': return (anchor.slide === null ? c('Photo from {date}') : c('Slide {slide} · photo from {date}').replace('{slide}', String(anchor.slide))).replace('{date}', dateLabel)
    case 'page': return c(source.item_kind === 'pdf' ? 'Page {page} · PDF' : 'Page {page} · document').replace('{page}', String(anchor.page))
    case 'paragraph': return c('Paragraph {paragraph} · text').replace('{paragraph}', String(anchor.paragraph))
    case 'section': return c('{heading} · web page').replace('{heading}', anchor.heading)
  }
}
