import { NextRequest } from 'next/server'
import { proxyBackend } from '@/lib/backend-proxy'

export function GET(request: NextRequest) {
  return proxyBackend(request, `study-materials${request.nextUrl.search}`, 'GET')
}

export function POST(request: NextRequest) {
  return proxyBackend(request, 'study-materials', 'POST')
}
