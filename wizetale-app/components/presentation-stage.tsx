'use client'

import Image from 'next/image'
import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Maximize2, Minimize2, Printer } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import type { PresentationSlide } from '@/lib/teacher-content'
import { PresentationVisualFigure } from './presentation-visual'
import { FibonacciMark } from '@/components/fibonacci-mark'

type PresentationStageProps = {
  title: string
  slides: PresentationSlide[]
  index: number
  changeIndex: (index: number) => void
  print: () => void
}

export function PresentationStage({ title, slides, index, changeIndex, print }: PresentationStageProps) {
  const c = useCopy()
  const stage = useRef<HTMLElement>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const [fallbackFullscreen, setFallbackFullscreen] = useState(false)
  const current = slides[index]

  useEffect(() => {
    const sync = () => {
      const active = document.fullscreenElement === stage.current
      setFullscreen(active)
      if (!active) setFallbackFullscreen(false)
    }
    document.addEventListener('fullscreenchange', sync)
    return () => document.removeEventListener('fullscreenchange', sync)
  }, [])

  useEffect(() => {
    if (!fullscreen && !fallbackFullscreen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight' || event.key === 'PageDown') {
        event.preventDefault()
        changeIndex(Math.min(slides.length - 1, index + 1))
      } else if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
        event.preventDefault()
        changeIndex(Math.max(0, index - 1))
      } else if (event.key === 'Home') {
        event.preventDefault()
        changeIndex(0)
      } else if (event.key === 'End') {
        event.preventDefault()
        changeIndex(slides.length - 1)
      } else if (event.key === 'Escape' && fallbackFullscreen) {
        setFallbackFullscreen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [changeIndex, fallbackFullscreen, fullscreen, index, slides.length])

  async function toggleFullscreen() {
    if (fullscreen || fallbackFullscreen) {
      if (document.fullscreenElement) await document.exitFullscreen()
      else setFallbackFullscreen(false)
      return
    }
    if (stage.current?.requestFullscreen) {
      try {
        await stage.current.requestFullscreen()
        return
      } catch {
        // Use the in-page full-screen layout when the browser blocks its API.
      }
    }
    setFallbackFullscreen(true)
  }

  return <section ref={stage} className={`prep-presentation-stage ${fullscreen || fallbackFullscreen ? 'is-fullscreen' : ''}`} aria-label={title}>
    <div className="prep-presentation-topline"><div className="prep-presentation-brand"><FibonacciMark size={36}/><span>Fibonacci</span></div><span className="prep-presentation-counter" aria-live="polite">{index + 1} / {slides.length}</span></div>
    {current ? <article className="prep-presentation-slide" aria-live="polite"><p className="prep-eyebrow">{c('Presentation')} · {c('Slide')} {index + 1}</p><h2>{current.title}</h2><PresentationVisualFigure visual={current.visual}/><ul>{current.key_points.map((point,pointIndex)=><li key={pointIndex}>{point}</li>)}</ul><details className="prep-speaker-notes"><summary>{c('Speaker notes')}</summary><p>{current.speaker_notes}</p></details></article> : <p className="prep-empty">{c('Your first slide will appear here.')}</p>}
    <div className="prep-presentation-controls"><button type="button" className="prep-button" onClick={()=>changeIndex(Math.max(0,index-1))} disabled={index===0} aria-label={c('Previous slide')}><ArrowLeft size={18} aria-hidden="true"/>{c('Previous')}</button><span className="prep-presentation-hint">{c('Use the arrow keys to move through slides.')}</span><button type="button" className="prep-button" onClick={()=>changeIndex(Math.min(slides.length-1,index+1))} disabled={index>=slides.length-1} aria-label={c('Next slide')}>{c('Next')}<ArrowRight size={18} aria-hidden="true"/></button><button type="button" className="prep-button" onClick={print}><Printer size={17} aria-hidden="true"/>{c('Export PDF')}</button><button type="button" className="prep-button primary" onClick={()=>void toggleFullscreen()}>{fullscreen||fallbackFullscreen?<Minimize2 size={17} aria-hidden="true"/>:<Maximize2 size={17} aria-hidden="true"/>}{c(fullscreen||fallbackFullscreen?'Exit presentation':'Present')}</button></div>
  </section>
}
