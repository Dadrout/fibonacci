'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ChevronLeft, ChevronRight, Maximize, Minimize, TriangleAlert } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { BrainApiError, type BrainApi } from '@/lib/brain-api'
import type { Presentation, SourceRef } from '@/lib/brain-types'
import { planLanguageFor } from './brain-exam-logic'
import { SourceChips } from './brain-exam-chips'
import { SourceViewer } from './source-viewer'
import { clampSlideIndex, slideIndexForKey } from './brain-presentation-logic'
import './brain-exam.css'
import './brain-presentation.css'

type DeckState = { phase: 'loading' } | { phase: 'ready'; deck: Presentation } | { phase: 'error'; code: string }

export function BrainPresentation({ api, courseId, courseTitle, presentation, onBack, onHome }: {
  api: BrainApi; courseId: string; courseTitle: string; presentation: boolean; onBack: () => void; onHome: () => void
}) {
  const c = useCopy()
  const { language } = useLanguage()
  const [state, setState] = useState<DeckState>({ phase: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [index, setIndex] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [fullscreenUnavailable, setFullscreenUnavailable] = useState(false)
  const [viewing, setViewing] = useState<SourceRef | null>(null)
  const frame = useRef<HTMLDivElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const presentButton = useRef<HTMLButtonElement>(null)
  const wasFullscreen = useRef(false)
  const planLanguage = planLanguageFor(language)

  useEffect(() => {
    let alive = true
    setState({ phase: 'loading' })
    setIndex(0)
    // The API owns its timeout/retries; generation commonly takes ten seconds live.
    api.createPresentation(courseId, { language: planLanguage }).then(deck => {
      if (alive) setState(deck.slides.length ? { phase: 'ready', deck } : { phase: 'error', code: 'not_enough_material' })
    }, error => { if (alive) setState({ phase: 'error', code: error instanceof BrainApiError ? error.code : 'unavailable' }) })
    return () => { alive = false }
  }, [api, courseId, planLanguage, attempt])

  useEffect(() => { heading.current?.focus({ preventScroll: true }) }, [state.phase])
  useEffect(() => {
    const changed = () => {
      const active = Boolean(frame.current && document.fullscreenElement === frame.current)
      setFullscreen(active)
      if (active) frame.current?.focus({ preventScroll: true })
      else if (wasFullscreen.current) presentButton.current?.focus({ preventScroll: true })
      wasFullscreen.current = active
    }
    document.addEventListener('fullscreenchange', changed)
    return () => { document.removeEventListener('fullscreenchange', changed) }
  }, [])

  const count = state.phase === 'ready' ? state.deck.slides.length : 0
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (viewing || event.defaultPrevented) return
      const target = event.target instanceof Element ? event.target : null
      const next = slideIndexForKey(event.key, index, count, {
        presenting: fullscreen,
        interactive: Boolean(target?.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="dialog"]') || (event.key === ' ' && target?.closest('button, a, summary'))),
        modified: event.altKey || event.ctrlKey || event.metaKey || event.shiftKey,
      })
      if (next === null) return
      event.preventDefault()
      setIndex(next)
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [index, count, fullscreen, viewing])

  const present = async () => {
    setFullscreenUnavailable(false)
    try {
      if (!frame.current?.requestFullscreen) throw new Error('fullscreen unavailable')
      await frame.current.requestFullscreen()
    } catch { setFullscreenUnavailable(true); frame.current?.focus({ preventScroll: true }) }
  }
  const exit = async () => {
    if (document.fullscreenElement === frame.current) {
      try { await document.exitFullscreen() } catch { /* The browser still offers Escape. */ }
    }
  }
  const openSource = async (source: SourceRef) => {
    // SourceViewer uses the shared dialog portal, outside the fullscreen frame.
    await exit()
    setViewing(source)
  }

  if (state.phase === 'loading') return <section className="brain-presentation" aria-labelledby="brain-presentation-title" aria-busy="true">
    <header className="brain-presentation-heading"><div>
      <h2 id="brain-presentation-title" ref={heading} tabIndex={-1}>{c('Building your slides…')}</h2>
      <p role="status">{c('Building your slides from your sources… usually about 10 seconds.')}</p>
    </div></header>
    <div className="brain-slide-frame brain-slide-skeleton" aria-hidden="true"><i /><i /><i /><i /></div>
  </section>

  if (state.phase === 'error') {
    const needsSources = state.code === 'not_enough_material'
    const missing = state.code === 'not_found'
    return <section className="brain-presentation" aria-labelledby="brain-presentation-title">
      <div className="brain-load-error" role="alert"><TriangleAlert size={24} aria-hidden="true" /><div>
        <h2 id="brain-presentation-title" ref={heading} tabIndex={-1}>{c(needsSources ? 'Add more course material first.' : missing ? 'This course is no longer available.' : 'Your slides could not be built.')}</h2>
        <p>{c(needsSources ? 'Add a lecture photo, PDF, or link to this course, then try building slides again.' : missing ? 'Return to your Brain and choose another course.' : 'Your sources are safe. Try again in a moment.')}</p>
      </div></div>
      <div className="brain-presentation-recovery">
        {!needsSources && !missing && <button type="button" className="brain-primary-button" onClick={() => setAttempt(value => value + 1)}>{c('Try again')}</button>}
        <button type="button" className="brain-secondary-button" onClick={missing ? onHome : onBack}><ArrowLeft size={16} aria-hidden="true" />{c(missing ? 'Back to your Brain' : 'Back to the course')}</button>
      </div>
    </section>
  }

  const { deck } = state
  const active = clampSlideIndex(index, count)
  const slide = deck.slides[active]
  const navigation = (inFrame = false) => <div className={`brain-slide-navigation${inFrame ? ' in-frame' : ''}`}>
    <button type="button" className="brain-icon-button" disabled={active === 0} aria-label={c('Previous slide')} onClick={() => setIndex(clampSlideIndex(active - 1, count))}><ChevronLeft size={20} aria-hidden="true" /></button>
    <span role="status" aria-live="polite" aria-atomic="true" aria-label={c('Slide {n} of {total}').replace('{n}', String(active + 1)).replace('{total}', String(count))}>{active + 1} / {count}</span>
    <button type="button" className="brain-icon-button" disabled={active === count - 1} aria-label={c('Next slide')} onClick={() => setIndex(clampSlideIndex(active + 1, count))}><ChevronRight size={20} aria-hidden="true" /></button>
    {inFrame && <button type="button" className="brain-icon-button" aria-label={c('Exit fullscreen')} onClick={() => void exit()}><Minimize size={20} aria-hidden="true" /></button>}
  </div>
  return <section className={`brain-presentation${presentation ? ' is-presentation' : ''}`} aria-labelledby="brain-presentation-title">
    <header className="brain-presentation-heading"><div>
      <h2 id="brain-presentation-title" ref={heading} tabIndex={-1}>{deck.title}</h2>
      <p>{courseTitle && <>{courseTitle} · </>}{c('{n} slides').replace('{n}', String(count))}</p>
    </div><button ref={presentButton} type="button" className="brain-primary-button" onClick={() => void present()}><Maximize size={18} aria-hidden="true" />{c('Present')}</button></header>
    {fullscreenUnavailable && <p className="brain-presentation-hint" role="status">{c('Fullscreen is unavailable. You can still use the slides and arrow keys here.')}</p>}
    <div className="brain-slide-frame" ref={frame} tabIndex={0} role="region" aria-label={c('Slide viewer')} aria-describedby="brain-slide-help">
      <article className="brain-slide" key={slide.id} lang={deck.language} aria-labelledby={`brain-slide-${slide.id}`}>
        <h3 id={`brain-slide-${slide.id}`}>{slide.title}</h3>
        <ul>{slide.bullets.map((bullet, n) => <li key={n}>{bullet.text}{' '}<SourceChips inline sources={bullet.sources} onOpen={source => void openSource(source)} presentation={presentation || fullscreen} /></li>)}</ul>
      </article>
      {fullscreen && navigation(true)}
    </div>
    {!fullscreen && navigation()}
    <p id="brain-slide-help" className="brain-presentation-hint">{c('Use ← and → to change slides. In fullscreen, Space advances and Esc exits.')}</p>
    <details className="brain-slide-notes" open>
      <summary>{c('Speaker notes')}</summary>
      <p lang={deck.language}>{slide.notes || c('No speaker notes for this slide.')}</p>
    </details>
    <nav className="brain-slide-list" aria-label={c('Slides')}><ol>{deck.slides.map((entry, n) => <li key={entry.id}>
      <button type="button" aria-current={n === active ? 'step' : undefined} onClick={() => setIndex(n)}><span aria-hidden="true">{n + 1}</span><span>{entry.title}</span></button>
    </li>)}</ol></nav>
    <SourceViewer source={viewing} onClose={() => { setViewing(null); frame.current?.focus({ preventScroll: true }) }} presentation={presentation} />
  </section>
}
