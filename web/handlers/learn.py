"""Learn handler — TUI-style merchant categorization via WebSocket."""
from fastapi import WebSocket
from app.queries import (
    get_uncategorized_merchants,
    get_ai_suggestions,
    get_all_categories,
    apply_rule,
)
from web.logic.formatter import merchants_to_table


async def handle(ws: WebSocket, params: dict = None, context: dict = None):
    await ws.send_json({"type": "progress", "message": "Suche unkategorisierte Händler..."})

    merchants = await get_uncategorized_merchants()

    if not merchants:
        await ws.send_json({"type": "text", "content": "✓ Alle Händler sind bereits kategorisiert!"})
        return

    await ws.send_json({"type": "progress", "message": f"KI generiert Vorschläge für {len(merchants)} Händler..."})

    categories = await get_all_categories()
    merchant_keys = [m["merchant"] for m in merchants]
    suggestions = await get_ai_suggestions(merchant_keys, categories)

    await ws.send_json({
        "type": "text",
        "content": f"{len(merchants)} unkategorisierte Händler. KI-Vorschläge in der Tabelle rechts.",
    })

    await ws.send_json({"type": "content_header",
                         "text": f"Kategorien lernen — {len(merchants)} Händler"})

    # Send table data + category list so client can render TUI-style
    table_data = merchants_to_table(merchants, suggestions)
    table_data["categories"] = categories
    await ws.send_json(table_data)

    await ws.send_json({"type": "set_context", "intent": "learn"})


async def handle_recategorize(ws: WebSocket, params: dict = None, context: dict = None):
    merchant = (params or {}).get("merchant", "").strip()
    category = (params or {}).get("category", "").strip()

    if not merchant or not category:
        await ws.send_json({
            "type": "text",
            "content": 'Schreibe z.B. „Ändere Amazon zu Shopping".',
        })
        return

    await ws.send_json({"type": "progress", "message": f"Aktualisiere {merchant}..."})

    from app.services.categorizer import normalize_merchant
    norm = normalize_merchant(merchant)
    count = await apply_rule(norm, category)

    await ws.send_json({
        "type": "text",
        "content": f"✅ **{merchant}** → {category} ({count} Transaktionen aktualisiert)",
    })


async def handle_apply_rule(ws: WebSocket, payload: dict):
    """Apply a single merchant rule (from table row click)."""
    merchant = payload.get("merchant", "")
    category = payload.get("category", "")
    display = payload.get("display", merchant)

    if not merchant or not category:
        return

    count = await apply_rule(merchant, category)

    await ws.send_json({
        "type": "text",
        "content": f"✅ {display} → {category}",
    })
    await ws.send_json({
        "type": "rule_applied",
        "merchant": merchant,
        "category": category,
        "count": count,
    })


async def handle_accept_all(ws: WebSocket, payload: dict):
    """Accept all pending AI suggestions at once."""
    rules = payload.get("rules", [])
    total_count = 0

    for rule in rules:
        merchant = rule.get("merchant", "")
        category = rule.get("category", "")
        if merchant and category:
            count = await apply_rule(merchant, category)
            total_count += count

    await ws.send_json({
        "type": "text",
        "content": f"✅ Alle KI-Vorschläge übernommen ({len(rules)} Händler, {total_count} Transaktionen).",
    })
    await ws.send_json({
        "type": "all_rules_applied",
        "count": len(rules),
    })


async def handle_save(ws: WebSocket, payload: dict):
    """Save selected rules (individual choices from the table)."""
    rules = payload.get("rules", [])
    total_count = 0

    for rule in rules:
        merchant = rule.get("merchant", "")
        category = rule.get("category", "")
        if merchant and category:
            count = await apply_rule(merchant, category)
            total_count += count

    await ws.send_json({
        "type": "text",
        "content": f"✅ **{len(rules)} Händler** gespeichert ({total_count} Transaktionen aktualisiert).",
    })
    await ws.send_json({"type": "learn_saved", "count": len(rules)})
