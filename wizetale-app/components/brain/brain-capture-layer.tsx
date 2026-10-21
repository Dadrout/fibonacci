'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { FileUp, Link2, LoaderCircle, X } from 'lucide-react'
import { useBrainApi, useBrainSession } from '@/hooks/use-brain-api'
import { useCopy } from '@/hooks/use-copy'
import { BRAIN_ACCEPT, BRAIN_MAX_UPLOAD_BYTES, BrainApiError } from '@/lib/brain-api'
import type { CaptureChannel } from '@/lib/brain-types'

type CaptureJob = {
  id: string
  title: string
  status: 'working' | 'done' | 'error'
  progress: number | null
  message: string
}

function newId() {
  return globalThis.crypto?.randomUUID?.() ?? `capture-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function isAcceptedFile(file: File) {
  const name = file.name.toLowerCase()
  return file.type.startsWith('image/')
    || file.type === 'application/pdf'
    || file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    || file.type === 'text/plain'
    || file.type.startsWith('audio/')
    || ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.heic', '.heif', '.pdf', '.docx', '.txt', '.m4a', '.mp3', '.ogg', '.oga', '.opus', '.wav', '.webm'].some((extension) => name.endsWith(extension))
}

function isUrl(value: string): boolean {
  try {
    const parsed = new URL(value.trim())
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
  } catch {
    return false
  }
}

function isEditable(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || Boolean(target.closest('input, textarea, select, [contenteditable="true"], [contenteditable=""], [role="textbox"]'))
}

export function BrainCaptureLayer() {
  const api = useBrainApi()
  const session = useBrainSession()
  const c = useCopy()
  const inputRef = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const [dragging, setDragging] = useState(false)
  const [jobs, setJobs] = useState<CaptureJob[]>([])

  const updateJob = useCallback((id: string, patch: Partial<CaptureJob>) => {
    setJobs((current) => current.map((job) => job.id === id ? { ...job, ...patch } : job))
  }, [])

  const removeLater = useCallback((id: string) => {
    window.setTimeout(() => setJobs((current) => current.filter((job) => job.id !== id)), 5200)
  }, [])

  const errorCopy = useCallback((error: unknown) => {
    if (!(error instanceof BrainApiError)) return c('Capture could not finish. Check your connection and try again.')
    if (error.code === 'unsupported_type') return c('This file type is not supported.')
    if (error.code === 'too_large') return c('Choose a file up to 20 MB.')
    if (error.code === 'invalid_input') return c('This source is empty or invalid.')
    if (error.code === 'rate_limited') return c('Too many captures at once. Try again shortly.')
    return c('Capture could not finish. Check your connection and try again.')
  }, [c])

  const addFile = useCallback(async (file: File, channel: Extract<CaptureChannel, 'web_drop' | 'web_picker'>) => {
    const id = newId()
    if (!file.size) {
      setJobs((current) => [{ id, title: file.name || c('Pasted image'), status: 'error' as const, progress: null, message: c('Choose a nonempty file.') }, ...current].slice(0, 3))
      return
    }
    if (file.size > BRAIN_MAX_UPLOAD_BYTES) {
      setJobs((current) => [{ id, title: file.name, status: 'error' as const, progress: null, message: c('Choose a file up to 20 MB.') }, ...current].slice(0, 3))
      return
    }
    if (!isAcceptedFile(file)) {
      setJobs((current) => [{ id, title: file.name, status: 'error' as const, progress: null, message: c('This file type is not supported.') }, ...current].slice(0, 3))
      return
    }

    setJobs((current) => [{ id, title: file.name, status: 'working' as const, progress: 0, message: c('Adding source') }, ...current].slice(0, 3))
    try {
      await api.captureFile(file, { channel, onUploadProgress: (progress) => updateJob(id, { progress }) })
      updateJob(id, { status: 'done', progress: 1, message: c('Added to your Brain') })
      removeLater(id)
    } catch (error) {
      updateJob(id, { status: 'error', progress: null, message: errorCopy(error) })
    }
  }, [api, c, errorCopy, removeLater, updateJob])

  const addText = useCallback(async (text: string, channel: Extract<CaptureChannel, 'web_drop' | 'web_paste' | 'web_picker'>, title?: string) => {
    const value = text.trim()
    if (!value) return
    const id = newId()
    setJobs((current) => [{ id, title: title || (isUrl(value) ? value : c('Pasted notes')), status: 'working' as const, progress: null, message: c('Adding source') }, ...current].slice(0, 3))
    try {
      if (isUrl(value)) await api.captureLink(value, channel)
      else await api.captureText(value, title, channel)
      updateJob(id, { status: 'done', progress: 1, message: c('Added to your Brain') })
      removeLater(id)
    } catch (error) {
      updateJob(id, { status: 'error', progress: null, message: errorCopy(error) })
    }
  }, [api, c, errorCopy, removeLater, updateJob])

  const pickFiles = useCallback(() => inputRef.current?.click(), [])

  useEffect(() => {
    if (!session.canUse) return
    const openPicker = () => pickFiles()
    const onDragEnter = (event: DragEvent) => {
      const types = Array.from(event.dataTransfer?.types ?? [])
      if (!types.includes('Files') && !types.includes('text/uri-list') && !types.includes('text/plain')) return
      event.preventDefault()
      dragDepth.current += 1
      setDragging(true)
    }
    const onDragOver = (event: DragEvent) => {
      const types = Array.from(event.dataTransfer?.types ?? [])
      if (!types.includes('Files') && !types.includes('text/uri-list') && !types.includes('text/plain')) return
      event.preventDefault()
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
    }
    const onDragLeave = (event: DragEvent) => {
      const target = event.relatedTarget
      if (target instanceof Node && document.documentElement.contains(target)) return
      dragDepth.current = 0
      setDragging(false)
    }
    const onDrop = (event: DragEvent) => {
      const transfer = event.dataTransfer
      if (!transfer) return
      const files = Array.from(transfer.files ?? [])
      const uri = transfer.getData('text/uri-list').split('\n').find((line) => line.trim() && !line.startsWith('#'))?.trim()
      const text = transfer.getData('text/plain').trim()
      if (!files.length && !uri && !text) return
      event.preventDefault()
      dragDepth.current = 0
      setDragging(false)
      files.forEach((file) => void addFile(file, 'web_drop'))
      if (uri || text) void addText(uri || text, 'web_drop')
    }
    const onPaste = (event: ClipboardEvent) => {
      if (isEditable(event.target) || isEditable(document.activeElement)) return
      const clipboard = event.clipboardData
      if (!clipboard) return
      const images = Array.from(clipboard.items)
        .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
        .map((item) => item.getAsFile())
        .filter((file): file is File => Boolean(file))
      if (images.length) {
        event.preventDefault()
        images.forEach((image, index) => {
          const file = image.name ? image : new File([image], `pasted-image-${index + 1}.png`, { type: image.type, lastModified: Date.now() })
          void addFile(file, 'web_drop')
        })
        return
      }
      const uri = clipboard.getData('text/uri-list').split('\n').find((line) => line.trim() && !line.startsWith('#'))?.trim()
      const text = uri || clipboard.getData('text/plain').trim()
      if (!text) return
      event.preventDefault()
      void addText(text, 'web_paste')
    }

    window.addEventListener('brain:open-picker', openPicker)
    window.addEventListener('dragenter', onDragEnter)
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('drop', onDrop)
    window.addEventListener('paste', onPaste)
    return () => {
      window.removeEventListener('brain:open-picker', openPicker)
      window.removeEventListener('dragenter', onDragEnter)
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('drop', onDrop)
      window.removeEventListener('paste', onPaste)
    }
  }, [addFile, addText, pickFiles, session.canUse])

  if (!session.canUse) return null

  return <>
    <input
      ref={inputRef}
      className="brain-file-input"
      type="file"
      accept={BRAIN_ACCEPT}
      multiple
      tabIndex={-1}
      aria-label={c('Choose files to add to your Brain')}
      onChange={(event) => {
        Array.from(event.currentTarget.files ?? []).forEach((file) => void addFile(file, 'web_picker'))
        event.currentTarget.value = ''
      }}
    />
    {dragging && <div className="brain-drop-overlay" aria-hidden="true"><div><Link2 size={28} /><strong>{c('Drop it into your Brain')}</strong><span>{c('Files, links, or selected text')}</span></div></div>}
    {jobs.length > 0 && <section className="brain-capture-jobs" aria-label={c('Capture status')} aria-live="polite">
      {jobs.map((job) => <div className={`brain-capture-job is-${job.status}`} key={job.id}>
        <span className="brain-capture-job-icon">{job.status === 'working' ? <LoaderCircle size={18} className="brain-spin" aria-hidden="true" /> : job.status === 'done' ? <FileUp size={18} aria-hidden="true" /> : <X size={18} aria-hidden="true" />}</span>
        <span className="brain-capture-job-copy"><strong>{job.title}</strong><span>{job.message}</span>{job.status === 'working' && job.progress !== null && <span className="brain-upload-meter" role="progressbar" aria-label={c('Upload progress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(job.progress * 100)}><span style={{ transform: `scaleX(${Math.max(0, Math.min(1, job.progress))})` }} /></span>}</span>
        {job.status === 'error' && <button type="button" className="brain-job-dismiss" aria-label={`${c('Dismiss')}: ${job.title}`} onClick={() => setJobs((current) => current.filter((entry) => entry.id !== job.id))}><X size={17} /></button>}
      </div>)}
    </section>}
    <button className="brain-global-add" type="button" onClick={pickFiles}><FileUp size={20} aria-hidden="true" /><span>{c('Add')}</span></button>
  </>
}
