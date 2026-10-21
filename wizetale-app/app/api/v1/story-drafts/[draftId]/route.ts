import { NextRequest } from 'next/server'
import { proxyBackend } from '@/lib/backend-proxy'

export const dynamic = 'force-dynamic'
type Context = { params: Promise<{ draftId: string }> }
export async function GET(request: NextRequest, { params }: Context) {
  const { draftId } = await params
  return proxyBackend(request, `story-drafts/${encodeURIComponent(draftId)}`, 'GET')
}
export async function PATCH(request: NextRequest, { params }: Context) {
  const { draftId } = await params
  return proxyBackend(request, `story-drafts/${encodeURIComponent(draftId)}`, 'PATCH')
}
export async function DELETE(request: NextRequest, { params }: Context) {
  const { draftId } = await params
  return proxyBackend(request, `story-drafts/${encodeURIComponent(draftId)}`, 'DELETE')
}
