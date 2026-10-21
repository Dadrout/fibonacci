'use client'

import { StudioIcon } from '@/components/studio-icon'
import { useCopy } from '@/hooks/use-copy'
import { AuthLanguageNav } from '@/components/auth-language-nav'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/hooks/use-auth'

export default function VerifyEmailPage() {
  const c = useCopy()

  const { user, resendSignupConfirmation } = useAuth()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    const query = new URLSearchParams(window.location.search)
    setEmail(query.get('email') || user?.email || '')
  }, [user])

  const resend = async () => {
    try {
      setSending(true)
      setError('')
      await resendSignupConfirmation(email)
      setSent(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : c("Could not resend confirmation email."))
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="auth-page">
      <AuthLanguageNav />
      <section className="auth-card p-[34px] text-center">
        <div className="flex justify-center text-primary"><StudioIcon name="mail" style={{width:36,height:36}}/></div>
        <h1 className="mt-4 text-3xl font-bold"> {c("Check your email")} </h1>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground"> {c("Follow the confirmation link we sent")} {email ? `: ${email}` : ''} {c(". Once confirmed, you can sign in and start learning.")} </p>
        {email && (
          <button
            disabled={sending || sent}
            onClick={() => void resend()}
            className="mt-6 min-h-11 w-full rounded-[6px] border border-input px-4 py-3 text-base font-semibold hover:bg-muted disabled:opacity-50"
          >
            {sending ? c("Sending…") : sent ? c("Confirmation email sent") : c("Resend confirmation email")}
          </button>
        )}
        {error && <p role="alert" className="mt-3 text-base text-destructive">{c(error)}</p>}
        <Link className="mt-5 inline-block text-base font-semibold text-primary underline" href="/login"> {c("Go to sign in")} </Link>
      </section>
    </main>
  )
}
