"""Report handler — generate markdown report."""
from pathlib import Path
from fastapi import WebSocket
from app.queries import get_latest_month


async def handle(ws: WebSocket, params: dict = None, context: dict = None):
    month = (params or {}).get("month") or (context or {}).get("month") or await get_latest_month()
    if not month:
        await ws.send_json({"type": "text", "content": "Keine Transaktionen vorhanden."})
        return

    await ws.send_json({"type": "progress", "message": f"Generiere Bericht {month}..."})

    # Reuse CLI report generation logic
    from cli.render.md_writer import generate_report
    filepath = generate_report(month)

    report_path = Path(filepath)
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
