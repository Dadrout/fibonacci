'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useCopy } from '@/hooks/use-copy'
import { ThemeToggle } from '@/components/theme-toggle'
import { LanguagePicker } from '@/components/language-picker'
import { FibonacciLogo } from '@/components/fibonacci-mark'

export function StudyShell({ children }: { children: React.ReactNode }) {
  const c = useCopy()
  return <main className="prep-shell app-content-page min-h-screen bg-background text-foreground">
    <header className="app-header prep-screen"><Link href="/create" className="app-brand" aria-label={c('Fibonacci home')}><FibonacciLogo size={30}/></Link><nav aria-label={c('Study tools')}><Link href="/create">{c('Create')}</Link><Link href="/study" aria-current="page">{c('Study')}</Link><Link href="/history">{c('Library')}</Link><Link href="/teacher/sources">{c('Sources')}</Link></nav><div className="app-header-tools"><Link className="app-mode-link" href="/teacher">{c('Teacher mode')}</Link><LanguagePicker/><ThemeToggle/></div></header>
    {children}
  </main>
}
