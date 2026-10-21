import { NextRequest } from 'next/server'
import { proxyBackend } from '@/lib/backend-proxy'

export const dynamic = 'force-dynamic'
export async function POST(request: NextRequest, { params }: { params: Promise<{ draftId: string }> }) {
  const { draftId } = await params
  return proxyBackend(request, `story-drafts/${encodeURIComponent(draftId)}/render`, 'POST')
}
