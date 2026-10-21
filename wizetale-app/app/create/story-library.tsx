'use client'

import { useStudentWorkspace } from '@/lib/student-workspace-context'
import { normalizeStudentSubject, studentSubjects } from '@/lib/student-workspace'
import { learnerStorageKey } from '@/lib/learner-storage'

import { useCopy } from '@/hooks/use-copy'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'

import { useEffect, useReducer, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useAuth } from '@/hooks/use-auth'
import { initialStoryHistoryState, reduceStoryHistory, type StoryHistoryRecord } from '@/lib/student-history-state'

type StoryRecord = StoryHistoryRecord

const PAGE_SIZE = 25

export default function StoryLibrary() {
  const c = useCopy()
  const workspace = useStudentWorkspace()

  const { user, loading, getToken } = useAuth()
  const [history, dispatch] = useReducer(reduceStoryHistory, initialStoryHistoryState)
  const [initialAttempt, setInitialAttempt] = useState(0)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const appendInFlight = useRef(false)
  const { stories, busy, initialError, moreError, hasMore, loadingMore, retryOffset } = history

  useEffect(() => {
    if (user) setActiveJobId(window.localStorage.getItem(learnerStorageKey('job', user.id)))
    let cancelled = false
    if (loading) return
    if (!user) {
      return
    }
    dispatch({ type: 'initialStarted' })
    void (async () => {
      try {
        const token = await getToken()
        if (!token) throw new Error(c("Please sign in again to view your stories."))
        const response = await fetch(`/api/v1/stories?limit=${PAGE_SIZE}&offset=0`, { headers: { Authorization: `Bearer ${token}` } })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || c("Could not load your stories."))
        if (!cancelled) {
          dispatch({ type: 'initialSucceeded', stories: data, hasMore: data.length === PAGE_SIZE })
        }
      } catch (cause) {
        if (!cancelled) dispatch({
          type: 'initialFailed',
          error: cause instanceof Error ? cause.message : c("Could not load your stories."),
        })
      }
    })()
    return () => { cancelled = true }
  }, [loading, user, getToken, initialAttempt])

  async function loadMoreStories(retryOffset?: number) {
    if (appendInFlight.current || !hasMore) return
    const offset = retryOffset ?? stories.length
    appendInFlight.current = true
    dispatch({ type: 'appendStarted' })
    try {
      const token = await getToken()
      if (!token) throw new Error(c("Please sign in again to view your stories."))
      const response = await fetch(`/api/v1/stories?limit=${PAGE_SIZE}&offset=${offset}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || c("Could not load more stories."))
      dispatch({ type: 'appendSucceeded', stories: data, hasMore: data.length === PAGE_SIZE })
    } catch (cause) {
      dispatch({
        type: 'appendFailed',
        error: cause instanceof Error ? cause.message : c("Could not load more stories."),
        offset,
      })
    } finally {
      appendInFlight.current = false
    }
  }

  function openSavedStory(story: StoryRecord) {
    workspace.setSetup(current => ({ ...current, subject: normalizeStudentSubject(story.subject), topic: story.topic }))
    workspace.openStory(story.task_id)
  }

  return (
    <section className="student-story-library text-foreground">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-4xl font-bold"> {c("My stories")} </h1>
        <p className="mt-2 text-base leading-relaxed text-muted-foreground"> {c("Your completed learning videos and recaps.")} </p>

        {activeJobId && (
          <button type="button" onClick={() => workspace.openStory(activeJobId)} className="mt-6 inline-flex min-h-11 items-center rounded-xl border border-border bg-secondary px-4 py-3 text-base font-semibold text-secondary-foreground hover:bg-accent"> {c("Resume video in progress")} </button>
        )}
        {busy && <p className="mt-8 text-base"> {c("Loading your stories…")} </p>}
        {initialError && <div className="mt-8 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-base text-destructive">
          <p role="alert">{c(initialError)}</p>
          <button type="button" onClick={() => setInitialAttempt((attempt) => attempt + 1)} className="mt-3 min-h-11 rounded-lg border border-destructive/40 px-4 py-2 font-semibold">{c('Retry loading stories')}</button>
        </div>}
        {!busy && !initialError && stories.length === 0 && (
          <section className="student-empty-shelf mt-8 rounded-3xl border border-border bg-card p-8 text-card-foreground">
            <img className="student-empty-art" src="/illustrations/empty-library.png" alt="" width={132} height={132} loading="lazy"/>
            <h2 className="text-2xl font-bold"> {c("Your story shelf is empty")} </h2>
            <p className="mt-2 text-base leading-relaxed text-muted-foreground"> {c("Create your first narrated learning story and it will show up here.")} </p>
            <button type="button" onClick={() => { workspace.selectMode('story'); workspace.openStory(null) }} className="mt-5 inline-flex min-h-11 items-center rounded-xl bg-primary px-5 py-3 text-base font-bold text-primary-foreground"> {c("Create a story")} </button>
          </section>
        )}
        <div className="mt-7 grid gap-5 sm:grid-cols-2">
          {stories.map((story) => (
            <article key={story.id} className="rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm">
              <p className="text-sm font-bold uppercase tracking-wider text-primary">{c(studentSubjects.find(item => item.value === normalizeStudentSubject(story.subject))?.label || story.subject)}</p>
              <h2 className="mt-2 text-2xl font-bold">{story.title || story.topic}</h2>
              <p className="mt-2 text-base text-muted-foreground">{new Date(story.created_at).toLocaleDateString()}</p>
              {story.result?.recap && <p className="mt-3 line-clamp-3 text-base leading-7">{story.result.recap}</p>}
              <div className="mt-5 flex flex-wrap gap-3">
                <button type="button" onClick={() => openSavedStory(story)} className="inline-flex min-h-11 items-center rounded-lg bg-primary px-4 py-2 text-base font-semibold text-primary-foreground"> {c("Open story")} </button>
                {story.result?.video_url && <a href={story.result.video_url} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 py-2 text-base font-semibold hover:bg-muted"> {c("Play video")} </a>}
              </div>
            </article>
          ))}
        </div>
        {hasMore && !initialError && (
          <div className="mt-7 flex flex-col items-center gap-3">
            {moreError && <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-base text-destructive">{c(moreError)}</p>}
            <button
              type="button"
              onClick={() => void loadMoreStories(retryOffset ?? undefined)}
              disabled={loadingMore}
              className="inline-flex min-h-11 items-center rounded-xl border border-border bg-card px-5 py-3 text-base font-semibold text-foreground hover:bg-muted disabled:cursor-wait disabled:opacity-60"
            >
              {loadingMore ? c("Loading stories…") : moreError ? c('Retry loading more stories') : c("Load more stories")}
            </button>
          </div>
        )}
      </div>
    </section>
  )
}
