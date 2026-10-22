'use client'

/*
 * Quiz + mistake → source moment (board row A6). One question at a time so it reads from the
 * back of a room. A wrong answer explains kindly, marks the correct option with text and an
 * icon, and offers one action: open the exact source moment the API returned.
 */
import { useEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from 'react'
import { ArrowLeft, ArrowRight, CircleCheck, CircleX, FileText, Image as ImageIcon, LoaderCircle, LocateFixed, TriangleAlert, Video } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import type { BrainApi } from '@/lib/brain-api'
import type { QuizOptionId, QuizQuestion, SourceMoment } from '@/lib/brain-types'
import { formatTimestamp } from '@/lib/brain-api-helpers'
import { safeSourceUrl, sourceLabel } from './source-viewer-helpers'
import { SourceChips, type OpenSource } from './brain-exam-chips'
import { optionLetter, optionStatus, quizScore, type AnswerState } from './brain-exam-logic'

export function BrainExamQuiz({ api, planId, questions, answers, setAnswers, index, setIndex, onOpen, presentation }: {
  api: BrainApi
  planId: string
  questions: QuizQuestion[]
  answers: Record<string, AnswerState>
  setAnswers: Dispatch<SetStateAction<Record<string, AnswerState>>>
  index: number
  setIndex: (index: number) => void
  onOpen: OpenSource
  presentation: boolean
}) {
  const c = useCopy()
  const promptRef = useRef<HTMLHeadingElement>(null)
  const feedbackRef = useRef<HTMLHeadingElement>(null)
  const justAnswered = useRef<string | null>(null)
  const navigated = useRef(false)
  const current = Math.min(Math.max(0, index), Math.max(0, questions.length - 1))
  const question = questions[current] as QuizQuestion | undefined
  const answer = question ? answers[question.id] : undefined

  useEffect(() => {
    if (!navigated.current) return
    navigated.current = false
    promptRef.current?.focus({ preventScroll: false })
  }, [current])

  useEffect(() => {
    if (!question || answer?.status !== 'answered' || justAnswered.current !== question.id) return
    justAnswered.current = null
    feedbackRef.current?.focus({ preventScroll: true })
    feedbackRef.current?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  }, [answer, question])

  if (!question) return <p className="brain-no-recent">{c('This plan has no quiz questions.')}</p>

  const goTo = (next: number) => { navigated.current = true; setIndex(next) }
  const locked = answer?.status === 'checking' || answer?.status === 'answered'
  const submit = async (optionId: QuizOptionId) => {
    if (locked) return
    const id = question.id
    setAnswers(all => ({ ...all, [id]: { status: 'checking', selected: optionId } }))
    try {
      const result = await api.answerQuiz(planId, id, optionId)
      justAnswered.current = id
      setAnswers(all => ({ ...all, [id]: { status: 'answered', selected: optionId, result } }))
    } catch {
      setAnswers(all => ({ ...all, [id]: { status: 'error', selected: optionId } }))
    }
  }

  const score = quizScore(answers)
  const allAnswered = questions.every(entry => answers[entry.id]?.status === 'answered')
  const firstMissed = questions.findIndex(entry => { const state = answers[entry.id]; return state?.status === 'answered' && !state.result.correct })
  const promptId = `brain-exam-q-${question.id}`

  return <div className="brain-exam-quiz">
    <div className="brain-exam-quiz-top">
      <ol className="brain-exam-steps" aria-label={c('Questions')}>
        {questions.map((entry, position) => {
          const state = answers[entry.id]
          const verdict = state?.status === 'answered' ? (state.result.correct ? 'correct' : 'missed') : null
          return <li key={entry.id}>
            <button type="button" className={`brain-exam-step${verdict ? ` is-${verdict}` : ''}`} aria-current={position === current ? 'step' : undefined}
              aria-label={`${c('Question {n}').replace('{n}', String(position + 1))}${verdict ? ` · ${c(verdict === 'correct' ? 'Correct' : 'Missed')}` : ''}`}
              onClick={() => goTo(position)}>
              {verdict === 'correct' ? <CircleCheck size={17} aria-hidden="true" /> : verdict === 'missed' ? <CircleX size={17} aria-hidden="true" /> : null}
              <span aria-hidden="true">{position + 1}</span>
            </button>
          </li>
        })}
      </ol>
      <p className="brain-exam-score" role="status">{c('{correct} of {answered} correct').replace('{correct}', String(score.correct)).replace('{answered}', String(score.answered))}</p>
    </div>

    {allAnswered && <div className="brain-exam-quiz-done">
      <p><strong>{c('Quiz finished: {correct} of {total} correct.').replace('{correct}', String(score.correct)).replace('{total}', String(questions.length))}</strong>
        {firstMissed >= 0 ? ` ${c('Each missed question links to the moment that explains it.')}` : ` ${c('Every answer was right.')}`}</p>
      {firstMissed >= 0 && firstMissed !== current && <button type="button" className="brain-text-button" onClick={() => goTo(firstMissed)}>{c('Review a missed question')}<ArrowRight size={16} aria-hidden="true" /></button>}
    </div>}

    <section className="brain-exam-question" aria-labelledby={promptId}>
      <p className="brain-exam-question-count">{c('Question {n} of {total}').replace('{n}', String(current + 1)).replace('{total}', String(questions.length))}</p>
      <h3 id={promptId} ref={promptRef} tabIndex={-1}>{question.prompt}</h3>
      <ul className="brain-exam-options" aria-busy={answer?.status === 'checking'}>
        {question.options.map(option => {
          const status = optionStatus(option.id, answer)
          const selected = answer?.selected === option.id && answer.status === 'answered'
          return <li key={option.id}>
            <button type="button" className={`brain-exam-option is-${status}`} aria-disabled={locked || undefined} onClick={() => void submit(option.id)}>
              <span className="brain-exam-option-letter" aria-hidden="true">{optionLetter(option.id)}</span>
              <span className="brain-exam-option-text"><span className="brain-exam-sr-only">{optionLetter(option.id)}. </span>{option.text}</span>
              {status === 'correct' && <span className="brain-exam-verdict"><CircleCheck size={20} aria-hidden="true" />{c(selected ? 'Your answer · correct' : 'Correct answer')}</span>}
              {status === 'wrong' && <span className="brain-exam-verdict"><CircleX size={20} aria-hidden="true" />{c('Your answer')}</span>}
              {status === 'checking' && <span className="brain-exam-verdict"><LoaderCircle className="brain-exam-pulse" size={20} aria-hidden="true" />{c('Checking…')}</span>}
            </button>
          </li>
        })}
      </ul>
      <div className="brain-exam-question-sources">
        <span>{c('Based on')}</span>
        <SourceChips sources={question.sources} onOpen={onOpen} presentation={presentation} label={c('Sources for this question')} />
      </div>
    </section>

    {answer?.status === 'error' && <p className="brain-exam-inline-error" role="alert"><TriangleAlert size={17} aria-hidden="true" />{c('Your answer could not be checked.')}
      <button type="button" className="brain-secondary-button" onClick={() => void submit(answer.selected)}>{c('Try again')}</button></p>}

    {answer?.status === 'answered' && <AnswerFeedback key={question.id} headingRef={feedbackRef} question={question} answer={answer} onOpen={onOpen} presentation={presentation}
      onNext={current < questions.length - 1 ? () => goTo(current + 1) : undefined} onPrevious={current > 0 ? () => goTo(current - 1) : undefined} />}
  </div>
}

function AnswerFeedback({ question, answer, headingRef, onOpen, onNext, onPrevious, presentation }: {
  question: QuizQuestion
  answer: Extract<AnswerState, { status: 'answered' }>
  headingRef: RefObject<HTMLHeadingElement | null>
  onOpen: OpenSource
  onNext?: () => void
  onPrevious?: () => void
  presentation: boolean
}) {
  const c = useCopy()
  const { result } = answer
  const correctOption = question.options.find(option => option.id === result.correct_option_id)
  return <div className={`brain-exam-feedback ${result.correct ? 'is-correct' : 'is-wrong'}`}>
    <h4 ref={headingRef} tabIndex={-1}>
      {result.correct ? <CircleCheck size={24} aria-hidden="true" /> : <CircleX size={24} aria-hidden="true" />}
      {c(result.correct ? 'Correct — well done.' : 'Not quite. This one is easy to mix up.')}
    </h4>
    {!result.correct && correctOption && <p className="brain-exam-correct-line">{c('The correct answer is')} <strong>{optionLetter(correctOption.id)}. {correctOption.text}</strong></p>}
    {result.explanation.text && <p className="brain-exam-explanation">{result.explanation.text}</p>}
    {result.explanation.sources.length > 0 && <SourceChips sources={result.explanation.sources} onOpen={onOpen} presentation={presentation} label={c('Sources for this explanation')} />}

    {result.moment && (result.correct
      ? <button type="button" className="brain-secondary-button brain-exam-moment-secondary" onClick={() => onOpen(result.moment!.source, result.moment!.reason)}><LocateFixed size={18} aria-hidden="true" />{c(result.moment.confidence < 0.7 ? 'Open closest match' : 'See where this was explained')}</button>
      : <MomentCard moment={result.moment} onOpen={onOpen} />)}

    {(onNext || onPrevious) && <div className="brain-exam-feedback-nav">
      {onPrevious && <button type="button" className="brain-text-button" onClick={onPrevious}><ArrowLeft size={16} aria-hidden="true" />{c('Previous question')}</button>}
      {onNext && <button type="button" className="brain-secondary-button" onClick={onNext}>{c('Next question')}<ArrowRight size={17} aria-hidden="true" /></button>}
    </div>}
  </div>
}

function MomentCard({ moment, onOpen }: { moment: SourceMoment; onOpen: OpenSource }) {
  const c = useCopy()
  const { language } = useLanguage()
  const { source } = moment
  const anchor = source.anchor
  const label = sourceLabel(source, c, language, anchor.kind === 'timestamp' ? `${formatTimestamp(anchor.start_sec)}–${formatTimestamp(anchor.end_sec)}` : '')
  const Icon = anchor.kind === 'timestamp' ? Video : anchor.kind === 'slide' ? ImageIcon : FileText
  const thumbnail = safeSourceUrl(source.thumbnail_url ?? (anchor.kind === 'slide' ? source.media_url : null))
  const [thumbFailed, setThumbFailed] = useState(false)
  return <div className="brain-exam-moment">
    {thumbnail && !thumbFailed && <span className="brain-exam-moment-thumb">
      {/* Decorative preview: the label beside it names the exact place. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={thumbnail} alt="" loading="lazy" onError={() => setThumbFailed(true)} />
    </span>}
    <div className="brain-exam-moment-copy">
      <p className="brain-section-kicker">{c(moment.confidence < 0.7 ? 'Closest match in your material' : 'Where you learned it')}</p>
      <p className="brain-exam-moment-reason">{moment.reason}</p>
      <p className="brain-exam-moment-source"><Icon size={17} aria-hidden="true" /><span><strong>{label}</strong> · {source.item_title}</span></p>
    </div>
    <button type="button" className="brain-primary-button brain-exam-moment-button" onClick={() => onOpen(source, moment.reason)}>
      <LocateFixed size={22} aria-hidden="true" />{c(moment.confidence < 0.7 ? 'Open closest match' : 'See where this was explained')}
    </button>
  </div>
}
