"""Insights handler — AI savings recommendations."""
from fastapi import WebSocket
from app.queries import get_insights_data


async def handle(ws: WebSocket, params: dict = None, context: dict = None):
    force = "neu" in str(params) if params else False

    await ws.send_json({"type": "progress", "message": "KI analysiert deine Ausgaben..."})

    data = await get_insights_data(force=force)

    items = data.get("items") or data.get("insights") or []
    if not items:
        await ws.send_json({"type": "text", "content": "Keine Sparempfehlungen verfügbar."})
        return

    await ws.send_json({
        "type": "text",
        "content": f"{len(items)} Sparempfehlungen — siehe rechts.",
    })

    await ws.send_json({"type": "content_header", "text": "Sparempfehlungen"})

    for item in items:
        await ws.send_json({
            "type": "insight",
            "insight_type": item.get("type", "info"),
            "text": item.get("text", str(item)),
        })

    await ws.send_json({"type": "set_context", "intent": "insights"})
