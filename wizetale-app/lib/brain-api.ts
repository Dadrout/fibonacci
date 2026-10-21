/**
 * Typed client for the Fibonacci Brain API. Owner: Claude.
 *
 * - `NEXT_PUBLIC_BRAIN_API=mock` serves lib/brain-mocks.ts (no backend needed),
 *   including the live event choreography. Anything else hits `/api/v1/brain/*`.
 * - `NEXT_PUBLIC_BRAIN_DEMO=1`: when there is no Supabase session, requests carry
 *   `X-Brain-Demo: 1` and the Next proxy signs them in as the demo student
 *   (only works when the API runs with DEMO_MODE=true).
 * - Errors are thrown as `BrainApiError` with a stable `code` for localized copy.
 *
 * Components should use the hooks in hooks/use-brain-api.ts.
 */
import type {
  BrainCourse,
  BrainErrorCode,
  BrainEvent,
  BrainGraph,
  BrainItem,
  BrainItemDetail,
  BrainLanguage,
  BrainOverview,
  CaptureChannel,
  ConceptDetail,
  CourseDetail,
  ExamPlanRequest,
  GapAlert,
  ItemPage,
  ItemStatus,
  QuizAnswerResult,
  QuizOptionId,
  RefileRequest,
  RefileResult,
  SearchResponse,
  StudyPlan,
  TelegramLinkCode,
  TelegramStatus,
  UUID,
} from './brain-types'
import { getMockBrain } from './brain-mocks'

export type BrainApiMode = 'mock' | 'live'

export const brainApiMode: BrainApiMode = process.env.NEXT_PUBLIC_BRAIN_API === 'mock' ? 'mock' : 'live'
export const brainDemoEnabled = process.env.NEXT_PUBLIC_BRAIN_DEMO === '1'

/** Files accepted by capture, for the picker's `accept` attribute. */
export const BRAIN_ACCEPT = 'image/*,application/pdf,.pdf,.docx,.txt,text/plain,audio/*,.m4a,.mp3,.ogg,.oga,.opus,.wav,.webm'
export const BRAIN_MAX_UPLOAD_BYTES = 20 * 1024 * 1024

export class BrainApiError extends Error {
  readonly status: number
  readonly code: BrainErrorCode
  readonly retryAfterSeconds: number | null
  constructor(status: number, code: BrainErrorCode, message: string, retryAfterSeconds: number | null = null) {
    super(message)
    this.name = 'BrainApiError'
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
  }
}

export type TokenGetter = () => Promise<string | null>

export interface CaptureFileOptions {
  channel?: Extract<CaptureChannel, 'web_drop' | 'web_picker'>
  /** 0..1 upload progress (live mode only; mock jumps to 1). */
  onUploadProgress?: (fraction: number) => void
  signal?: AbortSignal
}

export interface SubscribeOptions {
  /** Called when the stream (re)connects or drops; use for a subtle "live" indicator. */
  onConnectionChange?: (connected: boolean) => void
}

export interface BrainApi {
  readonly mode: BrainApiMode
  overview(): Promise<BrainOverview>
  graph(): Promise<BrainGraph>
  items(params?: { status?: ItemStatus; course_id?: UUID; limit?: number; cursor?: string }): Promise<ItemPage>
  item(id: UUID): Promise<BrainItemDetail>
  deleteItem(id: UUID): Promise<void>
  retryItem(id: UUID): Promise<BrainItem>
  refile(id: UUID, request: RefileRequest): Promise<RefileResult>
  captureLink(url: string, channel?: Extract<CaptureChannel, 'web_drop' | 'web_paste' | 'web_picker'>): Promise<BrainItem>
  captureText(text: string, title?: string, channel?: Extract<CaptureChannel, 'web_drop' | 'web_paste' | 'web_picker'>): Promise<BrainItem>
  captureFile(file: File, options?: CaptureFileOptions): Promise<BrainItem>
  concept(id: UUID): Promise<ConceptDetail>
  course(id: UUID): Promise<CourseDetail>
  renameCourse(id: UUID, title: string): Promise<BrainCourse>
  gaps(): Promise<GapAlert[]>
  search(query: string, limit?: number): Promise<SearchResponse>
  createExamPlan(courseId: UUID, request: { days: number; language: BrainLanguage; exam_date?: string; request_id?: UUID }): Promise<StudyPlan>
  plan(id: UUID): Promise<StudyPlan>
  coursePlans(courseId: UUID): Promise<StudyPlan[]>
  answerQuiz(planId: UUID, questionId: string, optionId: QuizOptionId): Promise<QuizAnswerResult>
  telegramStatus(): Promise<TelegramStatus>
  telegramLinkCode(): Promise<TelegramLinkCode>
  telegramUnlink(): Promise<void>
  /** Live events. Returns an unsubscribe function. One shared connection serves all listeners. */
  subscribe(listener: (event: BrainEvent) => void, options?: SubscribeOptions): () => void
  /** Mock mode only: plays the hero demo (three Telegram captures). No-op in live mode. */
  simulateHeroDemo(): Promise<void>
}

const ERROR_CODES: BrainErrorCode[] = ['unauthorized', 'not_found', 'invalid_input', 'unsupported_type', 'too_large', 'rate_limited', 'conflict', 'not_enough_material', 'telegram_not_configured', 'unavailable', 'internal']

function codeForStatus(status: number): BrainErrorCode {
  if (status === 401 || status === 403) return 'unauthorized'
  if (status === 404) return 'not_found'
  if (status === 409) return 'conflict'
  if (status === 413) return 'too_large'
  if (status === 415) return 'unsupported_type'
  if (status === 422 || status === 400) return 'invalid_input'
  if (status === 429) return 'rate_limited'
  if (status === 502 || status === 503 || status === 504) return 'unavailable'
  return 'internal'
}

async function toError(response: Response): Promise<BrainApiError> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown; code?: unknown } | null
  const code = typeof body?.code === 'string' && (ERROR_CODES as string[]).includes(body.code) ? (body.code as BrainErrorCode) : codeForStatus(response.status)
  const detail = typeof body?.detail === 'string' ? body.detail : 'The request could not be completed.'
  const retry = Number(response.headers.get('Retry-After'))
  return new BrainApiError(response.status, code, detail, Number.isFinite(retry) && retry > 0 ? retry : null)
}

function newRequestId(): UUID {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  // RFC 4122 v4 fallback for very old browsers.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    return (ch === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

// ---------------------------------------------------------------------------
// Live client
// ---------------------------------------------------------------------------

async function authHeaders(getToken: TokenGetter): Promise<Record<string, string>> {
  const token = await getToken().catch(() => null)
  if (token) return { Authorization: `Bearer ${token}` }
  if (brainDemoEnabled) return { 'X-Brain-Demo': '1' }
  throw new BrainApiError(401, 'unauthorized', 'Sign in to continue.')
}

function createLiveApi(getToken: TokenGetter): BrainApi {
  const request = async <T,>(path: string, init: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> => {
    const headers = await authHeaders(getToken)
    let response: Response
    try {
      response = await fetch(`/api/v1/brain/${path}`, {
        method: init.method ?? 'GET',
        headers: { ...headers, ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
        cache: 'no-store',
        signal: init.signal,
      })
    } catch (error) {
      if ((error as Error)?.name === 'AbortError') throw error
      throw new BrainApiError(0, 'unavailable', 'Network request failed.')
    }
    if (!response.ok) throw await toError(response)
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  }

  const capture = (body: Record<string, unknown>) =>
    request<BrainItem>('captures', { method: 'POST', body: { ...body, request_id: newRequestId() } })

  const captureFile = async (file: File, options: CaptureFileOptions = {}): Promise<BrainItem> => {
    if (file.size > BRAIN_MAX_UPLOAD_BYTES) throw new BrainApiError(413, 'too_large', 'Choose a file up to 20 MB.')
    if (file.size === 0) throw new BrainApiError(422, 'invalid_input', 'This file is empty.')
    const headers = await authHeaders(getToken)
    const form = new FormData()
    form.append('file', file, file.name)
    form.append('channel', options.channel ?? 'web_drop')
    form.append('request_id', newRequestId())
    // XHR, because fetch cannot report upload progress.
    return new Promise<BrainItem>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/v1/brain/captures/upload')
      Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value))
      xhr.responseType = 'text'
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) options.onUploadProgress?.(event.loaded / event.total)
      }
      xhr.onload = () => {
        const response = new Response(xhr.responseText || null, {
          status: xhr.status || 503,
          headers: { 'Content-Type': 'application/json', 'Retry-After': xhr.getResponseHeader('Retry-After') ?? '' },
        })
        if (response.ok) {
          options.onUploadProgress?.(1)
          response.json().then(resolve, () => reject(new BrainApiError(502, 'internal', 'Invalid server response.')))
        } else {
          toError(response).then(reject, reject)
        }
      }
      xhr.onerror = () => reject(new BrainApiError(0, 'unavailable', 'Upload failed. Check the connection and try again.'))
      xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))
      options.signal?.addEventListener('abort', () => xhr.abort(), { once: true })
      xhr.send(form)
    })
  }

  return {
    mode: 'live',
    overview: () => request('overview'),
    graph: () => request('graph'),
    items: (params = {}) => {
      const query = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== null) query.set(key, String(value)) })
      return request(`items${query.size ? `?${query}` : ''}`)
    },
    item: (id) => request(`items/${encodeURIComponent(id)}`),
    deleteItem: (id) => request(`items/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    retryItem: (id) => request(`items/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
    refile: (id, body) => request(`items/${encodeURIComponent(id)}/refile`, { method: 'POST', body }),
    captureLink: (url, channel = 'web_paste') => capture({ url, channel }),
    captureText: (text, title, channel = 'web_paste') => capture({ text, ...(title ? { title } : {}), channel }),
    captureFile,
    concept: (id) => request(`concepts/${encodeURIComponent(id)}`),
    course: (id) => request(`courses/${encodeURIComponent(id)}`),
    renameCourse: (id, title) => request(`courses/${encodeURIComponent(id)}`, { method: 'PATCH', body: { title } }),
    gaps: () => request('gaps'),
    search: (query, limit = 20) => request(`search?${new URLSearchParams({ q: query, limit: String(limit) })}`),
    createExamPlan: (courseId, body) =>
      request(`courses/${encodeURIComponent(courseId)}/exam-plan`, { method: 'POST', body: { ...body, request_id: body.request_id ?? newRequestId() } satisfies ExamPlanRequest }),
    plan: (id) => request(`plans/${encodeURIComponent(id)}`),
    coursePlans: (courseId) => request(`courses/${encodeURIComponent(courseId)}/plans`),
    answerQuiz: (planId, questionId, optionId) =>
      request(`plans/${encodeURIComponent(planId)}/quiz/${encodeURIComponent(questionId)}/answer`, { method: 'POST', body: { option_id: optionId } }),
    telegramStatus: () => request('telegram/status'),
    telegramLinkCode: () => request('telegram/link-code', { method: 'POST' }),
    telegramUnlink: () => request('telegram/link', { method: 'DELETE' }),
    subscribe: (listener, options) => liveHub.add(getToken, listener, options),
    simulateHeroDemo: async () => undefined,
  }
}

// ---------------------------------------------------------------------------
// Live events: one fetch-based SSE connection shared by all listeners
// (EventSource cannot send an Authorization header).
// ---------------------------------------------------------------------------

type HubListener = { listener: (event: BrainEvent) => void; options?: SubscribeOptions }

class LiveEventHub {
  private listeners = new Set<HubListener>()
  private getToken: TokenGetter | null = null
  private controller: AbortController | null = null
  private lastEventId: string | null = null
  private connected = false

  add(getToken: TokenGetter, listener: (event: BrainEvent) => void, options?: SubscribeOptions) {
    const entry: HubListener = { listener, options }
    this.getToken = getToken
    this.listeners.add(entry)
    if (!this.controller) this.start()
    else options?.onConnectionChange?.(this.connected)
    return () => {
      this.listeners.delete(entry)
      if (this.listeners.size === 0) this.stop()
    }
  }

  private setConnected(value: boolean) {
    if (this.connected === value) return
    this.connected = value
    this.listeners.forEach((entry) => entry.options?.onConnectionChange?.(value))
  }

  private stop() {
    this.controller?.abort()
    this.controller = null
    this.setConnected(false)
  }

  private start() {
    const controller = new AbortController()
    this.controller = controller
    void this.run(controller.signal)
  }

  private async run(signal: AbortSignal) {
    let backoff = 1000
    while (!signal.aborted) {
      try {
        const headers = await authHeaders(this.getToken ?? (async () => null))
        const response = await fetch('/api/v1/brain/events', {
          headers: { ...headers, Accept: 'text/event-stream', ...(this.lastEventId ? { 'Last-Event-ID': this.lastEventId } : {}) },
          cache: 'no-store',
          signal,
        })
        if (response.status === 401) { this.setConnected(false); return }
        if (!response.ok || !response.body) throw new Error(`events ${response.status}`)
        this.setConnected(true)
        backoff = 1000
        await this.read(response.body, signal)
      } catch (error) {
        if (signal.aborted) return
        if (error instanceof BrainApiError && error.code === 'unauthorized') { this.setConnected(false); return }
      }
      this.setConnected(false)
      if (signal.aborted) return
      await new Promise((resolve) => setTimeout(resolve, backoff))
      backoff = Math.min(backoff * 2, 10_000)
    }
  }

  private async read(body: ReadableStream<Uint8Array>, signal: AbortSignal) {
    const reader = body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (!signal.aborted) {
        const { value, done } = await reader.read()
        if (done) return
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n?/g, '\n')
        let boundary = buffer.indexOf('\n\n')
        while (boundary !== -1) {
          this.dispatch(buffer.slice(0, boundary))
          buffer = buffer.slice(boundary + 2)
          boundary = buffer.indexOf('\n\n')
        }
      }
    } finally {
      reader.cancel().catch(() => undefined)
    }
  }

  private dispatch(raw: string) {
    let data = ''
    let id: string | null = null
    for (const line of raw.split('\n')) {
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
      if (field === 'data') data += (data ? '\n' : '') + value
      else if (field === 'id') id = value
    }
    if (id) this.lastEventId = id
    if (!data) return
    try {
      const event = JSON.parse(data) as BrainEvent
      this.listeners.forEach((entry) => entry.listener(event))
    } catch {
      // Ignore malformed frames; the next event will resync state.
    }
  }
}

const liveHub = new LiveEventHub()

// ---------------------------------------------------------------------------
// Mock client
// ---------------------------------------------------------------------------

const mockDelay = (ms = 220) => new Promise<void>((resolve) => setTimeout(resolve, ms + Math.random() * 180))

function wrapMock<T>(promise: () => Promise<T>): Promise<T> {
  return mockDelay().then(promise).catch((error: unknown) => {
    if (error instanceof BrainApiError) throw error
    const status = (error as { status?: number })?.status ?? 500
    throw new BrainApiError(status, codeForStatus(status), (error as Error)?.message ?? 'Mock error')
  })
}

function createMockApi(): BrainApi {
  const brain = getMockBrain()
  return {
    mode: 'mock',
    overview: () => wrapMock(() => brain.overview()),
    graph: () => wrapMock(() => brain.graph()),
    items: (params) => wrapMock(() => brain.listItems(params)),
    item: (id) => wrapMock(() => brain.item(id)),
    deleteItem: (id) => wrapMock(() => brain.deleteItem(id)),
    retryItem: (id) => wrapMock(() => brain.retryItem(id)),
    refile: (id, body) => wrapMock(() => brain.refile(id, body)),
    captureLink: (url, channel) => wrapMock(() => {
      try { new URL(url) } catch { throw new BrainApiError(422, 'invalid_input', 'Enter a valid link.') }
      return brain.captureLink(url, channel)
    }),
    captureText: (text, title, channel) => wrapMock(() => {
      if (!text.trim()) throw new BrainApiError(422, 'invalid_input', 'Text is empty.')
      return brain.captureText(text, title, channel)
    }),
    captureFile: (file, options = {}) => wrapMock(() => {
      if (file.size > BRAIN_MAX_UPLOAD_BYTES) throw new BrainApiError(413, 'too_large', 'Choose a file up to 20 MB.')
      options.onUploadProgress?.(1)
      return brain.captureFile(file, options.channel)
    }),
    concept: (id) => wrapMock(() => brain.concept(id)),
    course: (id) => wrapMock(() => brain.course(id)),
    renameCourse: (id, title) => wrapMock(() => brain.renameCourse(id, title)),
    gaps: () => wrapMock(async () => brain.gaps()),
    search: (query, limit) => wrapMock(() => brain.search(query, limit)),
    createExamPlan: (courseId, body) => wrapMock(() => {
      if (!Number.isInteger(body.days) || body.days < 1 || body.days > 14) throw new BrainApiError(422, 'invalid_input', 'Choose 1–14 days.')
      return brain.createExamPlan(courseId, { ...body, request_id: body.request_id ?? newRequestId() })
    }),
    plan: (id) => wrapMock(() => brain.plan(id)),
    coursePlans: (courseId) => wrapMock(() => brain.coursePlans(courseId)),
    answerQuiz: (planId, questionId, optionId) => wrapMock(() => brain.answerQuiz(planId, questionId, optionId)),
    telegramStatus: () => wrapMock(() => brain.telegramStatus()),
    telegramLinkCode: () => wrapMock(() => brain.telegramLinkCode()),
    telegramUnlink: () => wrapMock(() => brain.telegramUnlink()),
    subscribe: (listener, options) => {
      options?.onConnectionChange?.(true)
      const unsubscribe = brain.subscribe(listener)
      return () => { unsubscribe(); options?.onConnectionChange?.(false) }
    },
    simulateHeroDemo: () => brain.simulateHeroDemo(),
  }
}

/** Create a client. Pass the Supabase token getter from `useAuth()`. */
export function createBrainApi(getToken: TokenGetter, mode: BrainApiMode = brainApiMode): BrainApi {
  return mode === 'mock' ? createMockApi() : createLiveApi(getToken)
}

// Pure helpers (formatting, embeds, event reducers) live in brain-api-helpers.ts.
export { formatTimestamp, youtubeEmbedUrl, reduceItems, reduceGraph } from './brain-api-helpers'
