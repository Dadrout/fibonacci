'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { Activity, ArrowLeft, ArrowLeftRight, Check, ChevronRight, FilePlus2, GitBranch, LayoutGrid, Presentation, Send, Sparkles, TriangleAlert, UploadCloud, X } from 'lucide-react'
import { useBrainApi, useBrainEvents, useBrainSession } from '@/hooks/use-brain-api'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { BrainItemCard } from '@/components/brain/brain-item-card'
import { CourseDetailView, CourseGrid } from '@/components/brain/brain-courses'
import { BrainDialog } from '@/components/brain/brain-dialog'
import { BrainDemoTools } from '@/components/brain/brain-demo-tools'
import { BrainPresentation } from '@/components/brain/brain-presentation'
import { BrainExam } from '@/components/brain/brain-exam'
import { BrainTelegram } from '@/components/brain/brain-telegram'
import { BrainSearch } from '@/components/brain/brain-search'
import { FibonacciLogo, FibonacciMark } from '@/components/fibonacci-mark'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'
import { ThemeToggle } from '@/components/theme-toggle'
import type { BrainEvent, BrainGraph as GraphData, BrainItem, BrainOverview } from '@/lib/brain-types'
import { reduceGraph, reduceItems } from '@/lib/brain-api-helpers'
import { addConnection, groupGaps, updateOverview, withUiTimeout, type NewConnection } from './brain-ui-state'

const BrainGraph = dynamic(() => import('./brain-graph').then(module => module.BrainGraph), { loading: () => <BrainLoading /> })

/** One home, then drill-down: Home → Course → Exam (or Home → All sources). No tabs. */
type View =
  | { name: 'home' }
  | { name: 'sources' }
  | { name: 'course'; courseId: string }
  | { name: 'presentation'; courseId: string; back: { name: 'home' } | { name: 'course'; courseId: string } }
  | { name: 'exam'; autoStart?: boolean; section?: 'cards' | 'quiz'; courseId: string | null; back: { name: 'home' } | { name: 'course'; courseId: string } }

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
  const [view, setView] = useState<View>({ name: 'home' })
  const [homeMode, setHomeMode] = useState<'courses' | 'map'>('courses')
  const [telegramOpen, setTelegramOpen] = useState(false)
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
  const hasOverview = useRef(false)
  const refreshRetry = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [simulating, setSimulating] = useState(false)
  const [simulationError, setSimulationError] = useState(false)
  const [presentation, setPresentation] = useState(false)
  const [presentationReady, setPresentationReady] = useState(false)

  // The floating Add button repeats the capture bar's "Add a file"; hide it while the bar is on screen.
  const watchCaptureBar = useCallback((node: HTMLElement | null) => {
    if (!node || typeof IntersectionObserver === 'undefined') return
    const root = document.documentElement
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) root.dataset.brainCaptureVisible = '1'
      else delete root.dataset.brainCaptureVisible
    })
    observer.observe(node)
    return () => { observer.disconnect(); delete root.dataset.brainCaptureVisible }
  }, [])

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
      if (overviewResult.status === 'fulfilled') {
        hasOverview.current = true
        setOverview(overviewResult.value)
      } else {
        setOverviewError(true)
        // A failed background refresh keeps the current screen and quietly tries again.
        if (hasOverview.current) {
          if (refreshRetry.current !== null) clearTimeout(refreshRetry.current)
          refreshRetry.current = setTimeout(() => { refreshRetry.current = null; void loadOverview(refreshGraph) }, 4000)
        }
      }
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
    return () => {
      snapshotRequest.current += 1
      if (refreshRetry.current !== null) clearTimeout(refreshRetry.current)
    }
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
    if (event.type === 'telegram.linked') setOverview(current => current ? { ...current, telegram: event.telegram } : current)

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
  // Older sources for "All sources": the overview carries the newest 20; the rest load page by page.
  const [olderItems, setOlderItems] = useState<BrainItem[]>([])
  const [olderCursor, setOlderCursor] = useState<string | null | undefined>(undefined)
  const [olderState, setOlderState] = useState<'idle' | 'loading' | 'error'>('idle')

  const itemUpdate = useCallback((updated: BrainItem) => {
    const event: BrainEvent = { type: 'item.refiled', item: updated, id: `local:${updated.id}`, at: new Date().toISOString() }
    setOverview(current => current ? updateOverview(current, event, reduceItems(current.recent_items, event), graphRef.current) : current)
    setOlderItems(list => list.map(item => item.id === updated.id ? updated : item))
  }, [])

  const itemDeleted = useCallback((id: string) => {
    setOverview(current => current ? { ...current, recent_items: current.recent_items.filter(item => item.id !== id) } : current)
    setOlderItems(items => items.filter(item => item.id !== id))
    void loadOverview(true)
  }, [loadOverview])

  const orderedItems = useMemo(() => overview?.recent_items ?? [], [overview?.recent_items])
  const allSources = useMemo(() => {
    const seen = new Set(orderedItems.map(item => item.id))
    return [...orderedItems, ...olderItems.filter(item => !seen.has(item.id))]
  }, [orderedItems, olderItems])
  const totalSources = overview ? overview.counts.items + overview.counts.processing + (overview.counts.failed ?? 0) : 0
  const canLoadOlder = olderCursor === undefined ? allSources.length < totalSources : olderCursor !== null
  const loadOlder = async () => {
    const cursor = olderCursor ?? allSources[allSources.length - 1]?.captured_at
    if (!cursor || olderState === 'loading') return
    setOlderState('loading')
    try {
      const page = await withUiTimeout(api.items({ limit: 25, cursor }))
      setOlderItems(list => [...list, ...page.items])
      setOlderCursor(page.next_cursor)
      setOlderState('idle')
    } catch {
      setOlderState('error')
    }
  }
  const isEmpty = Boolean(overview && overview.counts.items === 0 && overview.counts.processing === 0 && orderedItems.length === 0)
  const presentationActive = presentationReady && presentation
  const gaps = useMemo(() => groupGaps(overview?.gaps ?? []), [overview?.gaps])
  const courseColors = useMemo(() => new Map(graph?.courses.map(course => [course.id, course.color_index]) ?? []), [graph?.courses])
  const catalog = useMemo(() => graph ? { courses: graph.courses, topics: graph.topics } : null, [graph])
  const simulate = async () => {
    setSimulating(true)
    setSimulationError(false)
    try { await api.simulateHeroDemo() } catch { setSimulationError(true) } finally { setSimulating(false) }
  }
  const go = useCallback((next: View, behavior: ScrollBehavior = 'auto') => {
    setView(next)
    window.scrollTo({ top: 0, behavior })
  }, [])
  const [examToken, setExamToken] = useState(0)
  const showMap = () => {
    setHomeMode('map')
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    window.setTimeout(() => document.getElementById('brain-courses-title')?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' }), 60)
  }
  const openExam = (courseId: string | null, back: Extract<View, { name: 'exam' }>['back'], section?: 'cards' | 'quiz', autoStart = true) => { setExamToken(token => token + 1); go({ name: 'exam', courseId, back, section, autoStart }) }
  const liveItems = useMemo(() => {
    // Home shows what is arriving or just filed; failures live under "All sources" with their Retry.
    const active = orderedItems.filter(item => !['filed', 'failed'].includes(item.status) || newlyFiled.includes(item.id))
    return active.length ? active.slice(0, 6) : orderedItems.filter(item => item.status === 'filed').slice(0, 3)
  }, [orderedItems, newlyFiled])
  const telegram = overview?.telegram

  if (session.status === 'loading') return <BrainLoading />
  if (!session.canUse) return <SignInPrompt title="Sign in to your Brain" message="Your study materials are private. Sign in to keep building your Brain." />

  const counts = overview?.counts
  return <main className={`brain-app app-content-page${presentationActive ? ' is-presentation' : ''}`} data-workspace-role="student" data-brain-view={view.name}>
    <a className="brain-skip" href="#brain-content">{c('Skip to content')}</a>
    <header className="brain-header brain-header-simple prep-screen">
      <button type="button" className="brain-brand" aria-label={c('Your Brain')} onClick={() => go({ name: 'home' })}><FibonacciLogo size={30} /></button>
      {(session.demo || overview?.demo_mode) && <BrainDemoTools api={api} canReset={session.demo} presentation={presentationActive}
        onSent={() => {
          go({ name: 'home' }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth')
          setHomeMode('courses')
        }}
        onReset={() => {
          setConnections([])
          setNewlyFiled([])
          setOlderItems([])
          setOlderCursor(undefined)
          go({ name: 'home' }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth')
          setHomeMode('courses')
          void loadOverview(true)
        }} />}
      <BrainSearch api={api} courses={graph?.courses ?? []} presentation={presentationActive}
        onOpenConcept={(conceptId) => { setFocusRequest({ id: `concept:${conceptId}`, token: Date.now() }); setHomeMode('map'); go({ name: 'home' }) }} />
      <div className="brain-header-tools">
        <button type="button" className={`brain-telegram-pill${telegram?.linked ? ' is-linked' : ''}`} onClick={() => setTelegramOpen(true)}>
          <Send size={16} aria-hidden="true" />
          <span>{telegram?.linked ? (telegram.telegram_username ? `@${telegram.telegram_username}` : c('Telegram connected')) : c('Connect Telegram')}</span>
          {telegram?.linked && <Check size={15} aria-hidden="true" />}
        </button>
        <button type="button" className="brain-icon-toggle" aria-pressed={presentationActive} title={c(presentationActive ? 'Exit presentation mode' : 'Presentation mode')}
          aria-label={c(presentationActive ? 'Exit presentation mode' : 'Presentation mode')} onClick={() => setPresentation(value => !value)}>
          <Presentation size={18} aria-hidden="true" />
        </button>
        <LanguagePicker />
        <ThemeToggle />
      </div>
    </header>

    <div className="brain-content" id="brain-content">
      {view.name === 'home' && <>
        <section className="brain-home-intro">
          <h1>{c('Your Brain')}</h1>
          {counts && <p className="brain-stat-line">
            <span><b>{counts.items}</b> {c('sources')}</span><span><b>{counts.courses}</b> {c('courses')}</span>
            <span><b>{counts.concepts}</b> {c('concepts')}</span><span><b>{counts.cross_links}</b> {c('links between courses')}</span>
          </p>}
        </section>

        <section className="brain-capture-bar" ref={watchCaptureBar} aria-label={c('Add to your Brain')}>
          <UploadCloud size={30} aria-hidden="true" />
          <div>
            <strong>{c('Drop anything here')}</strong>
            <p>{c('Slide photos, PDFs, lecture links, voice notes, or notes — Fibonacci files them into the right course.')}</p>
            <p className="brain-capture-hint">{c('Paste with Ctrl+V, or forward it to the Telegram bot.')}{telegram?.bot_username && <> <b>@{telegram.bot_username}</b></>}</p>
          </div>
          <button type="button" className="brain-primary-button" onClick={() => window.dispatchEvent(new Event('brain:open-picker'))}><FilePlus2 size={18} aria-hidden="true" />{c('Add a file')}</button>
        </section>

        {connections.length > 0 && <section className="brain-connections" aria-labelledby="brain-connections-title" aria-live="polite" aria-relevant="additions">
          <header>
            <span className="brain-connection-symbol"><GitBranch size={19} aria-hidden="true" /></span>
            <h2 id="brain-connections-title">{c(connections.length === 1 ? 'New connection between your courses' : 'New connections between your courses')}<span className="brain-connection-count">{connections.length}</span></h2>
            <button type="button" className="brain-connections-map" onClick={showMap}>{c('See on the map')}<ChevronRight size={15} aria-hidden="true" /></button>
            <button type="button" className="brain-connections-close" aria-label={c('Dismiss')} onClick={() => setConnections([])}><X size={18} aria-hidden="true" /></button>
          </header>
          <ul>
            {connections.map(connection => <li key={connection.link.id}>
              <span className="brain-connection-pair">{connection.source.name}<ArrowLeftRight size={15} aria-hidden="true" /><span className="sr-only"> – </span>{connection.target.name}</span>
              <small>{connection.source_course.title} · {connection.target_course.title}</small>
            </li>)}
          </ul>
        </section>}

        {loadingOverview && !overview ? <div className="brain-source-skeletons" aria-busy="true" aria-label={c('Loading sources')}>
          {[0, 1].map((number) => <div className="brain-source-skeleton" key={number}><span /><div><i /><i /><i /></div></div>)}
        </div> : overviewError && !overview ? <div className="brain-load-error" role="alert"><TriangleAlert size={24} aria-hidden="true" /><div><strong>{c('Your Brain could not load.')}</strong><p>{c('Check your connection and try again.')}</p></div><button type="button" className="brain-secondary-button" onClick={() => void loadOverview()}>{c('Try again')}</button></div>
        : isEmpty ? <section className="brain-onboarding" aria-labelledby="brain-onboarding-title">
          <div className="brain-onboarding-mark"><FibonacciMark size={54} filled={5} /></div>
          <div className="brain-onboarding-copy"><p className="brain-section-kicker">{c('A lighter way to study')}</p><h2 id="brain-onboarding-title">{c('Just send us anything.')}</h2><p>{c('Drop a photo, paste a link or notes, or send a lecture to Fibonacci on Telegram. Your Brain will sort it into the right course and topic.')}</p></div>
          <ol className="brain-onboarding-steps"><li><span>1</span>{c('Drop files anywhere')}</li><li><span>2</span>{c('Paste a link, text, or photo')}</li><li><span>3</span>{c('Fibonacci files it for you')}</li></ol>
        </section>
        : <>
          <section className="brain-live-strip" aria-labelledby="brain-live-title">
            <div className="brain-section-row">
              <h2 id="brain-live-title">{liveItems.some(item => item.status !== 'filed') ? c('Arriving now') : c('Just added')}</h2>
              <span className="brain-live-meta">
                <span className="brain-live-status" role="status"><span className={connected ? 'is-connected' : ''} />{connected ? c('Live') : c('Reconnecting')}</span>
                {counts && counts.processing > 0 && <span className="brain-processing-count"><Activity size={15} aria-hidden="true" />{counts.processing} {c('in progress')}</span>}
                {api.mode === 'mock' && <button type="button" className="brain-simulate-button" disabled={simulating || loadingOverview} onClick={() => void simulate()}><Sparkles size={15} aria-hidden="true" />{simulating ? c('Simulating…') : c('Simulate Telegram demo')}</button>}
                <button type="button" className="brain-text-button" onClick={() => go({ name: 'sources' })}>{c('All sources')}{counts ? ` (${counts.items})` : ''}<ChevronRight size={16} aria-hidden="true" /></button>
              </span>
            </div>
            {simulationError && <p role="alert">{c('Check your connection and try again.')}</p>}
            <div className="brain-item-list">
              {liveItems.map(item => <BrainItemCard key={item.id} item={item} api={api} catalog={catalog} courseColor={courseColors.get(item.course_id ?? '')} recentlyFiled={newlyFiled.includes(item.id)} onItemChange={itemUpdate} onDeleted={itemDeleted} />)}
            </div>
          </section>

          <section className="brain-courses-section" aria-labelledby="brain-courses-title">
            <div className="brain-section-row">
              <h2 id="brain-courses-title">{c('Your courses')}</h2>
              <div className="brain-segmented" role="group" aria-label={c('Show courses as')}>
                <button type="button" aria-pressed={homeMode === 'courses'} onClick={() => setHomeMode('courses')}><LayoutGrid size={16} aria-hidden="true" />{c('Courses')}</button>
                <button type="button" aria-pressed={homeMode === 'map'} onClick={showMap}><GitBranch size={16} aria-hidden="true" />{c('Map')}</button>
              </div>
            </div>
            {homeMode === 'courses'
              ? <CourseGrid graph={graph} gaps={overview?.gaps ?? []} onOpen={(courseId) => go({ name: 'course', courseId })} onChooseDate={courseId => openExam(courseId, { name: 'home' }, undefined, false)} onExam={(courseId) => openExam(courseId, { name: 'home' })} onFlashcards={courseId => openExam(courseId, { name: 'home' }, 'cards')} onQuiz={courseId => openExam(courseId, { name: 'home' }, 'quiz')} onPresentation={courseId => go({ name: 'presentation', courseId, back: { name: 'home' } })} />
              : <BrainGraph graph={graph} api={api} loading={loadingOverview} error={graphError} onRetry={loadOverview} connections={connections} presentation={presentationActive} focusRequest={focusRequest} />}
          </section>
        </>}
      </>}

      {view.name === 'sources' && <section className="brain-subpage" aria-labelledby="brain-sources-title">
        <button type="button" className="brain-text-button brain-course-back" onClick={() => go({ name: 'home' })}><ArrowLeft size={16} aria-hidden="true" />{c('Back to your Brain')}</button>
        <h2 id="brain-sources-title">{c('All sources')}</h2>
        {gaps.map(gap => <aside className="brain-gap-alert" key={gap.id}>
          <span className="brain-gap-icon"><TriangleAlert size={19} aria-hidden="true" /></span>
          <div><strong>{gap.title}</strong><span>{gap.sequences.map(sequence => {
            const keys = { week: 'Missing weeks: {numbers}', lecture: 'Missing lectures: {numbers}', chapter: 'Missing chapters: {numbers}', module: 'Missing modules: {numbers}' }
            const numbers = new Intl.ListFormat(language, { style: 'long', type: 'conjunction' }).format(sequence.missing.map(String))
            return c(keys[sequence.kind]).replace('{numbers}', numbers)
          }).join(' · ')}</span></div>
          <button type="button" className="brain-text-button" onClick={() => go({ name: 'course', courseId: gap.id })}>{c('Open course')}<ChevronRight size={16} aria-hidden="true" /></button>
        </aside>)}
        <div className="brain-item-list" aria-label={c('Recent captures')}>
          {allSources.map((item) => <BrainItemCard key={item.id} item={item} api={api} catalog={catalog} courseColor={courseColors.get(item.course_id ?? '')} recentlyFiled={newlyFiled.includes(item.id)} onItemChange={itemUpdate} onDeleted={itemDeleted} />)}
          {allSources.length === 0 && !loadingOverview && <p className="brain-no-recent">{c('No recent sources yet.')}</p>}
        </div>
        {allSources.length > 0 && <div className="brain-show-more">
          <p>{c('Showing {shown} of {total}').replace('{shown}', String(allSources.length)).replace('{total}', String(Math.max(totalSources, allSources.length)))}</p>
          {canLoadOlder && <button type="button" className="brain-secondary-button" disabled={olderState === 'loading'} onClick={() => void loadOlder()}>{olderState === 'loading' ? c('Loading…') : c('Show more sources')}</button>}
          {olderState === 'error' && <p role="alert" className="brain-item-action-error">{c('Could not load more sources. Try again.')}</p>}
        </div>}
      </section>}

      {view.name === 'course' && <CourseDetailView api={api} catalog={catalog} courseId={view.courseId} version={eventVersion.current}
        onFlashcards={courseId => openExam(courseId, { name: 'course', courseId }, 'cards')} onQuiz={courseId => openExam(courseId, { name: 'course', courseId }, 'quiz')} onPresentation={courseId => go({ name: 'presentation', courseId, back: { name: 'course', courseId } })}
        onChanged={() => { setOlderItems([]); setOlderCursor(undefined); void loadOverview(true) }}
        onChooseDate={courseId => openExam(courseId, { name: 'course', courseId }, undefined, false)} onBack={() => go({ name: 'home' })} onStartExam={(courseId) => openExam(courseId, { name: 'course', courseId })} />}

      {view.name === 'exam' && <section className="brain-subpage">
        <button type="button" className="brain-text-button brain-course-back" onClick={() => go(view.back)}><ArrowLeft size={16} aria-hidden="true" />{view.back.name === 'course' ? c('Back to the course') : c('Back to your Brain')}</button>
        <BrainExam key={`${view.courseId}:${examToken}`} api={api} graph={graph} courseId={view.courseId} presentation={presentationActive} autoStart={Boolean(view.courseId) && view.autoStart !== false} initialSection={view.section} />
      </section>}

      {view.name === 'presentation' && <section className="brain-subpage">
        <button type="button" className="brain-text-button brain-course-back" onClick={() => go(view.back)}><ArrowLeft size={16} aria-hidden="true" />{view.back.name === 'course' ? c('Back to the course') : c('Back to your Brain')}</button>
        <BrainPresentation key={view.courseId} api={api} courseId={view.courseId} courseTitle={graph?.courses.find(course => course.id === view.courseId)?.title ?? ''} presentation={presentationActive} onHome={() => go({ name: 'home' })} onBack={() => go({ name: 'course', courseId: view.courseId })} />
      </section>}

      <footer className="brain-footer"><span><Check size={15} aria-hidden="true" />{c('Every source stays yours.')}</span><span>{c('The Brain grows with every class.')}</span></footer>
    </div>

    <BrainDialog open={telegramOpen} onClose={() => setTelegramOpen(false)} title={c('Telegram')} description={c('Forward anything to the bot and it appears in your Brain.')} presentation={presentationActive}>
      <BrainTelegram api={api} />
    </BrainDialog>
  </main>
}
