import StudentWorkspace from '@/app/create/student-workspace-client'

export default function HistoryPage() {
  return <StudentWorkspace initialEntry={{ mode: 'story', materialId: null, storyId: null, library: true }} />
}
