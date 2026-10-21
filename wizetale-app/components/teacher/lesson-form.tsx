'use client'
import { FormEvent, useEffect, useState } from 'react'
import { useCopy } from '@/hooks/use-copy'
import { useLanguage } from '@/hooks/use-language'
import { contentLanguageFor } from '@/lib/content-language'
import { LessonInput, schoolSubjects } from '@/lib/teacher-content'
export function LessonForm({ initial, submit, busy, editing = false }: { initial?: LessonInput; submit: (lesson: LessonInput) => Promise<void>; busy: boolean; editing?: boolean }) {
  const c = useCopy()
  const { language } = useLanguage()
  const [lesson, setLesson] = useState<LessonInput>(initial || {subject:'math',grade:'6',topic:'',language:'en-US',objectives:'',source_material:''})
  const [languageChosen, setLanguageChosen] = useState(false)
  useEffect(() => {
    if (!initial && !languageChosen) setLesson(current => ({...current, language: contentLanguageFor(language)}))
  }, [language, initial, languageChosen])
  const change = (key: keyof LessonInput, value: string) => {
    if (key === 'language') setLanguageChosen(true)
    setLesson(current => ({...current,[key]:value}))
  }
  const onSubmit = async (e: FormEvent) => { e.preventDefault(); await submit(lesson) }
  return <form className="prep-form" onSubmit={onSubmit}>
    <fieldset className="prep-form-fields" disabled={busy}>
    <legend className="sr-only">{c(editing ? 'Lesson details' : 'New lesson')}</legend>
    <div className="prep-form-grid">
      <label>{c('Subject')}<select value={lesson.subject} onChange={e=>change('subject',e.target.value)}>{schoolSubjects.map(s=><option key={s.value} value={s.value}>{c(s.label)}</option>)}</select></label>
      <label>{c('Grade')}<select value={lesson.grade} onChange={e=>change('grade',e.target.value)}><option value="K">{c('Kindergarten')}</option>{Array.from({length:12},(_,i)=><option key={i+1} value={String(i+1)}>{i+1}</option>)}</select></label>
    </div>
    <label>{c('Topic')}<input required maxLength={200} value={lesson.topic} onChange={e=>change('topic',e.target.value)} placeholder={c('e.g. Understanding fractions')} /></label>
    <label>{c('Material language')}<select value={lesson.language} onChange={e=>change('language',e.target.value)}><option value="en-US">{c('English')}</option><option value="ru-RU">{c('Russian')}</option><option value="kk-KZ">{c('Kazakh')}</option></select></label>
    <label>{c('Your learning objectives (optional)')}<textarea rows={3} maxLength={3000} value={lesson.objectives} onChange={e=>change('objectives',e.target.value)} /></label>
    <label>{c('Reference text (optional)')}<textarea rows={4} maxLength={20000} value={lesson.source_material} onChange={e=>change('source_material',e.target.value)} placeholder={c('Paste lesson notes or source material. Resources will follow this text.')} /></label>
    </fieldset>
    <button className="prep-button primary" disabled={busy || !lesson.topic.trim()}>{c(busy?'Saving…':editing?'Save lesson':'Create lesson')}</button>
  </form>
}
