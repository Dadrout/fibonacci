'use client'

import { learnerStorageKey } from '@/lib/learner-storage'

import { useCopy } from '@/hooks/use-copy'
import { LanguagePicker } from '@/components/language-picker'
import { SignInPrompt } from '@/components/sign-in-prompt'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/use-auth'

export default function ProfilePage() {
  const { user, loading } = useAuth()
  const c = useCopy()
  if (loading) return <main className="app-content-page"><p role="status">{c('Loading…')}</p></main>
  if (!user) return <SignInPrompt title="Account" />
  return <ProfileWorkspace key={user.id} />
}

function ProfileWorkspace() {
  const c = useCopy()

  const { user, userProfile, logout, getToken } = useAuth()
  const router = useRouter()
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  const deleteAccount = async () => {
    if (!window.confirm(c("Permanently delete your account, stories, and generated media? This cannot be undone."))) return
    setDeleting(true)
    setDeleteError('')
    try {
      const token = await getToken()
      if (!alive.current) return
      if (!token) throw new Error(c("Your sign-in has expired. Sign in again and retry."))
      const response = await fetch('/api/v1/account', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!alive.current) return
      if (!response.ok) {
        const result = await response.json().catch(() => null)
        throw new Error(result?.detail || c("Account deletion could not be completed. Please try again later."))
      }
      window.localStorage.removeItem(learnerStorageKey('draft', user!.id))
      window.localStorage.removeItem(learnerStorageKey('draft-shelf', user!.id))
      window.localStorage.removeItem(learnerStorageKey('job', user!.id))
      await logout('local')
      router.replace('/')
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : c("Account deletion could not be completed."))
      setDeleting(false)
    }
  }

  const signOut = async () => {
    if (signingOut || deleting) return
    setSigningOut(true)
    setSignOutError('')
    try {
      await logout()
      router.replace('/login')
    } catch {
      setSignOutError(c('Could not sign out. Please try again.'))
      setSigningOut(false)
    }
  }

  const card = 'rounded-[12px] border border-[var(--studio-line)] bg-card p-[21px] sm:p-[34px]'
  const quietLink = 'flex min-h-11 items-center justify-between gap-3 rounded-[6px] px-[13px] py-[8px] text-base font-medium text-[var(--studio-ink)] hover:bg-[var(--workspace-primary-soft)]'

  return (
    <main className="app-content-page min-h-screen bg-[var(--studio-paper)] px-4 py-[34px] text-[var(--studio-ink)] sm:py-[55px]">
      <header className="mx-auto mb-[21px] flex max-w-xl items-center justify-between gap-3">
        <Link href="/" className={`inline-flex min-h-11 items-center text-base font-semibold text-[var(--studio-green)] underline underline-offset-4`}> {c("← Back to Fibonacci")} </Link>
        <LanguagePicker />
      </header>
      <div className="mx-auto grid max-w-xl gap-[21px]">
        <section className={card} aria-labelledby="account-title">
          <h1 id="account-title" className="font-[family-name:var(--font-heading)] text-[34px] font-medium leading-tight tracking-[-0.02em]"> {c("Account")} </h1>
          {user ? (
            <>
              <div className="mt-[21px] border-t border-[var(--studio-line)] pt-[21px]">
                <p className="break-words text-lg font-semibold">{userProfile?.displayName || user.email}</p>
                <p className="mt-[5px] break-all text-base text-muted-foreground">{user.email}</p>
                <p className="mt-[13px] text-sm text-muted-foreground"> {c("Email status:")} <span className="font-semibold text-[var(--studio-ink)]">{userProfile?.emailVerified ? c("Verified") : c("Confirmation pending")}</span></p>
              </div>
              {signOutError && <p role="alert" className="mt-[13px] text-base text-[var(--workspace-danger)]">{c(signOutError)}</p>}
              <button onClick={() => void signOut()} disabled={signingOut || deleting} className={`mt-[21px] min-h-11 rounded-[6px] border border-[var(--studio-line)] bg-transparent px-[21px] py-2 text-base font-semibold text-[var(--studio-ink)] hover:bg-[var(--workspace-primary-soft)] disabled:opacity-60`}> {signingOut ? c('Signing out…') : c("Sign out")} </button>
            </>
          ) : (
            <>
              <p className="mt-4 text-base"> {c("Sign in to view your account.")} </p>
              <Link href="/login" className={`mt-5 inline-flex min-h-11 items-center rounded-[6px] bg-[var(--studio-green)] px-4 py-2 text-base font-semibold text-[var(--studio-on-green)]`}> {c("Sign in")} </Link>
            </>
          )}
        </section>
        {user && (
          <>
            <nav aria-label={c("Your workspaces")} className={card}>
              <h2 className="mb-[8px] text-sm font-semibold uppercase tracking-[0.07em] text-muted-foreground"> {c("Your workspaces")} </h2>
              <ul className="-mx-[13px] grid gap-[3px]">
                <li><Link href="/history" className={quietLink}><span>{c("Library")}</span><span aria-hidden="true" className="text-muted-foreground">→</span></Link></li>
                <li><Link href="/teacher" className={quietLink}><span>{c("Teacher mode")}</span><span aria-hidden="true" className="text-muted-foreground">→</span></Link></li>
              </ul>
            </nav>
            <section aria-labelledby="delete-account-title" className="rounded-[12px] border border-[var(--workspace-danger)] bg-card p-[21px] sm:p-[34px]">
              <p className="text-sm font-semibold uppercase tracking-[0.07em] text-[var(--workspace-danger)]"> {c("Danger zone")} </p>
              <h2 id="delete-account-title" className="mt-[8px] font-[family-name:var(--font-heading)] text-xl font-medium"> {c("Delete account")} </h2>
              <p className="mt-[8px] text-base leading-relaxed text-muted-foreground"> {c("Permanently remove your account, saved stories, and generated media.")} </p>
              {deleteError && <p role="alert" className="mt-3 text-base text-[var(--workspace-danger)]">{c(deleteError)}</p>}
              <button
                onClick={() => void deleteAccount()}
                disabled={deleting || signingOut}
                className={`mt-[21px] min-h-11 rounded-[6px] border border-[var(--workspace-danger)] bg-transparent px-[21px] py-2 text-base font-semibold text-[var(--workspace-danger)] hover:bg-[var(--workspace-danger-soft)] disabled:opacity-60`}
              >
                {deleting ? c("Deleting account…") : c("Delete my account")}
              </button>
            </section>
          </>
        )}
      </div>
    </main>
  )
}
