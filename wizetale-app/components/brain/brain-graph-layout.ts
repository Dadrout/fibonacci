import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from 'd3-force'
import type { BrainGraph } from '@/lib/brain-types'

export interface GraphNode extends SimulationNodeDatum {
  id: string; entityId: string; kind: 'course' | 'topic' | 'concept'; courseId: string; parentId: string | null
  label: string; color: number; radius: number; homeX: number; homeY: number; x: number; y: number
}
export interface GraphEdge {
  id: string; source: string | GraphNode; target: string | GraphNode; kind: 'contains' | 'within' | 'cross'
}
export interface GraphLayout { nodes: GraphNode[]; edges: GraphEdge[] }
export interface Camera { x: number; y: number; k: number }

export const nodeKey = (kind: GraphNode['kind'], id: string) => `${kind}:${id}`
export function conceptRadius(mentions: number) { return 6 + Math.min(10, Math.sqrt(Math.max(0, mentions))) }

/** Separate objects are essential: d3 mutates its nodes AND its link endpoints. */
export function makeGraphLayout(graph: BrainGraph, previous: GraphNode[] = []): GraphLayout {
  const old = new Map(previous.map(node => [node.id, node]))
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []
  const add = (node: GraphNode) => {
    const prior = old.get(node.id)
    nodes.push({ ...node, ...(prior && node.kind !== 'course' ? { x: prior.x, y: prior.y } : {}) })
    if (node.parentId) edges.push({ id: `parent:${node.id}`, source: node.parentId, target: node.id, kind: 'contains' })
  }
  const homes = new Map<string, GraphNode>()
  for (const [index, course] of graph.courses.entries()) {
    const angle = index * 2 * Math.PI / graph.courses.length - Math.PI / 2
    const spread = graph.courses.length === 1 ? 0 : Math.max(390, graph.courses.length * 125)
    const x = Math.cos(angle) * spread, y = Math.sin(angle) * spread
    const courseNode: GraphNode = { id: nodeKey('course', course.id), entityId: course.id, kind: 'course', courseId: course.id, parentId: null, label: course.title, color: course.color_index, radius: 28, homeX: x, homeY: y, x, y, fx: x, fy: y }
    add(courseNode); homes.set(courseNode.id, courseNode)
    const topics = graph.topics.filter(topic => topic.course_id === course.id)
    topics.forEach((topic, i) => {
      const theta = i * 2 * Math.PI / Math.max(1, topics.length)
      const orbit = 145 + Math.max(0, topics.length - 5) * 12
      const tx = x + Math.cos(theta) * orbit, ty = y + Math.sin(theta) * orbit
      const node: GraphNode = { id: nodeKey('topic', topic.id), entityId: topic.id, kind: 'topic', courseId: course.id, parentId: courseNode.id, label: topic.title, color: course.color_index, radius: 11, homeX: tx, homeY: ty, x: tx, y: ty }
      add(node); homes.set(node.id, node)
    })
  }
  const siblings = new Map<string, number>()
  for (const concept of graph.concepts) {
    const parent = (concept.topic_id ? homes.get(nodeKey('topic', concept.topic_id)) : undefined) ?? homes.get(nodeKey('course', concept.course_id))
    if (!parent) continue
    const ordinal = siblings.get(parent.id) ?? 0
    siblings.set(parent.id, ordinal + 1)
    const angle = ordinal * Math.PI * (3 - Math.sqrt(5))
    const distance = 44 + 24 * Math.sqrt(ordinal)
    const x = parent.homeX + Math.cos(angle) * distance, y = parent.homeY + Math.sin(angle) * distance
    add({ id: nodeKey('concept', concept.id), entityId: concept.id, kind: 'concept', courseId: concept.course_id, parentId: parent.id, label: concept.name, color: parent.color, radius: conceptRadius(concept.mention_count), homeX: x, homeY: y, x, y })
  }
  const ids = new Set(nodes.map(node => node.id))
  for (const link of graph.links) {
    const source = nodeKey('concept', link.source_concept_id), target = nodeKey('concept', link.target_concept_id)
    if (ids.has(source) && ids.has(target)) edges.push({ id: link.id, source, target, kind: link.cross_course ? 'cross' : 'within' })
  }
  return { nodes, edges }
}

export function createGraphSimulation(layout: GraphLayout) {
  return forceSimulation(layout.nodes)
    .force('charge', forceManyBody<GraphNode>().strength(node => node.kind === 'course' ? -500 : -90))
    .force('collide', forceCollide<GraphNode>().radius(node => node.radius + (node.kind === 'course' ? 50 : 12)).iterations(2))
    .force('x', forceX<GraphNode>(node => node.homeX).strength(.18))
    .force('y', forceY<GraphNode>(node => node.homeY).strength(.18))
    .force('links', forceLink<GraphNode, GraphEdge>(layout.edges).id(node => node.id)
      .distance(edge => edge.kind === 'contains' ? 90 : 120)
      .strength(edge => edge.kind === 'cross' ? .001 : edge.kind === 'within' ? .025 : .08))
    .alphaDecay(.055).velocityDecay(.45)
}

export function fitCamera(nodes: GraphNode[], width: number, height: number, padding = 70): Camera {
  if (!nodes.length) return { x: width / 2, y: height / 2, k: 1 }
  const left = Math.min(...nodes.map(n => n.x - n.radius)), right = Math.max(...nodes.map(n => n.x + n.radius))
  const top = Math.min(...nodes.map(n => n.y - n.radius)), bottom = Math.max(...nodes.map(n => n.y + n.radius))
  const k = Math.max(.15, Math.min(2.2, (width - padding * 2) / Math.max(100, right - left), (height - padding * 2) / Math.max(100, bottom - top)))
  return { x: width / 2 - (left + right) / 2 * k, y: height / 2 - (top + bottom) / 2 * k, k }
}

export function zoomCamera(camera: Camera, factor: number, point: { x: number; y: number }): Camera {
  const k = Math.max(.15, Math.min(4, camera.k * factor))
  return { k, x: point.x - (point.x - camera.x) * k / camera.k, y: point.y - (point.y - camera.y) * k / camera.k }
}
