from starlette.responses import PlainTextResponse


class BodyLimitMiddleware:
    """Bound request bodies even when Content-Length is absent or inaccurate."""
    def __init__(self, app, limit=65536):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        content_length = next((v for k,v in scope.get('headers', []) if k == b'content-length'), None)
        if content_length:
            try:
                length = int(content_length)
            except ValueError:
                return await PlainTextResponse('Invalid content length', 400)(scope, receive, send)
            if length < 0 or length > self.limit:
                return await PlainTextResponse('Request too large', 413)(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > self.limit:
                return await PlainTextResponse('Request too large', 413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        replayed = False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope, replay, send)
