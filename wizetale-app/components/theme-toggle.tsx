'use client'
import { useEffect, useState } from 'react'
import { useTheme } from 'next-themes'
import { useCopy } from '@/hooks/use-copy'
import { StudioIcon } from './studio-icon'
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const c = useCopy()
  useEffect(() => setMounted(true), [])
  const dark = mounted && resolvedTheme === 'dark'
  return <button type="button" className="studio-theme-toggle" disabled={!mounted} aria-label={c(dark ? 'Use light theme' : 'Use dark theme')} title={c(dark ? 'Use light theme' : 'Use dark theme')} onClick={() => setTheme(dark ? 'light' : 'dark')}><StudioIcon name={dark ? 'sun' : 'moon'}/></button>
}
