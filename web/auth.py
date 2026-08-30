"""Authentication for the FastAPI sidecar.

Two modes, both driven by env vars:

Desktop/sidecar mode (`CTF_AUTH_TOKEN` set, `CTF_COOKIE_AUTH` unset) — launched
by Tauri. All `/api/*` HTTP routes and the `/ws/chat` WebSocket require the
token:
  - HTTP: `X-CTF-Token` header
  - WebSocket: `?token=...` query parameter
HTML pages and static assets stay open (the webview loads them without headers).

Cloud mode (`CTF_AUTH_TOKEN` set and `CTF_COOKIE_AUTH=1`) — public deployment
behind CloudFront. Every path requires the token. First visit uses
`?token=<secret>` which sets an HttpOnly `ctf_token` cookie and redirects to the
clean URL; from then on the cookie authenticates pages, `/api/*` and the
WebSocket handshake alike (same-origin requests carry it automatically).

When `CTF_AUTH_TOKEN` is empty (standalone `./ctf-web` workflow), the
middleware is a no-op so the same backend is reachable from a regular browser
tab on http://127.0.0.1:8080.
"""
import hmac
import os
from urllib.parse import urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response


PROTECTED_PREFIX = "/api/"
AUTH_COOKIE = "ctf_token"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


def get_auth_token() -> str:
    """Read the token at request time so tests can override it."""
    return os.environ.get("CTF_AUTH_TOKEN", "")


def cookie_auth_enabled() -> bool:
    """Cloud mode: gate every path and hand out the auth cookie."""
    return os.environ.get("CTF_COOKIE_AUTH", "").lower() in ("1", "true", "yes")


def _matches(provided: str, token: str) -> bool:
    return bool(provided) and hmac.compare_digest(provided, token)


def assert_auth_configured() -> None:
    """Fail closed: cloud mode without a token would serve everything publicly.

    Raised at startup rather than per-request — a half-populated `.env` (e.g. a
    failed SSM sync) must stop the container, not silently disable auth.
    """
    if cookie_auth_enabled() and not get_auth_token():
        raise RuntimeError(
            "CTF_COOKIE_AUTH=1, aber CTF_AUTH_TOKEN ist leer — Start abgebrochen, "
            "sonst wäre die App ohne jede Authentifizierung erreichbar."
        )


class AuthMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests.

    Constant-time comparison via `hmac.compare_digest` to avoid leaking the
    token through timing differences.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        token = get_auth_token()
        if not token:
            return await call_next(request)

        cookie_mode = cookie_auth_enabled()
        path = request.url.path
        if path == "/health":
            return await call_next(request)
        if not cookie_mode and not path.startswith(PROTECTED_PREFIX):
            return await call_next(request)

        if _matches(request.headers.get("X-CTF-Token", ""), token):
            return await call_next(request)
        if cookie_mode and _matches(request.cookies.get(AUTH_COOKIE, ""), token):
            return await call_next(request)

        # First visit in cloud mode: ?token=… on a page URL logs the browser in.
        if (
            cookie_mode
            and not path.startswith(PROTECTED_PREFIX)
            and _matches(request.query_params.get("token", ""), token)
        ):
            params = [(k, v) for k, v in request.query_params.multi_items() if k != "token"]
            target = path + ("?" + urlencode(params) if params else "")
            response = RedirectResponse(target, status_code=303)
            response.set_cookie(
                AUTH_COOKIE,
                token,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                secure=True,
                samesite="lax",
            )
            return response

        if path.startswith(PROTECTED_PREFIX):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return HTMLResponse(
            "<h1>401</h1><p>Zugriff nur mit g&uuml;ltigem Token-Link.</p>",
            status_code=401,
        )


def check_ws_token(query_token: str, cookie_token: str = "") -> bool:
    """Check WebSocket credentials (query `?token=…` or `ctf_token` cookie).

    Returns True if no token is configured (standalone mode), or either
    credential matches under constant-time comparison.
    """
    token = get_auth_token()
    if not token:
        return True
    if _matches(query_token, token):
        return True
    return cookie_auth_enabled() and _matches(cookie_token, token)
