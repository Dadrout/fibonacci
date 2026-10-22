'use client'

import { useEffect, useId, useRef, useState } from 'react'
import { Check, GraduationCap } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { MAX_DAYS, daysFromDate, examDateFor, hintForDays } from './brain-exam-logic'

const OPTIONS = [{ days: 1, label: 'Tomorrow' }, { days: 3, label: '3 days' }, { days: 7, label: '1 week' }, { days: 14, label: '2 weeks' }]

/** Shared by setup and the inline ready-plan editor; submit belongs to the enclosing form. */
export function ExamDateChooser({ date, onChange, disabled = false, focusOnMount = false }: {
  date: string; onChange: (date: string) => void; disabled?: boolean; focusOnMount?: boolean
}) {
  const c = useCopy()
  const id = useId()
  const days = daysFromDate(date)
  const [custom, setCustom] = useState(!OPTIONS.some(option => option.days === days))
  const first = useRef<HTMLInputElement>(null)
  useEffect(() => { if (focusOnMount) first.current?.focus() }, [focusOnMount])
  return <div className="brain-exam-date-chooser">
    <fieldset className="brain-exam-field" aria-describedby={`${id}-hint`}>
      <legend>{c('Exam or deadline')}</legend>
      <div className="brain-exam-date-options">
        {OPTIONS.map((option, index) => <label key={option.days}>
          <input ref={index === 0 ? first : undefined} type="radio" name={id} checked={!custom && days === option.days}
            onChange={() => { setCustom(false); onChange(examDateFor(option.days)) }} />
          <span>{!custom && days === option.days && <Check size={14} aria-hidden="true" />}{c(option.label)}</span>
        </label>)}
        <label>
          <input type="radio" name={id} checked={custom} onChange={() => setCustom(true)} />
          <span>{custom && <Check size={14} aria-hidden="true" />}{c('Pick a date')}</span>
        </label>
      </div>
      {custom && <div className="brain-exam-custom-date">
        <label htmlFor={`${id}-date`}>{c('Pick a date')}</label>
        <input id={`${id}-date`} type="date" className="brain-exam-select" min={examDateFor(1)} max={examDateFor(MAX_DAYS)}
          required value={date} onChange={event => onChange(event.target.value)} aria-describedby={`${id}-hint`} />
      </div>}
      <p id={`${id}-hint`} className="brain-exam-hint" aria-live="polite" aria-atomic="true">
        {c(days === null ? 'Choose a date within the next 30 days.' : hintForDays(days))}
      </p>
    </fieldset>
    <button type="submit" className="brain-primary-button brain-exam-build" disabled={disabled || days === null}>
      <GraduationCap size={20} aria-hidden="true" />{c('Build my plan')}
    </button>
  </div>
}
