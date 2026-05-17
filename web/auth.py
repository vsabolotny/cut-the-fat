"""Authentication for the FastAPI sidecar.

When the backend is launched by Tauri it inherits the `CTF_AUTH_TOKEN` env var.
All `/api/*` HTTP routes and the `/ws/chat` WebSocket require this token from
that point on:
  - HTTP: `X-CTF-Token` header
  - WebSocket: `?token=...` query parameter

When the env var is empty (standalone `./ctf-web` workflow), the middleware is
a no-op so the same backend is reachable from a regular browser tab on
http://127.0.0.1:8765.
"""
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


PROTECTED_PREFIX = "/api/"


def get_auth_token() -> str:
    """Read the token at request time so tests can override it."""
    return os.environ.get("CTF_AUTH_TOKEN", "")


class AuthMiddleware(BaseHTTPMiddleware):
    """Reject `/api/*` requests with a missing/mismatched X-CTF-Token header.

    Constant-time comparison via `hmac.compare_digest` to avoid leaking the
    token through timing differences.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        token = get_auth_token()
        if not token:
            return await call_next(request)

        if not request.url.path.startswith(PROTECTED_PREFIX):
            return await call_next(request)

        provided = request.headers.get("X-CTF-Token", "")
        if not provided or not hmac.compare_digest(provided, token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


def check_ws_token(query_token: str) -> bool:
    """Compare a WebSocket query-string token against the expected one.

    Returns True if no token is configured (standalone mode), or the tokens
    match under constant-time comparison.
    """
    token = get_auth_token()
    if not token:
        return True
    return bool(query_token) and hmac.compare_digest(query_token, token)
