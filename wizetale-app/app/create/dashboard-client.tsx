'use client'

import { learnerStorageKey } from '@/lib/learner-storage'

import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { useStudentWorkspace } from '@/lib/student-workspace-context'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { ArrowDown, ArrowLeft, ArrowRight, BookOpen, Check, Clock3, GraduationCap, Globe2, Lightbulb, LogOut, Mic2, Sparkles, WandSparkles } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { useStoryGenerator, StoryDraft, StoryScript } from '@/hooks/use-story-generator'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'
import { normalizeStudentSubject } from '@/lib/student-workspace'
import { FibonacciMark } from '@/components/fibonacci-mark'

const spring = { type: 'spring' as const, stiffness: 300, damping: 30, mass: 0.85 }
const press = { scale: 0.975, y: 1 }

type SavedDraftShelfItem = { id: string; title: string; topic: string }

function StepMarker({ current }: { current: 1 | 2 }) {
  const c = useCopy()

  return <div className="dash-steps" aria-label={`${c('Step')} ${current} ${c('of')} 2`}>
    <span className={`dash-step ${current === 1 ? 'is-current' : 'is-done'}`}><span>{current === 1 ? '01' : <Check size={13} />}</span><b> {c("Make")} </b></span>
    <i aria-hidden="true" />
    <span className={`dash-step ${current === 2 ? 'is-current' : ''}`}><span>02</span><b> {c("Review")} </b></span>
  </div>
}

export default function StoryDraftWorkspace({ previewRequested }: { previewRequested: boolean }) {
  const c = useCopy()
  const workspace = useStudentWorkspace()
  const { subject, topic, language } = workspace.setup
  const setSubject = (subject: string) => workspace.setSetup(value => ({ ...value, subject }))
  const setTopic = (topic: string) => workspace.setSetup(value => ({ ...value, topic }))
  const setLanguage = (language: string) => workspace.setSetup(value => ({ ...value, language }))

  const router = useRouter()
  const { user, loading, logout } = useAuth()
  const { isGenerating, error, draft, draftSaveStatus, generateStory, updateDraft, flushDraft, renderDraft, restoreDraft, restoreDraftById, clearDraft, discardDraft } = useStoryGenerator()
  const [mounted, setMounted] = useState(false)
  const isPreview = process.env.NEXT_PUBLIC_ENABLE_DASHBOARD_PREVIEW === 'true' && previewRequested
  const [previewDraft, setPreviewDraft] = useState<StoryDraft | null>(null)
  const [grade, setGrade] = useState('13-15')
  const [duration, setDuration] = useState(180)
  const [voice, setVoice] = useState('female')
  const [script, setScript] = useState<StoryScript | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [savedDrafts, setSavedDrafts] = useState<SavedDraftShelfItem[]>([])
  const [showStartOver, setShowStartOver] = useState(false)
  const [isDiscarding, setIsDiscarding] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const loadedDraftId = useRef<string | null>(null)
  const autosaveTimer = useRef<number | null>(null)
  const discardingDraft = useRef(false)

  const activeDraft = isPreview ? previewDraft : draft

  useEffect(() => { workspace.reportBusy('story', isGenerating || signingOut || isDiscarding) }, [isGenerating, signingOut, isDiscarding, workspace.reportBusy])

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (mounted && !loading && !user && !isPreview) router.replace('/login')
  }, [mounted, loading, user, isPreview, router])

  useEffect(() => {
    if (user && !isPreview) void restoreDraft()
  }, [user, isPreview, restoreDraft])

  useEffect(() => {
    if (!user || isPreview) return
    try {
      const stored = window.localStorage.getItem(learnerStorageKey('draft-shelf', user.id))
      const parsed: unknown = stored ? JSON.parse(stored) : []
      if (Array.isArray(parsed)) {
        setSavedDrafts(parsed.filter((item): item is SavedDraftShelfItem =>
          Boolean(item && typeof item === 'object' && typeof item.id === 'string' && typeof item.title === 'string' && typeof item.topic === 'string'),
        ))
      }
    } catch {
      setSavedDrafts([])
    }
  }, [user, isPreview])

  useEffect(() => {
    if (!isPreview) setActiveJobId(window.localStorage.getItem(learnerStorageKey('job', user!.id)))
  }, [isPreview])

  useEffect(() => {
    if (isPreview) return
    if (!draft) {
      loadedDraftId.current = null
      return
    }
    if (loadedDraftId.current !== draft.id) {
      loadedDraftId.current = draft.id
      setTopic(draft.topic)
      setSubject(normalizeStudentSubject(draft.subject))
      setGrade(draft.grade_band)
      setDuration(draft.target_duration_sec)
      setLanguage(draft.language)
      setVoice(draft.voice)
      setScript(draft.script)
    }
  }, [draft?.id, isPreview])

  useEffect(() => {
    if (isPreview || !draft || !script || JSON.stringify(script) === JSON.stringify(draft.script) || discardingDraft.current) return
    const scriptToSave = script
    autosaveTimer.current = window.setTimeout(() => {
      autosaveTimer.current = null
      if (discardingDraft.current) return
      void updateDraft(scriptToSave)
    }, 900)
    return () => {
      if (autosaveTimer.current !== null) {
        window.clearTimeout(autosaveTimer.current)
        autosaveTimer.current = null
      }
    }
  }, [draft, isPreview, script, updateDraft])

  if (!mounted || ((!isPreview && loading) || (!user && !isPreview))) return <main className="dash-loading"><FibonacciMark size={48} className="dash-loading-logo"/><p> {c("Opening your story studio…")} </p></main>

  const createDraft = async () => {
    setNotice(null)
    if (isPreview) {
      const previewScript: StoryScript = {
        title: c('{topic} — a little story').replace('{topic}', topic.trim()),
        hook: c('What makes {topic} worth knowing?').replace('{topic}', topic.trim()),
        sections: [{ heading: c("The big idea"), summary: c('A short introduction to {topic}.').replace('{topic}', topic.trim()) }],
        full_narration: c('Imagine you could step inside the story of {topic}. Explore the people and ideas that shaped it, what changed, and why it matters today.').replace('{topic}', topic.trim()),
        estimated_duration_sec: duration,
      }
      setPreviewDraft({
        id: 'local-dashboard-preview', status: 'draft', subject, topic: topic.trim(), grade_band: grade,
        target_duration_sec: duration, language, voice, script: previewScript,
        recap: `This sample recap gives you a feel for how a story about ${topic.trim()} will be summarized.`, quiz: { recap: '', quiz: [] }, sources: [], knowledge_status: 'none',
      })
      setScript(previewScript)
      return
    }
    const sourceText = (workspace.setup.source_text ?? '').trim()
    await generateStory({ subject, topic, grade_band: grade, target_duration_sec: duration, language, voice, ...(sourceText ? { source_text: sourceText } : {}) })
  }

  const startVideo = async () => {
    if (!script) return
    if (isPreview) {
      setNotice(c("Preview mode: sign in to save this script and generate its video."))
      return
    }
    const jobId = await renderDraft(script)
    if (jobId) {
      window.localStorage.setItem(learnerStorageKey('job', user!.id), jobId)
      setActiveJobId(jobId)
      workspace.openStory(jobId)
    }
  }

  const newStory = async () => {
    if (isPreview) {
      setPreviewDraft(null)
    } else {
      if (!user || !draft || !script) return
      setNotice(null)
      const saved = await updateDraft(script)
      if (!saved) return
      const item = { id: saved.id, title: saved.script.title || saved.topic, topic: saved.topic }
      const shelf = [item, ...savedDrafts.filter(existing => existing.id !== item.id)]
      try {
        window.localStorage.setItem(learnerStorageKey('draft-shelf', user.id), JSON.stringify(shelf))
      } catch {
        setNotice(c('Could not save the draft to your saved drafts. Your story is still open.'))
        return
      }
      setSavedDrafts(shelf)
      await clearDraft()
    }
    setShowStartOver(false)
    setScript(null)
    setNotice(null)
    setTopic('')
  }

  const discardCurrentDraft = async () => {
    if (!user || !draft || !script || discardingDraft.current) return
    discardingDraft.current = true
    setIsDiscarding(true)
    if (autosaveTimer.current !== null) {
      window.clearTimeout(autosaveTimer.current)
      autosaveTimer.current = null
    }
    setNotice(null)
    const discarded = await discardDraft()
    if (!discarded) {
      discardingDraft.current = false
      setIsDiscarding(false)
      return
    }

    const shelf = savedDrafts.filter(item => item.id !== draft.id)
    setSavedDrafts(shelf)
    let shelfUpdateFailed = false
    try {
      window.localStorage.setItem(learnerStorageKey('draft-shelf', user.id), JSON.stringify(shelf))
    } catch {
      shelfUpdateFailed = true
    }
    setShowStartOver(false)
    setScript(null)
    setTopic('')
    setNotice(shelfUpdateFailed ? c('The draft was discarded, but the saved-drafts list could not update. Refresh it to sync.') : null)
    discardingDraft.current = false
    setIsDiscarding(false)
  }

  const returnToSavedDraft = async (id: string) => {
    const restored = await restoreDraftById(id)
    if (!restored || !user) return
    const shelf = savedDrafts.filter(item => item.id !== id)
    setSavedDrafts(shelf)
    try {
      window.localStorage.setItem(learnerStorageKey('draft-shelf', user.id), JSON.stringify(shelf))
    } catch {
      // The draft has already been restored and its current pointer is saved.
    }
  }

  const scriptHasUnsavedChanges = Boolean(
    !isPreview && draft && script && JSON.stringify(script) !== JSON.stringify(draft.script),
  )

  const signOut = async () => {
    if (signingOut || isGenerating || isDiscarding) return
    if (autosaveTimer.current !== null) {
      window.clearTimeout(autosaveTimer.current)
      autosaveTimer.current = null
    }
    setSigningOut(true)
    setSignOutError(null)
    try {
      if (!isPreview && draft && script && !(await flushDraft(script))) {
        setSignOutError(c('Could not save your latest changes. Please try again.'))
        setSigningOut(false)
        return
      }
      await logout()
      router.replace('/login')
    } catch {
      setSignOutError(c('Could not sign out. Please try again.'))
      setSigningOut(false)
    }
  }

  return <MotionConfig reducedMotion="user" transition={spring}>
    <div className="student-story-workspace">
      {signOutError && <p role="alert" className="dash-error">{c(signOutError)}</p>}

      {isPreview && <div className="dash-preview-banner" role="status"><span> {c("LOCAL PREVIEW")} </span> {c("Sample story content only. Sign in to save drafts or generate videos.")} </div>}

      <div className="dash-layout">
        <section className="dash-workspace" aria-live="polite">
          <div className="dash-workspace-head">
            <div><h2>{activeDraft && script ? c("Shape your story") : c("Story settings")}</h2></div>
            <StepMarker current={activeDraft && script ? 2 : 1} />
          </div>

          <AnimatePresence mode="popLayout" initial={false}>
            {!activeDraft && <motion.div key="create" className="dash-panel" initial={{ opacity: 0, y: 12, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.99 }} transition={spring}>
              <div className="dash-panel-intro"><div><h3> {c("Make it yours")} </h3><p> {c("Set the audience, length, and narration for your story.")} </p></div></div>

              {savedDrafts.length > 0 && <section className="dash-saved-drafts" aria-label={c('Saved drafts')}>
                <h3>{c('Saved drafts')}</h3>
                <ul>{savedDrafts.map(item => <li key={item.id}>
                  <div><strong>{item.title}</strong><span>{item.topic}</span></div>
                  <button type="button" className="dash-saved-draft-return" disabled={isGenerating} onClick={() => void returnToSavedDraft(item.id)}>{c('Return to draft')}<ArrowRight size={14} /></button>
                </li>)}</ul>
              </section>}

              <div className="dash-options-grid">
                <label className="dash-option"><span className="dash-option-icon"><Lightbulb size={16} /></span><span><b> {c("Made for")} </b><select value={grade} onChange={e => setGrade(e.target.value)}><option value="10-12"> {c("Ages 10–12")} </option><option value="13-15"> {c("Ages 13–15")} </option><option value="16-18"> {c("Ages 16–18")} </option></select></span><ArrowDown size={13} className="dash-select-arrow" /></label>
                <label className="dash-option"><span className="dash-option-icon"><Clock3 size={16} /></span><span><b> {c("Story length")} </b><select value={duration} onChange={e => setDuration(Number(e.target.value))}><option value={180}> {c("About 3 minutes")} </option><option value={240}> {c("About 4 minutes")} </option><option value={300}> {c("About 5 minutes")} </option></select></span><ArrowDown size={13} className="dash-select-arrow" /></label>
              </div>

              <label className="dash-option"><span className="dash-option-icon"><Mic2 size={16} /></span><span><b>{c('Narration')}</b><select value={voice} onChange={e => setVoice(e.target.value)}><option value="female">{c('Voice 1')}</option><option value="male">{c('Voice 2')}</option></select></span></label>

              {!topic.trim() && <p className="dash-topic-hint">{c("Add your question to get started.")}</p>}
              {error && <p role="alert" className="dash-error">{c(error)}</p>}
                <motion.button type="button" whileTap={press} disabled={!topic.trim() || isGenerating || signingOut} onClick={() => void createDraft()} className="dash-primary-button"><span>{isGenerating ? c("Finding the story in your question…") : c("Make my story preview")}</span><span className="dash-button-icon"><ArrowRight size={18} /></span></motion.button>
              <p className="dash-button-note"><Sparkles size={12} /> {c("Your video will have 5–10 topic-based sections, each with its own image.")} </p>
              {isGenerating && <div className="dash-generating" role="status"><span className="dash-generating-dot" /> {c("Writing your first draft… this usually takes a moment.")} </div>}
            </motion.div>}

            {activeDraft && script && <motion.div key="review" className="dash-panel dash-review-panel" initial={{ opacity: 0, y: 14, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.99 }} transition={spring}>
              <div className="dash-review-top"><div><div className="dash-ready-label"><span><Check size={12} /></span> {c("FIRST DRAFT READY")} </div><h3> {c("Your story, your words.")} </h3><p> {c("Make it sound just right. Nothing moves forward until you say so.")} </p></div><motion.button type="button" whileTap={press} disabled={isGenerating || signingOut} aria-expanded={isPreview ? undefined : showStartOver} aria-controls={isPreview ? undefined : 'dash-start-over-confirmation'} onClick={() => isPreview ? void newStory() : setShowStartOver(open => !open)} className="dash-back-button"><ArrowLeft size={14} /> {c("New story")} </motion.button></div>
              {showStartOver && !isPreview && <div id="dash-start-over-confirmation" className="dash-start-over-confirmation" role="group" aria-label={c('Start a new story?')}>
                <div><strong>{c('Start a new story?')}</strong><p>{c('You can save this draft for later or discard it permanently.')}</p></div>
                <div className="dash-start-over-actions">
                  <button type="button" className="dash-save-button" disabled={isGenerating || signingOut} onClick={() => setShowStartOver(false)}>{c('Keep editing')}</button>
                  <button type="button" className="dash-back-button" disabled={isGenerating || signingOut} onClick={() => void newStory()}>{isGenerating ? c('Saving your story…') : c('Save and start new')}</button>
                  <button type="button" className="dash-discard-button" disabled={isGenerating || isDiscarding || signingOut} onClick={() => void discardCurrentDraft()}>{isDiscarding ? c('Discarding…') : c('Discard draft and start new')}</button>
                </div>
              </div>}
              <label className="dash-field-block"><span className="dash-label"> {c("Story title")} </span><input aria-label={c("Story title")} value={script.title} disabled={signingOut} onChange={e => setScript({ ...script, title: e.target.value })} className="dash-input" /></label>
              <label className="dash-field-block dash-narration-block"><span className="dash-label"> {c("Narration script")} <span> {c("EDITABLE")} </span></span><textarea aria-label={c("Narration script")} value={script.full_narration} disabled={signingOut} onChange={e => setScript({ ...script, full_narration: e.target.value })} rows={10} className="dash-textarea" /></label>
              <aside className="dash-recap"><div className="dash-recap-icon"><Mic2 size={17} /></div><div><b> {c("A little recap")} </b><p>{activeDraft.recap}</p><span>{Math.round(script.estimated_duration_sec / 60)} {c("min story")} <i /> {c("Ages")} {activeDraft.grade_band}</span></div></aside>
              {activeDraft.sources?.length > 0 && <aside className="dash-recap"><div><b> {c("Learning sources")} </b><p>{activeDraft.knowledge_status === 'grounded' ? c("This topic matched a reviewed source.") : c("These sources are related to your topic.")}</p><ul className="mt-2 list-disc pl-5">{activeDraft.sources.map(source => <li key={source.url}><a className="underline" href={source.url} target="_blank" rel="noreferrer">{source.title}</a>{source.publisher ? ` · ${source.publisher}` : ''}</li>)}</ul></div></aside>}
              {activeDraft.knowledge_status === 'none' && <p className="dash-reference-note"> {c("No reviewed references are attached to this story.")} </p>}
              {error && <p role="alert" className="dash-error">{c(error)}</p>}{notice && <p role="status" className="dash-notice"><Check size={14} />{c(notice)}</p>}
              {!isPreview && draft && script && <p className={`dash-save-state${draftSaveStatus === 'error' ? ' is-error' : ''}`} role={draftSaveStatus === 'error' ? 'alert' : 'status'} aria-live={draftSaveStatus === 'error' ? 'assertive' : 'polite'}>
                {draftSaveStatus === 'error' ? c('Could not save your changes. Your text is still here.') : scriptHasUnsavedChanges ? c('Unsaved changes') : draftSaveStatus === 'saving' ? c('Saving changes…') : c('All changes saved')}
              </p>}
              <div className="dash-review-actions"><motion.button type="button" whileTap={press} disabled={isGenerating || signingOut} onClick={() => void startVideo()} className="dash-primary-button"><span>{isGenerating ? c("Saving your story…") : isPreview ? c("Sign in to make the video") : c("Looks good — make my video")}</span><span className="dash-button-icon"><ArrowRight size={18} /></span></motion.button><motion.button type="button" whileTap={press} disabled={isGenerating || signingOut} onClick={async () => { if (isPreview) { setNotice(c("Preview mode: sign in to save this draft.")); return } if (autosaveTimer.current !== null) { window.clearTimeout(autosaveTimer.current); autosaveTimer.current = null } await updateDraft(script) }} className="dash-save-button">{isPreview ? c("Save (sign in)") : c("Save changes")}</motion.button></div>
              <p className="dash-button-note"><Check size={12} /> {c("Video generation starts only when you choose to make it.")} </p>
            </motion.div>}
          </AnimatePresence>
          <div className="dash-workspace-foot">{!isPreview && <button type="button" className="dash-save-button" disabled={signingOut || isGenerating || isDiscarding} onClick={() => void signOut()}>{c(signingOut ? 'Signing out…' : 'Sign out')}</button>}<span> {c("Made for curious minds, ages 10–18")} </span><span aria-hidden="true">·</span><span> {c("One good question at a time")} </span></div>
        </section>
      </div>
    </div>
  </MotionConfig>
}
