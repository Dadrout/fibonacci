'use client'
import {useCallback,useEffect,useRef,useState} from 'react'
import Link from 'next/link'
import {reconcileSelection} from '@/lib/teacher-source-state'
import {useTeacherAPI} from '@/hooks/use-teacher-api'
import {useCopy} from '@/hooks/use-copy'
import type {Lesson,TeacherSource} from '@/lib/teacher-content'

export function SourcePicker({lesson,disabled,saved,selectionChanged}:{lesson:Lesson;disabled:boolean;selectionChanged:(dirty:boolean)=>void;saved:(lesson:Lesson)=>void}){
 const api=useTeacherAPI(),c=useCopy()
 const [sources,setSources]=useState<TeacherSource[]>([]),[selection,setSelection]=useState<string[]>(lesson.source_document_ids||[])
 const [busy,setBusy]=useState(false),[loadingSources,setLoadingSources]=useState(true),[error,setError]=useState('')
 const load=useCallback(async()=>{setLoadingSources(true);setError('');try{setSources(await api<TeacherSource[]>('documents?limit=50'))}catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}finally{setLoadingSources(false)}},[api])
 useEffect(()=>{void load()},[load])
 const savedIds=useRef(lesson.source_document_ids||[])
 useEffect(()=>{const current=lesson.source_document_ids||[],previous=savedIds.current;setSelection(old=>reconcileSelection(old,previous,current));savedIds.current=current},[lesson.source_document_ids])
 const dirty=JSON.stringify([...selection].sort())!==JSON.stringify([...(lesson.source_document_ids||[])].sort())
 useEffect(()=>{selectionChanged(dirty)},[dirty,selectionChanged])
 async function save(){setBusy(true);setError('');try{saved(await api<Lesson>(`lessons/${lesson.id}/sources`,'PUT',{document_ids:selection,revision:lesson.revision}))}catch(e){setError(e instanceof Error?e.message:'Could not complete this request. Please try again.')}finally{setBusy(false)}}
 return <section className="prep-card prep-source-picker"><div className="prep-section-heading"><h2>{c('Lesson sources')}</h2><Link href="/teacher/sources">{c('My sources')}</Link></div><p className="prep-hint">{c('Select up to five ready sources. Save your selection before generating.')}</p><p>{c(selection.length?'Materials will use only relevant passages from these sources.':'No sources selected. Generation uses the lesson details.')}</p>{error&&<p className="prep-error" role="alert">{c(error)}</p>}{loadingSources&&<p role="status">{c('Loading sources…')}</p>}<fieldset disabled={disabled||busy||loadingSources||Boolean(error)}><legend className="sr-only">{c('Lesson sources')}</legend>{sources.filter(s=>s.status==='ready').map(source=><label className="prep-source-option" key={source.id}><input type="checkbox" checked={selection.includes(source.id)} disabled={!selection.includes(source.id)&&selection.length>=5} onChange={e=>setSelection(old=>e.target.checked?[...old,source.id]:old.filter(id=>id!==source.id))}/><span>{source.title}</span></label>)}</fieldset>{!loadingSources&&!error&&!sources.some(s=>s.status==='ready')&&<div className="prep-source-empty"><p>{c('No ready sources yet.')}</p><p>{c('Upload a source and wait until it is ready.')}</p><Link className="prep-button" href="/teacher/sources">{c('Add a source')}</Link></div>}<div className="prep-source-actions"><button className={`prep-button ${dirty?'primary':''}`} disabled={!dirty||disabled||busy||loadingSources||Boolean(error)} onClick={()=>void save()}>{c(busy?'Saving…':'Save sources')}</button><button className="prep-button" disabled={disabled||busy||loadingSources} onClick={()=>void load()}>{c(error?'Retry loading sources':'Refresh')}</button></div>{dirty&&<p role="status">{c('Unsaved source selection')}</p>}</section>
}
