'use client'

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { ChevronDown, RotateCcw, Send } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import type { BrainApi } from '@/lib/brain-api'
import { demoPopoverLeft, demoResetStep } from './brain-demo-state'
import './brain-courses.css'

type Props = {
  api: BrainApi
  canReset: boolean
  presentation?: boolean
  onSent: () => void
  onReset: () => void
}

export function BrainDemoTools({ api, canReset, presentation, onSent, onReset }: Props) {
  const c = useCopy()
  const id = useId()
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const inFlight = useRef(false)
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState<'send' | 'reset' | null>(null)
  const [error, setError] = useState(false)
  const [armedUntil, setArmedUntil] = useState<number | null>(null)
  const [position, setPosition] = useState({ left: 0, maxHeight: 480 })

  const close = useCallback((returnFocus = false) => {
    setOpen(false)
    setArmedUntil(null)
    if (returnFocus) trigger.current?.focus()
  }, [])

  useEffect(() => {
    if (armedUntil === null) return
    const timer = window.setTimeout(() => setArmedUntil(null), Math.max(0, armedUntil - Date.now()))
    return () => window.clearTimeout(timer)
  }, [armedUntil])

  useEffect(() => {
    if (!canReset) setArmedUntil(null)
  }, [canReset])

  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      if (!root.current || !panel.current) return
      const anchor = root.current.getBoundingClientRect()
      setPosition({
        left: demoPopoverLeft(anchor.left, panel.current.offsetWidth, document.documentElement.clientWidth),
        maxHeight: Math.max(44, window.innerHeight - anchor.bottom - 20),
      })
    }
    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [open, presentation])

  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) close()
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); close(true) }
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open, close])

  const run = async (action: 'send' | 'reset') => {
    if (inFlight.current || (action === 'reset' && !canReset)) return
    setError(false)
    if (action === 'reset') {
      const step = demoResetStep(armedUntil, Date.now())
      setArmedUntil(step.armedUntil)
      if (!step.reset) return
    } else setArmedUntil(null)
    inFlight.current = true
    setPending(action)
    try {
      if (action === 'send') await api.sendDemoItems()
      else await api.resetDemo()
    } catch {
      setError(true)
      setOpen(true)
      return
    } finally {
      inFlight.current = false
      setPending(null)
    }
    close(true)
    if (action === 'send') onSent()
    else onReset()
  }

  return <div ref={root} className={`brain-demo-tools${presentation ? ' is-demo-presentation' : ''}`}
    onBlur={event => {
      if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) close()
    }}>
    <button ref={trigger} type="button" className="brain-demo-trigger" aria-expanded={open} aria-controls={id}
      onClick={() => { if (open) close(); else { setError(false); setOpen(true) } }}>
      <span className="brain-demo-badge">{c('Demo')}<ChevronDown size={13} aria-hidden="true" /></span>
    </button>
    <div ref={panel} id={id} hidden={!open} className="brain-demo-popover" style={position}>
      <button type="button" className="brain-demo-action" disabled={pending !== null} onClick={() => void run('send')}>
        <Send size={18} aria-hidden="true" />
        <span><strong aria-live="polite">{c(pending === 'send' ? 'Sending…' : 'Send the 3 demo items')}</strong>
          <span>{c('A slide photo, a lecture video and a PDF — the same path as Telegram.')}</span></span>
      </button>
      {canReset && <button type="button" className={`brain-demo-action brain-demo-reset${armedUntil !== null ? ' is-armed' : ''}`}
        disabled={pending !== null} onClick={() => void run('reset')}>
        <RotateCcw size={18} aria-hidden="true" />
        <span><strong aria-live="polite">{c(pending === 'reset' ? 'Starting over…' : armedUntil !== null ? 'Click again to start over' : 'Start over')}</strong>
          <span>{c('Back to the starting Brain. Telegram stays connected.')}</span></span>
      </button>}
      {error && <p className="brain-demo-error" role="alert">{c('Demo tools are unavailable right now.')}</p>}
    </div>
  </div>
}
