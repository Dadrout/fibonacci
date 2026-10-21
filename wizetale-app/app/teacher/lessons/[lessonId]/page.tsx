'use client'
import { use, useCallback, useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, FileText, Printer, Save, Sparkles, Trash2 } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { useCopy } from '@/hooks/use-copy'
import { useTeacherAPI } from '@/hooks/use-teacher-api'
import { editableResourceContent, isVideoResourceContent, Lesson, LessonInput, mergeSlideVisuals, Resource, ResourceContent, ResourceKind, resourceKinds, videoGenerationRequest, videoResourceTitle, VideoResourceContent } from '@/lib/teacher-content'
import { TeacherShell } from '@/components/teacher/shell'
import { LessonForm } from '@/components/teacher/lesson-form'
import { ResourceEditor } from '@/components/teacher/resource-editor'
import { SourcePicker } from '@/components/teacher/source-picker'
import { SourceReferences } from '@/components/teacher/source-references'
import { ResourceDocument } from '@/components/teacher/resource-document'
import { PresentationStage } from '@/components/presentation-stage'
import { PresentationRender } from '@/components/teacher/presentation-render'
import { VideoScriptEditor } from '@/components/teacher/video-script-editor'
import { VideoResourceRender } from '@/components/teacher/video-resource-render'
import { SignInPrompt } from '@/components/sign-in-prompt'

export default function LessonPage({params}: {params:Promise<{lessonId:string}>}) {
  const {user, loading}=useAuth(), c=useCopy()
  if(loading)return <TeacherShell><p role="status">{c('Loading…')}</p></TeacherShell>
  if(!user)return <TeacherShell><SignInPrompt teacher title="My lessons" message="Sign in to prepare your lessons." /></TeacherShell>
  // Identity-keyed mounts discard private state and prevent old requests from updating a new account's view.
  return <LessonWorkspace key={user.id} params={params}/>
}

function LessonWorkspace({params}: {params:Promise<{lessonId:string}>}) {
  const {lessonId}=use(params), {user,loading}=useAuth(), c=useCopy(), api=useTeacherAPI(), router=useRouter()
  const [lesson,setLesson]=useState<Lesson|null>(null), [resources,setResources]=useState<Resource[]>([])
  const [selected,setSelected]=useState<Resource|null>(null), [content,setContent]=useState<ResourceContent|VideoResourceContent|null>(null)
  const [kind,setKind]=useState<ResourceKind>('lesson_plan'), [busy,setBusy]=useState(false), [generating,setGenerating]=useState(false)
  const [videoDuration,setVideoDuration]=useState<180|240|300>(180), [videoVoice,setVideoVoice]=useState<'female'|'male'>('female')
  const [error,setError]=useState(''), [notice,setNotice]=useState(''), [more,setMore]=useState(false)
  const [sourcesDirty,setSourcesDirty]=useState(false)
  const [printMode,setPrintMode]=useState<'student'|'teacher'>('student')
  const [slideIndex,setSlideIndex]=useState(0)
  const [visualBusy,setVisualBusy]=useState<number|null>(null)
  const selectedIdRef=useRef<string|null>(null)
  const selectedRevisionRef=useRef(0)
  const visualRefreshRequestRef=useRef(0)
  const dirty=Boolean(content && selected?.content && JSON.stringify(editableResourceContent(content))!==JSON.stringify(editableResourceContent(selected.content)))
  const visualsPending=Boolean(selected?.kind==='presentation'&&selected.content&&!isVideoResourceContent(selected.content)&&selected.content.slides?.some(slide=>slide.visual?.status==='pending'||slide.visual?.status==='processing'))
  useEffect(()=>{if(!dirty&&!sourcesDirty)return;const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[dirty,sourcesDirty])
  const load=useCallback(async()=>{
    setBusy(true);setError('')
    try {const [row,items]=await Promise.all([api<Lesson>(`lessons/${lessonId}`),api<Resource[]>(`lessons/${lessonId}/resources?limit=25&offset=0`)]);setLesson(row);setResources(items);setMore(items.length===25)}
    catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}
    finally{setBusy(false)}
  },[api,lessonId])
  useEffect(()=>{if(!loading&&user)void load()},[loading,user?.id,load])
  const open=(resource:Resource)=>{if((dirty||sourcesDirty)&&!window.confirm(c('Leave without saving your changes?')))return;selectedIdRef.current=resource.id;selectedRevisionRef.current=resource.revision;setSelected(resource);setContent(resource.content?structuredClone(resource.content):null);setSlideIndex(0);setNotice('')}
  const refreshVisuals=useCallback(async(resourceId:string)=>{
    const request=++visualRefreshRequestRef.current
    const updated=await api<Resource>(`lessons/${lessonId}/resources/${resourceId}`)
    if(selectedIdRef.current!==resourceId || request!==visualRefreshRequestRef.current)return
    if(updated.revision!==selectedRevisionRef.current){setError(c('This resource changed. Reload before saving.'));return}
    selectedRevisionRef.current=updated.revision
    setSelected(updated)
    setResources(old=>old.map(row=>row.id===resourceId?updated:row))
    if(updated.content && !isVideoResourceContent(updated.content))setContent(draft=>draft&&!isVideoResourceContent(draft)?mergeSlideVisuals(draft,updated.content as ResourceContent):updated.content)
  },[api,c,lessonId])
  useEffect(()=>{
    if(!selected || selected.kind!=='presentation' || !selected.content || isVideoResourceContent(selected.content) || !selected.content.slides?.some(slide=>slide.visual?.status==='pending'||slide.visual?.status==='processing'))return
    const timer=window.setTimeout(()=>{void refreshVisuals(selected.id).catch(()=>{if(selectedIdRef.current===selected.id)setError(c('Could not refresh visuals. Try again.'))})},2500)
    return()=>window.clearTimeout(timer)
  },[selected,refreshVisuals,c])
  async function changeVisual(index:number,method:'POST'|'DELETE') {
    if(!selected || visualBusy!=null)return
    const resourceId=selected.id
    setVisualBusy(index);setError('')
    try {
      await api<void>(`lessons/${lessonId}/resources/${resourceId}/slides/${index+1}/visual`,method)
      await refreshVisuals(resourceId)
    } catch(reason) {
      setError(reason instanceof Error?reason.message:c('Could not update this visual. Try again.'))
    } finally {setVisualBusy(null)}
  }
  async function generate() {
    if(generating || !lesson)return
    if((dirty||sourcesDirty)&&!window.confirm(c('Leave without saving your changes?')))return
    setGenerating(true);setError('');setNotice('')
    try {const payload=kind==='video'?videoGenerationRequest(crypto.randomUUID(),videoDuration,videoVoice):{kind,request_id:crypto.randomUUID()};const item=await api<Resource>(`lessons/${lessonId}/resources`,'POST',payload);setResources(old=>[item,...old.filter(r=>r.id!==item.id)]);selectedIdRef.current=item.id;selectedRevisionRef.current=item.revision;setSelected(item);setContent(item.content);setSlideIndex(0);setNotice('Saved')}
    catch(e){await load();setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}
    finally{setGenerating(false)}
  }
  async function save() {
    if(!selected||!content)return
    setBusy(true);setError('');setNotice('')
    try {const item=await api<Resource>(`lessons/${lessonId}/resources/${selected.id}`,'PATCH',{content:editableResourceContent(content),revision:selected.revision});selectedRevisionRef.current=item.revision;setSelected(item);setContent(item.content);setResources(old=>old.map(r=>r.id===item.id?item:r));setNotice('Saved')}
    catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}
    finally{setBusy(false)}
  }
  async function updateLesson(input:LessonInput) {
    if(!lesson)return
    setBusy(true);setError('')
    try {const saved=await api<Lesson>(`lessons/${lessonId}`,'PATCH',{lesson:input,revision:lesson.revision});setLesson(saved);setNotice('Saved')}
    catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}
    finally{setBusy(false)}
  }
  async function remove(resource?:Resource) {
    if(!window.confirm(c(resource?'Delete this resource?':'Delete this lesson and all its resources?')))return
    setBusy(true);setError('')
    try {await api(resource?`lessons/${lessonId}/resources/${resource.id}`:`lessons/${lessonId}`,'DELETE');if(resource){setResources(old=>old.filter(r=>r.id!==resource.id));selectedIdRef.current=null;setSelected(null);setContent(null)}else router.push('/teacher')}
    catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}
    finally{setBusy(false)}
  }
  async function loadMore() {
    setBusy(true);setError('')
    try{const rows=await api<Resource[]>(`lessons/${lessonId}/resources?limit=25&offset=${resources.length}`);setResources(old=>[...old,...rows]);setMore(rows.length===25)}
    catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}
    finally{setBusy(false)}
  }
  function print(mode:'student'|'teacher'){flushSync(()=>setPrintMode(mode));window.print()}
  async function refresh() {if((dirty||sourcesDirty)&&!window.confirm(c('Leave without saving your changes?')))return;await load();if(selected){try{const updated=await api<Resource>(`lessons/${lessonId}/resources/${selected.id}`);selectedIdRef.current=updated.id;selectedRevisionRef.current=updated.revision;setSelected(updated);setContent(updated.content)}catch{selectedIdRef.current=null;setSelected(null);setContent(null)}}}
  return <TeacherShell onNavigate={e=>{if((dirty||sourcesDirty)&&!window.confirm(c('Leave without saving your changes?')))e.preventDefault()}}><div className="prep-detail prep-screen">
    <Link href="/teacher" className="prep-back" onClick={e=>{if((dirty||sourcesDirty)&&!window.confirm(c('Leave without saving your changes?')))e.preventDefault()}}><ArrowLeft size={17} aria-hidden="true" />{c('My lessons')}</Link>
    {error && <div className="prep-error" role="alert">{c(error)}<button disabled={busy||generating} onClick={()=>void refresh()}>{c('Refresh')}</button></div>}
    {notice && <p className="prep-notice" role="status">{c(notice)}</p>}
    {loading||(!lesson&&busy)?<p role="status">{c('Loading…')}</p>:!user?<Link className="prep-button primary" href="/login">{c('Sign in')}</Link>:lesson&&<>
      <header className="prep-page-heading prep-lesson-heading"><div><p className="prep-eyebrow">{c('Teacher prep')} · {c('Grade')} {lesson.grade}</p><h1>{lesson.topic}</h1><p>{c('Choose sources, then generate one material at a time and review it before class.')}</p></div><button className="prep-button danger" onClick={()=>void remove()} disabled={busy||generating}><Trash2 size={17} aria-hidden="true"/>{c('Delete lesson')}</button></header>
      <ol className="prep-steps" aria-label={c('Lesson preparation steps')}><li>{c('Set lesson context')}</li><li>{c('Choose sources')}</li><li aria-current={!selected ? 'step' : undefined}>{c('Generate materials')}</li><li aria-current={selected ? 'step' : undefined}>{c('Review and preview')}</li></ol>
      <details className="prep-card prep-context"><summary>{c('Lesson details')}</summary><p className="prep-hint">{c('Changes apply to future resources. Existing resources keep their original lesson context.')}</p><LessonForm key={`${lesson.id}-${lesson.revision}`} initial={lesson} editing submit={updateLesson} busy={busy||generating}/></details>
      <SourcePicker lesson={lesson} disabled={busy||generating||dirty} selectionChanged={setSourcesDirty} saved={row=>{setLesson(row);setNotice('Saved')}}/>
      <section className="prep-card prep-generator"><div className="prep-section-heading"><h2>{c('What would you like to prepare?')}</h2><Sparkles size={23} aria-hidden="true"/></div><fieldset disabled={generating||busy} className="prep-resource-options"><legend className="sr-only">{c('Generate one resource')}</legend>{resourceKinds.map(item=><button type="button" key={item.kind} onClick={()=>setKind(item.kind)} aria-pressed={kind===item.kind} className={`prep-resource-choice ${kind===item.kind?'selected':''}`}><span>{c(item.label)}</span><small>{c(item.detail)}</small></button>)}</fieldset>{kind==='video'&&<fieldset disabled={generating||busy} className="prep-video-options"><legend>{c('Topic video settings')}</legend><label>{c('Video length')}<select value={videoDuration} onChange={event=>setVideoDuration(Number(event.target.value) as 180|240|300)}><option value={180}>{c('3 minutes')}</option><option value={240}>{c('4 minutes')}</option><option value={300}>{c('5 minutes')}</option></select></label><label>{c('Narration voice')}<select value={videoVoice} onChange={event=>setVideoVoice(event.target.value as 'female'|'male')}><option value="female">{c('Female voice')}</option><option value="male">{c('Male voice')}</option></select></label></fieldset>}<button className="prep-button primary" disabled={busy||generating||sourcesDirty} onClick={()=>void generate()}><Sparkles size={18} aria-hidden="true"/>{c(generating?'Preparing your resource…':'Generate one resource')}</button>{generating&&<p role="status">{c('Preparing your resource…')}</p>}</section>
      <div className="prep-workspace"><aside className="prep-resource-list prep-card" aria-label={c('Saved resources')}><div className="prep-section-heading"><h2>{c('Saved resources')}</h2><button className="prep-icon-button" aria-label={c('Refresh resources')} onClick={()=>void refresh()} disabled={busy||generating}>↻</button></div>{!resources.length&&<div className="prep-empty prep-resources-empty"><FileText size={25} aria-hidden="true"/><p>{c('Your first resource will appear here.')}</p><p>{c('Choose a resource type above and generate it. It will be saved here for review.')}</p></div>}{resources.map(item=>{const title=item.kind==='video'?videoResourceTitle(item.content):item.content&&!isVideoResourceContent(item.content)?item.content.title:'';return <button key={item.id} className={`prep-resource-row ${selected?.id===item.id?'selected':''}`} aria-current={selected?.id===item.id?'true':undefined} aria-label={`${c('Open resource')}: ${title||c(resourceKinds.find(k=>k.kind===item.kind)?.label||item.kind)}`} onClick={()=>open(item)} disabled={busy||generating}><FileText size={18} aria-hidden="true"/><span><strong>{title||c(resourceKinds.find(k=>k.kind===item.kind)?.label||item.kind)}</strong><small>{c(item.status==='ready'?'Ready':item.status==='failed'?'Failed':'Preparing')}</small></span></button>})}{more&&<button className="prep-button" onClick={()=>void loadMore()} disabled={busy||generating}>{c('Load more')}</button>}</aside>
      <section className="prep-card prep-resource-area">{selected&&content?<><div className="prep-editor-toolbar"><span role="status">{c(dirty?'Unsaved changes':'Saved')}</span><button className="prep-button primary" disabled={!dirty||busy||generating} onClick={()=>void save()}><Save size={17} aria-hidden="true"/>{c(busy?'Saving…':'Save changes')}</button>{selected.kind!=='video'&&<><button className="prep-button" onClick={()=>print('student')} disabled={busy||generating||dirty}><Printer size={17} aria-hidden="true"/>{c('Print student copy')}</button><button className="prep-button" onClick={()=>print('teacher')} disabled={busy||generating||dirty}>{c('Print teacher copy')}</button></>}<button className="prep-icon-button danger" aria-label={c('Delete resource')} onClick={()=>void remove(selected)} disabled={busy||generating}><Trash2 size={17} aria-hidden="true"/></button></div><p className="prep-review-note">{c('Review this AI-generated draft for accuracy and suitability before using it with learners.')}</p>{selected.kind!=='video'&&<SourceReferences provenance={selected.provenance} language={selected.lesson_snapshot.language}/ >}{selected.kind==='video'?isVideoResourceContent(content)?<><VideoScriptEditor content={content} change={setContent} disabled={busy||generating}/><VideoResourceRender key={`${lessonId}:${selected.id}`} lessonId={lessonId} resourceId={selected.id} revision={selected.revision} disabled={dirty||busy||generating}/></>:<p className="prep-error" role="alert">{c('This video script could not be loaded. Refresh the lesson and try again.')}</p>:<ResourceEditor content={content as ResourceContent} kind={selected.kind} change={setContent} disabled={busy||generating} retryVisual={index=>void changeVisual(index,'POST')} removeVisual={index=>void changeVisual(index,'DELETE')} visualBusy={visualBusy}/ >}{selected.kind==='presentation'&&!isVideoResourceContent(content)&&<><PresentationStage title={content.title} slides={content.slides||[]} index={slideIndex} changeIndex={setSlideIndex} print={()=>print('teacher')}/><PresentationRender lessonId={lessonId} resourceId={selected.id} disabled={dirty||busy||generating||visualsPending} visualsPending={visualsPending}/></>}</>:selected?<><p>{c(selected.status==='failed'?'This item could not finish. Generate a new resource to try again.':'Preparing your resource…')}</p><button className="prep-button danger" disabled={busy||generating} onClick={()=>void remove(selected)}>{c('Delete resource')}</button></>:<div className="prep-empty prep-preview-empty"><FileText size={28} aria-hidden="true"/><p>{c('Choose a material type above, then generate it. Saved materials will appear in this list.')}</p></div>}</section></div>
    </>}
  </div>{content&&selected&&selected.kind!=='video'&&!isVideoResourceContent(content)&&<div className="prep-print"><ResourceDocument content={content} kind={selected.kind} mode={printMode} language={selected.lesson_snapshot.language} provenance={selected.provenance}/></div>}</TeacherShell>
}
