"""Enforce byte limits even for chunked uploads without Content-Length."""
import tempfile

from starlette.responses import JSONResponse


class UploadLimitMiddleware:
    def __init__(self,app,settings_getter):self.app,self.settings_getter=app,settings_getter

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method']!='POST':return await self.app(scope,receive,send)
        settings=self.settings_getter()
        limit=(settings.max_batch_mb if scope['path']=='/api/jobs' else settings.max_upload_mb*2)*1024**2+262144
        headers=dict(scope.get('headers',[]));declared=headers.get(b'content-length')
        if declared:
            try:
                size=int(declared)
                if size<0:raise ValueError()
            except ValueError:return await JSONResponse({'detail':'Invalid Content-Length.'},400)(scope,receive,send)
            if size>limit:return await JSONResponse({'detail':'Request exceeds the upload limit.'},413)(scope,receive,send)
        with tempfile.SpooledTemporaryFile(max_size=1024**2) as body:
            total=0
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return
                chunk=message.get('body',b'');total+=len(chunk)
                if total>limit:return await JSONResponse({'detail':'Request exceeds the streamed upload limit.'},413)(scope,receive,send)
                body.write(chunk)
                if not message.get('more_body',False):break
            body.seek(0);finished=False
            async def replay():
                nonlocal finished
                if finished:return await receive()
                chunk=body.read(65536);more=body.tell()<total;finished=not more
                return {'type':'http.request','body':chunk,'more_body':more}
            await self.app(scope,replay,send)
