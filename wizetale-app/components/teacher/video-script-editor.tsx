'use client'

import { Plus, Trash2 } from 'lucide-react'
import { useCopy } from '@/hooks/use-copy'
import { VideoResourceContent } from '@/lib/teacher-content'

export function VideoScriptEditor({
  content,
  change,
  disabled,
}: {
  content: VideoResourceContent
  change: (content: VideoResourceContent) => void
  disabled: boolean
}) {
  const c = useCopy()
  const setScript = (updates: Partial<VideoResourceContent['script']>) =>
    change({...content, script: {...content.script, ...updates}})

  return <fieldset className="prep-editor prep-form prep-video-script-editor" disabled={disabled}>
    <legend className="sr-only">{c('Review and edit the video script')}</legend>
    <p className="prep-hint">{c('Review this grade-tailored narration before rendering. Editing the script creates a new saved version.')}</p>
    <div className="prep-video-script-meta" aria-label={c('Video settings')}>
      <span>{c('Video length')}: {content.target_duration_sec / 60} {c('minutes')}</span>
      <span>{c(content.voice === 'female' ? 'Female voice' : 'Male voice')}</span>
    </div>
    <label>{c('Video title')}<input required maxLength={300} value={content.script.title} onChange={event=>setScript({title:event.target.value})}/></label>
    <label>{c('Opening hook')}<textarea rows={3} value={content.script.hook} onChange={event=>setScript({hook:event.target.value})}/></label>
    <section className="prep-edit-section prep-video-sections">
      <h3>{c('Story sections')}</h3>
      {content.script.sections.map((section,index)=><article className="prep-edit-item" key={index}>
        <div className="prep-section-heading"><h4>{c('Section')} {index+1}</h4><button type="button" className="prep-icon-button" aria-label={c('Remove section') + ' ' + (index+1)} onClick={()=>setScript({sections:content.script.sections.filter((_,itemIndex)=>itemIndex!==index)})}><Trash2 size={17} aria-hidden="true"/></button></div>
        <label>{c('Heading')}<input required maxLength={300} value={section.heading} onChange={event=>setScript({sections:content.script.sections.map((item,itemIndex)=>itemIndex===index?{...item,heading:event.target.value}:item)})}/></label>
        <label>{c('Section summary')}<textarea rows={3} value={section.summary} onChange={event=>setScript({sections:content.script.sections.map((item,itemIndex)=>itemIndex===index?{...item,summary:event.target.value}:item)})}/></label>
      </article>)}
      <button type="button" className="prep-button" onClick={()=>setScript({sections:[...content.script.sections,{heading:'',summary:''}]})}><Plus size={16} aria-hidden="true"/>{c('Add story section')}</button>
    </section>
    <label>{c('Full narration')}<textarea rows={16} value={content.script.full_narration} onChange={event=>setScript({full_narration:event.target.value})}/></label>
  </fieldset>
}
