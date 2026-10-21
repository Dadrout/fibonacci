'use client'

import { useCopy } from '@/hooks/use-copy'
import { AuthLanguageNav } from '@/components/auth-language-nav'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'

export default function UpdatePasswordPage() {
  const c = useCopy()

  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!supabase) {
      setMessage(c("Sign in is not configured."))
      return
    }
    setBusy(true)
    const { error } = await supabase.auth.updateUser({ password })
    setMessage(error?.message || c("Password updated. You can now sign in."))
    setBusy(false)
  }

  return (
    <main className="auth-page">
      <AuthLanguageNav />
      <form onSubmit={submit} className="auth-card p-[34px]">
        <h1 className="text-3xl font-bold leading-tight"> {c("Choose a new password")} </h1>
        <label className="mt-5 block text-base font-semibold"> {c("New password")} <input
            required
            minLength={8}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-2 h-11 w-full rounded-[6px] border border-input bg-background px-3 text-base text-foreground"
          />
        </label>
        <button
          disabled={busy}
          className="mt-5 min-h-11 w-full rounded-[6px] bg-primary px-4 py-3 text-base font-bold text-primary-foreground disabled:opacity-50"
        >
          {busy ? c("Updating…") : c("Update password")}
        </button>
        {message && <p role="status" className="mt-4 text-base text-muted-foreground">{c(message)}</p>}
        <Link href="/login" className="mt-4 inline-block text-base font-semibold text-primary underline"> {c("Return to sign in")} </Link>
      </form>
    </main>
  )
}
