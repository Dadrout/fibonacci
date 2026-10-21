'use client'
import { useCallback, useMemo } from 'react'
import { useAuth } from './use-auth'
import type { TeacherVideoRender } from '@/lib/teacher-content'

type TeacherAPI = {
  <T,>(path: string, method?: string, body?: unknown): Promise<T>
  startVideoRender(lessonId: string, resourceId: string): Promise<TeacherVideoRender>
  latestVideoRender(lessonId: string, resourceId: string): Promise<TeacherVideoRender>
  pollVideoRender(renderId: string): Promise<TeacherVideoRender>
  downloadVideo(renderId: string): Promise<Blob>
}

export function useTeacherAPI() {
  const { getToken } = useAuth()
  const request = useCallback(async <T,>(path: string, method = 'GET', body?: unknown): Promise<T> => {
    const token = await getToken()
    if (!token) throw new Error('Sign in to continue.')
    const response = await fetch(`/api/v1/teacher/${path}`, {
      method, headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type':'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}), cache: 'no-store',
    })
    if (response.status === 204) return undefined as T
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const message = typeof data?.detail === 'string' ? data.detail : response.status === 422 ? 'Check the fields and try again.' : 'Could not complete this request. Please try again.'
      throw new Error(message)
    }
    return data as T
  }, [getToken])

  const downloadVideo = useCallback(async (renderId: string): Promise<Blob> => {
    const token = await getToken()
    if (!token) throw new Error('Sign in to continue.')
    const response = await fetch(`/api/v1/teacher/video-renders/${encodeURIComponent(renderId)}/video`, {
      headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
    })
    if (!response.ok) throw new Error('The topic video could not be downloaded.')
    return response.blob()
  }, [getToken])

  return useMemo(() => Object.assign(request, {
    startVideoRender: (lessonId: string, resourceId: string) => request<TeacherVideoRender>(
      `lessons/${lessonId}/resources/${resourceId}/video-renders`, 'POST', {},
    ),
    latestVideoRender: (lessonId: string, resourceId: string) => request<TeacherVideoRender>(
      `lessons/${lessonId}/resources/${resourceId}/video-renders`,
    ),
    pollVideoRender: (renderId: string) => request<TeacherVideoRender>(
      `video-renders/${renderId}`,
    ),
    downloadVideo,
  }) as TeacherAPI, [request, downloadVideo])
}
