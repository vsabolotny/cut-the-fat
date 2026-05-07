"""Cut the Fat — FastAPI web app with WebSocket chat.

Kann standalone oder als Tauri-Sidecar laufen:
  Standalone:  uvicorn web.app:app --host 127.0.0.1 --port 8080
  Sidecar:     python -m web.app 8765   (gibt "READY:8765" auf stdout aus)
"""
import logging
import sys
import warnings

# Suppress SQLAlchemy pool warnings (same as CLI)
logging.getLogger("sqlalchemy.pool").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore", message=".*non-checked-in connection.*")
warnings.filterwarnings("ignore", message=".*garbage collector.*")

import json

import web  # noqa: ensure sys.path setup

from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from web.ws_manager import manager
from web.logic.processor import process_message

app = FastAPI(title="Cut the Fat")

# CORS: Tauri WebView uses tauri://localhost (macOS) or https://tauri.localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_TMP = Path(__file__).resolve().parent.parent / "data" / "uploads"


@app.on_event("startup")
async def startup():
    from app.queries import ensure_initialized
    await ensure_initialized()
    UPLOAD_TMP.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "text":
                await process_message(websocket, data)
            elif msg_type == "action":
                await process_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/transactions")
async def transactions_page():
    return FileResponse(STATIC_DIR / "transactions.html")


@app.get("/api/transactions")
async def api_transactions(
    date_from: str = None,
    date_to: str = None,
    category: str = None,
    merchant: str = None,
    type: str = None,
    limit: int = 200,
    offset: int = 0,
):
    """Return filtered transactions as JSON."""
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    conditions = ["1=1"]
    params = {}

    if date_from:
        conditions.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("date <= :date_to")
        params["date_to"] = date_to
    if category and category != "Alle":
        conditions.append("category = :category")
        params["category"] = category
    if merchant:
        conditions.append("merchant_normalized LIKE :merchant")
        params["merchant"] = f"%{merchant.lower()}%"
    if type and type != "all":
        conditions.append("type = :type")
        params["type"] = type

    where = " AND ".join(conditions)

    async with AsyncSessionLocal() as db:
        count_r = await db.execute(
            text(f"SELECT COUNT(*) FROM transactions WHERE {where}"), params
        )
        total = count_r.scalar_one()

        sum_r = await db.execute(
            text(f"""
                SELECT
                    COALESCE(SUM(CASE WHEN type='debit' THEN amount ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN type='credit' THEN amount ELSE 0 END), 0)
                FROM transactions WHERE {where}
            """), params
        )
        sums = sum_r.first()

        result = await db.execute(
            text(f"""
                SELECT id, date, merchant, amount, type, category, category_source, merchant_normalized
                FROM transactions
                WHERE {where}
                ORDER BY date DESC, id DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": limit, "offset": offset},
        )
        rows = result.all()

    return {
        "total": total,
        "sum_debit": float(sums[0]),
        "sum_credit": float(sums[1]),
        "offset": offset,
        "limit": limit,
        "rows": [
            {
                "id": r[0], "date": str(r[1]), "merchant": r[2],
                "amount": float(r[3]), "type": r[4], "category": r[5],
                "category_source": r[6], "merchant_normalized": r[7],
            }
            for r in rows
        ],
    }


@app.get("/api/categories")
async def api_categories():
    from app.queries import get_all_categories
    return await get_all_categories()

@app.get("/api/status")
async def api_status():
    """Return local status flags for the UI (no side effects)."""
    from app.config import get_settings

    settings = get_settings()
    anthropic_enabled = bool((settings.anthropic_api_key or "").strip())
    return {
        "anthropic_enabled": anthropic_enabled,
        "database": "sqlite",
        "notes": [
            "Wenn kein ANTHROPIC_API_KEY gesetzt ist, werden keine Daten an Anthropic gesendet.",
            "Daten/Regeln werden lokal in SQLite gespeichert (backend/cut_the_fat.db).",
        ],
    }


@app.post("/api/recategorize")
async def api_recategorize(body: dict):
    from app.queries import apply_rule
    merchant = body.get("merchant_normalized", "")
    category = body.get("category", "")
    if not merchant or not category:
        return {"error": "merchant_normalized and category required"}
    count = await apply_rule(merchant, category)
    return {"merchant": merchant, "category": category, "updated": count}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save uploaded file, then ingest via queries.ingest_file."""
    from app.queries import ingest_file

    dest = UPLOAD_TMP / file.filename
    content = await file.read()
    dest.write_bytes(content)

    try:
        result = await ingest_file(str(dest))
    except ValueError as e:
        return {"error": str(e)}
    finally:
        dest.unlink(missing_ok=True)

    return result


@app.get("/api/anthropic/insights-payload")
async def api_anthropic_insights_payload():
    """Return the exact payload that would be sent to Anthropic for insights."""
    from app.database import AsyncSessionLocal
    from app.services.insights import INSIGHTS_SYSTEM, _get_aggregated_data  # type: ignore

    async with AsyncSessionLocal() as db:
        data = await _get_aggregated_data(db)

    data_json = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2)
    return {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1024,
        "system": INSIGHTS_SYSTEM,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Here is my spending data for the last 6 months:\n\n"
                    f"{data_json}\n\n"
                    "Generate 5 specific cost-cutting insights."
                ),
            }
        ],
        "notes": [
            "Wenn ANTHROPIC_API_KEY gesetzt ist, wird dieser Payload an Anthropic gesendet.",
            "Wenn kein Key gesetzt ist, nutzt das System eine regelbasierte Fallback-Generierung.",
        ],
    }


@app.get("/api/anthropic/learn-payload")
async def api_anthropic_learn_payload():
    """Return the exact payload that would be sent to Anthropic for AI category suggestions (learn)."""
    from app.queries import get_uncategorized_merchants, get_all_categories
    from app.services.categorizer import _SYSTEM_PROMPT_TEMPLATE  # type: ignore

    merchants = await get_uncategorized_merchants()
    categories = await get_all_categories()
    merchant_keys = [m["merchant"] for m in merchants]

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(categories=", ".join(categories))
    merchant_list = "\n".join(f"- {m}" for m in merchant_keys)
    user_content = f"Kategorisiere diese Händler:\n{merchant_list}"

    return {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
        "notes": [
            "Dieser Payload wird beim 'Kategorien lernen' (KI-Vorschläge) an Anthropic gesendet, sofern ANTHROPIC_API_KEY gesetzt ist.",
            "Bekannte Händlerregeln werden ohne API-Aufruf angewendet; hier siehst du nur den Learn-Suggestions-Call.",
        ],
    }


@app.post("/api/bugreport")
async def api_bugreport(body: dict):
    """Accept a bug report from the desktop app and create a GitHub Issue."""
    from web.handlers.bugreport import create_bug_report

    title = body.get("title", "Bug Report aus Desktop-App")
    description = body.get("description", "")
    steps = body.get("steps", "")
    chat_log = body.get("chat_log", "")

    md_body = f"## Beschreibung\n\n{description}\n\n"
    if steps:
        md_body += f"## Schritte zur Reproduktion\n\n{steps}\n\n"
    if chat_log:
        md_body += f"## Chat-Kontext (letzte Nachrichten)\n\n```\n{chat_log}\n```\n"

    result = await create_bug_report(title=title, body=md_body)
    return result


# ── Settings (profile, API keys) ──

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_PROFILE_FILE = Path(__file__).resolve().parent.parent / ".ctf-profile.json"


def _read_env() -> list[str]:
    if _ENV_FILE.exists():
        return _ENV_FILE.read_text(encoding="utf-8").splitlines()
    return []


def _write_env_key(lines: list[str], key_name: str, value: str) -> list[str]:
    for i, line in enumerate(lines):
        if line.startswith(f"{key_name}=") or line.startswith(f"{key_name} ="):
            lines[i] = f"{key_name}={value}"
            return lines
    lines.append(f"{key_name}={value}")
    return lines


def _mask(key: str) -> str:
    if not key:
        return ""
    return ("*" * max(0, len(key) - 4) + key[-4:]) if len(key) > 4 else "*" * len(key)


@app.get("/api/settings")
async def api_settings_get():
    """Return current settings (keys masked, profile plain)."""
    from app.config import get_settings
    import os, json as _json
    settings = get_settings()
    anthropic_key = settings.anthropic_api_key or ""
    github_token = os.environ.get("GITHUB_TOKEN", "")

    profile = {}
    if _PROFILE_FILE.exists():
        try:
            profile = _json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "anthropic_key_set": bool(anthropic_key),
        "anthropic_key_masked": _mask(anthropic_key),
        "github_token_set": bool(github_token),
        "github_token_masked": _mask(github_token),
        "profile": profile,
        "db_path": str(Path(__file__).resolve().parent.parent / "backend" / "cut_the_fat.db"),
    }


@app.post("/api/settings")
async def api_settings_set(body: dict):
    """Save profile + env keys. Only updates fields present in the request."""
    import json as _json
    from app.config import get_settings

    lines = _read_env()
    changed_env = False

    if "anthropic_api_key" in body:
        key = (body["anthropic_api_key"] or "").strip()
        lines = _write_env_key(lines, "ANTHROPIC_API_KEY", key)
        changed_env = True

    if "github_token" in body:
        token = (body["github_token"] or "").strip()
        lines = _write_env_key(lines, "GITHUB_TOKEN", token)
        changed_env = True

    if changed_env:
        _ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        get_settings.cache_clear()

    if "profile" in body:
        profile = {k: str(v).strip() for k, v in (body["profile"] or {}).items() if v}
        _PROFILE_FILE.write_text(_json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True}


# Static files (CSS, JS) — mounted last so routes take priority
app.mount("/", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Sidecar entry point ──
# When invoked as `python -m web.app <port>`, runs uvicorn and prints
# the READY signal for Tauri to pick up.

if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    class ReadyServer(uvicorn.Server):
        """Custom uvicorn Server that prints READY after startup."""

        async def startup(self, sockets=None):
            await super().startup(sockets)
            # Signal to Tauri that the backend is listening
            print(f"READY:{port}", flush=True)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    ReadyServer(config).run()
