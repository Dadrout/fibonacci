'use client'

/* TEMPORARY STUB — replaced by the Exam mode + mistake → moment implementation (board rows A5, A6). */
import type { BrainApi } from '@/lib/brain-api'
import type { BrainGraph } from '@/lib/brain-types'

export type BrainExamProps = {
  api: BrainApi
  graph: BrainGraph | null
  /** Course chosen from the course view's "Exam in N days" button (null = let the student choose). */
  courseId: string | null
  presentation: boolean
}

export function BrainExam(_props: BrainExamProps) {
  return <section className="brain-coming-soon"><p>Exam</p></section>
}
