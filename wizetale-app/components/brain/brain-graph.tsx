'use client'

import { useCallback, useEffect, useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, GitBranch, List, Maximize, Minus, Plus } from 'lucide-react'
import type { BrainApi } from '@/lib/brain-api'
import type { BrainEvent, BrainGraph as GraphData } from '@/lib/brain-types'
import { useCopy } from '@/hooks/use-copy'
import { BrainConceptPanel } from './brain-concept-panel'
import { courseColorSlot } from './brain-ui-state'
import { connectedNodeIds, createGraphSimulation, edgeEndpointIds, fitCamera, makeGraphLayout, overviewConceptIds, zoomCamera, type Camera, type GraphLayout, type GraphNode } from './brain-graph-layout'

// Remember arrivals across Home's Courses / Map unmounts without retaining old API sessions.
const animatedLinksByApi = new WeakMap<BrainApi, Set<string>>()

type Props = {
  graph: GraphData | null; api: BrainApi; loading: boolean; error: boolean; onRetry: () => void | Promise<void>
  connections: Array<Extract<BrainEvent, { type: 'link.created' }>>
  presentation: boolean; focusRequest: { id: string; token: number } | null
}

export function BrainGraph({ graph, api, loading, error, onRetry, connections, presentation, focusRequest }: Props) {
  const c = useCopy()
  if (!graph) return <section className="brain-graph-empty" aria-busy={loading}>
    <GitBranch size={32} aria-hidden="true" /><h2>{c(error ? 'Your graph could not load.' : 'Finding the connections…')}</h2>
    {error && <button type="button" className="brain-secondary-button" onClick={() => void onRetry()}>{c('Try again')}</button>}
  </section>
  if (!graph.courses.length) return <section className="brain-graph-empty"><GitBranch size={36} aria-hidden="true" /><h2>{c('Your first source starts the map.')}</h2><p>{c('Send a photo, lecture, or notes. Courses and connected ideas will appear here.')}</p><button className="brain-primary-button" type="button" onClick={() => window.dispatchEvent(new Event('brain:open-picker'))}>{c('Add a file')}</button></section>
  return <GraphExplorer graph={graph} api={api} connections={connections} presentation={presentation} focusRequest={focusRequest} />
}

function GraphExplorer({ graph, api, connections, presentation, focusRequest }: Omit<Props, 'graph' | 'loading' | 'error' | 'onRetry'> & { graph: GraphData }) {
  const c = useCopy()
  const instructionsId = useId()
  const [list, setList] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)
  const [focused, setFocused] = useState<string | null>(null)
  const [arrivingLinks, setArrivingLinks] = useState<Set<string>>(new Set())
  const sectionRef = useRef<HTMLElement>(null)
  const [reduced, setReduced] = useState(true)
  const svgRef = useRef<SVGSVGElement>(null)
  const viewportRef = useRef<SVGGElement>(null)
  const hostRef = useRef<HTMLDivElement>(null)
  const nodeElements = useRef(new Map<string, SVGGElement>())
  const edgeElements = useRef(new Map<string, SVGPathElement>())
  const priorLayout = useRef<GraphLayout>({ nodes: [], edges: [] })
  const layout = useMemo(() => makeGraphLayout(graph, priorLayout.current.nodes), [graph])
  const size = useRef({ width: 1000, height: 620 })
  const camera = useRef<Camera>({ x: 500, y: 310, k: .6 })
  const initialized = useRef(false)
  const animation = useRef(0)
  const cameraFrame = useRef(0)
  const latestFocus = useRef<number | null>(null)
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const gesture = useRef({ x: 0, y: 0, moved: false, node: null as string | null, left: 0, top: 0 })
  const highlightedLinks = arrivingLinks
  const overviewLabels = useMemo(() => overviewConceptIds(graph), [graph])
  const activeNode = hovered ?? focused ?? selected
  const relatedNodes = useMemo(() => connectedNodeIds(layout.edges, activeNode), [layout, activeNode])

  useEffect(() => {
    const seen = animatedLinksByApi.get(api) ?? new Set<string>()
    animatedLinksByApi.set(api, seen)
    const edgeIds = new Set(layout.edges.map(edge => edge.id))
    const fresh = connections.filter(connection => connection.link.cross_course && edgeIds.has(connection.link.id) && !seen.has(connection.link.id))
    for (const connection of fresh) seen.add(connection.link.id)
    if (fresh.length) setArrivingLinks(current => new Set([...current, ...fresh.map(connection => connection.link.id)]))
  }, [api, connections, layout])
  useEffect(() => {
    if (!arrivingLinks.size) return
    const timer = window.setTimeout(() => setArrivingLinks(new Set()), 1400)
    return () => window.clearTimeout(timer)
  }, [arrivingLinks])

  // Map is a section on Home. Bring its section heading into view when it mounts.
  useEffect(() => {
    const section = sectionRef.current?.closest('.brain-courses-section')
    section?.scrollIntoView({ block: 'start', behavior: 'instant' })
  }, [])
  useEffect(() => {
    const section = sectionRef.current, host = hostRef.current
    const homeSection = section?.closest('.brain-courses-section')
    if (!section || !host || !homeSection || list) return
    const resize = () => {
      const canvas = host.getBoundingClientRect()
      const top = homeSection.getBoundingClientRect().top
      const footer = section.getBoundingClientRect().bottom - canvas.bottom
      host.style.setProperty('--brain-map-height', `${Math.max(320, window.innerHeight - 24 - (canvas.top - top) - footer)}px`)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(homeSection)
    window.addEventListener('resize', resize)
    resize()
    return () => { observer.disconnect(); window.removeEventListener('resize', resize) }
  }, [list, presentation])
  const highlightedNodes = useMemo(() => new Set(connections.filter(connection => arrivingLinks.has(connection.link.id)).flatMap(connection => [`concept:${connection.source.id}`, `concept:${connection.target.id}`])), [connections, arrivingLinks])

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const sync = () => setReduced(query.matches)
    sync(); query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])

  const paintCamera = useCallback(() => {
    const current = camera.current
    viewportRef.current?.setAttribute('transform', `translate(${current.x},${current.y}) scale(${current.k})`)
    svgRef.current?.setAttribute('data-detail', current.k >= 1.1 ? 'concept' : current.k >= .55 ? 'topic' : 'course')
    // Keep labels and hit targets legible as the world zooms. No layout measurements.
    for (const node of priorLayout.current.nodes) {
      const element = nodeElements.current.get(node.id)
      element?.querySelector('.brain-node-hit')?.setAttribute('r', String(Math.max(node.radius, 22 / current.k)))
      element?.querySelector('text')?.setAttribute('transform', `translate(0,${node.kind === 'course' ? -node.radius - 14 / current.k : node.radius + 16 / current.k}) scale(${1 / current.k})`)
    }
  }, [])

  const moveCamera = useCallback((target: Camera, smooth = false) => {
    window.cancelAnimationFrame(animation.current)
    window.cancelAnimationFrame(cameraFrame.current)
    if (!smooth || reduced) {
      camera.current = target
      cameraFrame.current = window.requestAnimationFrame(paintCamera)
      return
    }
    const start = { ...camera.current }, began = performance.now()
    const frame = (now: number) => {
      const t = Math.min(1, (now - began) / 380), eased = 1 - (1 - t) ** 3
      camera.current = { x: start.x + (target.x - start.x) * eased, y: start.y + (target.y - start.y) * eased, k: start.k + (target.k - start.k) * eased }
      paintCamera()
      if (t < 1) animation.current = window.requestAnimationFrame(frame)
    }
    animation.current = window.requestAnimationFrame(frame)
  }, [paintCamera, reduced])

  const fit = useCallback(() => moveCamera(fitCamera(priorLayout.current.nodes, size.current.width, size.current.height), true), [moveCamera])
  const zoom = useCallback((factor: number) => moveCamera(zoomCamera(camera.current, factor, { x: size.current.width / 2, y: size.current.height / 2 }), true), [moveCamera])
  const pan = useCallback((x: number, y: number) => moveCamera({ ...camera.current, x: camera.current.x + x, y: camera.current.y + y }), [moveCamera])
  const navigate = useCallback((id: string) => {
    const node = priorLayout.current.nodes.find(node => node.id === id)
    if (!node) return
    const focusNodes = node.kind === 'concept' ? [node] : priorLayout.current.nodes.filter(entry => entry.id === id || (node.kind === 'course' ? entry.courseId === node.entityId : entry.parentId === id))
    moveCamera(fitCamera(focusNodes, size.current.width, size.current.height, node.kind === 'concept' ? 100 : 80), true)
    setSelected(id)
  }, [moveCamera])

  useEffect(() => {
    priorLayout.current = layout
    const simulation = createGraphSimulation(layout).stop()
    // A short warm-up avoids a pile-up on the first frame; reduce-motion draws only the settled state.
    simulation.tick(reduced ? 140 : 35)
    const nodes = layout.nodes.map(node => ({ node, element: nodeElements.current.get(node.id) }))
    const edges = layout.edges.map(edge => ({ edge, element: edgeElements.current.get(edge.id) }))
    const draw = () => {
      for (const { node, element } of nodes) element?.setAttribute('transform', `translate(${node.x.toFixed(2)},${node.y.toFixed(2)})`)
      for (const { edge, element } of edges) {
        const a = edge.source as GraphNode, b = edge.target as GraphNode
        const bend = edge.kind === 'cross' ? .12 : 0
        const mx = (a.x + b.x) / 2 - (b.y - a.y) * bend, my = (a.y + b.y) / 2 + (b.x - a.x) * bend
        element?.setAttribute('d', `M${a.x.toFixed(2)},${a.y.toFixed(2)} Q${mx.toFixed(2)},${my.toFixed(2)} ${b.x.toFixed(2)},${b.y.toFixed(2)}`)
      }
    }
    draw()
    if (!initialized.current) { camera.current = fitCamera(layout.nodes, size.current.width, size.current.height); initialized.current = true }
    paintCamera()
    if (!reduced && !list) simulation.on('tick', draw).restart()
    return () => { simulation.stop() }
  }, [layout, reduced, paintCamera, list])

  useEffect(() => {
    const host = hostRef.current, svg = svgRef.current
    if (!host || !svg) return
    const observer = new ResizeObserver(entries => {
      const rect = entries[0].contentRect
      if (!rect.width || !rect.height) return
      const previous = size.current
      size.current = { width: rect.width, height: rect.height }
      svg.setAttribute('viewBox', `0 0 ${rect.width} ${rect.height}`)
      // Refit an overview on resize (including projector mode); preserve a learner's zoom.
      const previousFit = fitCamera(priorLayout.current.nodes, previous.width, previous.height)
      if ((previous.width === 1000 && previous.height === 620) || Math.abs(camera.current.k - previousFit.k) < .02) camera.current = fitCamera(priorLayout.current.nodes, rect.width, rect.height)
      else camera.current = { ...camera.current, x: camera.current.x + (rect.width - previous.width) / 2, y: camera.current.y + (rect.height - previous.height) / 2 }
      paintCamera()
    })
    observer.observe(host)
    const wheel = (event: WheelEvent) => {
      event.preventDefault()
      const rect = svg.getBoundingClientRect()
      moveCamera(zoomCamera(camera.current, Math.exp(-Math.max(-120, Math.min(120, event.deltaY)) * .004), { x: event.clientX - rect.left, y: event.clientY - rect.top }))
    }
    svg.addEventListener('wheel', wheel, { passive: false })
    return () => { observer.disconnect(); svg.removeEventListener('wheel', wheel) }
  }, [list, moveCamera, paintCamera])

  useEffect(() => {
    if (focusRequest && latestFocus.current !== focusRequest.token && layout.nodes.some(node => node.id === focusRequest.id)) {
      latestFocus.current = focusRequest.token
      navigate(focusRequest.id)
    }
  }, [focusRequest, layout, navigate])
  useEffect(() => () => { window.cancelAnimationFrame(animation.current); window.cancelAnimationFrame(cameraFrame.current) }, [])

  const pointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    window.cancelAnimationFrame(animation.current)
    const rect = event.currentTarget.getBoundingClientRect()
    const target = (event.target as Element).closest('[data-node-id]')
    if (!pointers.current.size) gesture.current = { x: event.clientX, y: event.clientY, moved: false, node: target?.getAttribute('data-node-id') ?? null, left: rect.left, top: rect.top }
    else gesture.current.moved = true
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const pointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const before = pointers.current.get(event.pointerId)
    if (!before) return
    const previous = [...pointers.current.values()]
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    if (Math.hypot(event.clientX - gesture.current.x, event.clientY - gesture.current.y) > 5) gesture.current.moved = true
    const next = [...pointers.current.values()]
    if (next.length === 2) {
      const distance = (points: typeof next) => Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y)
      const oldMid = { x: (previous[0].x + previous[1].x) / 2 - gesture.current.left, y: (previous[0].y + previous[1].y) / 2 - gesture.current.top }
      const newMid = { x: (next[0].x + next[1].x) / 2 - gesture.current.left, y: (next[0].y + next[1].y) / 2 - gesture.current.top }
      const target = zoomCamera(camera.current, distance(next) / Math.max(1, distance(previous)), oldMid)
      moveCamera({ ...target, x: target.x + newMid.x - oldMid.x, y: target.y + newMid.y - oldMid.y })
    } else if (gesture.current.moved) pan(event.clientX - before.x, event.clientY - before.y)
  }
  const pointerUp = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!pointers.current.has(event.pointerId)) return
    pointers.current.delete(event.pointerId)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    if (!pointers.current.size && !gesture.current.moved && gesture.current.node) {
      nodeElements.current.get(gesture.current.node)?.focus()
      navigate(gesture.current.node)
    }
  }
  const selectedNode = layout.nodes.find(node => node.id === selected) ?? null
  return <section className="brain-graph-section" ref={sectionRef}>
    <div className="brain-graph-heading"><div><h3>{c('Ideas that connect your courses')}</h3><p>{c('Most-mentioned ideas stay visible. Choose a seed to trace its sources and connections.')}</p></div><div className="brain-view-toggle" aria-label={c('Graph display')}><button type="button" aria-pressed={!list} onClick={() => setList(false)}><GitBranch size={17} aria-hidden="true" />{c('Graph')}</button><button type="button" aria-pressed={list} onClick={() => setList(true)}><List size={17} aria-hidden="true" />{c('List view')}</button></div></div>
    {list ? <GraphList graph={graph} onNavigate={navigate} /> : <>
      <div className="brain-graph-canvas" ref={hostRef}>
        <svg ref={svgRef} className="brain-graph-svg" viewBox="0 0 1000 620" role="group" aria-label={c('Interactive Brain graph')} aria-describedby={instructionsId} tabIndex={0}
          onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={event => { pointers.current.delete(event.pointerId); gesture.current.moved = true }}
          onKeyDown={event => {
            if (event.target !== event.currentTarget) return
            const movement: Record<string, [number, number]> = { ArrowLeft: [60, 0], ArrowRight: [-60, 0], ArrowUp: [0, 60], ArrowDown: [0, -60] }
            if (movement[event.key]) { event.preventDefault(); pan(...movement[event.key]) }
            else if (['+', '=', '-', 'Home'].includes(event.key)) { event.preventDefault(); if (event.key === 'Home') fit(); else zoom(event.key === '-' ? .8 : 1.25) }
          }}>
          <g ref={viewportRef}>
            <g aria-hidden="true">{layout.edges.map(edge => <path key={edge.id} ref={element => { if (element) edgeElements.current.set(edge.id, element); else edgeElements.current.delete(edge.id) }} className={`brain-graph-edge is-${edge.kind}${highlightedLinks.has(edge.id) ? ' is-new' : ''}${activeNode && edgeEndpointIds(edge).includes(activeNode) ? ' is-active' : ''}`} pathLength={edge.kind === 'cross' ? 1 : undefined} vectorEffect="non-scaling-stroke" />)}</g>
            {layout.nodes.map(node => <g key={node.id} ref={element => { if (element) nodeElements.current.set(node.id, element); else nodeElements.current.delete(node.id) }}
              data-node-id={node.id} data-course-color={courseColorSlot(node.color)} data-kind={node.kind} data-overview-label={overviewLabels.has(node.id) ? 'true' : undefined} data-emphasis={highlightedNodes.has(node.id) || relatedNodes.has(node.id) ? 'true' : undefined}
              className="brain-graph-node" role="button" tabIndex={0} aria-label={`${c(node.kind === 'course' ? 'Course' : node.kind === 'topic' ? 'Topic' : 'Concept')}: ${node.label}`} aria-haspopup="dialog"
              onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); navigate(node.id) } }}
              onPointerEnter={() => setHovered(node.id)} onPointerLeave={() => setHovered(null)}
              onFocus={() => setFocused(node.id)} onBlur={() => setFocused(null)}>
              <title>{node.label}</title><circle className="brain-node-hit" r={22} fill="transparent" />
              {highlightedNodes.has(node.id) && <circle className="brain-node-arrival" r={node.radius + 9} vectorEffect="non-scaling-stroke" />}
              <circle className="brain-node-shape" r={node.radius} vectorEffect="non-scaling-stroke" />
              {node.kind === 'course' && <circle className="brain-course-core" r={8} />}
              <text className="brain-node-label" textAnchor="middle" aria-hidden="true">{node.label}</text>
            </g>)}
          </g>
        </svg>
        <div className="brain-graph-controls" aria-label={c('Graph controls')}>
          <button type="button" onClick={() => zoom(1.25)} aria-label={c('Zoom in')}><Plus size={18} /></button><button type="button" onClick={() => zoom(.8)} aria-label={c('Zoom out')}><Minus size={18} /></button><button type="button" onClick={fit} aria-label={c('Fit whole Brain')}><Maximize size={18} /></button>
          <button type="button" onClick={() => pan(80, 0)} aria-label={c('Pan left')}><ArrowLeft size={18} /></button><button type="button" onClick={() => pan(-80, 0)} aria-label={c('Pan right')}><ArrowRight size={18} /></button><button type="button" onClick={() => pan(0, 80)} aria-label={c('Pan up')}><ArrowUp size={18} /></button><button type="button" onClick={() => pan(0, -80)} aria-label={c('Pan down')}><ArrowDown size={18} /></button>
        </div>
      </div>
      <p className="brain-graph-help" id={instructionsId}>{c('Drag to pan · scroll or pinch to zoom · arrow keys to move · + / − to zoom · Home to fit. Enter opens a node. Or use List view.')}</p>
    </>}
    <div className="brain-graph-legend"><span><i className="is-contains" />{c('Course → topic → concept')}</span><span><i className="is-within" />{c('Within a course')}</span><span><i className="is-cross" />{c('Across courses')}</span><span>{c('Larger seeds appear in more passages.')}</span></div>
    <BrainConceptPanel node={selectedNode} graph={graph} api={api} onClose={() => setSelected(null)} onNavigate={navigate} presentation={presentation} />
  </section>
}

function GraphList({ graph, onNavigate }: { graph: GraphData; onNavigate: (id: string) => void }) {
  const c = useCopy()
  return <div className="brain-graph-list">{graph.courses.map(course => <details key={course.id} open data-course-color={courseColorSlot(course.color_index)}><summary><span className="brain-course-dot" />{course.title}</summary>
    {graph.topics.filter(topic => topic.course_id === course.id).map(topic => <details key={topic.id}><summary>{topic.title}</summary><ul>{graph.concepts.filter(concept => concept.topic_id === topic.id).map(concept => <li key={concept.id}><button type="button" onClick={() => onNavigate(`concept:${concept.id}`)}>{concept.name}<span>{c('View sources')}</span></button></li>)}</ul></details>)}
    {graph.concepts.filter(concept => concept.course_id === course.id && (!concept.topic_id || !graph.topics.some(topic => topic.id === concept.topic_id))).map(concept => <button type="button" className="brain-loose-concept" key={concept.id} onClick={() => onNavigate(`concept:${concept.id}`)}>{concept.name}</button>)}
  </details>)}</div>
}
