import StudentWorkspace from './student-workspace-client'
import { resolveStudentEntry } from '@/lib/student-workspace'

export default async function CreatePage({ searchParams }: { searchParams: Promise<{ preview?: string; mode?: string; material?: string; story?: string; library?: string }> }) {
  const search = await searchParams
  return <StudentWorkspace previewRequested={search.preview === '1'} initialEntry={resolveStudentEntry(search)} />
}
