'use client'

/**
 * React access to the Fibonacci Brain API. Owner: Claude.
 *
 *   const api = useBrainApi()
 *   useBrainEvents((event) => setItems((items) => reduceItems(items, event)))
 *   const session = useBrainSession() // { status, canUse, mode, demo }
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { BrainEvent } from '@/lib/brain-types'
import { brainApiMode, brainDemoEnabled, createBrainApi, getBrainApiMode, type BrainApi, type BrainApiMode } from '@/lib/brain-api'
import { useAuth } from './use-auth'

/** Memoized API client bound to the current Supabase session. */
export function useBrainApi(): BrainApi {
  const { getToken } = useAuth()
  const mode = useBrainApiMode()
  // Keep the client stable across renders; read the latest token getter through a ref.
  const tokenRef = useRef(getToken)
  tokenRef.current = getToken
  const stableGetToken = useCallback(() => tokenRef.current(), [])
  return useMemo(() => createBrainApi(stableGetToken, mode), [stableGetToken, mode])
}

/** Build-time mode during SSR and the first render, then the browser's mode (hydration-safe). */
export function useBrainApiMode(): BrainApiMode {
  const [mode, setMode] = useState<BrainApiMode>(brainApiMode)
  useEffect(() => { setMode(getBrainApiMode()) }, [])
  return mode
}

/**
 * Subscribe to live brain events while mounted. The handler may change between renders.
 * Returns `connected` for a subtle live indicator.
 */
export function useBrainEvents(handler: (event: BrainEvent) => void, enabled = true): { connected: boolean } {
  const api = useBrainApi()
  const session = useBrainSession()
  const handlerRef = useRef(handler)
  handlerRef.current = handler
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!enabled || !session.canUse) return
    return api.subscribe((event) => handlerRef.current(event), { onConnectionChange: setConnected })
  }, [api, enabled, session.canUse])

  return { connected: enabled && session.canUse && connected }
}

export type BrainSessionStatus = 'loading' | 'signed_in' | 'demo' | 'mock' | 'signed_out'

export interface BrainSession {
  status: BrainSessionStatus
  /** True when brain screens can load data (signed in, demo session, or mock mode). */
  canUse: boolean
  mode: BrainApiMode
  /** True when showing the demo student (mock or DEMO_MODE without a Supabase session). */
  demo: boolean
}

export function useBrainSession(): BrainSession {
  const { user, loading } = useAuth()
  const mode = useBrainApiMode()
  return useMemo(() => {
    let status: BrainSessionStatus
    if (mode === 'mock') status = 'mock'
    else if (loading) status = 'loading'
    else if (user) status = 'signed_in'
    else if (brainDemoEnabled) status = 'demo'
    else status = 'signed_out'
    return {
      status,
      canUse: status === 'signed_in' || status === 'demo' || status === 'mock',
      mode,
      demo: status === 'demo' || status === 'mock',
    }
  }, [user, loading, mode])
}
