'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { BrainCircuit } from 'lucide-react'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/hooks/use-auth'
import { useLanguage } from '@/hooks/use-language'
import { useStudentCopy } from '@/hooks/use-student-copy'
import { contentLanguageFor } from '@/lib/content-language'
import { StudentWorkspaceContext } from '@/lib/student-workspace-context'
import { studentSubjects, type StudentEntry, type StudentMode, type StudentSetup } from '@/lib/student-workspace'
import { ThemeToggle } from '@/components/theme-toggle'
import { StudioIcon } from '@/components/studio-icon'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'
import StoryDraftWorkspace from './dashboard-client'
import StoryViewer from './story-viewer'
import StoryLibrary from './story-library'
import StudyWorkspace from './study-workspace'
import './student-workspace.css'
import '../teacher/teacher.css'
import { FibonacciLogo } from '@/components/fibonacci-mark'

const formats = [
  { mode: 'story', label: 'Story / video', detail: 'Preview a story, then create its video' },
  { mode: 'flashcards', label: 'Flashcards', detail: '12 cards to help key ideas stick' },
  { mode: 'quiz', label: 'Quiz', detail: '10 questions with helpful explanations' },
  { mode: 'presentation', label: 'Presentation', detail: '8 slides you can edit and present' },
] as const

const defaultEntry: StudentEntry = {mode:'story',materialId:null,storyId:null,library:false}
export default function StudentWorkspace({initialEntry=defaultEntry,previewRequested=false}:{initialEntry?:StudentEntry;previewRequested?:boolean}) {
  const {user,loading}=useAuth(),c=useStudentCopy()
  const isPreview=process.env.NEXT_PUBLIC_ENABLE_DASHBOARD_PREVIEW==='true'&&previewRequested
  if(!isPreview&&loading)return <main className="dash-loading"><p role="status">{c('Loading…')}</p></main>
  if(!isPreview&&!user)return <SignInPrompt title="Learning workspace"/>
  return <LearningWorkspace key={isPreview?'preview':user!.id} initialEntry={initialEntry} previewRequested={previewRequested} isPreview={isPreview}/>
}

function LearningWorkspace({initialEntry,previewRequested,isPreview}:{initialEntry:StudentEntry;previewRequested:boolean;isPreview:boolean}) {
  const c=useStudentCopy(),{user}=useAuth(),{language:interfaceLanguage}=useLanguage()
  const pathname=usePathname()
  const activeNav=pathname.startsWith('/story/')?'/create':pathname
  const [setup,setSetup]=useState<StudentSetup>({subject:'history_social_studies',topic:'',language:contentLanguageFor(interfaceLanguage)})
  const [languageChosen,setLanguageChosen]=useState(false)
  const [mode,setMode]=useState<StudentMode>(initialEntry.mode)
  const [storyId,setStoryId]=useState(initialEntry.storyId)
  const [showLibrary,setShowLibrary]=useState(initialEntry.library)
  const [libraryVisited,setLibraryVisited]=useState(initialEntry.library)
  const [busy,setBusy]=useState({story:false,study:false})
  const reportBusy=useCallback((format:'story'|'study',value:boolean)=>setBusy(current=>current[format]===value?current:{...current,[format]:value}),[])
  useEffect(()=>{if(!languageChosen)setSetup(current=>({...current,language:contentLanguageFor(interfaceLanguage)}))},[interfaceLanguage,languageChosen])
  useEffect(()=>{setMode(initialEntry.mode);setStoryId(initialEntry.storyId);setShowLibrary(initialEntry.library);if(initialEntry.library)setLibraryVisited(true)},[initialEntry.mode,initialEntry.storyId,initialEntry.library])

  const updateAddress=useCallback((nextMode:StudentMode,nextStory:string|null,library:boolean)=>{
    const search=new URLSearchParams()
    if(nextMode!=='story')search.set('mode',nextMode)
    if(nextStory&&nextMode==='story')search.set('story',nextStory)
    if(library)search.set('library','1')
    if(isPreview)search.set('preview','1')
    window.history.replaceState(null,'',`/create${search.size?`?${search}`:''}`)
  },[isPreview])
  const selectMode=useCallback((nextMode:StudentMode)=>{setMode(nextMode);updateAddress(nextMode,storyId,showLibrary)},[storyId,showLibrary,updateAddress])
  const openStory=useCallback((id:string|null)=>{setStoryId(id);setMode('story');updateAddress('story',id,showLibrary)},[showLibrary,updateAddress])
  const openLibrary=useCallback(()=>{setShowLibrary(true);setLibraryVisited(true);updateAddress(mode,storyId,true)},[mode,storyId,updateAddress])
  const creating=busy.story||busy.study
  const libraryOnly=activeNav==='/history'
  const heading=libraryOnly?['Your library','Everything you have made, in one place.']:activeNav==='/study'?['Study tools','Flashcards, quizzes, and slides from your topic or your own notes.']:['What do you want to learn?','Ask a question or paste your material, then choose how to learn it.']

  const suggestions = setup.subject === 'history_social_studies' ? ['What connected people along the Silk Road?', 'How did ancient cities grow?'] : setup.subject === 'geography' || setup.subject === 'science' ? ['How volcanoes form', 'Why do seasons change?'] : setup.subject === 'math' ? ['How do fractions work?', 'Why do we use zero?'] : setup.subject === 'philosophy' ? ['What makes a fair decision?', 'How do we know what is true?'] : ['How do stories help us understand people?', 'What makes a memorable character?']

  return <StudentWorkspaceContext.Provider value={{setup,setSetup,mode,selectMode,openStory,openLibrary,reportBusy}}>
    <main data-workspace-role="student" className="student-workspace prep-shell app-content-page min-h-screen bg-background text-foreground">
      <a href="#learning-content" className="studio-skip">{c('Skip to content')}</a><header className="app-header prep-screen"><Link href="/" className="app-brand" aria-label={c('Fibonacci home')}><FibonacciLogo size={30}/></Link><nav aria-label={c('Learning workspace')} className="student-primary-nav">
        <Link href="/create" aria-current={activeNav==='/create'?'page':undefined}><StudioIcon name="edit"/>{c('Create')}</Link>
        <Link href="/study" aria-current={activeNav==='/study'?'page':undefined}><StudioIcon name="cards"/>{c('Study')}</Link>
        <Link href="/history" aria-current={activeNav==='/history'?'page':undefined}><StudioIcon name="book"/>{c('Library')}</Link>
        <Link href="/brain"><BrainCircuit aria-hidden="true"/>{c('Brain')}</Link>
        <Link href="/teacher/sources"><StudioIcon name="presentation"/>{c('Sources')}</Link></nav>
        <div className="app-header-tools"><Link className="app-mode-link" href="/teacher">{c('Teacher mode')}</Link><LanguagePicker/><ThemeToggle/><Link className="app-account" href="/profile" aria-label={c('Account')} title={c('Account')}>{(user?.email?.[0] ?? '·')}</Link></div></header>
      <div className="student-workspace-body" id="learning-content">
        <div className="student-heading-row"><div className="student-workspace-heading"><h1>{c(heading[0])}</h1><p>{c(heading[1])}</p></div>{!libraryOnly&&!isPreview&&<Link href="/history" className="student-library-link"><StudioIcon name="book"/>{c('Open library')}</Link>}</div>
        <div className={`student-studio-grid${libraryOnly?' is-library':''}`}><aside className="student-setup-rail" hidden={libraryOnly}>
        <section className="prep-card student-shared-setup" aria-label={c('Start with your topic')}>
          <h2 className="student-setup-title">{c('Start with your topic')}</h2><div className="prep-form-grid"><label htmlFor="student-topic" className="student-topic-field">{c('Your question or topic')}<input id="student-topic" maxLength={200} value={setup.topic} disabled={creating} placeholder={c('What are you curious about?')} onChange={event=>setSetup(current=>({...current,topic:event.target.value}))}/></label><label htmlFor="student-subject">{c('Subject')}<select id="student-subject" value={setup.subject} disabled={creating} onChange={event=>setSetup(current=>({...current,subject:event.target.value}))}>{studentSubjects.map(subject=><option key={subject.value} value={subject.value}>{c(subject.label)}</option>)}</select></label><label htmlFor="student-language">{c('Material language')}<select id="student-language" value={setup.language} disabled={creating} onChange={event=>{setLanguageChosen(true);setSetup(current=>({...current,language:event.target.value}))}}><option value="en-US">{c('English')}</option><option value="ru-RU">{c('Russian')}</option><option value="kk-KZ">{c('Kazakh')}</option></select></label></div>
          <details className="student-topic-suggestions student-source" open={Boolean(setup.source_text)}><summary>{c('Add your own source (optional)')}<StudioIcon name="plus"/></summary><div><label htmlFor="student-source-text" className="student-source-label">{c('Paste notes, a textbook passage, or an article')}<textarea id="student-source-text" className="student-source-text" rows={6} maxLength={20000} value={setup.source_text ?? ''} disabled={creating} placeholder={c('Paste the text you want to learn from…')} onChange={event=>setSetup(current=>({...current,source_text:event.target.value}))}/></label><p className="student-source-hint">{c('Fibonacci will base your story, quiz, flashcards, and slides on this text.')} {(setup.source_text ?? '').length.toLocaleString()} / 20,000</p>{setup.source_text ? <button type="button" className="student-source-clear" disabled={creating} onClick={()=>setSetup(current=>({...current,source_text:''}))}>{c('Remove source')}</button> : null}</div></details>
          <details className="student-topic-suggestions" id="topic-suggestions"><summary>{c('Try a question')}<StudioIcon name="plus"/></summary><div>{suggestions.map(topic => <button type="button" key={topic} disabled={creating} onClick={() => setSetup(current => ({ ...current, topic: c(topic) }))}>{c(topic)}<StudioIcon name="plus"/></button>)}</div></details>
          <p className="prep-hint" role="status">{c(creating?'Generation in progress. You can switch formats while it finishes.':'Your work stays open when you switch formats.')}</p>
        </section></aside><div className="student-stage">
        <div className="student-format-tabs" role="group" aria-label={c('Choose your format')} hidden={libraryOnly}>{formats.map(format=><button type="button" key={format.mode} aria-pressed={mode===format.mode} className={`student-format-tab${mode===format.mode?' is-active':''}`} onClick={()=>selectMode(format.mode)}><StudioIcon name={format.mode === 'story' ? 'book' : format.mode === 'flashcards' ? 'cards' : format.mode === 'quiz' ? 'question' : 'presentation'}/><span><strong>{c(format.label)}</strong><small>{c(format.detail)}</small></span></button>)}</div>
        {!isPreview&&(libraryVisited||libraryOnly)&&<section hidden={!(showLibrary||libraryOnly)} className="student-saved-stories">{!libraryOnly&&<div className="prep-section-heading"><div><h2>{c('Saved work')}</h2><p>{c('Your stories and study materials, together.')}</p></div><button type="button" className="prep-button" onClick={()=>{setShowLibrary(false);updateAddress(mode,storyId,false)}}>{c('Hide saved work')}</button></div>}<StoryLibrary/></section>}
        <div hidden={libraryOnly||mode!=='story'||Boolean(storyId)}><StoryDraftWorkspace previewRequested={previewRequested}/></div>
        {storyId&&!isPreview&&<div hidden={libraryOnly||mode!=='story'}><div className="student-editor-actions"><button type="button" className="prep-button" onClick={()=>openStory(null)}>{c('Back to story draft')}</button></div><StoryViewer key={storyId} jobId={storyId}/></div>}
        {!isPreview&&<div hidden={mode==='story'&&!showLibrary&&!libraryOnly}><StudyWorkspace active={mode!=='story'&&!libraryOnly} showLibrary={showLibrary||libraryOnly} initialMaterialId={initialEntry.materialId}/></div>}
        {isPreview&&(showLibrary||libraryOnly)&&<p className="prep-notice">{c('Sign in to create and save study materials.')}</p>}
        {isPreview&&mode!=='story'&&!libraryOnly&&<p className="prep-notice">{c('Sign in to create and save study materials.')}</p>}
        </div></div>
      </div>
    </main>
  </StudentWorkspaceContext.Provider>
}
