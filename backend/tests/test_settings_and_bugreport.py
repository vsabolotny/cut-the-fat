"""Tests für die neuen Settings- und Bug-Report-Helfer im Web-Sidecar."""
import os
import sys

import pytest

# Make `web.*` importable from this test (mirrors the layout `web/app.py` uses).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from web.app import _mask, _sanitize_env_value, _write_env_key  # noqa: E402
from web.auth import check_ws_token  # noqa: E402
from web.handlers.bugreport import (  # noqa: E402
    DEFAULT_REPO,
    get_github_repo,
    mask_amounts,
)


# ---------------------------------------------------------------------------
# _mask
# ---------------------------------------------------------------------------


class TestMask:
    def test_empty_returns_empty(self):
        assert _mask("") == ""

    def test_short_value_full_mask(self):
        assert _mask("abc") == "***"

    def test_long_value_keeps_last_four(self):
        assert _mask("sk-ant-1234abcd") == "***********abcd"

    def test_exactly_four_chars(self):
        assert _mask("1234") == "****"


# ---------------------------------------------------------------------------
# _sanitize_env_value
# ---------------------------------------------------------------------------


class TestSanitizeEnvValue:
    def test_strips_surrounding_whitespace(self):
        assert _sanitize_env_value("  hello  ") == "hello"

    def test_drops_newlines(self):
        assert _sanitize_env_value("abc\ndef\r\n") == "abcdef"

    def test_drops_tabs_and_controls(self):
        assert _sanitize_env_value("a\tb\x00c") == "abc"

    def test_keeps_inner_spaces(self):
        assert _sanitize_env_value("foo bar") == "foo bar"


# ---------------------------------------------------------------------------
# _write_env_key
# ---------------------------------------------------------------------------


class TestWriteEnvKey:
    def test_appends_when_absent(self):
        lines = ["FOO=1"]
        result = _write_env_key(lines, "BAR", "2")
        assert result == ["FOO=1", "BAR=2"]

    def test_replaces_existing(self):
        lines = ["FOO=old", "BAR=keep"]
        result = _write_env_key(lines, "FOO", "new")
        assert result == ["FOO=new", "BAR=keep"]

    def test_matches_with_space_around_equal_sign(self):
        lines = ["FOO = old"]
        result = _write_env_key(lines, "FOO", "new")
        assert result == ["FOO=new"]

    def test_does_not_match_commented_lines(self):
        lines = ["# FOO=old"]
        result = _write_env_key(lines, "FOO", "new")
        assert result == ["# FOO=old", "FOO=new"]

    def test_quotes_values_with_whitespace(self):
        lines: list[str] = []
        result = _write_env_key(lines, "FOO", "hello world")
        assert result == ['FOO="hello world"']

    def test_drops_newline_in_value(self):
        """Pasting a multi-line secret must not break the .env file."""
        result = _write_env_key([], "FOO", "abc\ndef")
        assert result == ["FOO=abcdef"]
        # exactly one line, no embedded newline
        assert "\n" not in result[0]

    def test_does_not_match_lookalike_keys(self):
        lines = ["FOOBAR=keep"]
        result = _write_env_key(lines, "FOO", "new")
        assert result == ["FOOBAR=keep", "FOO=new"]


# ---------------------------------------------------------------------------
# check_ws_token
# ---------------------------------------------------------------------------


class TestCheckWsToken:
    def test_no_token_configured_allows_anything(self, monkeypatch):
        monkeypatch.delenv("CTF_AUTH_TOKEN", raising=False)
        assert check_ws_token("") is True
        assert check_ws_token("anything") is True

    def test_token_configured_rejects_empty(self, monkeypatch):
        monkeypatch.setenv("CTF_AUTH_TOKEN", "secret")
        assert check_ws_token("") is False

    def test_token_configured_rejects_mismatch(self, monkeypatch):
        monkeypatch.setenv("CTF_AUTH_TOKEN", "secret")
        assert check_ws_token("wrong") is False

    def test_token_configured_accepts_match(self, monkeypatch):
        monkeypatch.setenv("CTF_AUTH_TOKEN", "secret")
        assert check_ws_token("secret") is True


# ---------------------------------------------------------------------------
# get_github_repo
# ---------------------------------------------------------------------------


class TestGetGithubRepo:
    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        assert get_github_repo() == DEFAULT_REPO

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "vsabolotny/cut-the-fat")
        assert get_github_repo() == "vsabolotny/cut-the-fat"

    def test_empty_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "   ")
        assert get_github_repo() == DEFAULT_REPO


# ---------------------------------------------------------------------------
# mask_amounts
# ---------------------------------------------------------------------------


class TestMaskAmounts:
    def test_masks_euro_amount_with_symbol(self):
        assert mask_amounts("Ich habe 12,50 € ausgegeben") == "Ich habe XX,XX € ausgegeben"

    def test_masks_thousand_separator(self):
        assert mask_amounts("Miete 1.234,56 €") == "Miete XX,XX €"

    def test_masks_eur_suffix(self):
        assert mask_amounts("999,00 EUR") == "XX,XX EUR"

    def test_keeps_dates_intact(self):
        # Date-looking integers shouldn't be touched (no decimal, no currency).
        assert mask_amounts("Am 15.03.2026 gekauft") == "Am 15.03.2026 gekauft"

    def test_keeps_plain_integers(self):
        assert mask_amounts("Seite 5 von 10") == "Seite 5 von 10"
