import test from 'node:test'
import assert from 'node:assert/strict'
import { makeGraphLayout, createGraphSimulation, fitCamera, zoomCamera, conceptRadius } from '../components/brain/brain-graph-layout.ts'
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
