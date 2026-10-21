'use client'

import Link from 'next/link'
import { ThemeToggle } from '@/components/theme-toggle'
import { LanguagePicker } from '@/components/language-picker'
import { FibonacciLogo } from '@/components/fibonacci-mark'

export function AuthLanguageNav() {
  return <header className="auth-language-nav">
    <Link href="/" className="auth-home-link" aria-label="Fibonacci"><FibonacciLogo size={28}/></Link>
    <LanguagePicker /><ThemeToggle />
  </header>
}
