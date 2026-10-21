'use client'

import { useCallback } from 'react'
import { useAuth } from './use-auth'

export function useStudyAPI() {
  const { getToken } = useAuth()
  return useCallback(async <T,>(path: string, method = 'GET', body?: unknown): Promise<T> => {
    const token = await getToken()
    if (!token) throw new Error('Sign in to continue.')
    const response = await fetch(`/api/v1/study-materials${path ? `/${path}` : ''}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: 'no-store',
    })
    if (response.status === 204) return undefined as T
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const message = typeof data?.detail === 'string' ? data.detail : 'Could not complete this request. Please try again.'
      throw new Error(message)
    }
    return data as T
  }, [getToken])
}
