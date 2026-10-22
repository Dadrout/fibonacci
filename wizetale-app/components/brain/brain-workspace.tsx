'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { Activity, BookOpen, BrainCircuit, Check, ChevronRight, FilePlus2, GitBranch, GraduationCap, Inbox, LoaderCircle, Presentation, Send, Sparkles, TriangleAlert } from 'lucide-react'
import { useBrainApi, useBrainEvents, useBrainSession } from '@/hooks/use-brain-api'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { BrainItemCard } from '@/components/brain/brain-item-card'
import { BrainCourses } from '@/components/brain/brain-courses'
import { BrainExam } from '@/components/brain/brain-exam'
import { BrainTelegram } from '@/components/brain/brain-telegram'
import { FibonacciLogo, FibonacciMark } from '@/components/fibonacci-mark'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'
import { StudioIcon } from '@/components/studio-icon'
import { ThemeToggle } from '@/components/theme-toggle'
import type { BrainEvent, BrainGraph as GraphData, BrainItem, BrainOverview } from '@/lib/brain-types'
import { reduceGraph, reduceItems } from '@/lib/brain-api-helpers'
import { addConnection, groupGaps, updateOverview, withUiTimeout, type NewConnection } from './brain-ui-state'

const BrainGraph = dynamic(() => import('./brain-graph').then(module => module.BrainGraph), { loading: () => <BrainLoading /> })

type BrainTab = 'inbox' | 'graph' | 'courses' | 'exam' | 'telegram'

const tabs: Array<{ id: BrainTab; label: string; icon: typeof Inbox }> = [
  { id: 'inbox', label: 'Inbox', icon: Inbox },
  { id: 'graph', label: 'Graph', icon: GitBranch },
  { id: 'courses', label: 'Courses', icon: BookOpen },
  { id: 'exam', label: 'Exam', icon: GraduationCap },
  { id: 'telegram', label: 'Telegram', icon: Send },
]

function BrainLoading() {
  const c = useCopy()
  return <div className="brain-loading" aria-busy="true" aria-label={c('Loading your Brain')}>
    <div className="brain-loading-mark"><FibonacciMark size={34} filled={8} /></div>
    <div className="brain-loading-lines"><span /><span /><span /></div>
    <div className="brain-loading-card" /><div className="brain-loading-card" />
  </div>
}

export function BrainWorkspace() {
  const api = useBrainApi()
  const session = useBrainSession()
  const c = useCopy()
  const { language } = useLanguage()
  const [tab, setTab] = useState<BrainTab>('inbox')
  const [overview, setOverview] = useState<BrainOverview | null>(null)
  const [loadingOverview, setLoadingOverview] = useState(true)
  const [overviewError, setOverviewError] = useState(false)
  const [graph, setGraph] = useState<GraphData | null>(null)
  const graphRef = useRef<GraphData | null>(null)
  const [graphError, setGraphError] = useState(false)
  const [focusRequest, setFocusRequest] = useState<{ id: string; token: number } | null>(null)
  const [newlyFiled, setNewlyFiled] = useState<string[]>([])
  const filingTimers = useRef(new Map<string, number>())
  const [connections, setConnections] = useState<NewConnection[]>([])
  const seenEvents = useRef(new Set<string>())
  const eventVersion = useRef(0)
  const snapshotRequest = useRef(0)
  const reconcileTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconcileGraph = useRef(false)
  const [simulating, setSimulating] = useState(false)
  const [simulationError, setSimulationError] = useState(false)
  const [presentation, setPresentation] = useState(false)
  const [examCourseId, setExamCourseId] = useState<string | null>(null)
  const [presentationReady, setPresentationReady] = useState(false)

  const loadOverview = useCallback(async (refreshGraph = true) => {
    const request = ++snapshotRequest.current
    setLoadingOverview(true)
    setOverviewError(false)
    if (refreshGraph) setGraphError(false)
    // A snapshot fetched across an event boundary can overwrite newer live data.
    // Retry that read; keep the event-driven UI visible in the meantime.
    while (snapshotRequest.current === request) {
      const version = eventVersion.current
      const [overviewResult, graphResult] = await Promise.allSettled([withUiTimeout(api.overview()), refreshGraph ? withUiTimeout(api.graph()) : Promise.resolve(null)])
      if (snapshotRequest.current !== request) return
      if (version !== eventVersion.current) continue
      if (overviewResult.status === 'fulfilled') setOverview(overviewResult.value)
      else setOverviewError(true)
      if (graphResult.status === 'fulfilled' && graphResult.value) {
        graphRef.current = graphResult.value
        setGraph(graphResult.value)
      } else if (graphResult.status === 'rejected') setGraphError(true)
      setLoadingOverview(false)
      break
    }
  }, [api])

  useEffect(() => {
    if (session.canUse) void loadOverview()
    return () => { snapshotRequest.current += 1 }
  }, [loadOverview, session.canUse])

  useEffect(() => {
    try {
      setPresentation(window.localStorage.getItem('fibonacci:brain:presentation-mode:v1') === '1')
    } catch {
      setPresentation(false)
    }
    setPresentationReady(true)
  }, [])

  useEffect(() => {
    if (!presentationReady) return
    try {
      window.localStorage.setItem('fibonacci:brain:presentation-mode:v1', presentation ? '1' : '0')
    } catch {
      // The toggle remains usable if storage is disabled.
    }
  }, [presentation, presentationReady])

  useEffect(() => () => {
    filingTimers.current.forEach(timer => window.clearTimeout(timer))
    if (reconcileTimer.current !== null) clearTimeout(reconcileTimer.current)
  }, [])

  const handleEvent = useCallback((event: BrainEvent) => {
    if (seenEvents.current.has(event.id)) return
    seenEvents.current.add(event.id)
    if (seenEvents.current.size > 2000) seenEvents.current.delete(seenEvents.current.values().next().value!)
    eventVersion.current += 1
    let nextGraph = graphRef.current ? reduceGraph(graphRef.current, event) : null
    if (nextGraph && event.type === 'link.created') {
      // reduceGraph adds the concepts/edge; the event also supplies their course metadata.
      const courses = new Map(nextGraph.courses.map(course => [course.id, course]))
      courses.set(event.source_course.id, event.source_course)
      courses.set(event.target_course.id, event.target_course)
      nextGraph = { ...nextGraph, courses: [...courses.values()] }
    }
    if (nextGraph !== graphRef.current) { graphRef.current = nextGraph; setGraph(nextGraph) }
    setOverview(current => current ? updateOverview(current, event, reduceItems(current.recent_items, event), nextGraph) : current)
    setConnections(current => addConnection(current, event))

    if (event.type === 'item.filed') {
      setNewlyFiled((current) => [...current.filter((id) => id !== event.item.id), event.item.id])
      window.clearTimeout(filingTimers.current.get(event.item.id))
      filingTimers.current.set(event.item.id, window.setTimeout(() => {
        setNewlyFiled(current => current.filter(id => id !== event.item.id))
        filingTimers.current.delete(event.item.id)
      }, 4200))
    }

    if (['item.filed', 'item.refiled', 'item.deleted', 'link.created'].includes(event.type)) {
      // Reconcile items outside the 20-row window and any replay after a reconnect.
      // Debounce the burst; counters and graph have already updated immediately.
      if (reconcileTimer.current !== null) clearTimeout(reconcileTimer.current)
      reconcileGraph.current ||= event.type === 'item.refiled' || event.type === 'item.deleted' || !nextGraph
      reconcileTimer.current = setTimeout(() => {
        const refreshGraph = reconcileGraph.current
        reconcileGraph.current = false
        void loadOverview(refreshGraph)
      }, 1000)
    }
  }, [loadOverview])

  const { connected } = useBrainEvents(handleEvent, session.canUse)
  const itemUpdate = useCallback((updated: BrainItem) => {
    const event: BrainEvent = { type: 'item.refiled', item: updated, id: `local:${updated.id}`, at: new Date().toISOString() }
    setOverview(current => current ? updateOverview(current, event, reduceItems(current.recent_items, event), graphRef.current) : current)
  }, [])

  const orderedItems = useMemo(() => overview?.recent_items ?? [], [overview?.recent_items])
  const isEmpty = Boolean(overview && overview.counts.items === 0 && overview.counts.processing === 0 && orderedItems.length === 0)
  const presentationActive = presentationReady && presentation
  const gaps = useMemo(() => groupGaps(overview?.gaps ?? []), [overview?.gaps])
  const courseColors = useMemo(() => new Map(graph?.courses.map(course => [course.id, course.color_index]) ?? []), [graph?.courses])
  const simulate = async () => {
    setSimulating(true)
    setSimulationError(false)
    try { await api.simulateHeroDemo() } catch { setSimulationError(true) } finally { setSimulating(false) }
  }
  const tabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const currentIndex = tabs.findIndex((entry) => entry.id === tab)
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (currentIndex + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
    const next = tabs[nextIndex]
    setTab(next.id)
    document.getElementById(`brain-tab-${next.id}`)?.focus()
  }

  if (session.status === 'loading') return <BrainLoading />
  if (!session.canUse) return <SignInPrompt title="Sign in to your Brain" message="Your study materials are private. Sign in to keep building your Brain." />

  return <main className={`brain-app app-content-page${presentationActive ? ' is-presentation' : ''}`} data-workspace-role="student" data-brain-tab={tab}>
    <a className="brain-skip" href="#brain-content">{c('Skip to content')}</a>
    <header className="brain-header prep-screen">
      <Link href="/create" className="brain-brand" aria-label={c('Fibonacci home')}><FibonacciLogo size={30} /></Link>
      <nav className="brain-global-nav" aria-label={c('Learning workspace')}>
        <Link href="/create"><StudioIcon name="edit" />{c('Create')}</Link>
        <Link href="/study"><StudioIcon name="cards" />{c('Study')}</Link>
        <Link href="/history"><StudioIcon name="book" />{c('Library')}</Link>
        <Link href="/brain" aria-current="page"><BrainCircuit size={16} aria-hidden="true" />{c('Brain')}</Link>
      </nav>
      <div className="brain-header-tools">
        {session.demo && <span className="brain-demo-badge">{c('Demo')}</span>}
        <button type="button" className="brain-presentation-toggle" aria-pressed={presentationActive} aria-label={c(presentationActive ? 'Exit presentation mode' : 'Presentation mode')} onClick={() => setPresentation((value) => !value)}>
          <Presentation size={17} aria-hidden="true" /><span>{c(presentationActive ? 'Exit presentation mode' : 'Presentation mode')}</span>
        </button>
        <LanguagePicker />
        <ThemeToggle />
      </div>
    </header>

    <div className="brain-content" id="brain-content">
      <section className="brain-page-heading">
        <div className="brain-heading-copy">
          <p className="brain-eyebrow"><FibonacciMark size={19} filled={1} />{c('Your second brain')}</p>
          <h1>{c('Your Brain')}</h1>
          <p>{c('Send anything. Fibonacci sorts it, connects it, and keeps the sources close.')}</p>
        </div>
        {overview && <div className="brain-stats" aria-label={c('Brain overview')}>
          <div><strong>{overview.counts.items}</strong><span>{c('Sources filed')}</span></div>
          <div><strong>{overview.counts.courses}</strong><span>{c('Courses')}</span></div>
          <div><strong>{overview.counts.concepts}</strong><span>{c('Concepts')}</span></div>
          <div><strong>{overview.counts.cross_links}</strong><span>{c('Cross-course links')}</span></div>
        </div>}
      </section>

      <div className="brain-tabs-row">
        <div className="brain-tabs" role="tablist" aria-label={c('Brain sections')} onKeyDown={tabKeyDown}>
          {tabs.map(({ id, label, icon: Icon }) => <button key={id} id={`brain-tab-${id}`} type="button" role="tab" aria-selected={tab === id} aria-controls={`brain-panel-${id}`} tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}>
            <Icon size={17} aria-hidden="true" /><span>{c(label)}</span>{id === 'inbox' && overview && overview.counts.processing > 0 && <span className="brain-tab-count">{overview.counts.processing}</span>}
          </button>)}
        </div>
        <div className="brain-live-status" role="status"><span className={connected ? 'is-connected' : ''} />{connected ? c('Live') : c('Reconnecting')}</div>
      </div>

      <div className="brain-tab-panel" id={`brain-panel-${tab}`} role="tabpanel" aria-labelledby={`brain-tab-${tab}`} tabIndex={0}>
        {(tab === 'inbox' || tab === 'graph') && <>
          <div className="brain-live-actions">
            <span className="brain-processing-count" role="status"><Activity size={16} aria-hidden="true" />{overview ? `${overview.counts.processing} ${c('in progress')}` : c('Loading sources')}</span>
            {api.mode === 'mock' && <button type="button" className="brain-simulate-button" disabled={simulating || loadingOverview} onClick={() => void simulate()}><Sparkles size={15} aria-hidden="true" />{simulating ? c('Simulating…') : c('Simulate Telegram demo')}</button>}
          </div>
          {simulationError && <p role="alert">{c('Check your connection and try again.')}</p>}
          <div className="brain-connections" aria-live="polite" aria-relevant="additions">
            {connections.map(connection => <aside className="brain-connection-banner" key={connection.link.id}>
              <span className="brain-connection-symbol"><GitBranch size={23} aria-hidden="true" /></span>
              <span className="brain-connection-copy"><strong>{c('New cross-course connection')}</strong><span>{connection.source.name} <b aria-hidden="true">↔</b> {connection.target.name}</span><small>{connection.source_course.title} ↔ {connection.target_course.title}</small></span>
              <button type="button" aria-label={`${c('Dismiss')}: ${connection.source.name} ↔ ${connection.target.name}`} onClick={() => setConnections(current => current.filter(entry => entry.link.id !== connection.link.id))}>×</button>
            </aside>)}
          </div>
        </>}
        {tab === 'inbox' ? <>
          <div className="brain-inbox-heading">
            <div><p className="brain-section-kicker">{c('Automatically filed')}</p><h2>{c('Your sources, finding their place')}</h2><p>{c('New material moves from capture to course while you keep studying.')}</p></div>
          </div>
          {gaps.map(gap => <aside className="brain-gap-alert" key={gap.id}>
            <span className="brain-gap-icon"><TriangleAlert size={19} aria-hidden="true" /></span>
            <div><strong>{gap.title}</strong><span>{gap.sequences.map(sequence => {
              const keys = { week: 'Missing weeks: {numbers}', lecture: 'Missing lectures: {numbers}', chapter: 'Missing chapters: {numbers}', module: 'Missing modules: {numbers}' }
              const numbers = new Intl.ListFormat(language, { style: 'long', type: 'conjunction' }).format(sequence.missing.map(String))
              return c(keys[sequence.kind]).replace('{numbers}', numbers)
            }).join(' · ')}</span></div>
            <button type="button" className="brain-text-button" onClick={() => { setFocusRequest({ id: `course:${gap.id}`, token: Date.now() }); setTab('graph') }}>{c('View course')}<ChevronRight size={16} aria-hidden="true" /></button>
          </aside>)}

          {loadingOverview && !overview ? <div className="brain-source-skeletons" aria-busy="true" aria-label={c('Loading sources')}>
            {[0, 1, 2].map((number) => <div className="brain-source-skeleton" key={number}><span /><div><i /><i /><i /></div></div>)}
          </div> : overviewError ? <div className="brain-load-error" role="alert"><TriangleAlert size={24} aria-hidden="true" /><div><strong>{c('Your Brain could not load.')}</strong><p>{c('Check your connection and try again.')}</p></div><button type="button" className="brain-secondary-button" onClick={() => void loadOverview()}>{c('Try again')}</button></div> : isEmpty ? <section className="brain-onboarding" aria-labelledby="brain-onboarding-title">
            <div className="brain-onboarding-mark"><FibonacciMark size={54} filled={5} /></div>
            <div className="brain-onboarding-copy"><p className="brain-section-kicker">{c('A lighter way to study')}</p><h2 id="brain-onboarding-title">{c('Just send us anything.')}</h2><p>{c('Drop a photo, paste a link or notes, or send a lecture to Fibonacci on Telegram. Your Brain will sort it into the right course and topic.')}</p>
              <div className="brain-onboarding-actions"><button type="button" className="brain-primary-button" onClick={() => window.dispatchEvent(new Event('brain:open-picker'))}><FilePlus2 size={18} aria-hidden="true" />{c('Add a file')}</button><button type="button" className="brain-secondary-button" onClick={() => setTab('telegram')}><Send size={17} aria-hidden="true" />{c('Connect Telegram')}</button></div>
            </div>
            <ol className="brain-onboarding-steps"><li><span>1</span>{c('Drop files anywhere')}</li><li><span>2</span>{c('Paste a link, text, or photo')}</li><li><span>3</span>{c('Fibonacci files it for you')}</li></ol>
          </section> : <div className="brain-item-list" aria-label={c('Recent captures')}>
            {orderedItems.map((item) => <BrainItemCard key={item.id} item={item} api={api} courseColor={courseColors.get(item.course_id ?? '')} recentlyFiled={newlyFiled.includes(item.id)} onItemChange={itemUpdate} />)}
            {orderedItems.length === 0 && !loadingOverview && <p className="brain-no-recent">{c('No recent sources yet.')}</p>}
          </div>}
        </> : tab === 'graph' ? <BrainGraph graph={graph} api={api} loading={loadingOverview} error={graphError} onRetry={loadOverview} connections={connections} presentation={presentationActive} focusRequest={focusRequest} />
          : tab === 'courses' ? <BrainCourses api={api} graph={graph} version={eventVersion.current} onStartExam={(courseId) => { setExamCourseId(courseId); setTab('exam') }} />
          : tab === 'exam' ? <BrainExam api={api} graph={graph} courseId={examCourseId} presentation={presentationActive} />
          : tab === 'telegram' ? <BrainTelegram api={api} />
          : <BrainPlaceholder tab={tab} c={c} />}
      </div>

      <footer className="brain-footer"><span><Check size={15} aria-hidden="true" />{c('Every source stays yours.')}</span><span>{c('The Brain grows with every class.')}</span></footer>
    </div>
  </main>
}

function BrainPlaceholder({ tab, c }: { tab: Exclude<BrainTab, 'inbox'>; c: (text: string) => string }) {
  const content: Record<Exclude<BrainTab, 'inbox'>, { icon: typeof GitBranch; eyebrow: string; title: string; description: string }> = {
    graph: { icon: GitBranch, eyebrow: 'Across your courses', title: 'Your idea map is next.', description: 'The Brain will show the concepts and connections growing out of your sources.' },
    courses: { icon: BookOpen, eyebrow: 'Course by course', title: 'Your courses are taking shape.', description: 'Every filed source will appear with its topics, concepts, and coverage gaps.' },
    exam: { icon: GraduationCap, eyebrow: 'Built from your sources', title: 'Your next exam plan is close.', description: 'A study plan, cited notes, flashcards, and quiz will be built from your Brain.' },
    telegram: { icon: Send, eyebrow: 'Capture from your chats', title: 'Send it from Telegram.', description: 'Connect the Fibonacci bot to forward lecture photos, links, PDFs, and voice notes.' },
  }
  const item = content[tab]
  const Icon = item.icon
  return <section className="brain-coming-soon" aria-labelledby="brain-coming-title">
    <div className="brain-coming-icon"><Icon size={27} aria-hidden="true" /></div>
    <p className="brain-section-kicker">{c(item.eyebrow)}</p>
    <h2 id="brain-coming-title">{c(item.title)}</h2>
    <p>{c(item.description)}</p>
    <span className="brain-coming-status"><LoaderCircle size={15} aria-hidden="true" />{c('This section is coming next.')}</span>
    <button type="button" className="brain-secondary-button" onClick={() => document.getElementById('brain-tab-inbox')?.click()}><Inbox size={16} aria-hidden="true" />{c('Back to inbox')}</button>
  </section>
}
