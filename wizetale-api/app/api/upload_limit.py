"""Bound raw uploads before multipart parsing, including chunked requests."""
from starlette.responses import JSONResponse


class DocumentUploadLimit:
    def __init__(self,app): self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('path')!='/api/v1/teacher/documents/upload':
            return await self.app(scope,receive,send)
        limit=11*1024*1024
        headers=dict(scope.get('headers',[]))
        try: declared=int(headers.get(b'content-length',b'0'))
        except ValueError: declared=0
        if declared>limit:
            return await JSONResponse({'detail':'Choose a document up to 10 MB.'},status_code=413)(scope,receive,send)
        data=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            chunk=message.get('body',b'')
            if len(data)+len(chunk)>limit:
                return await JSONResponse({'detail':'Choose a document up to 10 MB.'},status_code=413)(scope,receive,send)
            data.extend(chunk)
            if not message.get('more_body',False): break
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if delivered: return await receive()
            delivered=True
            return {'type':'http.request','body':bytes(data),'more_body':False}
        await self.app(scope,bounded_receive,send)
