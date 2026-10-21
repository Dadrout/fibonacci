import { NextRequest } from 'next/server'
import { proxyBrain } from '@/lib/brain-proxy'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

type Context = { params: Promise<{ path: string[] }> }

async function handle(request: NextRequest, context: Context) {
  const { path } = await context.params
  return proxyBrain(request, path)
}

export const GET = handle
export const POST = handle
export const PATCH = handle
export const DELETE = handle
