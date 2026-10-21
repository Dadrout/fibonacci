import { NextRequest } from 'next/server'
import { proxyBackend, proxyTeacherUpload } from '@/lib/backend-proxy'

type Context = { params: Promise<{ path: string[] }> }
async function proxy(request: NextRequest, context: Context) {
  const { path } = await context.params
  if (request.method === 'POST' && path.join('/') === 'documents/upload') return proxyTeacherUpload(request)
  return proxyBackend(request, `teacher/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`, request.method)
}
export const GET = proxy
export const POST = proxy
export const PATCH = proxy
export const DELETE = proxy

export const PUT = proxy
