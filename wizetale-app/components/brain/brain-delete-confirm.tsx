'use client'

import { useEffect, useId, useRef } from 'react'
import { useCopy } from '@/hooks/use-copy'

/** Inline, explicit confirmation shared by source, lesson and course deletion. */
export function BrainDeleteConfirm({ message, label, busy, error, onConfirm, onCancel }: {
  message: string; label: string; busy: boolean; error?: string | null
  onConfirm: () => void; onCancel: () => void
}) {
  const c = useCopy()
  const id = useId()
  const confirm = useRef<HTMLButtonElement>(null)
  useEffect(() => { confirm.current?.focus() }, [])
  return <div className="brain-delete-confirm" role="group" aria-labelledby={id} aria-busy={busy}
    onKeyDown={event => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        if (!busy) onCancel()
      }
    }}>
    <p id={id}>{message}</p>
    <div className="brain-delete-actions">
      <button ref={confirm} type="button" className="brain-secondary-button brain-delete-button" disabled={busy} onClick={onConfirm}>{busy ? c('Deleting…') : label}</button>
      <button type="button" className="brain-text-button" disabled={busy} onClick={onCancel}>{c('Cancel')}</button>
    </div>
    {error && <p className="brain-item-action-error" role="alert">{error}</p>}
  </div>
}
