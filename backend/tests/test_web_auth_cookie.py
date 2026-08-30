"""Tests für den Cookie-Auth-Modus (CAT-27, Cloud-Deploy) und den Upload-Fix."""
import os
import sys

import pytest

# Make `web.*` importable from this test (mirrors the layout `web/app.py` uses).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from web.app import app  # noqa: E402
from web.auth import AUTH_COOKIE, assert_auth_configured, check_ws_token  # noqa: E402


TOKEN = "s3cret-token"


@pytest.fixture
def client():
    # No context manager: startup events (DB init) must not run for auth tests.
    return TestClient(app)


@pytest.fixture
def standalone(monkeypatch):
    monkeypatch.delenv("CTF_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CTF_COOKIE_AUTH", raising=False)


@pytest.fixture
def desktop_mode(monkeypatch):
    monkeypatch.setenv("CTF_AUTH_TOKEN", TOKEN)
    monkeypatch.delenv("CTF_COOKIE_AUTH", raising=False)


@pytest.fixture
def cookie_mode(monkeypatch):
    monkeypatch.setenv("CTF_AUTH_TOKEN", TOKEN)
    monkeypatch.setenv("CTF_COOKIE_AUTH", "1")


class TestStandalone:
    def test_everything_open(self, standalone, client):
        assert client.get("/").status_code == 200
        assert client.get("/api/status").status_code == 200


class TestDesktopMode:
    def test_pages_stay_open(self, desktop_mode, client):
        assert client.get("/").status_code == 200

    def test_api_requires_header(self, desktop_mode, client):
        assert client.get("/api/status").status_code == 401

    def test_api_rejects_wrong_header(self, desktop_mode, client):
        r = client.get("/api/status", headers={"X-CTF-Token": "wrong"})
        assert r.status_code == 401

    def test_api_accepts_header(self, desktop_mode, client):
        r = client.get("/api/status", headers={"X-CTF-Token": TOKEN})
        assert r.status_code == 200

    def test_cookie_does_not_authenticate(self, desktop_mode, client):
        r = client.get("/api/status", cookies={AUTH_COOKIE: TOKEN})
        assert r.status_code == 401


class TestCookieMode:
    def test_page_blocked_without_credentials(self, cookie_mode, client):
        assert client.get("/").status_code == 401

    def test_static_blocked_without_credentials(self, cookie_mode, client):
        assert client.get("/style.css").status_code == 401

    def test_api_blocked_returns_json(self, cookie_mode, client):
        r = client.get("/api/status")
        assert r.status_code == 401
        assert r.json() == {"error": "Unauthorized"}

    def test_health_stays_open(self, cookie_mode, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_token_link_sets_cookie_and_redirects(self, cookie_mode, client):
        r = client.get(f"/?token={TOKEN}", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        assert AUTH_COOKIE in r.cookies
        cookie_header = r.headers["set-cookie"]
        assert "HttpOnly" in cookie_header
        assert "Secure" in cookie_header

    def test_token_link_preserves_other_params(self, cookie_mode, client):
        r = client.get(f"/transactions?token={TOKEN}&month=2026-07", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/transactions?month=2026-07"

    def test_wrong_token_link_is_rejected(self, cookie_mode, client):
        assert client.get("/?token=wrong").status_code == 401

    def test_cookie_authenticates_page(self, cookie_mode, client):
        r = client.get("/", cookies={AUTH_COOKIE: TOKEN})
        assert r.status_code == 200

    def test_cookie_authenticates_api(self, cookie_mode, client):
        r = client.get("/api/status", cookies={AUTH_COOKIE: TOKEN})
        assert r.status_code == 200

    def test_header_still_authenticates_api(self, cookie_mode, client):
        r = client.get("/api/status", headers={"X-CTF-Token": TOKEN})
        assert r.status_code == 200

    def test_query_token_never_authenticates_api(self, cookie_mode, client):
        assert client.get(f"/api/status?token={TOKEN}").status_code == 401


class TestCheckWsToken:
    def test_no_token_configured_allows(self, standalone):
        assert check_ws_token("") is True

    def test_query_token_matches(self, desktop_mode):
        assert check_ws_token(TOKEN) is True
        assert check_ws_token("wrong") is False

    def test_cookie_ignored_in_desktop_mode(self, desktop_mode):
        assert check_ws_token("", TOKEN) is False

    def test_cookie_accepted_in_cookie_mode(self, cookie_mode):
        assert check_ws_token("", TOKEN) is True
        assert check_ws_token("", "wrong") is False


class TestAssertAuthConfigured:
    """Fail-closed guard: cloud mode must never start without a token."""

    def test_raises_when_cookie_mode_without_token(self, monkeypatch):
        monkeypatch.setenv("CTF_COOKIE_AUTH", "1")
        monkeypatch.delenv("CTF_AUTH_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="CTF_AUTH_TOKEN"):
            assert_auth_configured()

    def test_raises_when_token_is_blank(self, monkeypatch):
        monkeypatch.setenv("CTF_COOKIE_AUTH", "1")
        monkeypatch.setenv("CTF_AUTH_TOKEN", "")
        with pytest.raises(RuntimeError):
            assert_auth_configured()

    def test_passes_in_cookie_mode_with_token(self, cookie_mode):
        assert_auth_configured()

    def test_passes_in_standalone_mode(self, standalone):
        assert_auth_configured()

    def test_passes_in_desktop_mode(self, desktop_mode):
        assert_auth_configured()


class TestUploadFilenameSanitized:
    def test_traversal_filename_is_reduced_to_basename(self, standalone, client, monkeypatch):
        seen = {}

        async def fake_ingest(path: str):
            seen["path"] = path
            return {"ok": True}

        import app.queries as queries
        from web.app import UPLOAD_TMP

        UPLOAD_TMP.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(queries, "ingest_file", fake_ingest)
        r = client.post(
            "/api/upload",
            files={"file": ("../../evil.csv", b"datum;betrag\n", "text/csv")},
        )
        assert r.status_code == 200
        assert seen["path"].endswith("data/uploads/evil.csv")
        assert "/../" not in seen["path"]
