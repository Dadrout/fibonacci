import { NextRequest } from 'next/server'
import { proxyBackend } from '@/lib/backend-proxy'

export const dynamic = 'force-dynamic'
export async function GET(request: NextRequest, { params }: { params: Promise<{ storyId: string }> }) {
  const { storyId } = await params
  return proxyBackend(request, `stories/${encodeURIComponent(storyId)}/quiz-results`, 'GET')
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ storyId: string }> }) {
  const { storyId } = await params
  return proxyBackend(request, `stories/${encodeURIComponent(storyId)}/quiz-results`, 'POST')
}
