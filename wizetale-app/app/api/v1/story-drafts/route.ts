import { NextRequest } from 'next/server'
import { proxyBackend } from '@/lib/backend-proxy'

export const dynamic = 'force-dynamic'
export async function POST(request: NextRequest) {
  return proxyBackend(request, 'story-drafts', 'POST')
}
