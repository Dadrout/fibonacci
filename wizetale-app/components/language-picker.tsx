'use client'
import { Globe2 } from 'lucide-react'
import { useLanguage } from '@/hooks/use-language'
import { useCopy } from '@/hooks/use-copy'
import type { Language } from '@/lib/i18n'
export function LanguagePicker({ className = '' }: { className?: string }) {
  const {language,setLanguage}=useLanguage(), c=useCopy()
  return <label className={`language-picker ${className}`.trim()}><Globe2 size={17} aria-hidden="true"/><span className="sr-only">{c('Language')}</span><select aria-label={c('Language')} value={language} onChange={event=>setLanguage(event.target.value as Language)}><option value="en">English</option><option value="ru">Русский</option><option value="kk">Қазақша</option></select></label>
}
