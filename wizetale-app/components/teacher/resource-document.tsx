import Image from 'next/image'
import { printableContent, ResourceContent, ResourceKind } from '@/lib/teacher-content'
import { SourceReferences } from './source-references'
import { Provenance } from '@/lib/teacher-content'
import { copyText } from '@/lib/copy'
import { PresentationVisualFigure } from '@/components/presentation-visual'
import { FibonacciMark } from '@/components/fibonacci-mark'

export function ResourceDocument({content,kind,mode,language,provenance}: {content:ResourceContent;kind:ResourceKind;mode:'student'|'teacher';language:string;provenance?:Provenance|null}) {
  const printed=printableContent(content,mode)
  const locale=language==='kk-KZ'?'kk':language==='ru-RU'?'ru':'en'
  const c=(text:string)=>copyText(text,locale)
  return <article className="prep-document" lang={locale}>
    <div className="prep-document-header"><span className="prep-document-brand"><FibonacciMark size={30}/><strong>Fibonacci</strong></span><span>{c(mode==='student'?'Student copy':'Teacher copy')}</span></div>
    <h1>{printed.title}</h1>
    {kind==='lesson_plan' && <p>{printed.duration_minutes} {locale==='ru'?'минут':locale==='kk'?'минут':'minutes'}</p>}
    {printed.instructions && <p className="prep-document-instructions">{printed.instructions}</p>}
    {printed.objectives.length>0 && <section><h2>{c('Objectives')}</h2><ul>{printed.objectives.map((objective,i)=><li key={i}>{objective}</li>)}</ul></section>}
    {printed.sections.map((section,index)=><section key={index}><h2>{section.heading}</h2><p>{section.body}</p></section>)}
    {printed.questions.length>0 && <section><h2>{c('Questions')}</h2><ol className="prep-print-questions">{printed.questions.map((question,index)=><li key={index}><p><strong>{question.prompt}</strong>{kind==='test_paper' && <span> ({question.points} {c('Points').toLowerCase()})</span>}</p>{question.choices.length>0?<ol type="a">{question.choices.map((choice,i)=><li key={i}>{choice}</li>)}</ol>:<div className="prep-answer-space" aria-hidden="true" />}</li>)}</ol></section>}
    {printed.flashcards.length>0 && <section><h2>{c('Flashcards')}</h2><div className="prep-print-flashcards">{printed.flashcards.map((card,index)=><div key={index} className="prep-print-card"><p><strong>{card.front}</strong></p><hr/><p>{card.back}</p></div>)}</div></section>}
    {kind==='presentation'&&<div className="prep-presentation-pdf">{(printed.slides||[]).map((slide,index)=><section key={index} className="prep-presentation-pdf-slide"><p className="prep-document-kicker">{c('Slide')} {index+1}</p><h2>{slide.title}</h2><PresentationVisualFigure visual={slide.visual}/><ul>{slide.key_points.map((point,pointIndex)=><li key={pointIndex}>{point}</li>)}</ul>{mode==='teacher'&&<aside><h3>{c('Speaker notes')}</h3><p>{slide.speaker_notes}</p></aside>}</section>)}</div>}
    {printed.answer_key.length>0 && <section className="prep-print-key"><h2>{c('Answer key')}</h2>{printed.answer_key.map(answer=><div key={answer.question_number}><p><strong>{answer.question_number}. {answer.answer}</strong></p>{answer.explanation&&<p>{answer.explanation}</p>}</div>)}</section>}
    {printed.teacher_notes.map((section,index)=><section key={index}><h2>{section.heading}</h2><p>{section.body}</p></section>)}
    {mode==='teacher'&&<SourceReferences provenance={provenance} language={language}/>}
  </article>
}
