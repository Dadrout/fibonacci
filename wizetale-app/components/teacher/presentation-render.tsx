'use client'

import { useCallback, useEffect, useState } from 'react'
import { Download, RotateCcw, Video } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { useCopy } from '@/hooks/use-copy'
import { useTeacherAPI } from '@/hooks/use-teacher-api'

type RenderStatus = 'queued' | 'processing' | 'ready' | 'failed' | 'cancelled'
type RenderJob = { id: string; status: RenderStatus; progress: number; stage: string; message: string; error?: string|null; video_url?: string|null; duration_sec?: number|null }

export function PresentationRender({ lessonId, resourceId, disabled, visualsPending = false }: { lessonId: string; resourceId: string; disabled: boolean; visualsPending?: boolean }) {
  const c = useCopy()
  const api = useTeacherAPI()
  const { getToken } = useAuth()
  const [render, setRender] = useState<RenderJob|null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      setRender(await api<RenderJob>(`lessons/${lessonId}/resources/${resourceId}/render`))
    } catch {
      setRender(null)
    }
  }, [api, lessonId, resourceId])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!render || !['queued','processing'].includes(render.status)) return
    const timer = window.setTimeout(() => {
      void api<RenderJob>(`presentation-renders/${render.id}`).then(setRender).catch(() => setError('The video status could not be refreshed.'))
    }, 2500)
    return () => window.clearTimeout(timer)
  }, [api, render])

  async function start() {
    setBusy(true)
    setError('')
    try {
      setRender(await api<RenderJob>(`lessons/${lessonId}/resources/${resourceId}/render`, 'POST', {}))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : c('Could not start video render. Try again.'))
    } finally {
      setBusy(false)
    }
  }

  async function download() {
    if (!render) return
    setBusy(true)
    setError('')
    try {
      const token = await getToken()
      if (!token) throw new Error(c('Sign in to continue.'))
      const response = await fetch(`/api/v1/teacher/presentation-renders/${encodeURIComponent(render.id)}/video`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
      if (!response.ok) throw new Error(c('The presentation video could not be downloaded.'))
      const objectUrl = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = 'fibonacci-presentation.mp4'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : c('The presentation video could not be downloaded.'))
    } finally {
      setBusy(false)
    }
  }

  const working = render?.status === 'queued' || render?.status === 'processing'
  return <section className="prep-card prep-video-render" aria-labelledby="prep-video-title">
    <div className="prep-section-heading"><div><p className="prep-eyebrow">{c('Narrated presentation')}</p><h2 id="prep-video-title">{c('Turn your slides into a video')}</h2><p>{c('Add a natural voice-over to your saved slides and download the finished MP4.')}</p></div><Video size={28} aria-hidden="true"/></div>
    {error&&<p className="prep-error" role="alert">{c(error)}</p>}
    {visualsPending&&<p className="prep-hint" role="status">{c('Wait for slide visuals to finish before rendering this video.')}</p>}
    {render&&working&&<div className="prep-render-progress"><div><strong>{c(render.message)}</strong><span>{render.progress}%</span></div><progress max={100} value={render.progress} aria-label={c('Video render progress')}/><p className="prep-hint">{c('You can keep working while your video renders.')}</p></div>}
    {render?.status==='ready'&&render.video_url&&<div className="prep-video-result"><video controls preload="metadata" src={render.video_url} aria-label={c('Narrated presentation video')} /><div className="prep-source-actions"><button type="button" className="prep-button primary" onClick={()=>void download()} disabled={busy}><Download size={17} aria-hidden="true"/>{c(busy?'Preparing download…':'Download MP4')}</button><span className="prep-hint">{c('Video ready')}</span></div></div>}
    {render?.status==='failed'&&<p className="prep-hint" role="status">{c('The video could not be completed. You can retry the render.')}</p>}
    {!working&&render?.status!=='ready'&&<button type="button" className="prep-button primary" disabled={disabled||visualsPending||busy} onClick={()=>void start()}>{render?.status==='failed'?<RotateCcw size={17} aria-hidden="true"/>:<Video size={17} aria-hidden="true"/>}{c(busy?'Starting…':render?.status==='failed'?'Retry video render':'Render narrated video')}</button>}
  </section>
}
