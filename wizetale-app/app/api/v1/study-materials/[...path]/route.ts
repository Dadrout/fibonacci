import { NextRequest } from 'next/server'
import { proxyBackend } from '@/lib/backend-proxy'

type Context = { params: Promise<{ path: string[] }> }
async function proxy(request: NextRequest, context: Context) {
  const { path } = await context.params
  return proxyBackend(request, `study-materials/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`, request.method)
}

export const GET = proxy
export const POST = proxy
export const PATCH = proxy
export const DELETE = proxy
