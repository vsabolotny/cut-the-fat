"""Integrationstests für das Login-Gate (CAT-28).

Fährt die echte FastAPI-App gegen eine temporäre SQLite-Datei hoch und prüft
die Akzeptanzkriterien aus `doc/features/CAT-28-LOGIN.md` als Requests.
"""
import os
import secrets
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app import database as database_mod  # noqa: E402
from app import queries as queries_mod  # noqa: E402
from web import session as session_mod  # noqa: E402
from web.app import app  # noqa: E402


# Testpasswörter werden pro Lauf zufällig erzeugt. Nichts Passwortartiges
# liegt damit im Repo (Secret-Scanner schlagen sonst zu Recht an), und kein
# Test hängt an einer bestimmten Zeichenkette.
OWNER_PASSPHRASE = secrets.token_urlsafe(16)
OTHER_PASSPHRASE = secrets.token_urlsafe(16)
WRONG_PASSPHRASE = secrets.token_urlsafe(16)
UNKNOWN_PASSPHRASE = secrets.token_urlsafe(16)
TOO_SHORT_PASSPHRASE = secrets.token_urlsafe(16)[:4]
SIDECAR_TOKEN = secrets.token_urlsafe(16)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """App mit eigener DB und eigenem Signaturschlüssel.

    `queries.py` importiert `engine`/`AsyncSessionLocal` beim Modulimport, ein
    Patch auf `app.database` allein greift dort also nicht — beide Module
    müssen umgebogen werden.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    for module in (database_mod, queries_mod):
        monkeypatch.setattr(module, "engine", engine, raising=False)
        monkeypatch.setattr(module, "AsyncSessionLocal", sessionmaker, raising=False)
    monkeypatch.setattr(session_mod, "SECRET_FILE", tmp_path / "secret")

    # Der Startup-Hook legt via ensure_initialized() alle Tabellen an.
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def _setup_owner(client, password=OWNER_PASSPHRASE):
    response = client.post("/api/auth/setup", json={"password": password})
    assert response.status_code == 201, response.text
    return response.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _drop_cookies(client):
    """Setup/Login setzen ein Session-Cookie, das der TestClient wie ein
    Browser behält. Wer den Header-Pfad prüfen will — oder einen wirklich
    abgemeldeten Zustand — muss es loswerden."""
    client.cookies.clear()


# ---------------------------------------------------------------------------
# Erststart
# ---------------------------------------------------------------------------


class TestSetup:
    def test_fresh_db_reports_setup_required(self, client):
        assert client.get("/api/auth/status").json() == {"setup_required": True}

    def test_root_redirects_to_login_when_logged_out(self, client):
        response = client.get("/")
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_login_page_is_reachable_logged_out(self, client):
        assert client.get("/login").status_code == 200

    def test_short_password_is_rejected_and_creates_no_user(self, client):
        response = client.post("/api/auth/setup", json={"password": TOO_SHORT_PASSPHRASE})
        assert response.status_code == 400
        assert client.get("/api/auth/status").json() == {"setup_required": True}

    def test_setup_returns_a_working_token(self, client):
        token = _setup_owner(client)
        assert client.get("/api/auth/me", headers=_auth(token)).status_code == 200

    def test_status_flips_after_setup(self, client):
        _setup_owner(client)
        assert client.get("/api/auth/status").json() == {"setup_required": False}

    def test_second_setup_is_refused(self, client):
        _setup_owner(client)
        response = client.post("/api/auth/setup", json={"password": OTHER_PASSPHRASE})
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# Anmeldung
# ---------------------------------------------------------------------------


class TestLogin:
    def test_correct_password_returns_a_token(self, client):
        _setup_owner(client, OWNER_PASSPHRASE)
        response = client.post("/api/auth/login", json={"password": OWNER_PASSPHRASE})
        assert response.status_code == 200
        assert client.get("/api/auth/me", headers=_auth(response.json()["token"])).status_code == 200

    def test_wrong_password_is_rejected(self, client):
        _setup_owner(client, OWNER_PASSPHRASE)
        assert client.post("/api/auth/login", json={"password": WRONG_PASSPHRASE}).status_code == 401

    def test_error_does_not_reveal_whether_an_account_exists(self, client):
        before = client.post("/api/auth/login", json={"password": UNKNOWN_PASSPHRASE})
        _setup_owner(client, OWNER_PASSPHRASE)
        after = client.post("/api/auth/login", json={"password": UNKNOWN_PASSPHRASE})
        assert before.status_code == after.status_code == 401
        assert before.json() == after.json()


# ---------------------------------------------------------------------------
# Das Gate selbst
# ---------------------------------------------------------------------------


class TestGate:
    def test_api_without_token_is_401(self, client):
        _setup_owner(client)
        _drop_cookies(client)
        assert client.get("/api/transactions").status_code == 401

    def test_api_with_token_is_200(self, client):
        token = _setup_owner(client)
        _drop_cookies(client)
        assert client.get("/api/transactions", headers=_auth(token)).status_code == 200

    def test_raw_html_file_does_not_bypass_the_gate(self, client):
        # StaticFiles hängt auf "/", also wäre /index.html sonst die ganze App.
        _setup_owner(client)
        _drop_cookies(client)
        response = client.get("/index.html")
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_stylesheet_stays_public(self, client):
        _setup_owner(client)
        assert client.get("/style.css").status_code == 200

    def test_expired_token_is_rejected(self, client):
        _setup_owner(client)
        _drop_cookies(client)
        expired = session_mod.create_token(1, ttl_seconds=-1)
        assert client.get("/api/transactions", headers=_auth(expired)).status_code == 401

    def test_tampered_token_is_rejected(self, client):
        token = _setup_owner(client)
        _drop_cookies(client)
        payload, signature = token.split(".")
        assert client.get(
            "/api/transactions", headers=_auth(f"{payload}x.{signature}")
        ).status_code == 401

    def test_non_bearer_authorization_is_rejected(self, client):
        token = _setup_owner(client)
        _drop_cookies(client)
        assert client.get(
            "/api/transactions", headers={"Authorization": f"Basic {token}"}
        ).status_code == 401

    def test_page_routes_are_reachable_with_a_token(self, client):
        token = _setup_owner(client)
        _drop_cookies(client)
        for path in ("/", "/transactions", "/settings"):
            assert client.get(path, headers=_auth(token)).status_code == 200, path


class TestSessionCookie:
    """Eine Dokument-Navigation kann keinen Authorization-Header setzen — ohne
    Cookie würde jeder Login sofort wieder auf /login zurückgeworfen."""

    def test_login_sets_an_httponly_cookie(self, client):
        _setup_owner(client)
        response = client.post("/api/auth/login", json={"password": OWNER_PASSPHRASE})
        cookie = response.headers["set-cookie"]
        assert session_mod.COOKIE_NAME in cookie
        assert "HttpOnly" in cookie

    def test_page_navigation_works_on_the_cookie_alone(self, client):
        # TestClient hält das Cookie aus dem Setup — genau wie ein Browser nach
        # dem Redirect auf "/". Kein Authorization-Header im Spiel.
        _setup_owner(client)
        assert client.get("/").status_code == 200

    def test_logout_clears_the_cookie_and_relocks_the_app(self, client):
        _setup_owner(client)
        assert client.get("/").status_code == 200
        client.post("/api/auth/logout")
        assert client.get("/").status_code == 303

    def test_forged_cookie_is_rejected(self, client):
        _setup_owner(client)
        client.cookies.set(session_mod.COOKIE_NAME, "gefaelscht.gefaelscht")
        assert client.get("/").status_code == 303


class TestSidecarTokenStillApplies:
    def test_session_token_does_not_replace_the_sidecar_token(self, client, monkeypatch):
        """Beide Ebenen gelten unabhängig — eine gültige Session ersetzt das
        Sidecar-Token nicht."""
        token = _setup_owner(client)
        _drop_cookies(client)
        monkeypatch.setenv("CTF_AUTH_TOKEN", SIDECAR_TOKEN)

        assert client.get("/api/transactions", headers=_auth(token)).status_code == 401

        response = client.get(
            "/api/transactions",
            headers={**_auth(token), "X-CTF-Token": SIDECAR_TOKEN},
        )
        assert response.status_code == 200
