"""Login-Endpunkte für den Nutzer-Login (CAT-28).

Single-User: Es gibt genau einen Datensatz in `users`. Solange keiner existiert,
ist `/api/auth/setup` offen — danach nicht mehr.
"""
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from web.session import (
    COOKIE_NAME,
    TOKEN_TTL_SECONDS,
    create_token,
    hash_password,
    password_problem,
    verify_password,
)

router = APIRouter(prefix="/api/auth")

# Absichtlich identisch für "kein Nutzer angelegt" und "falsches Passwort" —
# nicht als Geheimhaltung (`/api/auth/status` sagt ohnehin offen, ob das Gerät
# eingerichtet ist; die Login-Seite braucht das), sondern damit der Ratende aus
# der Antwort nichts über den Zustand des Kontos ableiten kann.
INVALID_CREDENTIALS = "Passwort falsch."


def _with_session_cookie(response: JSONResponse, token: str) -> JSONResponse:
    """Hänge den Token zusätzlich als Cookie an.

    `httponly`, weil kein Skript ihn aus dem Cookie lesen muss — das Frontend
    bekommt denselben Token im Body und legt ihn selbst ab. `samesite=lax`
    reicht: Die App läuft auf 127.0.0.1 und wird nie in einem fremden Kontext
    eingebettet.
    """
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=TOKEN_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


class PasswordPayload(BaseModel):
    password: str = Field(default="", max_length=1024)


async def _user_count() -> int:
    from app.database import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())


@router.get("/status")
async def auth_status():
    """Sagt der Login-Seite, ob sie das Setup- oder das Login-Formular zeigt."""
    return {"setup_required": await _user_count() == 0}


@router.post("/setup")
async def auth_setup(payload: PasswordPayload):
    """Lege den einzigen Nutzer an und logge ihn direkt ein."""
    from app.database import AsyncSessionLocal
    from app.models.user import OWNER_USERNAME, User

    problem = password_problem(payload.password)
    if problem:
        return JSONResponse({"error": problem}, status_code=400)

    # Race zwischen zwei parallelen Setup-Requests: Der unique-Index auf
    # `username` entscheidet, der Verlierer bekommt denselben 409 wie ein
    # verspäteter zweiter Versuch.
    if await _user_count() > 0:
        return JSONResponse(
            {"error": "Es ist bereits ein Passwort gesetzt."}, status_code=409
        )

    async with AsyncSessionLocal() as db:
        user = User(
            username=OWNER_USERNAME,
            password_hash=hash_password(payload.password),
            last_login_at=datetime.now(),
        )
        db.add(user)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            return JSONResponse(
                {"error": "Es ist bereits ein Passwort gesetzt."}, status_code=409
            )
        await db.refresh(user)
        user_id = user.id

    token = create_token(user_id)
    return _with_session_cookie(JSONResponse({"token": token}, status_code=201), token)


@router.post("/login")
async def auth_login(payload: PasswordPayload):
    from app.database import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).order_by(User.id).limit(1))
        user = result.scalar_one_or_none()

        if user is None or not verify_password(payload.password, user.password_hash):
            return JSONResponse({"error": INVALID_CREDENTIALS}, status_code=401)

        user.last_login_at = datetime.now()
        await db.commit()
        user_id = user.id

    token = create_token(user_id)
    return _with_session_cookie(JSONResponse({"token": token}), token)


@router.get("/me")
async def auth_me(request: Request):
    """Session-Check fürs Frontend. Die Middleware hat die Session hier bereits
    geprüft und die user_id in den Request-State gelegt."""
    return {"user_id": getattr(request.state, "user_id", None)}


@router.post("/logout")
async def auth_logout():
    """Löscht das Session-Cookie.

    Der Token selbst ist zustandslos und läuft nur ab — wer ihn kopiert hat,
    kann ihn bis dahin weiterverwenden. Für ein Ein-Nutzer-Gate auf 127.0.0.1
    ist das akzeptiert; die Notbremse ist das Löschen von
    `.ctf-session-secret`, das alle Tokens auf einmal ungültig macht.
    """
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response
