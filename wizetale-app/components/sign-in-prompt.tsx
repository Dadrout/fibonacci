'use client'

import Image from 'next/image'
import Link from 'next/link'
import { BookOpen } from 'lucide-react'
import { AuthLanguageNav } from '@/components/auth-language-nav'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useCopy } from '@/hooks/use-copy'
import { FibonacciMark } from '@/components/fibonacci-mark'

type SignInPromptProps = {
  title: string
  message?: string
  teacher?: boolean
}

export function SignInPrompt({ title, message, teacher = false }: SignInPromptProps) {
  const c = useCopy()

  if (teacher) {
    return (
      <div className="prep-home prep-screen">
        <section className="prep-card prep-sign-in-prompt" aria-labelledby="sign-in-prompt-title">
          <BookOpen size={30} aria-hidden="true" />
          <p className="prep-eyebrow">{c('Teacher prep')}</p>
          <h1 id="sign-in-prompt-title">{c(title)}</h1>
          {message && <p>{c(message)}</p>}
          <Link className="prep-button primary" href="/login">{c('Sign in')}</Link>
        </section>
      </div>
    )
  }

  return (
    <main className="auth-page app-content-page">
      <AuthLanguageNav />
      <Card className="auth-card">
        <CardHeader className="space-y-1 text-center">
          <div className="mb-4 flex justify-center">
            <FibonacciMark size={48} label={c("Fibonacci Logo")}/>
          </div>
          <CardTitle className="text-2xl font-bold">{c(title)}</CardTitle>
          <CardDescription>{c(message ?? 'Sign in to continue.')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="w-full">
            <Link href="/login">{c('Sign in')}</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}
