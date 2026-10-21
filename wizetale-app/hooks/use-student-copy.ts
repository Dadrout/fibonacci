'use client'
import { useCallback } from 'react'
import { studentCopyText } from '@/lib/student-copy'
import { useLanguage } from './use-language'
export function useStudentCopy() {
  const { language }=useLanguage()
  return useCallback((text:string)=>studentCopyText(text,language),[language])
}
