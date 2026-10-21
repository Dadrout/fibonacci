'use client'

import { learnerStorageKey } from '@/lib/learner-storage'

import { useEffect, useRef, useState } from 'react'
import { useAuth } from './use-auth'
import type { KnowledgeSource, KnowledgeStatus, QuizQuestion } from './use-story-generator'

export interface GenerationResult {
  id: string
  story_id?: string
  draft_id?: string
  video_url?: string
  audio_url?: string
  transcript?: string
  recap?: string
  quiz?: QuizQuestion[]
  sources?: KnowledgeSource[]
  knowledge_status?: KnowledgeStatus
}

interface JobState {
  isPolling: boolean
  progress: number
  status: string
  error: string | null
  result: GenerationResult | null
  draftId: string | null
  generationFailed: boolean
  retry: () => Promise<boolean>
}

export const useStoryPoller = (jobId: string | null): JobState => {
  const { getToken, user } = useAuth()
  const [isPolling, setIsPolling] = useState(true)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('Waiting for video generation…')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [draftId, setDraftId] = useState<string | null>(null)
  const [generationFailed, setGenerationFailed] = useState(false)
  const [pollAttempt, setPollAttempt] = useState(0)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  useEffect(() => {
    setResult(null)
    setError(null)
    setDraftId(null)
    setGenerationFailed(false)
    setProgress(0)
    setStatus('Waiting for video generation…')
    if (!jobId) { setIsPolling(false); return }
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const token = await getToken()
        if (cancelled) return
        if (!token) throw new Error('Your sign-in session has expired. Please sign in again.')
        const response = await fetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`, { headers: { Authorization: `Bearer ${token}` } })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'Could not retrieve this story job.')
        if (cancelled) return
        setProgress(data.progress ?? 0)
        setStatus(data.message || data.stage || 'Working on your video…')
        if (data.draft_id) setDraftId(data.draft_id)
        if (data.status === 'SUCCESS') {
          if (window.localStorage.getItem(learnerStorageKey('job', user!.id)) === jobId) {
            window.localStorage.removeItem(learnerStorageKey('job', user!.id))
          }
          setResult({ ...data.result, transcript: data.result?.script, id: jobId, story_id: data.story_id, draft_id: data.draft_id })
          setIsPolling(false)
        } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
          setGenerationFailed(true)
          setError(data.error || 'Video generation failed. Your draft is saved and ready to retry.')
          setIsPolling(false)
        } else {
          timer = setTimeout(poll, 2000)
        }
      } catch (cause) {
        if (cancelled) return
        setError(cause instanceof Error ? cause.message : 'Could not check video progress.')
        setIsPolling(false)
      }
    }
    setIsPolling(true)
    void poll()
    return () => { cancelled = true; if (timer) clearTimeout(timer) }
  }, [jobId, getToken, pollAttempt])

  const retry = async () => {
    if (!generationFailed) {
      setPollAttempt((attempt) => attempt + 1)
      return true
    }
    if (!draftId) return false
    try {
      const token = await getToken()
      if (!alive.current) return false
      if (!token) throw new Error('Your sign-in session has expired.')
      const response = await fetch(`/api/v1/story-drafts/${encodeURIComponent(draftId)}/render`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: '{}',
      })
      const data = await response.json()
      if (!alive.current) return false
      if (!response.ok) throw new Error(data.detail || 'Could not retry video generation.')
      window.localStorage.setItem(learnerStorageKey('job', user!.id), data.job_id)
      window.location.assign(`/story/${encodeURIComponent(data.job_id)}`)
      return true
    } catch (cause) {
      if (!alive.current) return false
      setError(cause instanceof Error ? cause.message : 'Could not retry video generation.')
      return false
    }
  }

  return { isPolling, progress, status, error, result, draftId, generationFailed, retry }
}
