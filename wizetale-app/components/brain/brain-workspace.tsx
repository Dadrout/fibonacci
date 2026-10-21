'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import Link from 'next/link'
import { Activity, BookOpen, BrainCircuit, Check, ChevronRight, FilePlus2, GitBranch, GraduationCap, Inbox, LoaderCircle, Presentation, Send, Sparkles, TriangleAlert } from 'lucide-react'
import { useBrainApi, useBrainEvents, useBrainSession } from '@/hooks/use-brain-api'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { BrainItemCard } from '@/components/brain/brain-item-card'
import { FibonacciLogo, FibonacciMark } from '@/components/fibonacci-mark'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'
import { StudioIcon } from '@/components/studio-icon'
import { ThemeToggle } from '@/components/theme-toggle'
import type { BrainEvent, BrainItem, BrainOverview, GapAlert } from '@/lib/brain-types'
import { reduceItems } from '@/lib/brain-api-helpers'

type BrainTab = 'inbox' | 'graph' | 'courses' | 'exam' | 'telegram'

const tabs: Array<{ id: BrainTab; label: string; icon: typeof Inbox }> = [
  { id: 'inbox', label: 'Inbox', icon: Inbox },
  { id: 'graph', label: 'Graph', icon: GitBranch },
  { id: 'courses', label: 'Courses', icon: BookOpen },
  { id: 'exam', label: 'Exam', icon: GraduationCap },
  { id: 'telegram', label: 'Telegram', icon: Send },
]

function gapText(gap: GapAlert, language: string, c: (text: string) => string) {
  const labels: Record<GapAlert['sequence_kind'], string> = { week: 'Week', lecture: 'Lecture', chapter: 'Chapter', module: 'Module' }
  const label = c(labels[gap.sequence_kind])
  return language === 'kk'
    ? `${gap.missing}-${label.toLocaleLowerCase('kk-KZ')} ${c('is missing')}`
    : `${label} ${gap.missing} ${c('is missing')}`
}

function stageCounts(items: BrainItem[]) {
  return items.filter((item) => !['filed', 'failed'].includes(item.status)).length
}

function BrainLoading() {
  const c = useCopy()
  return <main className="brain-loading" aria-busy="true" aria-label={c('Loading your Brain')}>
    <div className="brain-loading-mark"><FibonacciMark size={34} filled={8} /></div>
    <div className="brain-loading-lines"><span /><span /><span /></div>
    <div className="brain-loading-card" /><div className="brain-loading-card" />
  </main>
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
  const [courseNames, setCourseNames] = useState<Record<string, string>>({})
  const courseNamesRef = useRef<Record<string, string>>({})
  const [newlyFiled, setNewlyFiled] = useState<string[]>([])
  const [connection, setConnection] = useState<{ source: string; target: string; sourceCourseId: string; targetCourseId: string } | null>(null)
  const connectionTimer = useRef<number | null>(null)
  const [simulating, setSimulating] = useState(false)
  const [presentation, setPresentation] = useState(false)
  const [presentationReady, setPresentationReady] = useState(false)

  const loadOverview = useCallback(async () => {
    setLoadingOverview(true)
    setOverviewError(false)
    try {
      const data = await api.overview()
      setOverview(data)
    } catch {
      setOverviewError(true)
    } finally {
      setLoadingOverview(false)
    }
    void api.graph().then((graph) => {
      const names = Object.fromEntries(graph.courses.map((course) => [course.id, course.title]))
      courseNamesRef.current = names
      setCourseNames(names)
    }).catch(() => undefined)
  }, [api])

  useEffect(() => {
    if (session.canUse) void loadOverview()
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
    if (connectionTimer.current !== null) window.clearTimeout(connectionTimer.current)
  }, [])

  const handleEvent = useCallback((event: BrainEvent) => {
    setOverview((current) => {
      if (!current) return current
      let gaps = current.gaps
      if (event.type === 'gap.detected' && !gaps.some((gap) => gap.id === event.gap.id)) gaps = [...gaps, event.gap]
      if (event.type === 'gap.resolved') gaps = gaps.filter((gap) => gap.id !== event.gap_id)
      return { ...current, recent_items: reduceItems(current.recent_items, event), gaps }
    })

    if (event.type === 'item.filed') {
      setNewlyFiled((current) => [...current.filter((id) => id !== event.item.id), event.item.id])
      window.setTimeout(() => setNewlyFiled((current) => current.filter((id) => id !== event.item.id)), 2600)
    }

    if (event.type === 'link.created' && event.link.cross_course) {
      const names = courseNamesRef.current
      setConnection({
        source: event.source.name,
        target: event.target.name,
        sourceCourseId: event.source.course_id,
        targetCourseId: event.target.course_id,
      })
      if (connectionTimer.current !== null) window.clearTimeout(connectionTimer.current)
      connectionTimer.current = window.setTimeout(() => setConnection(null), 12_000)
    }
  }, [])

  const { connected } = useBrainEvents(handleEvent, session.canUse)
  const itemUpdate = useCallback((updated: BrainItem) => {
    setOverview((current) => current ? {
      ...current,
      recent_items: current.recent_items.some((item) => item.id === updated.id)
        ? current.recent_items.map((item) => item.id === updated.id ? updated : item)
        : [updated, ...current.recent_items].slice(0, 20),
    } : current)
  }, [])

  const orderedItems = useMemo(() => overview?.recent_items ?? [], [overview?.recent_items])
  const isEmpty = Boolean(overview && overview.counts.items === 0 && overview.counts.processing === 0 && orderedItems.length === 0)
  const presentationActive = presentationReady && presentation
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

  return <main className={`brain-app app-content-page${presentationActive ? ' is-presentation' : ''}`} data-workspace-role="student">
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
            <Icon size={17} aria-hidden="true" /><span>{c(label)}</span>{id === 'inbox' && overview && stageCounts(overview.recent_items) > 0 && <span className="brain-tab-count">{stageCounts(overview.recent_items)}</span>}
          </button>)}
        </div>
        <div className="brain-live-status" role="status"><span className={connected ? 'is-connected' : ''} />{connected ? c('Live') : c('Reconnecting')}</div>
      </div>

      <div className="brain-tab-panel" id={`brain-panel-${tab}`} role="tabpanel" aria-labelledby={`brain-tab-${tab}`} tabIndex={0}>
        {tab === 'inbox' ? <>
          <div className="brain-inbox-heading">
            <div><p className="brain-section-kicker">{c('Automatically filed')}</p><h2>{c('Your sources, finding their place')}</h2><p>{c('New material moves from capture to course while you keep studying.')}</p></div>
            <div className="brain-inbox-actions">
              <span className="brain-processing-count"><Activity size={16} aria-hidden="true" />{overview ? `${overview.counts.processing} ${c('in progress')}` : c('Loading sources')}</span>
              {api.mode === 'mock' && <button type="button" className="brain-simulate-button" disabled={simulating} onClick={async () => { setSimulating(true); try { await api.simulateHeroDemo() } catch { /* The mock control is best-effort only. */ } finally { window.setTimeout(() => setSimulating(false), 800) } }}>
                <Sparkles size={15} aria-hidden="true" />{simulating ? c('Simulating…') : c('Simulate Telegram demo')}
              </button>}
            </div>
          </div>

          {connection && <aside className="brain-connection-banner" role="status" aria-live="polite">
            <span className="brain-connection-symbol"><GitBranch size={23} aria-hidden="true" /></span>
            <span className="brain-connection-copy"><strong>{c('New cross-course connection')}</strong><span>{connection.source} <b aria-hidden="true">↔</b> {connection.target}</span><small>{courseNames[connection.sourceCourseId] || c('Across courses')}{courseNames[connection.targetCourseId] ? ` · ${courseNames[connection.targetCourseId]}` : ''}</small></span>
            <button type="button" aria-label={c('Dismiss')} onClick={() => setConnection(null)}>×</button>
          </aside>}

          {overview?.gaps.map((gap) => <aside className="brain-gap-alert" key={gap.id}>
            <span className="brain-gap-icon"><TriangleAlert size={19} aria-hidden="true" /></span>
            <div><strong>{gapText(gap, language, c)}</strong><span>{c('There is a gap in')} {gap.course_title}.</span></div>
            <button type="button" className="brain-text-button" onClick={() => setTab('courses')}>{c('View course')}<ChevronRight size={16} aria-hidden="true" /></button>
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
            {orderedItems.map((item) => <BrainItemCard key={item.id} item={item} api={api} recentlyFiled={newlyFiled.includes(item.id)} onItemChange={itemUpdate} />)}
            {orderedItems.length === 0 && !loadingOverview && <p className="brain-no-recent">{c('No recent sources yet.')}</p>}
          </div>}
        </> : <BrainPlaceholder tab={tab} c={c} />}
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
