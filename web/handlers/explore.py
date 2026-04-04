"""Explore handler — merchant/category drill-down."""
from fastapi import WebSocket
from app.database import AsyncSessionLocal
from sqlalchemy import text
from web.logic.formatter import fmt_eur
from app.services.categorizer import normalize_merchant


async def handle_merchant(ws: WebSocket, params: dict = None, context: dict = None):
    merchant_query = (params or {}).get("merchant", "").strip()
    if not merchant_query:
        await ws.send_json({"type": "text", "content": "Welchen Händler suchst du?"})
        return

    await ws.send_json({"type": "progress", "message": f"Suche {merchant_query}..."})

    norm = normalize_merchant(merchant_query)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT date, merchant, amount, category
                FROM transactions
                WHERE merchant_normalized LIKE :q AND type='debit'
                ORDER BY date DESC
                LIMIT 20
            """),
            {"q": f"%{norm}%"},
        )
        rows = result.all()

    if not rows:
        await ws.send_json({
            "type": "text",
            "content": f'Keine Transaktionen für „{merchant_query}" gefunden.',
        })
        return

    total = sum(r[2] for r in rows)
    await ws.send_json({
        "type": "text",
        "content": f"**{merchant_query.upper()}** — {len(rows)} Transaktionen, Gesamt: **{fmt_eur(total)}**",
    })

    await ws.send_json({"type": "content_header", "text": f"{merchant_query.upper()} — Transaktionen"})

    table_rows = [[str(r[0]), r[1], round(float(r[2]), 2), r[3]] for r in rows]
    await ws.send_json({
        "type": "table",
        "columns": ["Datum", "Händler", "Betrag", "Kategorie"],
        "rows": table_rows,
    })


async def handle_category(ws: WebSocket, params: dict = None, context: dict = None):
    category_query = (params or {}).get("category", "").strip()
    if not category_query:
        await ws.send_json({"type": "text", "content": "Welche Kategorie suchst du?"})
        return

    await ws.send_json({"type": "progress", "message": f"Suche {category_query}..."})

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
                FROM transactions
                WHERE category LIKE :q AND type='debit'
                GROUP BY month
                ORDER BY month ASC
            """),
            {"q": f"%{category_query}%"},
        )
        rows = result.all()

    if not rows:
        await ws.send_json({
            "type": "text",
            "content": f'Keine Transaktionen für „{category_query}" gefunden.',
        })
        return

    total = sum(r[1] for r in rows)
    avg = total / len(rows) if rows else 0

    await ws.send_json({
        "type": "text",
        "content": f"**{category_query}** — Gesamt: **{fmt_eur(total)}** (Ø {fmt_eur(avg)}/Monat)",
    })

    await ws.send_json({"type": "content_header", "text": f"{category_query} — Verlauf"})

    await ws.send_json({
        "type": "chart",
        "chart_type": "line",
        "title": f"{category_query} pro Monat",
        "data": {
            "labels": [r[0] for r in rows],
            "datasets": [{
                "label": category_query,
                "data": [round(float(r[1]), 2) for r in rows],
            }],
        },
    })
