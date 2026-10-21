import type { ResourceKind, VideoResourceContent } from '../lib/teacher-content'

const content: VideoResourceContent = {
  script: {
    title: 'Fractions in a Pizza',
    hook: 'How can one pizza show many fractions?',
    sections: [{ heading: 'Equal parts', summary: 'Fractions name equal parts.' }],
    full_narration: 'Imagine a pizza divided into equal slices.',
    estimated_duration_sec: 180,
  },
  target_duration_sec: 240,
  voice: 'male',
}

export const teacherVideoResourceContract = {
  kind: 'video' as ResourceKind,
  content,
}
