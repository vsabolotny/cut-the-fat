"""History handler — trend over N months."""
from fastapi import WebSocket
from app.queries import get_history
from web.logic.formatter import history_to_messages


async def handle(ws: WebSocket, params: dict = None, context: dict = None):
    months = int((params or {}).get("months", 5))

    await ws.send_json({"type": "progress", "message": "Lade Verlauf..."})

    data = await get_history(months)

    if not data["months"]:
        await ws.send_json({"type": "text", "content": "Keine Daten für diesen Zeitraum."})
        return

    await ws.send_json({
        "type": "text",
        "content": f"Trend der letzten {len(data['months'])} Monate.",
    })

    await ws.send_json({"type": "content_header",
                         "text": f"Ausgaben-Trend — {len(data['months'])} Monate"})

    for msg in history_to_messages(data):
        await ws.send_json(msg)

    await ws.send_json({"type": "set_context", "intent": "history"})
