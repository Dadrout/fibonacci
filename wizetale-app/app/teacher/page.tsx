'use client'
import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { BookOpen, Plus, ArrowUpRight } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { useCopy } from '@/hooks/use-copy'
import { useTeacherAPI } from '@/hooks/use-teacher-api'
import { Lesson, LessonInput, schoolSubjects } from '@/lib/teacher-content'
import { TeacherShell } from '@/components/teacher/shell'
import { LessonForm } from '@/components/teacher/lesson-form'
import { SignInPrompt } from '@/components/sign-in-prompt'

export default function TeacherPage() {
  const {user,loading}=useAuth(), c=useCopy()
  if(loading)return <TeacherShell><p role="status">{c('Loading…')}</p></TeacherShell>
  if(!user)return <TeacherShell><SignInPrompt teacher title="Sign in to prepare your lessons." /></TeacherShell>
  return <TeacherWorkspace key={user.id}/>
}

function TeacherWorkspace() {
  const {user,loading} = useAuth()
  const c = useCopy(), api = useTeacherAPI(), router = useRouter()
  const [enabled,setEnabled] = useState<boolean | null>(null)
  const [lessons,setLessons] = useState<Lesson[]>([])
  const [busy,setBusy] = useState(false), [error,setError] = useState('')
  const [showForm,setShowForm] = useState(false), [more,setMore] = useState(false)
  const load = useCallback(async()=>{
    setError(''); setBusy(true)
    try {
      let profile = await api<{teacher_enabled:boolean}>('profile')
      // Metadata is an onboarding preference only. API authorization uses the persisted profile.
      if (!profile.teacher_enabled && (user?.user_metadata?.learning_role === 'teacher' || window.sessionStorage.getItem('fibonacci-teacher-intent') === '1')) profile = await api('profile','POST')
      if (profile.teacher_enabled) window.sessionStorage.removeItem('fibonacci-teacher-intent')
      setEnabled(profile.teacher_enabled)
      if (profile.teacher_enabled) {
        const rows = await api<Lesson[]>('lessons?limit=25&offset=0')
        setLessons(rows); setMore(rows.length === 25)
      }
    } catch(e) { setError(e instanceof Error ? e.message : c('Could not complete this request. Please try again.')) }
    finally { setBusy(false) }
  },[api,user?.user_metadata?.learning_role])
  useEffect(()=>{if(!loading && user) void load()},[loading,user?.id,load])
  async function enable() {
    setBusy(true); setError('')
    try { await api('profile','POST'); await load() }
    catch(e) { setError(e instanceof Error?e.message:c('Could not complete this request. Please try again.')) }
    finally {setBusy(false)}
  }
  async function create(lesson: LessonInput) {
    setBusy(true); setError('')
    try { const row=await api<Lesson>('lessons','POST',lesson); router.push(`/teacher/lessons/${row.id}`) }
    catch(e) {setError(e instanceof Error?e.message:c('Could not complete this request. Please try again.'))}
    finally {setBusy(false)}
  }
  async function loadMore() {
    setBusy(true); setError('')
    try {const rows=await api<Lesson[]>(`lessons?limit=25&offset=${lessons.length}`);setLessons(old=>[...old,...rows]);setMore(rows.length===25)}
    catch(e){setError(e instanceof Error?e.message:c('Could not complete this request. Please try again.'))}
    finally{setBusy(false)}
  }
  return <TeacherShell><div className="prep-home prep-screen">
    <header className="prep-hero prep-page-heading"><p className="prep-eyebrow">{c('Teacher prep')}</p><h1>{c('Prepare a lesson worth remembering.')}</h1><p>{c('Create a lesson, then choose what to prepare. Your materials stay together here.')}</p></header>
    {error && <div role="alert" className="prep-error">{c(error)}<button onClick={()=>void load()} disabled={busy}>{c('Refresh')}</button></div>}
    {loading || (user && enabled===null && busy) ? <p role="status">{c('Loading…')}</p> : !user ? <section className="prep-card"><h2>{c('Sign in to prepare your lessons.')}</h2><Link className="prep-button primary" href="/login">{c('Sign in')}</Link></section> : enabled===false ? <section className="prep-card prep-onboarding prep-mode-card"><BookOpen size={28} aria-hidden="true" /><h2>{c('One topic. All your teaching materials.')}</h2><p>{c('Create your private prep library with lesson plans, quizzes, tests, flashcards, and activities.')}</p><p className="prep-hint">{c('Teacher mode is self-selected. Your saved lessons are private.')}</p><button className="prep-button primary" onClick={()=>void enable()} disabled={busy}>{c(busy?'Saving…':'Enable teacher mode')}</button></section> : enabled && <>
      <div className="prep-section-heading prep-lessons-heading"><div><h2>{c('My lessons')}</h2><p className="prep-hint">{c('Start with a topic and grade. You can add sources and materials next.')}</p></div>{(lessons.length>0||showForm) && <button className={`prep-button ${showForm?'':'primary'}`} onClick={()=>setShowForm(value=>!value)} aria-expanded={showForm}>{!showForm && <Plus size={18} aria-hidden="true" />}{c(showForm?'Close lesson form':'New lesson')}</button>}</div>
      {showForm && <section className="prep-card prep-new-lesson" aria-label={c('New lesson')}><h2>{c('New lesson')}</h2><LessonForm submit={create} busy={busy}/></section>}
      {!lessons.length && !busy && !showForm && <div className="prep-empty prep-lesson-empty"><BookOpen size={28} aria-hidden="true"/><h3>{c('Create your first lesson')}</h3><p>{c('Add a topic and grade to start. You can attach sources and generate a lesson plan, quiz, flashcards, or presentation next.')}</p><button className="prep-button primary" onClick={()=>setShowForm(true)} aria-expanded={showForm}><Plus size={17} aria-hidden="true"/>{c('Create lesson')}</button></div>}
      {lessons.length>0 && <div className="prep-lesson-grid">{lessons.map(lesson=><Link key={lesson.id} href={`/teacher/lessons/${lesson.id}`} className="prep-card prep-lesson-card"><span className="prep-eyebrow">{c(schoolSubjects.find(s=>s.value===lesson.subject)?.label||lesson.subject)} · {c('Grade')} {lesson.grade}</span><h3>{lesson.topic}</h3><p>{c(lesson.language==='kk-KZ'?'Kazakh':lesson.language==='ru-RU'?'Russian':'English')}</p><span className="prep-open">{c('Open lesson')}<ArrowUpRight size={18} aria-hidden="true" /></span></Link>)}</div>}
      {more && <button className="prep-button prep-load-more" onClick={()=>void loadMore()} disabled={busy}>{c('Load more')}</button>}
      <p className="prep-hint prep-home-sources">{c('Have a textbook chapter or worksheet?')} <Link href="/teacher/sources">{c('Add it to My sources')}</Link></p>
    </>}
  </div></TeacherShell>
}
