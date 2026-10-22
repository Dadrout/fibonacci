import test from 'node:test'
import assert from 'node:assert/strict'
import { makeGraphLayout, createGraphSimulation, fitCamera, zoomCamera, conceptRadius, overviewConceptIds, edgeEndpointIds, connectedNodeIds } from '../components/brain/brain-graph-layout.ts'
import { MockBrain } from '../lib/brain-mocks.ts'

const deepFreeze = value => { Object.freeze(value); for (const child of Object.values(value)) if (child && typeof child === 'object' && !Object.isFrozen(child)) deepFreeze(child); return value }

test('layout and simulation preserve API objects and connect every concept to a real parent', async () => {
  const graph = deepFreeze(await new MockBrain().graph())
  const before = JSON.stringify(graph)
  const layout = makeGraphLayout(graph)
  const ids = new Set(layout.nodes.map(n => n.id))
  assert.equal(ids.size, graph.courses.length + graph.topics.length + graph.concepts.length)
  for (const node of layout.nodes.filter(n => n.kind !== 'course')) assert.ok(ids.has(node.parentId))
  const cross = layout.edges.filter(e => e.kind === 'cross')
  assert.equal(cross.length, 8)
  assert.ok(cross.every(edge => ids.has(edge.source) && ids.has(edge.target)))
  const simulation = createGraphSimulation(layout).stop().tick(150)
  assert.ok(simulation.alpha() < .001, 'simulation settles rather than moving continuously')
  assert.ok(layout.nodes.every(n => Number.isFinite(n.x) && Number.isFinite(n.y)))
  assert.equal(JSON.stringify(graph), before)
  const refreshed = makeGraphLayout(graph, layout.nodes)
  const concept = refreshed.nodes.find(n => n.kind === 'concept')
  assert.equal(concept.x, layout.nodes.find(n => n.id === concept.id).x, 'events preserve settled node positions')
})

test('orphaned links are excluded and concepts without topics still belong to their course', async () => {
  const graph = await new MockBrain().graph()
  graph.concepts[0].topic_id = 'missing-topic'
  graph.links.push({ ...graph.links[0], id: 'orphan', target_concept_id: 'missing-concept' })
  const layout = makeGraphLayout(graph)
  assert.equal(layout.nodes.find(n => n.entityId === graph.concepts[0].id).parentId, `course:${graph.concepts[0].course_id}`)
  assert.equal(layout.edges.some(e => e.id === 'orphan'), false)
  assert.ok(conceptRadius(25) > conceptRadius(1))
  assert.ok(conceptRadius(100000) <= 16, 'very common concepts must not cover a cluster')
})

test('camera fits nodes on phones, clamps scale and zooms around the pointer without drifting', () => {
  const nodes = [{ x: -200, y: -100, radius: 10 }, { x: 200, y: 100, radius: 10 }]
  const camera = fitCamera(nodes, 360, 500, 40)
  for (const node of nodes) {
    const x = camera.x + node.x * camera.k, y = camera.y + node.y * camera.k
    assert.ok(x >= 40 && x <= 320 && y >= 40 && y <= 460)
  }
  const point = { x: 87, y: 203 }
  const zoomed = zoomCamera(camera, 1.5, point)
  assert.ok(Math.abs((point.x - camera.x) / camera.k - (point.x - zoomed.x) / zoomed.k) < 1e-9)
  assert.equal(zoomCamera(camera, 1000, point).k, 4)
  assert.equal(zoomCamera(camera, .0001, point).k, .15)
  assert.ok(Number.isFinite(fitCamera([], 0, 0).k))
})

test('a few hundred nodes settle with finite coordinates and intact links', async () => {
  const graph = await new MockBrain().graph()
  const sample = graph.concepts[0]
  for (let i = 0; i < 300; i++) graph.concepts.push({ ...sample, id: `stress-${i}`, topic_id: graph.topics[i % graph.topics.length].id, course_id: graph.topics[i % graph.topics.length].course_id, mention_count: i % 40 })
  const layout = makeGraphLayout(graph)
  createGraphSimulation(layout).stop().tick(150)
  assert.ok(layout.nodes.length > 350)
  assert.ok(layout.nodes.every(node => Number.isFinite(node.x) && Number.isFinite(node.y)))
  assert.ok(layout.edges.every(edge => typeof edge.source === 'object' && typeof edge.target === 'object'))
})


test('overview keeps the two most-mentioned ideas per course readable with stable ties', async () => {
  const graph = await new MockBrain().graph()
  for (const concept of graph.concepts) concept.mention_count = 3
  const before = JSON.stringify(graph)
  const labels = overviewConceptIds(graph)
  for (const course of graph.courses) {
    const expected = graph.concepts.filter(concept => concept.course_id === course.id)
      .map(concept => concept.id).sort().slice(0, 2).map(id => `concept:${id}`)
    const actual = [...labels].filter(id => graph.concepts.some(concept => `concept:${concept.id}` === id && concept.course_id === course.id))
    assert.deepEqual(actual.sort(), expected.sort())
  }
  assert.deepEqual([...overviewConceptIds({ ...graph, concepts: [...graph.concepts].reverse() })].sort(), [...labels].sort())
  assert.equal(overviewConceptIds(graph, 0).size, 0)
  const winner = graph.concepts[graph.concepts.length - 1]
  winner.mention_count = 10000
  assert.ok(overviewConceptIds(graph, 1).has(`concept:${winner.id}`))
  winner.mention_count = 3
  assert.equal(JSON.stringify(graph), before, 'ranking must not reorder API concepts')
})

test('focus traces direct connections before and after d3 mutates endpoints', async () => {
  const graph = await new MockBrain().graph()
  const layout = makeGraphLayout(graph)
  const cross = layout.edges.find(edge => edge.kind === 'cross')
  const [source, target] = edgeEndpointIds(cross)
  const before = [...connectedNodeIds(layout.edges, source)].sort()
  assert.ok(before.includes(target), 'focus reveals the named cross-course relationship')
  assert.ok(connectedNodeIds(layout.edges, target).has(source))
  const parent = layout.nodes.find(node => node.id === source).parentId
  assert.equal(before.includes(parent), false, 'containment must not light up an entire cluster')
  createGraphSimulation(layout).stop().tick(150)
  assert.deepEqual(edgeEndpointIds(cross), [source, target])
  assert.deepEqual([...connectedNodeIds(layout.edges, source)].sort(), before)
  assert.equal(connectedNodeIds(layout.edges, null).size, 0)
  assert.deepEqual([...connectedNodeIds(layout.edges, 'unknown')], ['unknown'])
})

test('mock graph concepts resolve to exact source anchors across photo, PDF and video', async () => {
  const brain = new MockBrain()
  const graph = await brain.graph()
  const kinds = new Set()
  for (const concept of graph.concepts) {
    const detail = await brain.concept(concept.id)
    assert.equal(detail.concept.id, concept.id)
    for (const source of detail.sources) {
      assert.ok(source.item_id && source.chunk_id && source.item_title)
      assert.ok(source.quote, 'the quote remains usable even when media is offline')
      kinds.add(source.anchor.kind)
      if (source.anchor.kind === 'timestamp') assert.ok(source.anchor.end_sec >= source.anchor.start_sec)
    }
  }
  for (const kind of ['slide', 'page', 'timestamp']) assert.ok(kinds.has(kind), `missing ${kind} citation path`)
})
