"""Basic perimeter controls. Shared edge throttling remains deployment-specific."""
import os
import threading
import time
from collections import OrderedDict
from urllib.parse import urlsplit
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

attempts = OrderedDict()
guard = threading.Lock()


class BodyLimitMiddleware:
    def __init__(self, app, limit=6*1024*1024):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try: length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'მოთხოვნის ზომა არასწორია'}, 400)(scope, receive, send)
        if length > self.limit:
            return await JSONResponse({'detail': 'მოთხოვნა აღემატება დასაშვებ ზომას'}, 413)(scope, receive, send)
        size = 0
        async def limited_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > self.limit: raise HTTPException(413, 'მოთხოვნა აღემატება დასაშვებ ზომას')
            return message
        return await self.app(scope, limited_receive, send)


def install_middleware(app):
    app.add_middleware(BodyLimitMiddleware)
    @app.middleware('http')
    async def perimeter(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin:
                parsed = urlsplit(origin)
                allowed = {str(request.base_url).rstrip('/')}
                if os.getenv('PUBLIC_BASE_URL'): allowed.add(os.environ['PUBLIC_BASE_URL'].rstrip('/'))
                if origin.rstrip('/') not in allowed or parsed.path or parsed.query or parsed.fragment:
                    return JSONResponse({'detail': 'მოთხოვნის წყარო არასწორია'}, status_code=403)
            if request.url.path.startswith('/api/auth/'):
                client = request.client.host if request.client else 'unknown'
                now = time.monotonic()
                with guard:
                    # Bound memory and do not trust forwarded client IPs here.
                    if len(attempts) >= 10000: attempts.popitem(last=False)
                    since, count = attempts.get(client, (now, 0))
                    if now - since >= 60: since, count = now, 0
                    attempts[client] = (since, count + 1)
                if count >= 30:
                    return JSONResponse({'detail': 'ძალიან ბევრი მცდელობა. სცადე ცოტა მოგვიანებით.'}, status_code=429, headers={'Retry-After': '60'})
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if request.url.path.startswith(('/api/', '/workspace', '/account', '/studio')):
            response.headers['Cache-Control'] = 'no-store'
        if os.getenv('APP_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response
