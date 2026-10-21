'use client'

import { createContext, useContext } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { StudentMode, StudentSetup } from './student-workspace'

type StudentWorkspaceState = {
  setup: StudentSetup
  setSetup: Dispatch<SetStateAction<StudentSetup>>
  mode: StudentMode
  selectMode: (mode: StudentMode) => void
  openStory: (id: string | null) => void
  openLibrary: () => void
  reportBusy: (format: 'story' | 'study', busy: boolean) => void
}
export const StudentWorkspaceContext = createContext<StudentWorkspaceState | null>(null)
export function useStudentWorkspace() {
  const state = useContext(StudentWorkspaceContext)
  if (!state) throw new Error('Student tools need the learning workspace.')
  return state
}
