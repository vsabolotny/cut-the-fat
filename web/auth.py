"""Authentication for the FastAPI sidecar.

Zwei unabhängige Ebenen:

1. `AuthMiddleware` — Transport-Gate zwischen Tauri und Sidecar. Wenn der
   Backend-Prozess von Tauri gestartet wird, erbt er `CTF_AUTH_TOKEN`. Ab dann
   brauchen alle `/api/*`-Routen und der `/ws/chat`-WebSocket dieses Token:
     - HTTP: `X-CTF-Token` header
     - WebSocket: `?token=...` query parameter
   Ist die Env-Var leer (standalone `./ctf-web`), ist die Middleware ein No-op,
   damit dasselbe Backend aus einem normalen Browser-Tab erreichbar bleibt.

2. `LoginRequiredMiddleware` — Nutzer-Gate (CAT-28). Verlangt einen
   Session-Token aus `web/session.py` für alle App-Seiten und `/api/*`-Routen.
   Gilt in beiden Modi, unabhängig von Ebene 1.
"""
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from web.session import COOKIE_NAME, verify_token


PROTECTED_PREFIX = "/api/"

# Alles, was vor dem Login erreichbar sein muss — sonst könnte sich niemand
# jemals anmelden. Bewusst eine Positivliste: Der Static-Mount hängt auf "/",
# und jede Negativliste (etwa "alles außer *.html") lässt sich umgehen. Genau
# das passierte hier: `.endswith(".html")` ist case-sensitiv, macOS und Windows
# sind es nicht — `GET /INDEX.HTML` lieferte die komplette App am Gate vorbei.
#
# Wer der Login-Seite eine neue Datei hinzufügt, muss sie hier eintragen. Das
# ist der Sinn der Sache: Vergessen heißt "Datei lädt nicht", nicht "App ist
# offen".
PUBLIC_PATHS = frozenset({
    "/login",
    "/login.html",
    "/login.js",
    "/topbar.js",
    "/style.css",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
})


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


def requires_login(path: str) -> bool:
    """Braucht dieser Pfad eine gültige Session? Alles außer `PUBLIC_PATHS`.

    Case-insensitiv verglichen, weil die Dateisysteme unter macOS und Windows
    es auch sind: `StaticFiles` liefert `/INDEX.HTML` genauso aus wie
    `/index.html`. Ein Vergleich, der die Schreibweise ernst nimmt, der
    Dateisystem-Lookup dahinter aber nicht, ist genau die Lücke.
    """
    return path.lower() not in PUBLIC_PATHS


def session_user_id(request: Request) -> int | None:
    """Lies die user_id aus dem Bearer-Header oder dem Session-Cookie.

    Beide Wege, weil beide gebraucht werden: `fetch` schickt den Header, eine
    Dokument-Navigation kann das nicht und bringt nur das Cookie mit.
    """
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        user_id = verify_token(token)
        if user_id is not None:
            return user_id

    return verify_token(request.cookies.get(COOKIE_NAME, ""))


class LoginRequiredMiddleware(BaseHTTPMiddleware):
    """Sperrt die App hinter dem Nutzer-Login (CAT-28).

    Seitenaufrufe werden auf `/login` umgeleitet statt mit 401 beantwortet,
    damit ein Deep-Link im Browser nicht als roher JSON-Fehler landet.
    `/api/*` bekommt weiterhin 401, damit `apiFetch` es als abgelaufene Session
    erkennen kann.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if not requires_login(request.url.path):
            return await call_next(request)

        user_id = session_user_id(request)
        if user_id is None:
            if request.url.path.startswith(PROTECTED_PREFIX):
                return JSONResponse({"error": "Nicht angemeldet"}, status_code=401)
            return RedirectResponse("/login", status_code=303)

        request.state.user_id = user_id
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
