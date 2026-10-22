'use client'

import Image from 'next/image'
import { useEffect, useRef, useState } from 'react'
import { ExternalLink, FileText, Quote, RotateCcw, Video } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import type { SourceRef } from '@/lib/brain-types'
import { formatTimestamp, youtubeEmbedUrl } from '@/lib/brain-api-helpers'
import { BrainDialog } from './brain-dialog'
import { sourceLabel, sourceOpenUrl } from './source-viewer-helpers'

function useSourceLabel(source: SourceRef) {
  const c = useCopy()
  const { language } = useLanguage()
  const anchor = source.anchor
  return sourceLabel(source, c, language, anchor.kind === 'timestamp' ? `${formatTimestamp(anchor.start_sec)}–${formatTimestamp(anchor.end_sec)}` : '')
}

/** Can own its dialog or delegate to a shared viewer in an exam/mistake surface. */
export function CitationChip({ source, onOpen, presentation = false }: { source: SourceRef; onOpen?: (source: SourceRef) => void; presentation?: boolean }) {
  const label = useSourceLabel(source)
  const [open, setOpen] = useState(false)
  return <>
    <button type="button" className="brain-citation-chip" aria-label={`${label} · ${source.item_title}`} onClick={() => onOpen ? onOpen(source) : setOpen(true)}>
      <Quote size={15} aria-hidden="true" /><span>{label}</span>
    </button>
    {!onOpen && <SourceViewer source={open ? source : null} onClose={() => setOpen(false)} presentation={presentation} />}
  </>
}

function SourceImage({ url, title, video = false }: { url: string | null; title: string; video?: boolean }) {
  const [failed, setFailed] = useState(false)
  const c = useCopy()
  if (!url || failed) return <div className="brain-media-unavailable">{video ? <Video size={30} aria-hidden="true" /> : <FileText size={30} aria-hidden="true" />}<span>{c('Preview unavailable. The source excerpt is below.')}</span></div>
  return <Image className="brain-source-image" src={url} alt={title} width={960} height={540} unoptimized onError={() => setFailed(true)} />
}

function SourceVideo({ source }: { source: SourceRef }) {
  const c = useCopy()
  const iframe = useRef<HTMLIFrameElement>(null)
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<'loading' | 'ready' | 'unavailable'>('loading')
  const anchor = source.anchor
  useEffect(() => {
    setState(navigator.onLine ? 'loading' : 'unavailable')
    const offline = () => setState('unavailable')
    window.addEventListener('offline', offline)
    // iframe load also fires for error pages; only a player handshake counts as ready.
    const receive = (event: MessageEvent) => {
      if (event.source !== iframe.current?.contentWindow || !['https://www.youtube-nocookie.com', 'https://www.youtube.com'].includes(event.origin)) return
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
        if (data?.event === 'onError') setState('unavailable')
        else if (['onReady', 'initialDelivery', 'infoDelivery'].includes(data?.event)) setState('ready')
      } catch { /* Ignore unrelated window messages. */ }
    }
    window.addEventListener('message', receive)
    const listen = window.setInterval(() => {
      const player = iframe.current?.contentWindow
      player?.postMessage(JSON.stringify({ event: 'listening' }), 'https://www.youtube-nocookie.com')
      player?.postMessage(JSON.stringify({ event: 'command', func: 'addEventListener', args: ['onError'] }), 'https://www.youtube-nocookie.com')
    }, 750)
    const timeout = window.setTimeout(() => {
      window.clearInterval(listen)
      setState(current => current === 'loading' ? 'unavailable' : current)
    }, 8000)
    return () => { window.clearTimeout(timeout); window.clearInterval(listen); window.removeEventListener('message', receive); window.removeEventListener('offline', offline) }
  }, [attempt])
  if (anchor.kind !== 'timestamp' || !source.youtube_id) return null
  return <div className="brain-video-block">
    <div className="brain-video-frame">
      {state !== 'ready' && <SourceImage key={source.thumbnail_url} url={source.thumbnail_url} title={source.item_title} video />}
      {state !== 'unavailable' && <iframe key={attempt} ref={iframe} title={source.item_title}
        src={youtubeEmbedUrl(source.youtube_id, anchor.start_sec, anchor.end_sec)}
        className={state === 'ready' ? 'is-ready' : ''} tabIndex={state === 'ready' ? 0 : -1}
        allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />}
    </div>
    {state !== 'ready' && <div className="brain-media-status" role="status"><span>{c(state === 'loading' ? 'Loading video. You can read the excerpt now.' : 'Video unavailable. Your quote and timestamp are still here.')}</span>{state === 'unavailable' && <button type="button" className="brain-secondary-button" onClick={() => setAttempt(value => value + 1)}>{c('Retry')}</button>}</div>}
  </div>
}

function SourceAudio({ source }: { source: SourceRef }) {
  const c = useCopy()
  const audio = useRef<HTMLAudioElement>(null)
  const [failed, setFailed] = useState(false)
  const anchor = source.anchor
  if (anchor.kind !== 'timestamp' || !source.media_url) return null
  const seek = () => {
    if (!audio.current) return
    try { audio.current.currentTime = Math.max(0, Math.min(anchor.start_sec, Number.isFinite(audio.current.duration) ? audio.current.duration : anchor.start_sec)) } catch { setFailed(true) }
  }
  return <div className="brain-source-audio">
    <audio ref={audio} controls preload="metadata" src={source.media_url} onLoadedMetadata={seek} onError={() => setFailed(true)} aria-label={source.item_title} />
    <button className="brain-secondary-button" type="button" onClick={seek}><RotateCcw size={16} aria-hidden="true" />{c('Back to cited moment')}</button>
    {failed && <p role="status">{c('Audio unavailable. Your quote and timestamp are still here.')}</p>}
  </div>
}

function SourceContents({ source }: { source: SourceRef }) {
  const c = useCopy()
  const label = useSourceLabel(source)
  const anchor = source.anchor
  const openUrl = sourceOpenUrl(source)
  return <div className="brain-source-contents">
    <p className="brain-source-location">{label}</p>
    {anchor.kind === 'timestamp' && source.youtube_id ? <SourceVideo source={source} /> : anchor.kind === 'timestamp' && source.media_url ? <SourceAudio source={source} /> : anchor.kind === 'slide' ? <SourceImage url={source.media_url ?? source.thumbnail_url} title={label} /> : anchor.kind === 'page' && source.thumbnail_url ? <SourceImage url={source.thumbnail_url} title={label} /> : null}
    <div className="brain-source-excerpt"><h3>{c('From your source')}</h3><blockquote>{source.quote || c('No excerpt is available for this source.')}</blockquote></div>
    {openUrl && <a className="brain-secondary-button" href={openUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} aria-hidden="true" />{c(anchor.kind === 'page' ? 'Open this page in the original' : 'Open original source')}</a>}
  </div>
}

export function SourceViewer({ source, onClose, presentation = false, note }: { source: SourceRef | null; onClose: () => void; presentation?: boolean; note?: { title: string; text: string } }) {
  const c = useCopy()
  return <BrainDialog open={Boolean(source)} onClose={onClose} title={source?.item_title ?? c('Source')} description={c('The exact place in your material.')} presentation={presentation}>
    {source && note && <div className="brain-exam-moment-note"><p>{note.title}</p><strong>{note.text}</strong></div>}
    {source && <SourceContents key={`${source.item_id}:${source.chunk_id}`} source={source} />}
  </BrainDialog>
}
