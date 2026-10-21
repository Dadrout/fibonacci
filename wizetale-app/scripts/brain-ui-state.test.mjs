import test from 'node:test'
import assert from 'node:assert/strict'
import { updateOverview, addConnection, groupGaps } from '../components/brain/brain-ui-state.ts'
import { reduceItems, reduceGraph } from '../lib/brain-api-helpers.ts'
import { MockBrain, setMockTimeScale } from '../lib/brain-mocks.ts'

setMockTimeScale(0.002)

test('live counters track all three hero captures, new concepts and links without losing older totals', async () => {
  const brain = new MockBrain()
  let overview = await brain.overview()
  let graph = await brain.graph()
  const start = overview.counts.items
  let maxProcessing = 0
  let connections = []
  const stop = brain.subscribe(event => {
    graph = reduceGraph(graph, event)
    overview = updateOverview(overview, event, reduceItems(overview.recent_items, event), graph)
    connections = addConnection(connections, event)
    maxProcessing = Math.max(maxProcessing, overview.counts.processing)
  })
  await brain.simulateHeroDemo()
  await new Promise(resolve => setTimeout(resolve, 200))
  stop()
  assert.ok(maxProcessing > 0, 'processing must be visible during capture')
  assert.equal(overview.counts.items, start + 3)
  assert.deepEqual(overview.counts, (await brain.overview()).counts)
  assert.ok(connections.some(e => e.source.name === 'Heteroskedasticity' && e.target.name === 'Variance'))
  assert.ok(connections.every(e => e.source_course.title && e.target_course.title))
})

test('a duplicate filed event does not increment counts twice; retries, failures and deletion update processing', async () => {
  const brain = new MockBrain()
  let state = await brain.overview()
  const graph = await brain.graph()
  const item = { ...state.recent_items[0], id: 'new', status: 'queued', progress: 0 }
  const apply = event => { state = updateOverview(state, event, reduceItems(state.recent_items, event), graph) }
  const start = state.counts.items
  apply({ type: 'item.created', item })
  assert.equal(state.counts.processing, 1)
  apply({ type: 'item.failed', item_id: item.id, failure_code: 'internal' })
  assert.equal(state.counts.processing, 0)
  apply({ type: 'item.progress', item_id: item.id, status: 'queued', progress: 0 })
  assert.equal(state.counts.processing, 1)
  const filed = { type: 'item.filed', item: { ...item, status: 'filed', progress: 1 } }
  apply(filed)
  apply(filed)
  assert.equal(state.counts.items, start + 1)
  assert.equal(state.counts.processing, 0)
  apply({ type: 'item.deleted', item_id: item.id })
  assert.equal(state.counts.items, start)
})

test('connections retain three newest distinct links and ignore within-course/replayed links', () => {
  const event = (id, cross = true) => ({ type: 'link.created', link: { id, cross_course: cross } })
  let stack = []
  for (const id of ['a', 'b', 'c', 'c', 'd']) stack = addConnection(stack, event(id))
  assert.deepEqual(stack.map(e => e.link.id), ['d', 'c', 'b'])
  assert.equal(addConnection(stack, event('e', false)), stack)
})

test('gaps group by course, deduplicate and numerically order each sequence kind', () => {
  const gap = (course_id, sequence_kind, missing) => ({ id: `${course_id}:${sequence_kind}:${missing}`, course_id, course_title: course_id, sequence_kind, missing, present: [] })
  const groups = groupGaps([gap('econ', 'week', 7), gap('econ', 'week', 6), gap('econ', 'week', 7), gap('econ', 'chapter', 2), gap('stats', 'week', 4)])
  assert.equal(groups.length, 2)
  assert.deepEqual(groups[0].sequences, [{ kind: 'week', missing: [6, 7] }, { kind: 'chapter', missing: [2] }])
})

test('loading deadlines reject a hung request and leave successful reads intact', async () => {
  const { withUiTimeout } = await import('../components/brain/brain-ui-state.ts')
  assert.equal(await withUiTimeout(Promise.resolve('snapshot'), 100), 'snapshot')
  await assert.rejects(withUiTimeout(new Promise(() => {}), 5), /timed out/)
})
