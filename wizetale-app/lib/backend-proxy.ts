import { NextRequest, NextResponse } from 'next/server'

function getBackendUrl() {
  const configuredUrl = process.env.BACKEND_API_URL?.trim()
  if (!configuredUrl) throw new Error('BACKEND_API_URL is not configured')

  const backendUrl = new URL(configuredUrl)
  if (process.env.NODE_ENV === 'production' && backendUrl.protocol !== 'https:') {
    throw new Error('BACKEND_API_URL must use HTTPS in production')
  }

  return backendUrl.toString().replace(/\/$/, '')
}

function retryAfterHeader(response: Response): Record<string, string> {
  const value = response.headers.get('Retry-After')
  return value ? { 'Retry-After': value } : {}
}

export async function proxyBackend(request: NextRequest, path: string, method: string) {
  const authorization = request.headers.get('Authorization')
  if (!authorization) {
    return NextResponse.json({ detail: 'Sign in to continue.' }, { status: 401 })
  }

  try {
    const body = ['GET', 'HEAD'].includes(method) ? undefined : await request.text()
    const response = await fetch(`${getBackendUrl()}/api/v1/${path}`, {
      method,
      cache: 'no-store',
      headers: {
        Authorization: authorization,
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body,
    })
    if (path.startsWith('teacher/documents/') && path.endsWith('/original') && response.ok) {
      return new NextResponse(response.body, {status:response.status,headers:{'Content-Type':'application/octet-stream','Content-Disposition':response.headers.get('Content-Disposition')||'attachment','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}})
    }
    if ((path.startsWith('teacher/presentation-renders/') || path.startsWith('teacher/video-renders/')) && path.endsWith('/video') && response.ok) {
      return new NextResponse(response.body, {status:response.status,headers:{'Content-Type':'video/mp4','Content-Disposition':response.headers.get('Content-Disposition')||'attachment; filename="talespark-presentation.mp4"','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}})
    }
    const responseBody = await response.text()
    return new NextResponse([204, 205, 304].includes(response.status) ? null : responseBody, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/json',
        'Cache-Control': 'no-store, max-age=0',
        ...retryAfterHeader(response),
      },
    })
  } catch (error) {
    console.error('Fibonacci API request failed:', error)
    return NextResponse.json({ detail: 'The learning service is temporarily unavailable.' }, { status: 503 })
  }
}

/** A bounded binary route; multipart bytes and boundary must remain identical. */
export async function proxyTeacherUpload(request: NextRequest) {
  const authorization = request.headers.get('Authorization')
  if (!authorization) return NextResponse.json({detail:'Sign in to continue.'},{status:401})
  const limit=11*1024*1024
  if (Number(request.headers.get('Content-Length')||0)>limit) return NextResponse.json({detail:'Choose a document up to 10 MB.'},{status:413})
  const contentType=request.headers.get('Content-Type')||''
  if (!contentType.startsWith('multipart/form-data;')) return NextResponse.json({detail:'Choose a PDF, DOCX, or UTF-8 text document.'},{status:415})
  const reader=request.body?.getReader()
  if (!reader) return NextResponse.json({detail:'Choose a nonempty document up to 10 MB.'},{status:422})
  try {
    const chunks:Uint8Array[]=[];let size=0
    while(true){const {value,done}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();return NextResponse.json({detail:'Choose a document up to 10 MB.'},{status:413})}chunks.push(value)}
    const body=new Uint8Array(size);let offset=0;for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.byteLength}
    const response=await fetch(`${getBackendUrl()}/api/v1/teacher/documents/upload`,{method:'POST',cache:'no-store',headers:{Authorization:authorization,'Content-Type':contentType},body:body.buffer})
    return new NextResponse(await response.text(),{status:response.status,headers:{'Content-Type':response.headers.get('Content-Type')||'application/json','Cache-Control':'no-store',...retryAfterHeader(response)}})
  } catch {
    return NextResponse.json({detail:'Source upload could not complete. Try again.'},{status:503})
  } finally {reader.releaseLock()}
}
