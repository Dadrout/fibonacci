'use client'

import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import type { User, Session } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'
import { trackEvent, trackConversion, trackFunnelStep } from '@/lib/analytics'

export interface UserProfile {
  uid: string
  email: string
  username: string
  displayName?: string
  photoURL?: string
  emailVerified: boolean
  bio?: string
  createdAt?: string
}

interface AuthContextType {
  user: User | null
  userProfile: UserProfile | null
  loading: boolean
  getToken: () => Promise<string | null>
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, username: string, displayName?: string, role?: 'learner' | 'teacher') => Promise<void>
  logout: (scope?: 'global' | 'local') => Promise<void>
  signInWithGoogle: (next?: '/create' | '/teacher') => Promise<void>
  sendVerificationEmail: () => Promise<void>
  resendSignupConfirmation: (email: string) => Promise<void>
  resetPassword: (email: string) => Promise<void>
  refreshUserProfile: () => Promise<void>
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}

const toProfile = (user: User | null): UserProfile | null => {
  if (!user) return null
  const metadata = user.user_metadata || {}
  return {
    uid: user.id,
    email: user.email || '',
    username: metadata.username || user.email?.split('@')[0] || 'learner',
    displayName: metadata.display_name || metadata.full_name || user.email?.split('@')[0],
    photoURL: metadata.avatar_url,
    emailVerified: Boolean(user.email_confirmed_at),
    createdAt: user.created_at,
  }
}

const requireClient = () => {
  if (!supabase) throw new Error('Supabase Auth is not configured. Set the Supabase URL and publishable key.')
  return supabase
}

export const useAuthState = () => {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const userProfile = toProfile(user)

  useEffect(() => {
    const previewMode = process.env.NEXT_PUBLIC_ENABLE_DASHBOARD_PREVIEW === 'true'
      && window.location.pathname === '/create'
      && new URLSearchParams(window.location.search).get('preview') === '1'
    if (previewMode) {
      setUser(null)
      setLoading(false)
      return
    }

    if (!supabase) {
      setLoading(false)
      return
    }

    let alive = true
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (alive) {
        setUser(session?.user ?? null)
        setLoading(false)
      }
    })
    supabase.auth.getSession().then(({ data, error }) => {
      if (!alive) return
      if (error) console.error('Could not restore Supabase session:', error.message)
      setUser(data.session?.user ?? null)
      setLoading(false)
    })
    return () => {
      alive = false
      subscription.unsubscribe()
    }
  }, [])

  const signIn = async (email: string, password: string) => {
    const client = requireClient()
    setLoading(true)
    const { error } = await client.auth.signInWithPassword({ email, password })
    setLoading(false)
    if (error) throw error
    trackEvent('login_email')
    trackConversion('user_logged_in', 1)
  }

  const signUp = async (email: string, password: string, username: string, displayName?: string, role: 'learner' | 'teacher' = 'learner') => {
    const client = requireClient()
    setLoading(true)
    try {
      const { error } = await client.auth.signUp({
        email,
        password,
        options: {
          data: { username, display_name: displayName || username, learning_role: role },
          emailRedirectTo: typeof window === 'undefined' ? undefined : `${window.location.origin}/auth/callback?next=${role === 'teacher' ? '/teacher' : '/create'}`,
        },
      })
      if (error) throw error
      trackEvent('sign_up_email')
      trackConversion('user_registered', 1)
      trackFunnelStep('registration_completed', 2, 2)
    } finally {
      setLoading(false)
    }
  }

  const signInWithGoogle = async (next: '/create' | '/teacher' = '/create') => {
    if (typeof window !== 'undefined') {
      if (next === '/teacher') window.sessionStorage.setItem('talespark-teacher-intent', '1')
      else window.sessionStorage.removeItem('talespark-teacher-intent')
    }
    const client = requireClient()
    setLoading(true)
    const { error } = await client.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: typeof window === 'undefined' ? undefined : `${window.location.origin}/auth/callback?next=${next}`,
      },
    })
    if (error) {
      setLoading(false)
      throw error
    }
  }

  const getToken = useCallback(async (): Promise<string | null> => {
    if (!supabase) return null
    const { data, error } = await supabase.auth.getSession()
    if (error) throw error
    if (!user || data.session?.user.id !== user.id) return null
    let session: Session | null = data.session
    if (session?.expires_at && session.expires_at <= Math.floor(Date.now() / 1000) + 60) {
      const refreshed = await supabase.auth.refreshSession()
      if (refreshed.error) throw new Error('Your sign-in session has expired. Please sign in again.')
      session = refreshed.data.session
      if (!session || session.user.id !== user.id) return null
    }
    return session?.access_token ?? null
  }, [user?.id])

  const logout = async (scope: 'global' | 'local' = 'global') => {
    const client = requireClient()
    setLoading(true)
    try {
      const { error } = await client.auth.signOut({ scope })
      if (error) throw error
      setUser(null)
      trackEvent('logout')
    } finally {
      setLoading(false)
    }
  }

  const sendVerificationEmail = async () => {
    if (!user?.email) throw new Error('Sign in first to resend verification email.')
    return resendSignupConfirmation(user.email)
  }

  const resendSignupConfirmation = async (email: string) => {
    const { error } = await requireClient().auth.resend({
      type: 'signup',
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=/create` },
    })
    if (error) throw error
  }

  const resetPassword = async (email: string) => {
    const { error } = await requireClient().auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/callback?next=/reset-password/update`,
    })
    if (error) throw error
    trackEvent('password_reset_requested')
  }

  const refreshUserProfile = useCallback(async () => {
    if (!supabase) return
    const { data, error } = await supabase.auth.getUser()
    if (error) throw error
    setUser(data.user)
  }, [])

  return {
    user,
    userProfile,
    loading,
    signIn,
    signUp,
    logout,
    getToken,
    signInWithGoogle,
    sendVerificationEmail,
    resendSignupConfirmation,
    resetPassword,
    refreshUserProfile,
  }
}
