import { NextRequest, NextResponse } from 'next/server'
import { getBackendUrl } from './backend-proxy'

/**
 * Server-side proxy for /api/v1/brain/**. Owner: Claude.
 * - Forwards the Supabase bearer token, or — only when BRAIN_DEMO_TOKEN is set on the server
 *   and the client asks with `X-Brain-Demo: 1` — the demo token (the API also requires DEMO_MODE).
 * - Streams Server-Sent Events and media without buffering.
 * - Media links (`media/<token>`) carry their own signature and need no auth header.
 */
const UPLOAD_LIMIT = 21 * 1024 * 1024
const JSON_LIMIT = 256 * 1024

function json(detail: string, code: string, status: number) {
  return NextResponse.json({ detail, code }, { status })
}

function authorization(request: NextRequest): string | null {
  const header = request.headers.get('Authorization')
  if (header) return header
  const demo = process.env.BRAIN_DEMO_TOKEN?.trim()
  if (demo && request.headers.get('X-Brain-Demo') === '1') return `Bearer ${demo}`
  return null
}

function passHeaders(response: Response, extra: Record<string, string> = {}) {
  const headers: Record<string, string> = { 'Cache-Control': response.headers.get('Cache-Control') || 'no-store', ...extra }
  for (const name of ['Content-Type', 'Retry-After', 'Content-Range', 'Accept-Ranges', 'Content-Security-Policy', 'X-Content-Type-Options']) {
    const value = response.headers.get(name)
    if (value) headers[name] = value
  }
  return headers
}

export async function proxyBrain(request: NextRequest, segments: string[]) {
  const path = segments.map(encodeURIComponent).join('/')
  const method = request.method.toUpperCase()
  const target = `${getBackendUrl()}/api/v1/brain/${path}${request.nextUrl.search}`

  // Telegram calls the API directly; never expose the webhook through the web app.
  if (segments[0] === 'telegram' && segments[1] === 'webhook') return json('Not found.', 'not_found', 404)

  try {
    if (segments[0] === 'media' && segments.length === 2 && method === 'GET') {
      const range = request.headers.get('Range')
      const upstream = await fetch(target, { cache: 'no-store', headers: range ? { Range: range } : {} })
      return new NextResponse(upstream.body, { status: upstream.status, headers: passHeaders(upstream) })
    }

    const auth = authorization(request)
    if (!auth) return json('Sign in to continue.', 'unauthorized', 401)

    if (segments[0] === 'events' && method === 'GET') {
      const lastEventId = request.headers.get('Last-Event-ID')
      const upstream = await fetch(target, {
        cache: 'no-store',
        headers: { Authorization: auth, Accept: 'text/event-stream', ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}) },
        signal: request.signal,
      })
      if (!upstream.ok || !upstream.body) {
        return new NextResponse(await upstream.text(), { status: upstream.status, headers: passHeaders(upstream) })
      }
      return new NextResponse(upstream.body, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no', Connection: 'keep-alive' },
      })
    }

    if (path === 'captures/upload' && method === 'POST') {
      if (Number(request.headers.get('Content-Length') || 0) > UPLOAD_LIMIT) return json('Choose a file up to 20 MB.', 'too_large', 413)
      const contentType = request.headers.get('Content-Type') || ''
      if (!contentType.startsWith('multipart/form-data;')) return json('Send the file as a form upload.', 'invalid_input', 415)
      const body = await readLimited(request, UPLOAD_LIMIT)
      if (!body) return json('Choose a file up to 20 MB.', 'too_large', 413)
      const upstream = await fetch(target, { method, cache: 'no-store', headers: { Authorization: auth, 'Content-Type': contentType }, body })
      return new NextResponse(await upstream.text(), { status: upstream.status, headers: passHeaders(upstream) })
    }

    let body: Uint8Array | undefined
    if (!['GET', 'HEAD', 'DELETE'].includes(method)) {
      const read = await readLimited(request, JSON_LIMIT)
      if (!read) return json('Request is too large.', 'too_large', 413)
      body = read
    }
    const upstream = await fetch(target, {
      method, cache: 'no-store',
      headers: { Authorization: auth, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body && body.byteLength ? body : undefined,
    })
    const text = [204, 205, 304].includes(upstream.status) ? null : await upstream.text()
    return new NextResponse(text, { status: upstream.status, headers: passHeaders(upstream, { 'Cache-Control': 'no-store, max-age=0' }) })
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') return new NextResponse(null, { status: 499 })
    console.error('Fibonacci Brain API request failed:', (error as Error)?.name)
    return json('The Brain is temporarily unavailable.', 'unavailable', 503)
  }
}

async function readLimited(request: NextRequest, limit: number): Promise<Uint8Array<ArrayBuffer> | null> {
  const reader = request.body?.getReader()
  if (!reader) return new Uint8Array(new ArrayBuffer(0))
  const chunks: Uint8Array[] = []
  let size = 0
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      size += value.byteLength
      if (size > limit) {
        await reader.cancel()
        return null
      }
      chunks.push(value)
    }
  } finally {
    reader.releaseLock()
  }
  const out = new Uint8Array(new ArrayBuffer(size))
  let offset = 0
  for (const chunk of chunks) {
    out.set(chunk, offset)
    offset += chunk.byteLength
  }
  return out
}
