import { NextRequest } from 'next/server'
import { proxyBackend } from '@/lib/backend-proxy'

export async function DELETE(request: NextRequest) {
  return proxyBackend(request, 'account', 'DELETE')
}
