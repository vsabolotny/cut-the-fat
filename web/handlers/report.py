"""Report handler — generate markdown report."""
from pathlib import Path
import re
from fastapi import WebSocket
from app.queries import get_latest_month, get_summary, get_comparison, get_insights_data

_YYYY_MM_RE = re.compile(r"^\d{4}-\d{2}$")


async def handle(ws: WebSocket, params: dict = None, context: dict = None):
    raw_month = (params or {}).get("month") or (context or {}).get("month")
    month = raw_month if (isinstance(raw_month, str) and _YYYY_MM_RE.match(raw_month)) else None
    if not month:
        month = await get_latest_month()
    if not month:
        await ws.send_json({"type": "text", "content": "Keine Transaktionen vorhanden."})
        return

    await ws.send_json({"type": "progress", "message": f"Generiere Bericht {month}..."})

    # Reuse CLI markdown writer (without CLI progress/console)
    from cli.render.md_writer import write_monthly_report

    summary = await get_summary(month)
    comparison = await get_comparison(month)
    insights_data = await get_insights_data(force=False)
    report_path = write_monthly_report(month, summary, comparison, insights_data)
    filepath = str(report_path)

    content = report_path.read_text(encoding="utf-8") if report_path.exists() else ""

    await ws.send_json({
        "type": "text",
        "content": f"📄 Bericht **{month}** generiert: `{filepath}`",
    })

    await ws.send_json({"type": "content_header", "text": f"Bericht — {month}"})

    await ws.send_json({
        "type": "report_preview",
        "month": month,
        "path": filepath,
        "content": content,
    })

    await ws.send_json({"type": "set_context", "month": month, "intent": "report"})
