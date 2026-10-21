"""Bound raw uploads before multipart parsing, including chunked requests."""
from starlette.responses import JSONResponse


class DocumentUploadLimit:
    def __init__(self,app): self.app=app

    async def __call__(self,scope,receive,send):
        path=scope.get('path')
        limits={'/api/v1/teacher/documents/upload':11*1024*1024,'/api/v1/brain/captures/upload':21*1024*1024}
        if scope['type']!='http' or path not in limits:
            return await self.app(scope,receive,send)
        limit=limits[path]
        message_text='Choose a document up to 10 MB.' if limit<20*1024*1024 else 'Choose a file up to 20 MB.'
        headers=dict(scope.get('headers',[]))
        try: declared=int(headers.get(b'content-length',b'0'))
        except ValueError: declared=0
        if declared>limit:
            return await JSONResponse({'detail':message_text,'code':'too_large'},status_code=413)(scope,receive,send)
        data=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            chunk=message.get('body',b'')
            if len(data)+len(chunk)>limit:
                return await JSONResponse({'detail':message_text,'code':'too_large'},status_code=413)(scope,receive,send)
            data.extend(chunk)
            if not message.get('more_body',False): break
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if delivered: return await receive()
            delivered=True
            return {'type':'http.request','body':bytes(data),'more_body':False}
        await self.app(scope,bounded_receive,send)
