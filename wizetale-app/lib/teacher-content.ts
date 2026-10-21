export type ResourceKind = 'objectives' | 'lesson_plan' | 'quiz' | 'test_paper' | 'flashcards' | 'worksheet' | 'exit_ticket' | 'homework' | 'presentation' | 'video'
export type Section = { heading: string; body: string }
export type VideoScript = {
  title: string
  hook: string
  sections: { heading: string; summary: string }[]
  full_narration: string
  estimated_duration_sec: number
}
export type VideoResourceContent = {
  script: VideoScript
  target_duration_sec: 180 | 240 | 300
  voice: 'female' | 'male'
}
export type TeacherVideoRender = {
  id: string
  status: 'queued' | 'processing' | 'ready' | 'failed' | 'cancelled'
  progress: number
  stage: string
  message: string
  resource_revision: number
  duration_sec?: number | null
  video_url?: string | null
}
export type Question = { prompt: string; choices: string[]; points: number }
export type PresentationVisual = {
  status: 'pending' | 'processing' | 'ready' | 'failed';
  kind: 'image' | 'diagram';
  alt_text: string;
  caption: string;
  image_url: string | null;
}
export type PresentationSlide = { title: string; key_points: string[]; speaker_notes: string; visual?: PresentationVisual }
export type ResourceContent = {
  title: string; instructions: string; objectives: string[]; sections: Section[];
  questions: Question[]; flashcards: { front: string; back: string }[];
  slides?: PresentationSlide[]; teacher_notes: Section[]; answer_key: { question_number: number; answer: string; explanation: string }[];
  duration_minutes: number;
}
export type LessonInput = {
  subject: string; grade: string; topic: string; language: string; objectives: string; source_material: string;
}
export type Lesson = LessonInput & { id: string; revision: number; source_document_ids?: string[]; updated_at: string }
export type Resource = {
  id: string; lesson_id: string; kind: ResourceKind; status: 'generating' | 'ready' | 'failed';
  content: ResourceContent | VideoResourceContent | null; provenance?: Provenance | null; revision: number; lesson_snapshot: LessonInput; created_at: string;
}
export const resourceKinds: { kind: ResourceKind; label: string; detail: string }[] = [
  {kind:'objectives',label:'Learning objectives',detail:'3–5 objectives'},
  {kind:'lesson_plan',label:'Lesson plan',detail:'45 minutes'},
  {kind:'quiz',label:'Quiz',detail:'10 questions'},
  {kind:'test_paper',label:'Test paper',detail:'20 points + rubric'},
  {kind:'flashcards',label:'Flashcards',detail:'12 cards'},
  {kind:'presentation',label:'Presentation',detail:'8 slides + speaker notes'},
  {kind:'video',label:'Topic video',detail:'Review a narrated story for this grade'},
  {kind:'worksheet',label:'Worksheet / activity',detail:'One printable page'},
  {kind:'exit_ticket',label:'Exit ticket',detail:'3 quick questions'},
  {kind:'homework',label:'Homework',detail:'5 practice tasks'},
]
export const schoolSubjects = [
  {value:'language_arts',label:'Language arts'}, {value:'math',label:'Math'}, {value:'science',label:'Science'},
  {value:'history_social_studies',label:'History / social studies'}, {value:'geography',label:'Geography'},
]
export function printableContent(content: ResourceContent, mode: 'student' | 'teacher'): ResourceContent {
  return mode === 'teacher' ? content : { ...content, teacher_notes: [], answer_key: [] }
}
export function removeQuestion(content: ResourceContent, index: number): ResourceContent {
  return {...content, questions: content.questions.filter((_, i) => i !== index),
    answer_key: content.answer_key.filter(a => a.question_number !== index+1).map(a => ({...a, question_number: a.question_number > index+1 ? a.question_number-1 : a.question_number}))}
}
export function editableResourceContent(content: ResourceContent | VideoResourceContent): ResourceContent | VideoResourceContent {
  if (isVideoResourceContent(content)) {
    return {...content, script: {...content.script, sections: content.script.sections.map(section => ({...section}))}}
  }
  return {...content, slides: content.slides?.map(({visual: _visual, ...slide}) => slide)}
}
export function isVideoResourceContent(content: unknown): content is VideoResourceContent {
  if (!content || typeof content !== 'object') return false
  const value = content as Partial<VideoResourceContent>
  const script = value.script as Partial<VideoScript> | undefined
  return Boolean(
    script && typeof script === 'object'
    && typeof script.title === 'string' && typeof script.hook === 'string'
    && typeof script.full_narration === 'string'
    && typeof script.estimated_duration_sec === 'number'
    && Array.isArray(script.sections)
    && script.sections.every(section => Boolean(section && typeof section.heading === 'string' && typeof section.summary === 'string'))
    && [180, 240, 300].includes(value.target_duration_sec as number)
    && (value.voice === 'female' || value.voice === 'male')
  )
}
export function videoResourceTitle(content: unknown): string {
  return isVideoResourceContent(content) ? content.script.title : ''
}
export function videoGenerationRequest(
  requestId: string,
  targetDurationSec: VideoResourceContent['target_duration_sec'],
  voice: VideoResourceContent['voice'],
) {
  return {kind: 'video' as const, request_id: requestId, target_duration_sec: targetDurationSec, voice}
}
export function currentVideoPlaybackUrl(
  render: TeacherVideoRender | null | undefined,
  revision: number,
): string | null {
  return render?.status === 'ready' && render.resource_revision === revision && render.video_url
    ? render.video_url
    : null
}
export function mergeSlideVisuals(draft: ResourceContent, server: ResourceContent): ResourceContent {
  if (!draft.slides || !server.slides) return draft
  return {...draft, slides: draft.slides.map((slide, index) => {
    const {visual: _visual, ...text} = slide
    const visual = server.slides?.[index]?.visual
    return visual ? {...text, visual} : text
  })}
}

export type TeacherSource = { id:string; title:string; kind:'pdf'|'docx'|'txt'; language:string; status:'uploading'|'processing'|'ready'|'failed'|'deleting'; error_message:string|null; created_at:string; updated_at:string }
export type SourceReference = { passage_id:string; document_id:string|null; title:string; location:string; removed?:boolean }
export type Provenance = { status:'source_based'; sources:SourceReference[] }
