import type { Metadata } from 'next'
import { FibonacciLanding } from '@/components/landing/fibonacci-landing'

export const metadata: Metadata = {
  title: 'Fibonacci — Stop organizing. Start learning.',
  description: 'Your lecture photos, links and PDFs, filed into courses. Connect ideas and prepare for exams with citations to your own sources.',
}

export default function HomePage() {
  return <FibonacciLanding />
}
