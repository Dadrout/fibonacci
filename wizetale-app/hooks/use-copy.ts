'use client'
import { useCallback } from 'react'
import { copyText } from '@/lib/copy'
import { useLanguage } from './use-language'
export function useCopy() {
  const { language } = useLanguage()
  return useCallback((text: string) => copyText(text, language), [language])
}
