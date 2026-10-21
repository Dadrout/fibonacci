'use client'

import * as Dialog from '@radix-ui/react-dialog'
import { useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'

/** Shared modal primitive: localised controls, trapped focus and explicit return target. */
export function BrainDialog({ open, onClose, title, description, children, sheet = false, presentation = false }: {
  open: boolean; onClose: () => void; title: string; description: string; children: ReactNode; sheet?: boolean; presentation?: boolean
}) {
  const c = useCopy()
  const returnFocus = useRef<HTMLElement | SVGElement | null>(null)
  return <Dialog.Root open={open} onOpenChange={value => { if (!value) onClose() }}>
    <Dialog.Portal>
      <Dialog.Overlay className="brain-dialog-overlay" />
      <Dialog.Content className={`brain-dialog${sheet ? ' brain-sheet' : ''}${presentation ? ' is-presentation' : ''}`}
        onOpenAutoFocus={() => { returnFocus.current = document.activeElement as HTMLElement | SVGElement | null }}
        onCloseAutoFocus={event => { event.preventDefault(); if (returnFocus.current?.isConnected) returnFocus.current.focus() }}>
        <div className="brain-dialog-heading">
          <div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div>
          <Dialog.Close className="brain-icon-button" aria-label={c('Close source panel')}><X size={21} aria-hidden="true" /></Dialog.Close>
        </div>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
