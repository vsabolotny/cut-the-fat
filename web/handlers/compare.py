"""Compare handler — current vs previous month."""
from fastapi import WebSocket
from app.queries import get_comparison, get_latest_month
from web.logic.formatter import comparison_to_messages, fmt_eur, NATALIE_CATS


async def handle(ws: WebSocket, params: dict = None, context: dict = None):
    month = (context or {}).get("month") or await get_latest_month()
    if not month:
        await ws.send_json({"type": "text", "content": "Keine Transaktionen vorhanden."})
        return

    await ws.send_json({"type": "progress", "message": "Lade Vergleich..."})

    data = await get_comparison(month)

    curr_total = sum(v for k, v in data["current_categories"].items() if k not in NATALIE_CATS)
    prev_total = sum(v for k, v in data["previous_categories"].items() if k not in NATALIE_CATS)
    delta = curr_total - prev_total
    arrow = "▲" if delta > 0 else "▼"
    color = "red" if delta > 0 else "green"

    await ws.send_json({
        "type": "text",
        "content": f"{data['current_month']} vs. {data['previous_month']}: {arrow} {fmt_eur(abs(delta))} {'mehr' if delta > 0 else 'weniger'}",
    })

    await ws.send_json({"type": "content_header",
                         "text": f"Vergleich — {data['current_month']} vs. {data['previous_month']}"})

    for msg in comparison_to_messages(data):
        await ws.send_json(msg)

    await ws.send_json({"type": "set_context", "month": month, "intent": "compare"})
