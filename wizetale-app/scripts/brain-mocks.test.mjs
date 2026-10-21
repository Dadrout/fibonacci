import assert from 'node:assert/strict'
import test from 'node:test'

const { MockBrain, mockId, setMockTimeScale } = await import(new URL('../lib/brain-mocks.ts', import.meta.url))
const api = await import(new URL('../lib/brain-api-helpers.ts', import.meta.url))
setMockTimeScale(0.002)

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const ECON = mockId(101)

function allSourcesOf(content) {
  return [
    ...content.days.flatMap((d) => d.tasks.map((t) => t.sources)),
    ...content.notes.flatMap((n) => n.bullets.map((b) => b.sources)),
    ...content.flashcards.map((f) => f.sources),
    ...content.quiz.map((q) => q.sources),
  ]
}

test('seed has three courses, ~40 items, cross-course links, and weeks 6–7 missing in Econometrics', async () => {
  const brain = new MockBrain()
  const overview = await brain.overview()
  assert.equal(overview.counts.courses, 3)
  assert.ok(overview.counts.items >= 35, `items: ${overview.counts.items}`)
  assert.ok(overview.counts.cross_links >= 5)
  const econGaps = brain.gaps(ECON).map((g) => g.missing)
  assert.deepEqual(econGaps, [6, 7])
  const graph = await brain.graph()
  const conceptIds = new Set(graph.concepts.map((c) => c.id))
  for (const link of graph.links) {
    assert.ok(conceptIds.has(link.source_concept_id) && conceptIds.has(link.target_concept_id), 'links point at known concepts')
  }
})

test('hero demo files three Telegram captures, lights a new cross-course link, and leaves only Week 7 missing', async () => {
  const brain = new MockBrain()
  const events = []
  brain.subscribe((event) => events.push(event))
  await brain.simulateHeroDemo()
  await wait(200)
  const filed = events.filter((e) => e.type === 'item.filed')
  assert.equal(filed.length, 3)
  assert.ok(filed.every((e) => e.item.channel === 'telegram' && e.item.topic_title === 'Heteroskedasticity'))
  assert.equal(filed.filter((e) => e.new_topic).length, 1, 'only the first capture creates the Week 6 topic')
  const order = events.filter((e) => e.type.startsWith('item.') && e.item_id === undefined ? true : true).map((e) => e.type)
  assert.ok(order.indexOf('item.created') < order.indexOf('item.progress'))
  const cross = events.filter((e) => e.type === 'link.created' && e.link.cross_course)
  assert.ok(cross.length >= 1, 'a new cross-course link appears')
  assert.ok(events.some((e) => e.type === 'gap.resolved' && e.gap_id.endsWith(':week:6')))
  assert.deepEqual(brain.gaps(ECON).map((g) => g.missing), [7])
})

test('exam plan cites sources everywhere and a wrong answer returns the YouTube moment', async () => {
  const brain = new MockBrain()
  await brain.simulateHeroDemo()
  await wait(200)
  const events = []
  brain.subscribe((event) => events.push(event))
  const requestId = '11111111-1111-4111-8111-111111111111'
  const pending = await brain.createExamPlan(ECON, { days: 3, language: 'en-US', request_id: requestId })
  assert.equal(pending.status, 'generating')
  await wait(100)
  const ready = events.find((e) => e.type === 'plan.ready')
  assert.ok(ready, 'plan.ready emitted')
  const { content } = ready.plan
  assert.equal(content.days.length, 3)
  for (const sources of allSourcesOf(content)) assert.ok(sources.length >= 1, 'every claim has a citation')
  const q2 = content.quiz.find((q) => q.id === 'q2')
  assert.ok(q2 && !('correct_option' in q2), 'correct answer is not sent with the question')
  const result = await brain.answerQuiz(requestId, 'q2', 'a')
  assert.equal(result.correct, false)
  assert.equal(result.correct_option_id, 'b')
  assert.equal(result.moment.source.anchor.kind, 'timestamp')
  assert.equal(result.moment.source.anchor.start_sec, 872)
  assert.match(result.moment.source.open_url, /t=872s/)
})

test('re-filing moves the item and reports learned', async () => {
  const brain = new MockBrain()
  const item = mockId(436)
  const result = await brain.refile(item, { course_id: mockId(102), topic_id: mockId(213) })
  assert.equal(result.item.course_id, mockId(102))
  assert.equal(result.item.needs_review, false)
  assert.equal(result.learned, true)
})

test('api helpers: timestamps, embeds, and event reducers', () => {
  assert.equal(api.formatTimestamp(872), '14:32')
  assert.equal(api.formatTimestamp(3725), '1:02:05')
  assert.match(api.youtubeEmbedUrl('2xcUup_-K6c', 872, 910), /start=872.*end=910/)
  const base = { id: 'a', status: 'queued', progress: 0, title: 'x' }
  let items = api.reduceItems([], { type: 'item.created', id: '1', at: '', item: base })
  items = api.reduceItems(items, { type: 'item.progress', id: '2', at: '', item_id: 'a', status: 'classifying', progress: 0.5, title: 'x' })
  assert.equal(items[0].status, 'classifying')
  items = api.reduceItems(items, { type: 'item.deleted', id: '3', at: '', item_id: 'a' })
  assert.equal(items.length, 0)
})
