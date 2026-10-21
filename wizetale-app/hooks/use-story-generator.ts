'use client'

import { learnerStorageKey } from '@/lib/learner-storage'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from './use-auth'
import { trackEvent, trackConversion, trackFunnelStep } from '@/lib/analytics'

export interface StoryScript {
  title: string
  hook: string
  sections: { heading: string; summary: string }[]
  full_narration: string
  estimated_duration_sec: number
}

export interface QuizQuestion {
  question: string
  options: { id: 'a' | 'b' | 'c' | 'd'; text: string }[]
  correct_option: 'a' | 'b' | 'c' | 'd'
  explanation: string
}

export interface KnowledgeSource {
  title: string
  url: string
  publisher?: string
}

export type KnowledgeStatus = 'grounded' | 'partial' | 'none'

export interface StoryDraft {
  id: string
  status: string
  subject: string
  topic: string
  grade_band: string
  target_duration_sec: number
  language: string
  voice: string
  script: StoryScript
  recap: string
  quiz: { recap: string; quiz: QuizQuestion[] }
  sources: KnowledgeSource[]
  knowledge_status: KnowledgeStatus
}

export interface GenerationResult {
  id: string
  job_id: string
  status: string
  video_url?: string
  audio_url?: string
  transcript?: string
  recap?: string
  quiz?: QuizQuestion[]
  sources?: KnowledgeSource[]
  knowledge_status?: KnowledgeStatus
}

interface GenerateParams {
  subject: string
  topic: string
  grade_band: string
  target_duration_sec: number
  voice: string
  language: string
}

async function requestJson<T>(url: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw Object.assign(new Error(data.detail || data.error || `Request failed (${response.status})`), { status: response.status })
  return data as T
}

export const useStoryGenerator = () => {
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<StoryDraft | null>(null)
  const [draftSaveStatus, setDraftSaveStatus] = useState<'saved' | 'saving' | 'error'>('saved')
  const { getToken, user } = useAuth()
  const alive = useRef(true)
  const draftQueue = useRef<Promise<void>>(Promise.resolve())
  const pendingSaves = useRef(0)
  const saveSequence = useRef(0)
  const mutationInProgress = useRef(false)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  const saveDraftId = useCallback((id: string | null) => {
    if (!user) return
    if (typeof window !== 'undefined') {
      if (id) window.localStorage.setItem(learnerStorageKey('draft', user.id), id)
      else window.localStorage.removeItem(learnerStorageKey('draft', user.id))
    }
  }, [user?.id])

  const tokenOrThrow = useCallback(async () => {
    const token = await getToken()
    if (!token) throw new Error('Please sign in again to continue.')
    if (!alive.current) throw new Error("This workspace is no longer active.")
    return token
  }, [getToken])

  const generateStory = useCallback(async (params: GenerateParams) => {
    setIsGenerating(true)
    setError(null)
    setDraft(null)
    try {
      const token = await tokenOrThrow()
      const result = await requestJson<StoryDraft>('/api/v1/story-drafts', token, {
        method: 'POST',
        body: JSON.stringify(params),
      })
      if (!alive.current) return
      setDraft(result)
      saveDraftId(result.id)
      trackFunnelStep('story_script_ready', 1, 3)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not create a story draft.')
    } finally {
      setIsGenerating(false)
    }
  }, [saveDraftId, tokenOrThrow])

  const restoreDraft = useCallback(async () => {
    if (typeof window === 'undefined') return
    const legacyId = window.localStorage.getItem('talespark-current-draft')
    const id = window.localStorage.getItem(learnerStorageKey('draft', user!.id)) || legacyId
    if (!id) return
    try {
      const token = await tokenOrThrow()
      const restored = await requestJson<StoryDraft>(`/api/v1/story-drafts/${encodeURIComponent(id)}`, token)
      if (!alive.current) return
      if (id === legacyId) {
        // Migrate only after the server has confirmed this learner owns it.
        saveDraftId(id)
        window.localStorage.removeItem('talespark-current-draft')
      }
      if (restored.status === 'draft') setDraft(restored)
      else saveDraftId(null)
    } catch (cause) {
      if (!alive.current) return
      if (cause instanceof Error && 'status' in cause && cause.status === 404) saveDraftId(null)
      else setError('Could not restore your draft. Refresh to try again.')
    }
  }, [saveDraftId, tokenOrThrow])

  const restoreDraftById = useCallback(async (id: string): Promise<boolean> => {
    setIsGenerating(true)
    setError(null)
    try {
      const token = await tokenOrThrow()
      const restored = await requestJson<StoryDraft>(`/api/v1/story-drafts/${encodeURIComponent(id)}`, token)
      if (!alive.current) return false
      if (restored.status !== 'draft') {
        setError('This saved draft is no longer available.')
        return false
      }
      setDraft(restored)
      saveDraftId(restored.id)
      return true
    } catch (cause) {
      if (!alive.current) return false
      if (cause instanceof Error && 'status' in cause && cause.status === 404) setError('This saved draft is no longer available.')
      else setError(cause instanceof Error ? cause.message : 'Could not restore your draft. Refresh to try again.')
      return false
    } finally {
      setIsGenerating(false)
    }
  }, [saveDraftId, tokenOrThrow])

  const clearDraft = useCallback(() => {
    setDraft(null)
    saveDraftId(null)
    setDraftSaveStatus('saved')
    setError(null)
  }, [saveDraftId])

  const updateDraft = useCallback(async (script: StoryScript): Promise<StoryDraft | null> => {
    if (!draft || mutationInProgress.current) return null
    const draftId = draft.id
    const sequence = ++saveSequence.current
    pendingSaves.current += 1
    setIsGenerating(true)
    setError(null)
    setDraftSaveStatus('saving')

    const save = draftQueue.current.then(async () => {
      const token = await tokenOrThrow()
      const updated = await requestJson<StoryDraft>(`/api/v1/story-drafts/${encodeURIComponent(draftId)}`, token, {
        method: 'PATCH', body: JSON.stringify({ script }),
      })
      if (!alive.current) return null
      setDraft(updated)
      if (sequence === saveSequence.current) setDraftSaveStatus('saved')
      return updated
    }).catch(cause => {
      if (alive.current && sequence === saveSequence.current) {
        setError(cause instanceof Error ? cause.message : 'Could not save your script edits.')
        setDraftSaveStatus('error')
      }
      return null
    }).finally(() => {
      pendingSaves.current -= 1
      if (pendingSaves.current === 0 && !mutationInProgress.current && alive.current) {
        setIsGenerating(false)
      }
    })
    draftQueue.current = save.then(() => undefined, () => undefined)
    return save
  }, [draft, tokenOrThrow])

  const discardDraft = useCallback(async (): Promise<boolean> => {
    if (!draft || mutationInProgress.current) return false
    const draftId = draft.id
    mutationInProgress.current = true
    setIsGenerating(true)
    setError(null)
    setDraftSaveStatus('saving')
    try {
      await draftQueue.current
      const token = await tokenOrThrow()
      await requestJson<unknown>(`/api/v1/story-drafts/${encodeURIComponent(draftId)}`, token, {
        method: 'DELETE',
      })
      if (!alive.current) return false
      setDraft(null)
      saveDraftId(null)
      setDraftSaveStatus('saved')
      return true
    } catch (cause) {
      if (!alive.current) return false
      const statusCode = typeof cause === 'object' && cause !== null && 'status' in cause
        ? Number(cause.status)
        : 0
      if (statusCode === 404) {
        setDraft(null)
        saveDraftId(null)
        setDraftSaveStatus('saved')
        return true
      }
      setError(cause instanceof Error ? cause.message : 'Could not discard your draft.')
      setDraftSaveStatus('error')
      return false
    } finally {
      mutationInProgress.current = false
      if (pendingSaves.current === 0 && alive.current) setIsGenerating(false)
    }
  }, [draft, saveDraftId, tokenOrThrow])

  const flushDraft = useCallback(async (script: StoryScript | null): Promise<boolean> => {
    if (!draft || !script) {
      await draftQueue.current
      return true
    }

    const hasUnsavedChanges = JSON.stringify(script) !== JSON.stringify(draft.script)
    if (hasUnsavedChanges || pendingSaves.current > 0) {
      // Queue the current editor snapshot after any earlier autosaves so it wins
      // even when the learner changed the text back while a save was pending.
      return Boolean(await updateDraft(script))
    }

    await draftQueue.current
    return true
  }, [draft, updateDraft])

  const renderDraft = useCallback(async (script: StoryScript): Promise<string | null> => {
    if (!draft || mutationInProgress.current) return null
    const draftId = draft.id
    mutationInProgress.current = true
    setIsGenerating(true)
    setError(null)
    setDraftSaveStatus('saving')
    let scriptSaved = false
    const render = draftQueue.current.then(async () => {
      const token = await tokenOrThrow()
      const updated = await requestJson<StoryDraft>(`/api/v1/story-drafts/${encodeURIComponent(draftId)}`, token, {
        method: 'PATCH', body: JSON.stringify({ script }),
      })
      if (!alive.current) return null
      setDraft(updated)
      setDraftSaveStatus('saved')
      scriptSaved = true
      const job = await requestJson<{ job_id: string }>(`/api/v1/story-drafts/${encodeURIComponent(draftId)}/render`, token, {
        method: 'POST', body: JSON.stringify({}),
      })
      if (!alive.current) return null
      trackFunnelStep('story_video_started', 2, 3)
      trackEvent('generate_story_video')
      return job.job_id
    }).catch(cause => {
      if (alive.current) {
        setError(cause instanceof Error ? cause.message : 'Could not start video generation.')
        if (!scriptSaved) setDraftSaveStatus('error')
      }
      return null
    }).finally(() => {
      mutationInProgress.current = false
      if (pendingSaves.current === 0 && alive.current) setIsGenerating(false)
    })
    draftQueue.current = render.then(() => undefined, () => undefined)
    return render
  }, [draft, tokenOrThrow])

  const completeStory = useCallback((jobId: string) => {
    trackConversion('story_generated', 1)
    trackEvent('story_generation_completed')
    trackFunnelStep('story_generation_completed', 3, 3)
  }, [])

  return { isGenerating, error, draft, draftSaveStatus, generateStory, updateDraft, flushDraft, renderDraft, completeStory, restoreDraft, restoreDraftById, clearDraft, discardDraft }
}
