'use client'
import {useCallback,useEffect,useRef,useState} from 'react'
import Link from 'next/link'
import Image from 'next/image'
import {sourceRefreshLimit} from '@/lib/teacher-source-state'
import {ArrowLeft,BookOpen,Upload,Trash2,Download,RotateCcw,RefreshCw} from 'lucide-react'
import {useAuth} from '@/hooks/use-auth'
import {useCopy} from '@/hooks/use-copy'
import {useLanguage} from '@/hooks/use-language'
import {contentLanguageFor} from '@/lib/content-language'
import {useTeacherAPI} from '@/hooks/use-teacher-api'
import {useSourceTransfer} from '@/hooks/use-source-transfer'
import type {TeacherSource} from '@/lib/teacher-content'
import {TeacherShell} from '@/components/teacher/shell'
import {SignInPrompt} from '@/components/sign-in-prompt'

// The API answers 403 with this message while the persisted teacher profile is missing.
const TEACHER_MODE_REQUIRED='Enable teacher mode to prepare lessons.'

export default function SourcesPage(){
 const {user,loading}=useAuth(),c=useCopy()
 if(loading)return <TeacherShell><p role="status">{c('Loading…')}</p></TeacherShell>
 if(!user)return <TeacherShell><SignInPrompt teacher title="My sources" message="Sign in to prepare your lessons." /></TeacherShell>
 return <SourceLibrary key={user.id}/>
}

function SourceLibrary(){
 const api=useTeacherAPI(),transfer=useSourceTransfer(),c=useCopy()
 const {language:interfaceLanguage}=useLanguage()
 const [sources,setSources]=useState<TeacherSource[]>([]),[busy,setBusy]=useState(false),[sourcesLoading,setSourcesLoading]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState('')
 const [teacherModeOff,setTeacherModeOff]=useState(false),[enabling,setEnabling]=useState(false),[checked,setChecked]=useState(false)
 const [title,setTitle]=useState(''),[text,setText]=useState(''),[language,setLanguage]=useState('en-US'),[more,setMore]=useState(false)
 const [languageChosen,setLanguageChosen]=useState(false)
 useEffect(()=>{if(!languageChosen)setLanguage(contentLanguageFor(interfaceLanguage))},[interfaceLanguage,languageChosen])
 const fileInput=useRef<HTMLInputElement>(null),alive=useRef(true),loadedCount=useRef(0)
 loadedCount.current=sources.length
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
 const load=useCallback(async()=>{setSourcesLoading(true);setError('');try{const limit=sourceRefreshLimit(loadedCount.current);const rows=await api<TeacherSource[]>(`documents?limit=${limit}`);setTeacherModeOff(false);setSources(rows);setMore(rows.length===limit&&limit<50)}catch(e){const message=e instanceof Error?e.message:'Could not complete this request. Please try again.';if(message===TEACHER_MODE_REQUIRED)setTeacherModeOff(true);else setError(message)}finally{setSourcesLoading(false);setChecked(true)}},[api])
 useEffect(()=>{void load()},[load])
 const pending=sources.some(s=>s.status==='processing'||s.status==='uploading')
 useEffect(()=>{if(!pending||busy)return;const timer=setInterval(()=>void load(),5000);return()=>clearInterval(timer)},[pending,busy,load])
 async function perform(action:()=>Promise<unknown>,message=''){
  setBusy(true);setError('');setNotice('')
  try{await action();if(alive.current){if(message)setNotice(message);await load()}}catch(e){if(alive.current)setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}finally{if(alive.current)setBusy(false)}
 }
 // Same onboarding call as the teacher home page: persist the teacher profile, then load the library.
 async function enableTeacherMode(){
  setEnabling(true);setError('')
  try{await api('profile','POST');window.sessionStorage.removeItem('talespark-teacher-intent');if(alive.current){setTeacherModeOff(false);await load()}}
  catch(e){if(alive.current)setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}
  finally{if(alive.current)setEnabling(false)}
 }
 async function download(source:TeacherSource){await perform(async()=>{const result=await transfer.download(source);if(!alive.current)return;const url=URL.createObjectURL(result.blob);const link=document.createElement('a');link.href=url;link.download=result.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)})}
 async function loadMore(){setBusy(true);try{const rows=await api<TeacherSource[]>(`documents?limit=25&offset=${sources.length}`);setSources(old=>[...old,...rows]);setMore(rows.length===25)}catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}finally{setBusy(false)}}
 const errorBox=error&&<div className="prep-error" role="alert"><span>{c(error)}</span><button className="prep-button" onClick={()=>void load()} disabled={sourcesLoading||enabling}>{c('Retry loading sources')}</button></div>
 return <TeacherShell><div className="prep-detail prep-screen prep-sources-page">
  <header className="prep-page-heading">
   <p className="prep-eyebrow">{c('Teacher prep')}</p>
   <h1>{c('My sources')}</h1>
   <p>{c('Your private library for lessons, quizzes, and flashcards.')}</p>
  </header>
  {!checked ? <p role="status" className="prep-hint">{c('Loading sources…')}</p> : teacherModeOff ? <>
   {errorBox}
   <section className="prep-card prep-mode-card" aria-labelledby="teacher-mode-title">
    <BookOpen size={28} aria-hidden="true"/>
    <h2 id="teacher-mode-title">{c('Turn on teacher mode to add sources')}</h2>
    <p>{c('Teacher mode gives you a private library for lesson sources, plus lesson plans, quizzes, flashcards, and presentations built from them.')}</p>
    <p className="prep-hint">{c('Teacher mode is self-selected. Your saved lessons are private.')}</p>
    <button className="prep-button primary" onClick={()=>void enableTeacherMode()} disabled={enabling}>{c(enabling?'Saving…':'Enable teacher mode')}</button>
   </section>
  </> : <>
   {errorBox}
   {notice&&<p className="prep-notice" role="status">{c(notice)}</p>}
   <ol className="prep-steps prep-steps-three" aria-label={c('Source preparation steps')}><li aria-current="step">{c('Add a source')}</li><li>{c('Wait for processing')}</li><li>{c('Attach it to a lesson')}</li></ol>
   <p className="prep-hint prep-privacy-hint">{c('Use teaching content without personal or confidential information.')}</p>
   <div className="prep-source-create">
    <section className="prep-card prep-source-card" aria-labelledby="upload-source-title">
     <h2 id="upload-source-title">{c('Upload a document')}</h2>
     <p>{c('PDF, DOCX, or UTF-8 text. Up to 10 MB, 200 PDF pages, and 200,000 characters. Scanned PDFs need a text version.')}</p>
     <label className="prep-source-label">{c('Document language')}<select value={language} onChange={e=>{setLanguageChosen(true);setLanguage(e.target.value)}} disabled={busy}><option value="en-US">{c('English')}</option><option value="ru-RU">{c('Russian')}</option><option value="kk-KZ">{c('Kazakh')}</option></select></label>
     <label className="prep-source-label">{c('Choose document')}<input ref={fileInput} type="file" accept=".pdf,.docx,.txt" disabled={busy}/></label>
     <button className="prep-button primary" disabled={busy} onClick={()=>{const file=fileInput.current?.files?.[0];if(!file){setError('Choose document');return}void perform(async()=>{await transfer.upload(file,language);if(alive.current&&fileInput.current)fileInput.current.value=''},'Source added. Processing will begin shortly.')}}><Upload size={17} aria-hidden="true"/>{c(busy?'Uploading…':'Upload document')}</button>
    </section>
    <section className="prep-card prep-source-card" aria-labelledby="paste-source-title">
     <h2 id="paste-source-title">{c('Paste source text')}</h2>
     <p>{c('Paste text from a textbook, worksheet, or your own notes.')}</p>
     <form onSubmit={e=>{e.preventDefault();void perform(async()=>{await api('documents/text','POST',{title,text,language});if(alive.current){setTitle('');setText('')}},'Source added. Processing will begin shortly.')}}>
      <label className="prep-source-label">{c('Source title')}<input required maxLength={200} value={title} onChange={e=>setTitle(e.target.value)} disabled={busy}/></label>
      <label className="prep-source-label">{c('Source text')}<textarea required maxLength={200000} rows={6} value={text} onChange={e=>setText(e.target.value)} disabled={busy}/><span className="prep-hint prep-character-count" aria-live="polite">{c('{count} of 200,000 characters').replace('{count}', text.length.toLocaleString())}</span></label>
      <button className="prep-button" disabled={busy||!title.trim()||!text.trim()}>{c('Add text source')}</button>
     </form>
    </section>
   </div>
   <section className="prep-card prep-saved-sources" aria-labelledby="saved-sources-title">
    <div className="prep-section-heading"><h2 id="saved-sources-title">{c('Saved sources')}</h2><button className="prep-button" onClick={()=>void load()} disabled={busy}><RefreshCw size={16} aria-hidden="true"/>{c('Refresh')}</button></div>
    {sourcesLoading&&!sources.length ? <p role="status" className="prep-hint">{c('Loading sources…')}</p> : !error&&!sources.length ? <div className="prep-empty prep-source-empty"><Image className="prep-empty-illustration" src="/illustrations/empty-sources.png" alt="" width={480} height={480}/><h3>{c('Your source library is empty.')}</h3><p>{c('Add a source above, then attach it to a lesson when it is ready.')}</p></div> : null}
    <div className="prep-sources-list">{sources.map(source=><article key={source.id} className="prep-source-row"><div><h3>{source.title}</h3><p>{source.kind.toUpperCase()} · {c(source.status==='ready'?'Ready':source.status==='failed'?'Failed':source.status==='deleting'?'Removal pending':'Processing')}</p>{source.error_message&&<p className="prep-error">{c(source.error_message)}</p>}</div><div className="prep-source-actions">{source.status!=='uploading'&&source.status!=='deleting'&&<button className="prep-button" disabled={busy} aria-label={`${c('Download original')}: ${source.title}`} onClick={()=>void download(source)}><Download size={17} aria-hidden="true"/>{c('Download original')}</button>}{(source.status==='failed'||(source.status!=='deleting'&&Date.now()-Date.parse(source.updated_at)>180000&&source.status!=='ready'))&&<button className="prep-button" disabled={busy} onClick={()=>void perform(()=>api(`documents/${source.id}/retry`,'POST'))}><RotateCcw size={17} aria-hidden="true"/>{c('Retry')}</button>}<button className="prep-button danger" disabled={busy} aria-label={`${c('Delete source')}: ${source.title}`} onClick={()=>{if(window.confirm(c('Delete this source? Existing generated materials will remain saved.')))void perform(()=>api(`documents/${source.id}`,'DELETE'))}}><Trash2 size={17} aria-hidden="true"/>{c(source.status==='deleting'?'Retry removal':'Delete source')}</button></div></article>)}</div>
    {more&&<button className="prep-button" onClick={()=>void loadMore()} disabled={busy}>{c('Load more')}</button>}
   </section>
  </>}
  <Link className="prep-back" href="/teacher"><ArrowLeft size={17} aria-hidden="true"/>{c('My lessons')}</Link>
 </div></TeacherShell>
}
