"""Exact browser-origin checks and cache policy for cookie-based accounts."""

from urllib.parse import urlsplit

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

PRIVATE_CACHE_CONTROL = "private, no-store"
AUTH_WRITES = {"/auth/send-link", "/auth/logout", "/auth/complete-profile"}


def origin_key(value: str, *, referer: bool = False) -> tuple[str, str, int]:
    """Reject malformed origins; normalize only scheme, hostname and default port."""
    if not value or any(c.isspace() for c in value) or any(c in value for c in "\\,*"):
        raise ValueError("Expected an exact HTTP(S) origin")
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or (not referer and (url.path or url.query or url.fragment))
    ):
        raise ValueError("Expected an exact HTTP(S) origin")
    port = url.port if url.port is not None else (443 if url.scheme == "https" else 80)
    return url.scheme, url.hostname, port


def origin_allowed(request: Request) -> bool:
    # An explicit (even invalid) Origin always takes precedence over Referer.
    values = request.headers.getlist("origin")
    referer = False
    if not values:
        values = request.headers.getlist("referer")
        referer = True
    if len(values) != 1:
        return False
    try:
        origin = origin_key(values[0], referer=referer)
        allowed = {origin_key(settings.BASE_URL)} | {
            origin_key(value) for value in settings.CSRF_TRUSTED_ORIGINS
        }
    except ValueError:
        return False
    return origin in allowed


def private_request(request: Request) -> bool:
    path = request.url.path
    return (
        path == "/auth"
        or path.startswith("/auth/")
        or path == "/bookmarks"
        or path.startswith("/bookmarks/")
        or "session_token" in request.cookies
    )


def private_response(request: Request, response):
    # Also used by ServerErrorMiddleware's handler, outside application middleware.
    if private_request(request) or "set-cookie" in response.headers:
        response.headers["Cache-Control"] = PRIVATE_CACHE_CONTROL
    return response


class AccountSecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        path = request.url.path.rstrip("/")
        protected_write = path in AUTH_WRITES or path.startswith("/bookmarks/")
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and protected_write
            and not origin_allowed(request)
        ):
            response = JSONResponse(
                {"detail": "Origine de la requête refusée."},
                status_code=403,
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
            return await response(scope, receive, send)

        async def send_private(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if private_request(request) or "set-cookie" in headers:
                    headers["Cache-Control"] = PRIVATE_CACHE_CONTROL
            await send(message)

        await self.app(scope, receive, send_private)
