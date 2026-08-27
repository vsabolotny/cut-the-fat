"""Smoke-Tests für den CAT-26-Design-Prototyp (doc/design/CAT-26-frontend-redesign/).

Der Prototyp ist ein eigenständiges Design-Artefakt: er muss parsen,
alle drei Varianten enthalten und offline funktionieren (keine externen
Ressourcen — im Gegensatz zur App gibt es keine CSP, die das erzwingt).
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

PROTO = Path(__file__).parents[2] / "doc" / "design" / "CAT-26-frontend-redesign" / "prototype.html"
DECISIONS = PROTO.parent / "DECISIONS.md"


class _CountingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors: list[str] = []
        self.stack: list[str] = []
        self.void = {"meta", "link", "br", "hr", "img", "input", "col", "area", "base", "wbr", "source"}

    def handle_starttag(self, tag, attrs):
        if tag not in self.void:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.void:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unbalanced </{tag}> (stack: {self.stack[-3:]})")
        else:
            self.stack.pop()


@pytest.fixture(scope="module")
def html() -> str:
    return PROTO.read_text(encoding="utf-8")


def test_prototype_exists_with_decisions_doc():
    assert PROTO.is_file()
    assert DECISIONS.is_file()


def test_prototype_tags_balanced(html):
    parser = _CountingParser()
    parser.feed(html)
    assert not parser.errors, parser.errors
    assert not parser.stack, f"unclosed tags: {parser.stack}"


def test_all_three_variants_present(html):
    for variant_id in ("v-fluss", "v-konto", "v-klassik"):
        assert f'id="{variant_id}"' in html
    for switch in ('data-v="fluss"', 'data-v="konto"', 'data-v="klassik"'):
        assert switch in html


def test_no_external_resources(html):
    # Keine geladenen externen Ressourcen: src/href mit http(s), kein @import, kein fetch.
    assert not re.search(r'(?:src|href)\s*=\s*["\']https?://', html)
    assert "@import" not in html
    assert "fetch(" not in html


def test_canonical_categories_only(html):
    from app.models.transaction import CATEGORIES

    used = set(re.findall(r"cat:\s*'([^']+)'", html))
    assert used, "no mock transactions found"
    assert used <= set(CATEGORIES), used - set(CATEGORIES)
