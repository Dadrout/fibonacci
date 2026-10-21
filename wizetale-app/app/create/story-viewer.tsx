'use client'

import { useCopy } from '@/hooks/use-copy'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useStoryPoller } from '@/hooks/use-story-poller'
import { useAuth } from '@/hooks/use-auth'
import { useStudentWorkspace } from '@/lib/student-workspace-context'
import { parseQuizResult } from '@/lib/student-quiz-result'

export default function StoryViewer({ jobId }: { jobId: string }) {
  const c = useCopy()
  const workspace = useStudentWorkspace()

  const { isPolling, progress, status, error, result, generationFailed, retry } = useStoryPoller(jobId)
  const { getToken } = useAuth()
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [score, setScore] = useState<{ score: number; total: number } | null>(null)
  const [quizError, setQuizError] = useState<string | null>(null)
  const [savingQuiz, setSavingQuiz] = useState(false)
  const [quizLoadState, setQuizLoadState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [quizLoadAttempt, setQuizLoadAttempt] = useState(0)
  const [videoPlaybackError, setVideoPlaybackError] = useState(false)
  const questions = result?.quiz || []
  const optionIds = questions.map((question) => question.options.map((option) => option.id))

  useEffect(() => {
    const storyId = result?.story_id
    if (!storyId || questions.length === 0) {
      setAnswers({})
      setScore(null)
      setQuizError(null)
      setQuizLoadState('ready')
      return
    }

    let cancelled = false
    setQuizLoadState('loading')
    setQuizError(null)
    setAnswers({})
    setScore(null)

    void (async () => {
      try {
        const token = await getToken()
        if (!token) throw new Error(c('Please sign in again to save your quiz result.'))
        const response = await fetch(`/api/v1/stories/${encodeURIComponent(storyId)}/quiz-results`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || c('Could not load saved quiz result.'))
        const saved = parseQuizResult(data, optionIds)
        if (cancelled) return
        if (saved) {
          setAnswers(saved.answers)
          setScore({ score: saved.score, total: saved.total })
        }
        setQuizLoadState('ready')
      } catch (cause) {
        if (cancelled) return
        setQuizError(cause instanceof Error ? cause.message : c('Could not load saved quiz result.'))
        setQuizLoadState('error')
      }
    })()

    return () => { cancelled = true }
  }, [result?.story_id, result?.quiz, getToken, quizLoadAttempt])

  useEffect(() => { setVideoPlaybackError(false) }, [result?.video_url])

  const submitQuiz = async () => {
    if (!result?.story_id || savingQuiz || score || quizLoadState !== 'ready') return
    setSavingQuiz(true)
    try {
      setQuizError(null)
      const token = await getToken()
      if (!token) throw new Error(c("Please sign in again to save your quiz result."))
      const response = await fetch(`/api/v1/stories/${encodeURIComponent(result.story_id)}/quiz-results`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || c("Could not save your quiz result."))
      const saved = parseQuizResult(data, optionIds)
      if (!saved) throw new Error(c('Could not save your quiz result.'))
      setAnswers(saved.answers)
      setScore({ score: saved.score, total: saved.total })
    } catch (cause) {
      setQuizError(cause instanceof Error ? cause.message : c("Could not save quiz result."))
    } finally {
      setSavingQuiz(false)
    }
  }

  return (
    <section className="student-story-viewer text-foreground">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-4xl font-bold"> {c("Your learning story")} </h1>
        {workspace.setup.topic.trim() && <p className="mt-2 text-base text-muted-foreground">{workspace.setup.topic}</p>}

        {(isPolling || (!result && !error)) && (
          <section className="mt-8 rounded-3xl border border-border bg-card p-6 text-card-foreground sm:p-8">
            <div className="flex items-center justify-between gap-3 text-base font-semibold"><span>{c(status)}</span><span>{progress}%</span></div>
            <div className="mt-4 h-3 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.max(4, Math.min(progress, 100))}%` }} />
            </div>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground"> {c("You can leave this page. Your progress is saved and this page will pick up where it left off.")} </p>
          </section>
        )}

        {error && (
          <section role="alert" className="mt-8 rounded-2xl border border-destructive/30 bg-destructive/10 p-6 text-foreground">
            <h2 className="text-2xl font-bold"> {c(generationFailed ? "We couldn’t finish this video" : "Could not check video progress.")} </h2>
            <p className="mt-2 text-base leading-relaxed">{c(error)}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button onClick={() => void retry()} className="min-h-11 rounded-lg bg-primary px-4 py-2 text-base font-semibold text-primary-foreground"> {c(generationFailed ? "Retry video" : "Refresh")} </button>
              <button type="button" onClick={() => workspace.openStory(null)} className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 py-2 text-base"> {c("Return to draft")} </button>
            </div>
          </section>
        )}

        {result && (
          <div className="mt-8 space-y-7">
            {result.video_url && (
              <section className="overflow-hidden rounded-3xl bg-black shadow-xl">
                <video className="aspect-video w-full" controls playsInline src={result.video_url} onError={() => setVideoPlaybackError(true)}> {c("Your browser does not support video playback.")} </video>
                {videoPlaybackError && <p role="status" className="bg-card px-5 py-3 text-base text-card-foreground">{c('The video could not play. You can continue reading the story and quiz below.')}</p>}
              </section>
            )}
            <section className="rounded-3xl border border-border bg-card p-6 text-card-foreground">
              <h2 className="text-2xl font-bold"> {c("Story recap")} </h2>
              <p className="mt-3 text-base leading-7 text-muted-foreground">{result.recap}</p>
              {result.transcript && (
                <details className="mt-5">
                  <summary className="flex min-h-11 cursor-pointer items-center text-base font-semibold"> {c("Read the full narration")} </summary>
                  <p className="mt-3 whitespace-pre-wrap text-base leading-7 text-muted-foreground">{result.transcript}</p>
                </details>
              )}
            </section>

            {result.sources?.length ? (
              <section className="rounded-3xl border border-border bg-card p-6 text-card-foreground">
                <h2 className="text-2xl font-bold"> {c("Learning sources")} </h2>
                <p className="mt-1 text-base text-muted-foreground">{result.knowledge_status === 'grounded' ? c("Reviewed material matched this topic.") : c("Related reviewed material helped shape this story.")}</p>
                <ul className="mt-4 list-disc space-y-2 pl-5 text-base">
                  {result.sources.map((source) => (
                    <li key={source.url}>
                      <a className="font-semibold text-primary underline" href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
                      {source.publisher ? <span className="text-muted-foreground"> · {source.publisher}</span> : null}
                    </li>
                  ))}
                </ul>
              </section>
            ) : result.knowledge_status === 'none' ? (
              <p className="text-base text-muted-foreground"> {c("No reviewed references are attached to this story.")} </p>
            ) : null}

            {questions.length > 0 && (
              <section className="rounded-3xl border border-border bg-card p-6 text-card-foreground">
                <h2 className="text-2xl font-bold"> {c("Check what you learned")} </h2>
                <p className="mt-1 text-base text-muted-foreground"> {c("Choose one answer for each question.")} </p>
                {quizLoadState === 'loading' && <p role="status" className="mt-3 text-base text-muted-foreground">{c('Loading saved quiz result…')}</p>}
                {quizLoadState === 'error' && <div className="mt-3 rounded-xl border border-destructive/30 bg-destructive/10 p-4">
                  <p role="alert" className="text-base text-destructive">{c(quizError || 'Could not load saved quiz result.')}</p>
                  <button type="button" onClick={() => setQuizLoadAttempt((attempt) => attempt + 1)} className="mt-3 min-h-11 rounded-lg border border-border px-4 py-2 text-base font-semibold">{c('Retry loading quiz result')}</button>
                </div>}
                <div className="mt-5 space-y-6">
                  {questions.map((question, index) => (
                    <fieldset key={index}>
                      <legend className="text-base font-semibold">{index + 1}. {question.question}</legend>
                      <div className="mt-2 space-y-2">
                        {question.options.map((option) => (
                          <label key={option.id} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-border p-3 text-base hover:border-primary">
                            <input
                              type="radio"
                              name={`question-${index}`}
                              value={option.id}
                              checked={answers[String(index + 1)] === option.id}
                              disabled={quizLoadState !== 'ready' || savingQuiz || Boolean(score)}
                              onChange={() => setAnswers({ ...answers, [String(index + 1)]: option.id })}
                            />
                            <span>{option.text}</span>
                          </label>
                        ))}
                      </div>
                      {score && <p className={`mt-2 text-base ${answers[String(index + 1)] === question.correct_option ? 'text-sky-700 dark:text-sky-400' : 'text-amber-700 dark:text-amber-400'}`}>{answers[String(index + 1)] === question.correct_option ? c('Correct.') : c("Review this one.")} {question.explanation}</p>}
                    </fieldset>
                  ))}
                </div>
                {quizError && quizLoadState === 'ready' && <p role="alert" className="mt-4 text-base text-destructive">{c(quizError)}</p>}
                {score ? (
                  <p className="mt-5 rounded-xl bg-accent p-4 text-base font-bold text-accent-foreground"> {c("You got")} {score.score} {c("of")} {score.total} {c("correct.")} </p>
                ) : quizLoadState === 'ready' ? (
                  <button disabled={savingQuiz || Object.keys(answers).length !== questions.length} onClick={() => void submitQuiz()} className="mt-5 min-h-11 rounded-xl bg-primary px-5 py-3 text-base font-bold text-primary-foreground disabled:opacity-50"> {savingQuiz ? c('Saving quiz result…') : c("Check my answers")} </button>
                ) : null}
              </section>
            )}

            <div className="flex flex-wrap gap-3">
              <button type="button" onClick={() => workspace.openStory(null)} className="inline-flex min-h-11 items-center rounded-xl bg-primary px-5 py-3 text-base font-bold text-primary-foreground"> {c("Return to draft")} </button>
              <button type="button" onClick={workspace.openLibrary} className="inline-flex min-h-11 items-center rounded-xl border border-border px-5 py-3 text-base font-semibold hover:bg-muted"> {c("View history")} </button>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
