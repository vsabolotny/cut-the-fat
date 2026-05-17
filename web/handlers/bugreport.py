"""Bug report handler — creates GitHub Issues from the desktop app."""
import os
import re

import httpx


DEFAULT_REPO = "paulwilke/cut-the-fat"


def get_github_repo() -> str:
    """Honor the GITHUB_REPO env var if set (e.g. for forks)."""
    return os.environ.get("GITHUB_REPO", "").strip() or DEFAULT_REPO


_CURRENCY = r"€|EUR|USD|\$|GBP|£|CHF"

# Three patterns, ordered most-to-least specific:
#   1. German decimal (comma + two digits) — always replaced. Dates use dots,
#      so "15.03.2026" is safe.
#   2. English decimal (dot + two digits) — only when followed by a currency
#      token; bare "15.03" stays intact.
#   3. Bare integer immediately followed by a currency token.
_AMOUNT_RE = re.compile(
    rf"""
    (?<!\w)
    (?:
        [+-]?\d{{1,3}}(?:\.\d{{3}})+,\d{{2}}                # 1.234,56
        |
        [+-]?\d+,\d{{2}}                                    # 12,50
        |
        [+-]?\d{{1,3}}(?:,\d{{3}})+\.\d{{2}}\s?(?:{_CURRENCY})  # 1,234.56 EUR
        |
        [+-]?\d+\.\d{{2}}\s?(?:{_CURRENCY})                 # 12.50 EUR
        |
        [+-]?\d+\s?(?:{_CURRENCY})                          # 100 €
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_CUR_TAIL_RE = re.compile(rf"({_CURRENCY})\s*$", re.IGNORECASE)


def mask_amounts(text: str) -> str:
    """Replace monetary amounts with `XX,XX`, preserving any currency suffix.

    Conservative by design: matches German comma-decimals or
    digit-plus-currency tokens, so dates and plain integers are left alone.
    """

    def replace(match: re.Match[str]) -> str:
        whole = match.group(0)
        cur_match = _CUR_TAIL_RE.search(whole)
        if cur_match:
            return f"XX,XX {cur_match.group(1)}"
        return "XX,XX"

    return _AMOUNT_RE.sub(replace, text)


async def create_bug_report(title: str, body: str, labels: list[str] | None = None) -> dict:
    """Create a GitHub Issue with the given title and body.

    Requires GITHUB_TOKEN in the environment.
    Returns the issue URL on success, or an error dict.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN nicht gesetzt — Bug Report konnte nicht erstellt werden."}

    repo = get_github_repo()
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "title": title,
        "body": body,
        "labels": labels or ["bug", "desktop-app"],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=15)

    if resp.status_code == 201:
        data = resp.json()
        return {"url": data["html_url"], "number": data["number"]}
    else:
        return {"error": f"GitHub API {resp.status_code}: {resp.text[:200]}"}
