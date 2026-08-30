"""Tests für den Nutzer-Login (CAT-28).

Zwei Ebenen:
  - reine Funktionen aus `web/session.py` (Passwort-Hash, Token)
  - das Gate als echte Requests gegen eine temporäre SQLite-Datei
"""
import base64
import json
import os
import sys
import time

import pytest

# Make `web.*` importable from this test (mirrors the layout `web/app.py` uses).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from web import session as session_mod  # noqa: E402
from web.auth import requires_login  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_secret(tmp_path, monkeypatch):
    """Jeder Test bekommt einen eigenen Signaturschlüssel.

    Ohne das würden die Tests die echte `.ctf-session-secret` des Entwicklers
    anlegen oder überschreiben — und damit dessen Session beenden.
    """
    monkeypatch.setattr(session_mod, "SECRET_FILE", tmp_path / "secret")


# ---------------------------------------------------------------------------
# Passwort-Hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_is_not_the_plaintext(self):
        hashed = session_mod.hash_password("korrekt-pferd-batterie")
        assert "korrekt-pferd-batterie" not in hashed

    def test_verify_accepts_the_right_password(self):
        hashed = session_mod.hash_password("korrekt-pferd-batterie")
        assert session_mod.verify_password("korrekt-pferd-batterie", hashed)

    def test_verify_rejects_the_wrong_password(self):
        hashed = session_mod.hash_password("korrekt-pferd-batterie")
        assert not session_mod.verify_password("falsch-pferd-batterie", hashed)

    def test_same_password_hashes_differently(self):
        # Unterschiedliches Salt pro Aufruf — sonst wären Rainbow-Tables möglich.
        assert session_mod.hash_password("passwort1") != session_mod.hash_password("passwort1")

    def test_hash_has_the_documented_format(self):
        scheme, n, r, p, salt, digest = session_mod.hash_password("passwort1").split("$")
        assert scheme == "scrypt"
        assert (int(n), int(r), int(p)) == (2 ** 14, 8, 1)
        assert salt and digest

    def test_umlauts_round_trip(self):
        hashed = session_mod.hash_password("straße-müßig-ÄÖÜ")
        assert session_mod.verify_password("straße-müßig-ÄÖÜ", hashed)

    @pytest.mark.parametrize(
        "broken",
        ["", "nonsense", "scrypt$notanumber$8$1$aaaa$bbbb", "bcrypt$1$2$3$aa$bb", "a$b$c"],
    )
    def test_broken_hash_returns_false_instead_of_raising(self, broken):
        # Ein beschädigter Datensatz darf niemanden einloggen und darf den
        # Login-Endpunkt auch nicht in einen 500er kippen.
        assert not session_mod.verify_password("passwort1", broken)


# ---------------------------------------------------------------------------
# Session-Tokens
# ---------------------------------------------------------------------------


class TestSessionToken:
    def test_round_trip(self):
        assert session_mod.verify_token(session_mod.create_token(7)) == 7

    def test_expired_token_is_rejected(self):
        assert session_mod.verify_token(session_mod.create_token(7, ttl_seconds=-1)) is None

    def test_tampered_payload_is_rejected(self):
        token = session_mod.create_token(7)
        encoded, signature = token.split(".")
        forged = json.dumps({"sub": 99, "exp": int(time.time()) + 600}).encode()
        tampered = base64.urlsafe_b64encode(forged).decode().rstrip("=")
        assert session_mod.verify_token(f"{tampered}.{signature}") is None

    def test_token_from_another_secret_is_rejected(self, tmp_path, monkeypatch):
        token = session_mod.create_token(7)
        monkeypatch.setattr(session_mod, "SECRET_FILE", tmp_path / "other-secret")
        assert session_mod.verify_token(token) is None

    @pytest.mark.parametrize(
        "garbage",
        ["", "no-dot", "a.b.c", "....", "!!!.???", "eyJzdWIiOjF9"],
    )
    def test_garbage_is_rejected(self, garbage):
        assert session_mod.verify_token(garbage) is None

    def test_payload_without_exp_is_rejected(self):
        # Selbst korrekt signiert: ohne Ablauf gäbe es ein ewig gültiges Token.
        import hashlib
        import hmac

        payload = json.dumps({"sub": 7}).encode()
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        signature = hmac.new(
            session_mod.get_secret(), encoded.encode("ascii"), hashlib.sha256
        ).digest()
        signed = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        assert session_mod.verify_token(f"{encoded}.{signed}") is None

    def test_secret_file_is_created_with_owner_only_permissions(self):
        session_mod.get_secret()
        assert (session_mod.SECRET_FILE.stat().st_mode & 0o777) == 0o600

    def test_secret_is_stable_across_calls(self):
        assert session_mod.get_secret() == session_mod.get_secret()

    def test_secret_survives_the_write_read_round_trip(self, tmp_path, monkeypatch):
        """Regression: der Schlüssel lag früher als Rohbytes auf der Platte und
        wurde beim Lesen gestrippt. Jeder zwanzigste Zufallsschlüssel beginnt
        oder endet auf einem Whitespace-Byte — dort verschwand ein Byte und
        *jeder* ausgegebene Token wurde ungültig. Ein einzelner Durchlauf
        trifft das kaum, deshalb hier viele.
        """
        for i in range(60):
            monkeypatch.setattr(session_mod, "SECRET_FILE", tmp_path / f"secret-{i}")
            written = session_mod.get_secret()
            assert session_mod.get_secret() == written, "Schlüssel überlebt das Lesen nicht"
            assert session_mod.verify_token(session_mod.create_token(1)) == 1

    def test_unreadable_secret_file_is_replaced(self, tmp_path, monkeypatch):
        path = tmp_path / "kaputt"
        path.write_bytes(b"\xff\xfe kein hex")
        monkeypatch.setattr(session_mod, "SECRET_FILE", path)
        assert len(session_mod.get_secret()) == 32


class TestPasswordProblem:
    def test_short_password_is_rejected(self):
        assert session_mod.password_problem("kurz") is not None

    def test_eight_characters_are_enough(self):
        assert session_mod.password_problem("12345678") is None


# ---------------------------------------------------------------------------
# Welche Pfade das Gate schützt
# ---------------------------------------------------------------------------


class TestRequiresLogin:
    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/transactions",
            "/settings",
            "/api/transactions",
            "/api/settings",
            "/api/auth/me",
            # Static-Mount liegt auf "/", also liefert das die App direkt aus.
            "/index.html",
            "/transactions.html",
            "/settings.html",
        ],
    )
    def test_protected(self, path):
        assert requires_login(path)

    @pytest.mark.parametrize(
        "path",
        [
            # Regression: `.endswith(".html")` war case-sensitiv, das
            # Dateisystem unter macOS/Windows nicht — `GET /INDEX.HTML` lieferte
            # die komplette App ungeschützt aus.
            "/INDEX.HTML",
            "/Index.Html",
            "/TRANSACTIONS.HTML",
            "/API/TRANSACTIONS",
            # Nichts Öffentliches außerhalb der Positivliste.
            "/chat.js",
            "/settings.js",
            "/transactions.css",
            "/irgendwas-neues.html",
        ],
    )
    def test_protected_regardless_of_spelling(self, path):
        assert requires_login(path)

    @pytest.mark.parametrize(
        "path",
        [
            "/login",
            "/login.html",
            "/login.js",
            "/style.css",
            "/topbar.js",
            "/api/auth/status",
            "/api/auth/setup",
            "/api/auth/login",
        ],
    )
    def test_public(self, path):
        assert not requires_login(path)

    def test_the_login_page_can_load_every_asset_it_references(self):
        """Die Positivliste ist nur so gut wie ihre Vollständigkeit: Fehlt eine
        Datei, die login.html einbindet, ist die Login-Seite kaputt — und zwar
        erst in Produktion."""
        import os
        import re

        static = os.path.join(ROOT, "web", "static")
        markup = open(os.path.join(static, "login.html"), encoding="utf-8").read()
        referenced = re.findall(r'(?:src|href)="([^"]+)"', markup)

        assert referenced, "login.html bindet nichts ein — Regex kaputt?"
        for asset in referenced:
            assert not requires_login("/" + asset.lstrip("/")), asset
