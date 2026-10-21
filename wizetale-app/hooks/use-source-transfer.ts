'use client'
import { useCallback } from 'react'
import { useAuth } from './use-auth'
import type { TeacherSource } from '@/lib/teacher-content'

export function useSourceTransfer(){
 const {getToken}=useAuth()
 const upload=useCallback(async(file:File,language:string):Promise<TeacherSource>=>{
   if(file.size>10*1024*1024)throw Error('Choose a document up to 10 MB.')
   const token=await getToken();if(!token)throw Error('Sign in to continue.')
   const body=new FormData();body.append('file',file);body.append('language',language)
   const response=await fetch('/api/v1/teacher/documents/upload',{method:'POST',headers:{Authorization:`Bearer ${token}`},body,cache:'no-store'})
   const data=await response.json().catch(()=>null)
   if(!response.ok)throw Error(typeof data?.detail==='string'?data.detail:'Source upload could not complete. Try again.')
   return data
 },[getToken])
 const download=useCallback(async(source:TeacherSource)=>{
   const token=await getToken();if(!token)throw Error('Sign in to continue.')
   const response=await fetch(`/api/v1/teacher/documents/${source.id}/original`,{headers:{Authorization:`Bearer ${token}`},cache:'no-store'})
   if(!response.ok)throw Error('Source is not available for download.')
   return {blob:await response.blob(),filename:`${source.title.replace(/[^\p{L}\p{N} ._-]/gu,'_').replace(/\.(pdf|docx|txt)$/i,'')}.${source.kind}`}
 },[getToken])
 return {upload,download}
}
