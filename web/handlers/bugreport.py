"""Bug report handler — creates GitHub Issues from the desktop app."""
import os
import httpx


GITHUB_REPO = "paulwilke/cut-the-fat"


async def create_bug_report(title: str, body: str, labels: list[str] | None = None) -> dict:
    """Create a GitHub Issue with the given title and body.

    Requires GITHUB_TOKEN in the environment.
    Returns the issue URL on success, or an error dict.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN nicht gesetzt — Bug Report konnte nicht erstellt werden."}

    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
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
