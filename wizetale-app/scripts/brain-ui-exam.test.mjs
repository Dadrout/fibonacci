import test from 'node:test'
import assert from 'node:assert/strict'
import {
  advanceStage, clampDays, coverageGaps, examReducer, failureFromError, formatPlanDate, initialExamState, optionStatus,
  newestReadyPlan, parseDays, planLanguageFor, quizScore, shouldStopPolling, stageProgress, uniqueSources,
} from '../components/brain/brain-exam-logic.ts'
import { examCopy } from '../lib/copy-brain/exam.ts'

const { MockBrain, mockId, setMockTimeScale } = await import(new URL('../lib/brain-mocks.ts', import.meta.url))
setMockTimeScale(0.002)
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const ECON = mockId(101)

const request = { courseId: 'course-1', days: 3, language: 'en-US' }
const at = '2026-10-22T10:00:00Z'
const progress = (planId, stage, id = stage) => ({ type: 'plan.progress', plan_id: planId, stage, id, at })
const planOf = (overrides = {}) => ({
  id: 'plan-1', course_id: 'course-1', days: 3, exam_date: '2026-10-25', language: 'en-US', status: 'generating',
  failure_code: null, content: null, coverage: null, created_at: at, ...overrides,
})
const content = { title: 'Econometrics — exam in 3 days', days: [], notes: [], flashcards: [], quiz: [] }
const run = (actions, state = initialExamState) => actions.reduce(examReducer, state)

test('setup defaults follow the UI language and keep days within 1–14', () => {
  assert.equal(planLanguageFor('en'), 'en-US')
  assert.equal(planLanguageFor('ru'), 'ru-RU')
  assert.equal(planLanguageFor('kk'), 'kk-KZ')
  assert.equal(clampDays(0), 1)
  assert.equal(clampDays(30), 14)
  assert.equal(clampDays(Number.NaN), 3)
  assert.equal(parseDays('', 5), 5)
  assert.equal(parseDays('7', 3), 7)
  assert.equal(parseDays('99', 3), 14)
  assert.equal(formatPlanDate('2026-10-25', 'en'), 'Sun, Oct 25')
})

test('progress events that race ahead of the POST response are replayed, and stages never rewind', () => {
  let state = run([{ type: 'start', request, requestId: 'req-1' }, { type: 'event', event: progress('plan-1', 'planning') }])
  assert.equal(state.view.phase, 'generating')
  assert.equal(state.view.planId, null)
  state = run([{ type: 'created', requestId: 'req-1', plan: planOf() }], state)
  assert.equal(state.view.planId, 'plan-1')
  assert.equal(state.view.stage, 'planning')
  state = run([{ type: 'event', event: progress('plan-1', 'gathering', 'late') }, { type: 'event', event: progress('other-plan', 'citing') }], state)
  assert.equal(state.view.stage, 'planning', 'late or foreign events do not move the rail')
  assert.equal(advanceStage('citing', 'gathering'), 'citing')
  assert.ok(stageProgress(null) < stageProgress('planning') && stageProgress('planning') < stageProgress('citing'))
  state = run([{ type: 'event', event: { type: 'plan.ready', plan: planOf({ status: 'ready', content }), id: 'r', at } }], state)
  assert.equal(state.view.phase, 'ready')
})

test('polling resolves the plan when the event stream is silent; a stale POST response is ignored', () => {
  let state = run([{ type: 'start', request, requestId: 'req-1' }, { type: 'created', requestId: 'req-1', plan: planOf() }])
  state = run([{ type: 'polled', plan: planOf() }], state)
  assert.equal(state.view.phase, 'generating')
  state = run([{ type: 'polled', plan: planOf({ status: 'ready', content }) }], state)
  assert.equal(state.view.phase, 'ready')
  const restarted = run([{ type: 'start', request, requestId: 'req-2' }, { type: 'created', requestId: 'req-1', plan: planOf({ status: 'ready', content }) }])
  assert.equal(restarted.view.phase, 'generating', 'a response for an abandoned request does not open')
})

test('failures map to localized copy and the right retry: same request, resumed polling, or a new plan', () => {
  assert.equal(failureFromError({ code: 'not_enough_material' }), 'not_enough_material')
  assert.equal(failureFromError({ code: 'unavailable' }), 'network')
  assert.equal(failureFromError({ code: 'rate_limited' }), 'rate_limited')
  assert.equal(failureFromError(new Error('boom')), 'internal')
  assert.equal(shouldStopPolling('network', 2), false)
  assert.equal(shouldStopPolling('network', 4), true)
  assert.equal(shouldStopPolling('not_found', 1), true)

  const created = run([{ type: 'start', request, requestId: 'req-1' }, { type: 'error', failure: 'network', retry: 'create', requestId: 'req-1' }])
  assert.deepEqual([created.view.phase, created.view.retry, created.view.requestId], ['failed', 'create', 'req-1'])

  const generating = run([{ type: 'start', request, requestId: 'req-1' }, { type: 'created', requestId: 'req-1', plan: planOf() }, { type: 'event', event: progress('plan-1', 'citing') }])
  const polling = run([{ type: 'error', failure: 'network', retry: 'poll', planId: 'plan-1' }], generating)
  assert.equal(polling.view.retry, 'poll')
  const resumed = run([{ type: 'resume', planId: 'plan-1' }], polling)
  assert.deepEqual([resumed.view.phase, resumed.view.planId, resumed.view.stage], ['generating', 'plan-1', 'citing'])

  for (const code of ['not_enough_material', 'ai_unavailable', 'internal']) {
    const failed = run([{ type: 'event', event: { type: 'plan.failed', plan_id: 'plan-1', failure_code: code, id: code, at } }], generating)
    assert.deepEqual([failed.view.phase, failed.view.failure, failed.view.retry], ['failed', code, 'restart'])
    assert.deepEqual(failed.view.request, request)
  }
  const empty = run([{ type: 'polled', plan: planOf({ status: 'ready', content: null }) }], generating)
  assert.deepEqual([empty.view.phase, empty.view.failure], ['failed', 'internal'])
})

test('reopening an earlier plan lands in the matching view; a missing restored plan returns to setup', () => {
  assert.equal(run([{ type: 'open', plan: planOf({ status: 'ready', content }) }]).view.phase, 'ready')
  const reopened = run([{ type: 'open', plan: planOf() }])
  assert.deepEqual([reopened.view.phase, reopened.view.planId], ['generating', 'plan-1'])
  assert.equal(run([{ type: 'open', plan: planOf({ status: 'failed', failure_code: 'ai_unavailable' }) }]).view.failure, 'ai_unavailable')
  assert.equal(run([{ type: 'restore', planId: 'plan-1' }, { type: 'polled', plan: planOf({ status: 'ready', content }) }]).view.phase, 'ready')
  assert.equal(run([{ type: 'restore', planId: 'plan-1' }, { type: 'error', failure: 'not_found', retry: 'restart' }]).view.phase, 'setup')
})

test('quiz marks the correct option and the wrong pick separately, and keeps score', () => {
  const result = { question_id: 'q2', correct: false, correct_option_id: 'b', explanation: { text: '', sources: [] }, moment: null, attempt_id: 'x' }
  const answer = { status: 'answered', selected: 'a', result }
  assert.deepEqual(['a', 'b', 'c'].map(id => optionStatus(id, answer)), ['wrong', 'correct', 'muted'])
  assert.deepEqual(['a', 'b'].map(id => optionStatus(id, { status: 'checking', selected: 'a' })), ['checking', 'muted'])
  assert.equal(optionStatus('a', { status: 'error', selected: 'a' }), 'idle')
  assert.deepEqual(quizScore({ q1: { status: 'answered', selected: 'a', result: { ...result, correct: true } }, q2: answer, q3: { status: 'checking', selected: 'c' } }), { answered: 2, correct: 1 })
})

test('chips dedupe repeated passages and gaps are listed once each', () => {
  const ref = { item_id: 'i', chunk_id: 'c' }
  assert.equal(uniqueSources([ref, { ...ref }, { item_id: 'i', chunk_id: 'd' }]).length, 2)
  const gap = { id: 'g7', course_id: 'c', course_title: 'Econometrics', sequence_kind: 'week', missing: 7, present: [1, 2, 3, 4, 5, 6, 8] }
  assert.deepEqual(coverageGaps([gap, gap, { ...gap, id: 'g6', missing: 6 }]).map(entry => entry.missing), [6, 7])
})

test('every exam string has Russian and Kazakh copy', () => {
  for (const [key, [ru, kk]] of Object.entries(examCopy)) {
    assert.ok(ru && kk, `missing translation: ${key}`)
    for (const placeholder of key.match(/\{\w+\}/g) ?? []) {
      assert.ok(ru.includes(placeholder) && kk.includes(placeholder), `placeholder ${placeholder} kept in: ${key}`)
    }
  }
})

test('demo flow: Econometrics plan streams to ready, every claim is cited, and the wrong q2 answer returns the 14:32 moment', async () => {
  const brain = new MockBrain()
  await brain.simulateHeroDemo()
  await wait(200)
  let state = initialExamState
  const stages = []
  brain.subscribe((event) => {
    if (event.type === 'plan.progress') stages.push(event.stage)
    state = examReducer(state, { type: 'event', event })
  })
  state = examReducer(state, { type: 'start', request: { courseId: ECON, days: 3, language: 'en-US' }, requestId: 'demo-plan' })
  const pending = await brain.createExamPlan(ECON, { days: 3, language: 'en-US', request_id: 'demo-plan' })
  state = examReducer(state, { type: 'created', requestId: 'demo-plan', plan: pending })
  for (let tries = 0; tries < 100 && state.view.phase !== 'ready'; tries += 1) await wait(10)
  assert.equal(state.view.phase, 'ready')
  assert.deepEqual(stages, ['gathering', 'planning', 'citing'])

  const plan = state.view.plan
  assert.equal(plan.content.days.length, 3)
  const claims = [
    ...plan.content.days.flatMap(day => day.tasks), ...plan.content.notes.flatMap(note => note.bullets),
    ...plan.content.flashcards, ...plan.content.quiz,
  ]
  for (const claim of claims) assert.ok(uniqueSources(claim.sources).length >= 1, 'every claim shows at least one chip')
  assert.ok(plan.coverage.cited_item_count <= plan.coverage.item_count)
  assert.deepEqual(coverageGaps(plan.coverage.missing).map(gap => gap.missing), [7])

  const result = await brain.answerQuiz(plan.id, 'q2', 'a')
  const answer = { status: 'answered', selected: 'a', result }
  assert.equal(result.correct, false)
  assert.equal(optionStatus('a', answer), 'wrong')
  assert.equal(optionStatus(result.correct_option_id, answer), 'correct')
  assert.ok(result.explanation.sources.length >= 1)
  assert.equal(result.moment.source.anchor.kind, 'timestamp')
  assert.equal(result.moment.source.anchor.start_sec, 872)
  assert.ok(result.moment.reason.length > 0)
})


test('direct course tools reopen the newest ready plan without choosing unfinished plans or mutating history', () => {
  const older = planOf({ id: 'older', status: 'ready', content, created_at: '2026-10-20T10:00:00Z' })
  const newest = planOf({ id: 'newest', status: 'ready', content, created_at: '2026-10-21T10:00:00Z' })
  const pending = planOf({ id: 'pending' })
  const failed = planOf({ id: 'failed', status: 'failed' })
  const incomplete = planOf({ id: 'incomplete', status: 'ready', content: null })
  const history = [older, pending, newest, failed, incomplete]
  assert.equal(newestReadyPlan(history), newest)
  assert.deepEqual(history.map(plan => plan.id), ['older', 'pending', 'newest', 'failed', 'incomplete'])
  assert.equal(newestReadyPlan([pending, failed, incomplete]), undefined)
  assert.equal(newestReadyPlan([]), undefined)
  const reopened = examReducer(initialExamState, { type: 'open', plan: newestReadyPlan(history) })
  assert.equal(reopened.view.phase, 'ready')
  assert.equal(reopened.view.plan.id, 'newest')
})
