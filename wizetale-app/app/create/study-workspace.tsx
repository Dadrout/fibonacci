'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Image from 'next/image'
import { BookOpen, Check, ChevronLeft, ChevronRight, FileQuestion, Layers3, Plus, Presentation, Sparkles, Trash2 } from 'lucide-react'
import { SignInPrompt } from '@/components/sign-in-prompt'
import { PresentationStage } from '@/components/presentation-stage'
import { StudyShell } from '@/components/study/study-shell'
import { useAuth } from '@/hooks/use-auth'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { contentLanguageFor } from '@/lib/content-language'
import { useStudyAPI } from '@/hooks/use-study-api'
import { studentSubjects as schoolSubjects, mergeSlideVisuals, studentGenerationContext, type StudentPresentationSlide as PresentationSlide } from '@/lib/student-workspace'
import { useStudentWorkspace } from '@/lib/student-workspace-context'
import { useStudentCopy } from '@/hooks/use-student-copy'
import { FibonacciMark } from '@/components/fibonacci-mark'

type MaterialKind = 'flashcards'|'quiz'|'presentation'
type StudyOption = { id: 'a'|'b'|'c'|'d'; text: string }
type StudyQuestion = { prompt: string; options: StudyOption[]; explanation?: string }
type StudyContent = { title: string; instructions: string; flashcards: {front:string;back:string}[]; questions: StudyQuestion[]; slides: PresentationSlide[] }
type StudyMaterial = { id:string; kind:MaterialKind; status:'generating'|'ready'|'failed'; subject:string; grade:string; topic:string; language:string; context:{subject:string;grade:string;topic:string;language:string}; content:StudyContent|null; revision:number; created_at:string }
type QuizResult = { score:number; total:number; results:{question_number:number;correct:boolean;correct_option:string;explanation:string}[] }

export default function StudyWorkspace({ active, showLibrary, initialMaterialId }: { active: boolean; showLibrary: boolean; initialMaterialId: string | null }) {
  const c=useStudentCopy(),api=useStudyAPI(),workspace=useStudentWorkspace()
  const { subject, topic, language }=workspace.setup
  const kind: MaterialKind=workspace.mode==='story'?'flashcards':workspace.mode
  const [materials,setMaterials]=useState<StudyMaterial[]>([]),[selected,setSelected]=useState<StudyMaterial|null>(null)
  const [grade,setGrade]=useState('6')
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const [flashcardIndex,setFlashcardIndex]=useState(0),[flipped,setFlipped]=useState(false)
  const [answers,setAnswers]=useState<Record<string,string>>({}),[quizResult,setQuizResult]=useState<QuizResult|null>(null)
  const [editedContent,setEditedContent]=useState<StudyContent|null>(null),[slideIndex,setSlideIndex]=useState(0)
  const [visualBusy,setVisualBusy]=useState<number|null>(null)
  const sessions=useRef<Record<string,{editedContent:StudyContent|null;flashcardIndex:number;flipped:boolean;answers:Record<string,string>;quizResult:QuizResult|null;slideIndex:number}>>({})
  const requestedMaterial=useRef(initialMaterialId)
  const libraryLoaded=useRef(false)
  useEffect(()=>{workspace.reportBusy('study',busy||visualBusy!==null)},[busy,visualBusy,workspace.reportBusy])
  const sessionId=useRef<string|null>(null)
  useEffect(()=>{if(selected&&sessionId.current===selected.id)sessions.current[selected.id]={editedContent,flashcardIndex,flipped,answers,quizResult,slideIndex}},[editedContent,flashcardIndex,flipped,answers,quizResult,slideIndex])
  const dirty=Boolean(selected?.kind==='presentation'&&selected.content&&editedContent&&JSON.stringify(selected.content)!==JSON.stringify(editedContent))
  const load=useCallback(async()=>{
    setLoading(true);setError('')
    try{const rows=await api<StudyMaterial[]>('', 'GET');setMaterials(rows);setSelected(current=>current?rows.find(row=>row.id===current.id)||null:rows.find(row=>row.id===requestedMaterial.current)||rows.find(row=>row.kind===kind)||null)}
    catch(reason){setError(reason instanceof Error?reason.message:c('Could not load your study library. Try again.'))}
    finally{setLoading(false)}
  },[api,c])
  useEffect(()=>{
    if(!active&&!showLibrary)return
    if(libraryLoaded.current)return
    libraryLoaded.current=true
    void load()
  },[active,showLibrary,load])
  useEffect(()=>{
    const session=selected?sessions.current[selected.id]:null
    sessionId.current=selected?.id||null
    setEditedContent(session?.editedContent??(selected?.content?structuredClone(selected.content):null))
    setFlashcardIndex(session?.flashcardIndex??0);setFlipped(session?.flipped??false);setAnswers(session?.answers??{});setQuizResult(session?.quizResult??null);setSlideIndex(session?.slideIndex??0)
    if(selected&&requestedMaterial.current===selected.id){workspace.selectMode(selected.kind);workspace.setSetup(value=>({...value,subject:selected.subject,topic:selected.topic,language:selected.language}));setGrade(selected.grade);requestedMaterial.current=null}
  },[selected?.id])
  useEffect(()=>{if(active&&!requestedMaterial.current&&selected?.kind!==kind)setSelected(materials.find(item=>item.kind===kind)||null)},[kind,active,materials])
  useEffect(()=>{
    if(!initialMaterialId||initialMaterialId===selected?.id)return
    requestedMaterial.current=initialMaterialId
    const material=materials.find(item=>item.id===initialMaterialId)
    if(material)setSelected(material)
  },[initialMaterialId,materials])
  const selectMaterial=(material:StudyMaterial)=>{setSelected(material);workspace.selectMode(material.kind);workspace.setSetup(value=>({...value,subject:material.subject,topic:material.topic,language:material.language}));setGrade(material.grade);setError('');setNotice('')}

  const refreshSelected=useCallback(async()=>{
    if(!selected)return
    try{
      const refreshed=await api<StudyMaterial>(selected.id,'GET')
      if(refreshed.revision!==selected.revision){
        setError(c('This study material changed. Reload before saving.'))
        const keepTextAndUpdateVisuals=(item:StudyMaterial)=>item.id!==refreshed.id||!item.content||!refreshed.content?item:{...item,content:{...item.content,slides:mergeSlideVisuals(item.content.slides,refreshed.content.slides)}}
        setSelected(current=>current?keepTextAndUpdateVisuals(current):current)
        setMaterials(old=>old.map(keepTextAndUpdateVisuals))
        setEditedContent(current=>current&&refreshed.content?{...current,slides:mergeSlideVisuals(current.slides,refreshed.content.slides)}:current)
        return
      }
      setSelected(refreshed);setMaterials(old=>old.map(item=>item.id===refreshed.id?refreshed:item))
      setEditedContent(current=>current&&refreshed.content?{...current,slides:mergeSlideVisuals(current.slides,refreshed.content.slides)}:refreshed.content)
    }catch(reason){setError(reason instanceof Error?reason.message:c('Could not refresh slide visuals. Try again.'))}
  },[api,selected?.id,selected?.revision,c])
  useEffect(()=>{
    const pending=selected?.status==='generating'||selected?.content?.slides?.some(slide=>slide.visual?.status==='pending'||slide.visual?.status==='processing')
    if(!pending)return
    const timer=window.setInterval(()=>void refreshSelected(),4000)
    return()=>window.clearInterval(timer)
  },[selected,refreshSelected])
  async function changeVisual(index:number,method:'POST'|'DELETE'){
    if(!selected||busy||visualBusy!==null)return
    setVisualBusy(index);setError('')
    try{
      await api(`${encodeURIComponent(selected.id)}/slides/${index+1}/visual`,method)
      await refreshSelected()
    }catch(reason){setError(reason instanceof Error?reason.message:c('Could not update slide visual. Try again.'))}
    finally{setVisualBusy(null)}
  }

  async function reloadSelected(){
    if(!selected){await load();return}
    if(dirty&&!window.confirm(c('Leave without saving your changes?')))return
    setLoading(true);setError('');setNotice('')
    try{
      const refreshed=await api<StudyMaterial>(selected.id,'GET')
      setSelected(refreshed);setMaterials(old=>old.map(item=>item.id===refreshed.id?refreshed:item))
      setEditedContent(refreshed.content?structuredClone(refreshed.content):null)
    }catch(reason){setError(reason instanceof Error?reason.message:c('Could not complete this request. Please try again.'))}
    finally{setLoading(false)}
  }

  async function generate(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();if(busy)return
    setBusy(true);setError('');setNotice('')
    try{
      const created=await api<StudyMaterial>('', 'POST',{kind,request_id:crypto.randomUUID(),context:studentGenerationContext(workspace.setup,grade)})
      setMaterials(old=>[created,...old.filter(item=>item.id!==created.id)]);delete sessions.current[created.id];setSelected(created);setNotice(c('Saved to your private study library.'))
    }catch(reason){setError(reason instanceof Error?reason.message:c('Could not create study material. Try again.'))}
    finally{setBusy(false)}
  }

  async function savePresentation(){
    if(!selected||!editedContent)return
    setBusy(true);setError('');setNotice('')
    try{
      const saved=await api<StudyMaterial>(selected.id,'PATCH',{content:editedContent,revision:selected.revision})
      setSelected(saved);setMaterials(old=>old.map(item=>item.id===saved.id?saved:item));setEditedContent(saved.content);setNotice(c('Saved'))
    }catch(reason){setError(reason instanceof Error?reason.message:c('This study material changed. Reload before saving.'))}
    finally{setBusy(false)}
  }

  async function deleteMaterial(material:StudyMaterial){
    if(!window.confirm(c('Delete this study material?')))return
    setBusy(true);setError('')
    try{await api(material.id,'DELETE');const remaining=materials.filter(item=>item.id!==material.id);setMaterials(remaining);setSelected(current=>current?.id===material.id?remaining[0]||null:current);setNotice(c('Study material deleted.'))}
    catch(reason){setError(reason instanceof Error?reason.message:c('Could not complete this request. Please try again.'))}
    finally{setBusy(false)}
  }

  async function submitQuiz(){
    if(!selected)return
    setBusy(true);setError('')
    try{setQuizResult(await api<QuizResult>(`${selected.id}/check`,'POST',{answers}))}
    catch(reason){setError(reason instanceof Error?reason.message:c('Check every question and try again.'))}
    finally{setBusy(false)}
  }

  const currentSlide=editedContent?.slides?.[slideIndex]
  const currentCard=selected?.content?.flashcards?.[flashcardIndex]
  const currentQuestions=selected?.content?.questions||[]
  const allAnswers=currentQuestions.length>0&&currentQuestions.every((_,index)=>Boolean(answers[String(index+1)]))
  const quizResults=useMemo(()=>new Map((quizResult?.results||[]).map(item=>[item.question_number,item])),[quizResult])
  const printPresentation=()=>window.print()

  return <>
    <div className="prep-detail prep-screen study-screen">
      {error&&<p className="prep-error" role="alert">{c(error)}<button type="button" onClick={()=>void reloadSelected()} disabled={busy||loading}>{c('Refresh')}</button></p>}{notice&&<p className="prep-notice" role="status">{notice}</p>}
      <section className="prep-card study-create-card" hidden={!active}><div className="prep-section-heading"><div><p className="prep-eyebrow">{c('Uses your topic and source')}</p><h2>{c('Make your study tool')}</h2></div><Sparkles size={25} aria-hidden="true"/></div>
        <form className="prep-form study-create-form" onSubmit={generate}>
          <label>{c('Grade')}<select value={grade} onChange={event=>setGrade(event.target.value)} disabled={busy}><option value="K">{c('Kindergarten')}</option>{Array.from({length:12},(_,index)=><option key={index+1} value={String(index+1)}>{index+1}</option>)}</select></label>
          <button type="submit" className="prep-button primary" disabled={busy||!topic.trim()}><Plus size={18} aria-hidden="true"/>{c(busy?'Creating your study tool…':'Create study tool')}</button>
        </form>
      </section>
      <div className="study-workspace">
        <aside className="prep-card study-library" hidden={!showLibrary} aria-labelledby="study-library-title"><div className="prep-section-heading"><div><p className="prep-eyebrow">{c('Saved for you')}</p><h2 id="study-library-title">{c('Study library')}</h2></div><span className="study-library-count">{materials.length}</span></div>
          {loading?<p role="status">{c('Loading…')}</p>:!materials.length?<div className="prep-empty"><img className="student-empty-art" src="/illustrations/empty-library.png" alt="" width={110} height={110} loading="lazy"/><p>{c('Your study library is empty. Create a tool from a topic to get started.')}</p></div>:<div className="study-library-list">{materials.map(item=><button key={item.id} type="button" className={`study-library-item ${selected?.id===item.id?'selected':''}`} onClick={()=>selectMaterial(item)} disabled={busy}><span className="study-library-icon">{item.kind==='quiz'?<FileQuestion size={19}/>:item.kind==='presentation'?<Presentation size={19}/>:<Layers3 size={19}/>}</span><span className="study-library-copy"><strong>{item.content?.title||c(item.kind)}</strong><small>{item.topic} · {c(schoolSubjects.find(entry=>entry.value===item.subject)?.label||item.subject)} · {c('Grade')} {item.grade}</small><small>{c(item.status==='ready'?'Ready':item.status==='failed'?'Failed':'Creating')}</small></span><span className="study-library-arrow" aria-hidden="true">›</span></button>)}</div>}
        </aside>
        <section className="prep-card study-viewer" hidden={!active} aria-label={c('Selected study material')}>
          {!selected?.content?<div className="prep-empty"><img className="student-empty-art" src="/illustrations/empty-study.png" alt="" width={132} height={132} loading="lazy"/><p>{c('Choose an item from your study library, or create one from a new topic.')}</p></div>:<>
            <div className="study-viewer-heading"><div><p className="prep-eyebrow">{c(selected.kind)} · {c(schoolSubjects.find(entry=>entry.value===selected.subject)?.label||selected.subject)} · {c('Grade')} {selected.grade}</p><h2>{selected.content.title}</h2><p>{selected.topic}</p></div><button type="button" className="prep-icon-button danger" aria-label={`${c('Delete study material')}: ${selected.content.title}`} disabled={busy||visualBusy!==null} onClick={()=>void deleteMaterial(selected)}><Trash2 size={17} aria-hidden="true"/></button></div>
            {selected.kind==='flashcards'&&currentCard&&<section className="study-flashcard-session"><p className="study-session-caption">{c('Flashcard')} {flashcardIndex+1} {c('of')} {selected.content.flashcards.length}</p><button type="button" className={`study-flashcard ${flipped?'is-flipped':''}`} aria-pressed={flipped} onClick={()=>setFlipped(value=>!value)}><span>{flipped?c('Answer'):c('Tap to reveal')}</span><strong>{flipped?currentCard.back:currentCard.front}</strong><small>{c('Tap the card to flip it')}</small></button><div className="study-session-actions"><button type="button" className="prep-button" aria-label={c('Previous flashcard')} onClick={()=>{setFlashcardIndex(value=>Math.max(0,value-1));setFlipped(false)}} disabled={flashcardIndex===0}><ChevronLeft size={18} aria-hidden="true"/>{c('Previous')}</button><button type="button" className="prep-button" aria-label={c('Next flashcard')} onClick={()=>{setFlashcardIndex(value=>Math.min(selected.content!.flashcards.length-1,value+1));setFlipped(false)}} disabled={flashcardIndex>=selected.content.flashcards.length-1}>{c('Next')}<ChevronRight size={18} aria-hidden="true"/></button></div></section>}
            {selected.kind==='quiz'&&<section className="study-quiz-session"><p className="prep-hint">{c('Choose an answer for each question, then check your work. Answers and explanations appear after you submit.')}</p>{quizResult&&<div className="study-score" role="status"><Check size={20} aria-hidden="true"/><strong>{c('You got')} {quizResult.score} {c('of')} {quizResult.total} {c('correct')}</strong><button type="button" onClick={()=>{setQuizResult(null);setAnswers({})}}>{c('Try again')}</button></div>}<div className="study-question-list">{currentQuestions.map((question,index)=>{const number=index+1,result=quizResults.get(number);return <fieldset key={index} className={`study-question ${result?result.correct?'is-correct':'is-incorrect':''}`}><legend><strong>{number}.</strong> {question.prompt}</legend><div className="study-option-list">{question.options.map(option=><label key={option.id} className={result?.correct_option===option.id?'is-answer':''}><input type="radio" name={`question-${number}`} value={option.id} checked={answers[String(number)]===option.id} disabled={busy||Boolean(quizResult)} onChange={()=>setAnswers(previous=>({...previous,[String(number)]:option.id}))}/><span>{option.text}</span></label>)}</div>{result&&<div className="study-explanation"><strong>{result.correct?c('Correct!'):c('Review this one')}</strong><p>{result.explanation}</p></div>}</fieldset>})}</div>{!quizResult&&<button type="button" className="prep-button primary" disabled={busy||!allAnswers} onClick={()=>void submitQuiz()}>{c(busy?'Checking…':'Check my answers')}</button>}</section>}
            {selected.kind==='presentation'&&editedContent&&<section className="study-presentation-session"><div className="study-presentation-edit"><div className="prep-section-heading"><div><h3>{c('Edit your presentation')}</h3><p className="prep-hint">{c('Changes stay in your private study library.')}</p></div><button type="button" className="prep-button primary" disabled={!dirty||busy||visualBusy!==null} onClick={()=>void savePresentation()}>{c(busy?'Saving…':'Save changes')}</button></div><label>{c('Title')}<input maxLength={300} value={editedContent.title} onChange={event=>setEditedContent({...editedContent,title:event.target.value})}/></label>{editedContent.slides.map((slide,index)=><details className="study-slide-edit" key={index} open={index===slideIndex} onToggle={event=>{if(event.currentTarget.open)setSlideIndex(index)}}><summary>{c('Slide')} {index+1}: {slide.title}</summary><div><label>{c('Slide title')}<input maxLength={200} value={slide.title} onChange={event=>setEditedContent(value=>value?({...value,slides:value.slides.map((item,i)=>i===index?{...item,title:event.target.value}:item)}):value)}/></label><label>{c('Key points')}<textarea rows={4} value={slide.key_points.join('\n')} onChange={event=>setEditedContent(value=>value?({...value,slides:value.slides.map((item,i)=>i===index?{...item,key_points:event.target.value.split('\n').map(point=>point.trim()).filter(Boolean)}:item)}):value)}/></label><label>{c('Speaker notes')}<textarea rows={4} value={slide.speaker_notes} onChange={event=>setEditedContent(value=>value?({...value,slides:value.slides.map((item,i)=>i===index?{...item,speaker_notes:event.target.value}:item)}):value)}/></label><div className="student-slide-visual"><strong>{c('Slide visual')}</strong><p role="status">{c(slide.visual?.status==='ready'?'Visual ready':slide.visual?.status==='failed'?'Visual failed':slide.visual?.status==='processing'?'Creating visual…':slide.visual?.status==='pending'?'Visual queued':'No visual')}</p>{slide.visual?.status==='ready'&&slide.visual.image_url&&<figure className="prep-slide-visual"><img src={slide.visual.image_url} alt={slide.visual.alt_text}/>{slide.visual.caption&&<figcaption>{slide.visual.caption}</figcaption>}</figure>}<div className="study-session-actions">{slide.visual&&<button type="button" className="prep-button" disabled={busy||visualBusy!==null||slide.visual.status==='pending'||slide.visual.status==='processing'} onClick={()=>void changeVisual(index,'POST')}>{c(visualBusy===index?'Updating visual…':'Retry visual')}</button>}{slide.visual&&<button type="button" className="prep-button" disabled={busy||visualBusy!==null} onClick={()=>void changeVisual(index,'DELETE')}>{c('Remove visual')}</button>}</div></div></div></details>)}</div><PresentationStage title={editedContent.title} slides={editedContent.slides} index={slideIndex} changeIndex={setSlideIndex} print={printPresentation}/></section>}
          </>}
        </section>
      </div>
    </div>
    {active&&selected?.kind==='presentation'&&editedContent&&<div className="prep-print"><article className="prep-document prep-study-document" lang={selected.language==='kk-KZ'?'kk':selected.language==='ru-RU'?'ru':'en'}><div className="prep-document-header"><span className="prep-document-brand"><FibonacciMark size={30}/><strong>Fibonacci</strong></span><span>{c('My presentation')}</span></div><h1>{editedContent.title}</h1><p>{selected.topic} · {c(schoolSubjects.find(entry=>entry.value===selected.subject)?.label||selected.subject)} · {c('Grade')} {selected.grade}</p>{editedContent.slides.map((slide,index)=><section className="prep-presentation-pdf-slide" key={index}><p className="prep-document-kicker">{c('Slide')} {index+1}</p><h2>{slide.title}</h2>{slide.visual?.status==='ready'&&slide.visual.image_url&&<figure><img src={slide.visual.image_url} alt={slide.visual.alt_text}/>{slide.visual.caption&&<figcaption>{slide.visual.caption}</figcaption>}</figure>}<ul>{slide.key_points.map((point,pointIndex)=><li key={pointIndex}>{point}</li>)}</ul><aside><h3>{c('Speaker notes')}</h3><p>{slide.speaker_notes}</p></aside></section>)}</article></div>}
  </>
}
