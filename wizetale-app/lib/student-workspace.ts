import type { PresentationSlide } from './teacher-content'

export type StudentMode = 'story' | 'flashcards' | 'quiz' | 'presentation'
export type StudentSetup = { subject: string; topic: string; language: string; source_text?: string }
export type StudentEntry = { mode: StudentMode; materialId: string | null; storyId: string | null; library: boolean }
export const studentSubjects = [
  { value: 'history_social_studies', label: 'History / social studies' },
  { value: 'geography', label: 'Geography' },
  { value: 'philosophy', label: 'Philosophy' },
  { value: 'science', label: 'Science' },
  { value: 'math', label: 'Math' },
  { value: 'language_arts', label: 'Language arts' },
] as const
export type StudentSlideVisual = { status: 'pending' | 'processing' | 'ready' | 'failed'; kind: 'image' | 'diagram'; alt_text: string; caption: string; image_url: string | null }
export type StudentPresentationSlide = PresentationSlide & { visual?: StudentSlideVisual }

export function resolveStudentEntry(search: { mode?: string; material?: string; story?: string; library?: string }): StudentEntry {
  const mode = ['flashcards','quiz','presentation'].includes(search.mode || '') ? search.mode as StudentMode : 'story'
  return { mode: search.story ? 'story' : mode, materialId: search.story ? null : search.material || null, storyId: search.story || null, library: search.library === '1' }
}
export function normalizeStudentSubject(value: string) {
  if (value === 'history' || value === 'history_social_studies') return 'history_social_studies'
  if (value === 'literature' || value === 'language_arts') return 'language_arts'
  return value
}
export function studentGenerationContext(setup: StudentSetup, grade: string) {
  const subject = normalizeStudentSubject(setup.subject)
  if (!studentSubjects.some(entry => entry.value === subject)) throw new Error('Choose a subject.')
  const { source_text, ...rest } = setup
  const source = (source_text ?? '').trim()
  return { ...rest, subject, topic: setup.topic.trim(), grade, ...(source ? { source_text: source } : {}) }
}
export function mergeSlideVisuals<T extends { visual?: unknown }>(edited: T[], refreshed: T[]): T[] {
  return edited.map((slide, index) => {
    const updated = { ...slide }
    if (refreshed[index]?.visual) updated.visual = refreshed[index].visual
    else delete updated.visual
    return updated
  })
}
