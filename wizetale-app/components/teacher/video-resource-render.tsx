'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Download, RotateCcw, Video } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { useTeacherAPI } from '@/hooks/use-teacher-api'
import { currentVideoPlaybackUrl, TeacherVideoRender } from '@/lib/teacher-content'

export function VideoResourceRender({
  lessonId,
  resourceId,
  revision,
  disabled,
}: {
  lessonId: string
  resourceId: string
  revision: number
  disabled: boolean
}) {
  const c = useCopy()
  const api = useTeacherAPI()
  const identity = `${lessonId}:${resourceId}:${revision}`
  const identityRef = useRef(identity)
  identityRef.current = identity
  const [render, setRender] = useState<TeacherVideoRender | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [pollRetry, setPollRetry] = useState(0)
  const playbackUrl = currentVideoPlaybackUrl(render, revision)

  const refresh = useCallback(async () => {
    const requestIdentity = identity
    try {
      const latest = await api.latestVideoRender(lessonId, resourceId)
      if (requestIdentity !== identityRef.current) return
      setRender(latest)
      setError('')
    } catch {
      if (requestIdentity !== identityRef.current) return
      setRender(null)
    }
  }, [api, identity, lessonId, resourceId])

  useEffect(() => { void refresh() }, [refresh, revision])

  const working = render?.status === 'queued' || render?.status === 'processing'
  useEffect(() => {
    if (!working || !render) return
    const requestIdentity = identity
    const requestRenderId = render.id
    const timer = window.setTimeout(() => {
      void api.pollVideoRender(render.id)
        .then(updated => {
          if (
            requestIdentity !== identityRef.current ||
            updated.id !== requestRenderId ||
            updated.resource_revision !== revision
          ) return
          setRender(updated)
          setError('')
        })
        .catch(() => {
          if (requestIdentity !== identityRef.current) return
          setError('The video status could not be refreshed.')
          setPollRetry(attempt => attempt + 1)
        })
    }, 2200)
    return () => window.clearTimeout(timer)
  }, [api, identity, render, revision, working, pollRetry])

  async function start() {
    const requestIdentity = identity
    setBusy(true)
    setError('')
    try {
      const started = await api.startVideoRender(lessonId, resourceId)
      if (
        requestIdentity !== identityRef.current ||
        started.resource_revision !== revision
      ) return
      setRender(started)
    } catch (reason) {
      if (requestIdentity !== identityRef.current) return
      setError(reason instanceof Error ? reason.message : 'Could not start video render. Try again.')
    } finally {
      if (requestIdentity === identityRef.current) setBusy(false)
    }
  }

  async function download() {
    if (!render || !playbackUrl) return
    const requestIdentity = identity
    const requestRenderId = render.id
    setBusy(true)
    setError('')
    try {
      const blob = await api.downloadVideo(requestRenderId)
      if (requestIdentity !== identityRef.current || requestRenderId !== render?.id) return
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = 'fibonacci-topic-video.mp4'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch (reason) {
      if (requestIdentity !== identityRef.current) return
      setError(reason instanceof Error ? reason.message : 'The topic video could not be downloaded.')
    } finally {
      if (requestIdentity === identityRef.current) setBusy(false)
    }
  }

  const canStart = !working && !playbackUrl
  const canRetry = render?.status === 'failed' || render?.status === 'cancelled'
  return <section className="prep-card prep-video-render" aria-labelledby="prep-topic-video-title">
    <div className="prep-section-heading"><div><p className="prep-eyebrow">{c('Lesson video')}</p><h2 id="prep-topic-video-title">{c('Illustrated topic video')}</h2><p>{c('Render your reviewed script as an illustrated narrated video.')}</p></div><Video size={28} aria-hidden="true"/></div>
    {error&&<p className="prep-error" role="alert">{c(error)}</p>}
    {working&&render&&<div className="prep-render-progress" aria-live="polite"><div><strong>{c(render.message)}</strong><span>{render.progress}%</span></div><progress max={100} value={render.progress} aria-label={c('Video render progress')}/><p className="prep-hint">{c('You can keep working while your video renders.')}</p></div>}
    {playbackUrl&&render&&<div className="prep-video-result"><video controls preload="metadata" src={playbackUrl} aria-label={c('Topic video playback')}/><div className="prep-source-actions"><button type="button" className="prep-button primary" onClick={()=>void download()} disabled={busy}><Download size={17} aria-hidden="true"/>{c(busy?'Preparing download…':'Download MP4')}</button><span className="prep-hint">{c('Video ready')}{render.duration_sec ? <> · {Math.round(render.duration_sec)} {c('seconds')}</> : null}</span></div></div>}
    {render?.status==='failed'&&<p className="prep-hint" role="status">{c('The video could not be completed. You can retry the render.')}</p>}
    {render?.status==='cancelled'&&<p className="prep-hint" role="status">{c('The saved script changed. Render the current version again.')}</p>}
    {render?.status==='ready'&&!playbackUrl&&<p className="prep-hint" role="status">{c('The saved script changed. Render the current version again.')}</p>}
    {canStart&&<button type="button" className="prep-button primary" disabled={disabled||busy} onClick={()=>void start()}>{canRetry?<RotateCcw size={17} aria-hidden="true"/>:<Video size={17} aria-hidden="true"/>}{c(busy?'Starting…':canRetry?'Retry video render':'Render topic video')}</button>}
  </section>
}
