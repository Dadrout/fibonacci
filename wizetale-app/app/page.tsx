import { redirect } from 'next/navigation'

/** Fibonacci opens straight into the Brain. */
export default function HomePage() {
  redirect('/brain')
}
