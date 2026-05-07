"""Cut the Fat — FastAPI web app with WebSocket chat."""
import logging
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

from web.ws_manager import manager
from web.logic.processor import process_message

app = FastAPI(title="Cut the Fat")

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


# Static files (CSS, JS) — mounted last so routes take priority
app.mount("/", StaticFiles(directory=str(STATIC_DIR)), name="static")
