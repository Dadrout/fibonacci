import StudentWorkspace from '@/app/create/student-workspace-client'
import { resolveStudentEntry } from '@/lib/student-workspace'

export default async function StudyPage({ searchParams }: { searchParams: Promise<{ mode?: string; material?: string }> }) {
  const search = await searchParams
  return <StudentWorkspace initialEntry={resolveStudentEntry({ ...search, mode: search.mode || 'flashcards' })} />
}
