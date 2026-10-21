'use client'

import { useCopy } from '@/hooks/use-copy'
import { AuthLanguageNav } from '@/components/auth-language-nav'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'

export default function AuthCallbackPage(){
  const c = useCopy()

  const router=useRouter();const [message,setMessage]=useState(c("Finishing sign in…"))
  useEffect(()=>{let active=true;void(async()=>{if(!supabase){setMessage(c("Sign in is not configured."));return}const {data,error}=await supabase.auth.getSession();if(error||!data.session){setMessage(c("This sign-in link could not be used. Please request a new one."));return}const requested=new URLSearchParams(window.location.search).get('next')||'/create';const allowed=new Set(['/','/create','/teacher','/verify-email','/reset-password/update']);if(active)router.replace(allowed.has(requested)?requested:'/create')} )();return()=>{active=false}},[router])
  return <main className="auth-page"><AuthLanguageNav /><p role="status">{c(message)}</p></main>
}
