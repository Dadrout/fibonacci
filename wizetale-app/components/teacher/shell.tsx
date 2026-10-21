'use client'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { useCopy } from '@/hooks/use-copy'
import { ThemeToggle } from '@/components/theme-toggle'
import { LanguagePicker } from '@/components/language-picker'
import { FibonacciLogo } from '@/components/fibonacci-mark'
import { useAuth } from '@/hooks/use-auth'
export function TeacherShell({ children, onNavigate }: { children: React.ReactNode; onNavigate?: (event: React.MouseEvent<HTMLAnchorElement>) => void }) {
  const c = useCopy()
  const { user } = useAuth()
  const pathname = usePathname()
  const active = (href: string) => href === '/teacher' ? pathname === href || pathname.startsWith('/teacher/lessons/') : pathname === href || pathname.startsWith(`${href}/`)
  return <main data-workspace-role="teacher" className="prep-shell app-content-page min-h-screen bg-background text-foreground">
    <header className="app-header prep-screen"><Link onClick={onNavigate} href="/teacher" className="app-brand" aria-label={c('Fibonacci home')}><FibonacciLogo size={30}/><span className="prep-brand-label">{c('Teacher')}</span></Link><nav aria-label={c('Teacher prep')}><Link onClick={onNavigate} href="/teacher" aria-current={active('/teacher') ? 'page' : undefined}>{c('Lessons')}</Link><Link onClick={onNavigate} href="/teacher/sources" aria-current={active('/teacher/sources') ? 'page' : undefined}>{c('Sources')}</Link></nav><div className="app-header-tools"><Link onClick={onNavigate} className="app-mode-link" href="/create">{c('Student mode')}</Link><LanguagePicker /><ThemeToggle /><Link onClick={onNavigate} className="app-account" href="/profile" aria-label={c('Account')} title={c('Account')}>{(user?.email?.[0] ?? '·')}</Link></div></header>
    {children}
  </main>
}
