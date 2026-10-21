import StudentWorkspace from '@/app/create/student-workspace-client'

export default async function StoryPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params
  return <StudentWorkspace initialEntry={{ mode: 'story', storyId: taskId, materialId: null, library: false }} />
}
