"""Dashboard handler — summary for a month."""
from fastapi import WebSocket
from app.queries import get_summary, get_latest_month, get_comparison
from web.logic.formatter import summary_to_messages, fmt_eur, NATALIE_CATS


async def handle(ws: WebSocket, params: dict = None, context: dict = None):
    month = (context or {}).get("month") or await get_latest_month()
    if not month:
        await ws.send_json({"type": "text", "content": "Keine Transaktionen vorhanden."})
        return

    await ws.send_json({"type": "progress", "message": "Lade Ausgabenübersicht..."})

    data = await get_summary(month)

    # Compute totals excluding Natalie
    cats = [c for c in data["categories"] if c["category"] not in NATALIE_CATS]
    total = sum(c["total"] for c in cats)

    # Get comparison delta
    comp = await get_comparison(month)
    prev_cats = {k: v for k, v in comp["previous_categories"].items() if k not in NATALIE_CATS}
    prev_total = sum(prev_cats.values())
    delta = total - prev_total
    delta_pct = (delta / prev_total * 100) if prev_total else 0

    arrow = "▲" if delta > 0 else "▼"
    sign = "+" if delta > 0 else ""
    await ws.send_json({
        "type": "text",
        "content": f"Ausgaben {month}: **{fmt_eur(total)}** ({arrow} {sign}{delta_pct:.1f}% vs. Vormonat)",
    })

    await ws.send_json({"type": "content_header", "text": f"Ausgabenübersicht — {month}"})

    for msg in summary_to_messages(data):
        await ws.send_json(msg)

    await ws.send_json({"type": "set_context", "month": month, "intent": "dashboard"})
