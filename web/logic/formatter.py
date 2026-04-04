"""Convert raw query data → WebSocket JSON messages (table, chart, text)."""

# Natalie categories to exclude from user-facing analysis
NATALIE_CATS = {"Business Natalie", "Kinder Natalie", "Wohnen Natalie",
                "Einnahmen Natalie"}


def fmt_eur(n: float) -> str:
    return f"{n:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def summary_to_messages(data: dict) -> list[dict]:
    """Dashboard summary → chart + table messages."""
    cats = [c for c in data["categories"] if c["category"] not in NATALIE_CATS]
    total = sum(c["total"] for c in cats)

    chart_data = {
        "labels": [c["category"] for c in cats],
        "datasets": [{
            "data": [round(c["total"], 2) for c in cats],
            "backgroundColor": None,  # client picks colors
            "borderWidth": 0,
        }],
    }

    rows = []
    for c in cats:
        pct = (c["total"] / total * 100) if total else 0
        rows.append([c["category"], round(c["total"], 2), round(pct, 1)])

    return [
        {"type": "chart", "chart_type": "doughnut", "title": "Nach Kategorie",
         "data": chart_data},
        {"type": "table", "columns": ["Kategorie", "Betrag", "Anteil %"],
         "rows": rows, "title": None},
    ]


def comparison_to_messages(data: dict) -> list[dict]:
    """Comparison → table message."""
    all_cats = sorted(
        set(data["current_categories"]) | set(data["previous_categories"])
    )
    cats = [c for c in all_cats if c not in NATALIE_CATS]

    rows = []
    for cat in cats:
        curr = data["current_categories"].get(cat, 0)
        prev = data["previous_categories"].get(cat, 0)
        delta = curr - prev
        rows.append([cat, round(curr, 2), round(prev, 2), round(delta, 2)])

    return [
        {"type": "table",
         "columns": ["Kategorie", data["current_month"], data["previous_month"], "Δ"],
         "rows": rows, "title": "Kategorie-Vergleich"},
    ]


def history_to_messages(data: dict) -> list[dict]:
    """History → bar chart + table."""
    months = data["months"]
    totals = [mt["total"] for mt in data["monthly_totals"]]
    incomes = [mi["total"] - mi["natalie"] for mi in data["monthly_income"]]

    chart_data = {
        "labels": months,
        "datasets": [
            {"label": "Ausgaben", "data": [round(t, 2) for t in totals]},
            {"label": "Einnahmen", "data": [round(i, 2) for i in incomes]},
        ],
    }

    rows = []
    for i, m in enumerate(months):
        t = totals[i]
        inc = incomes[i]
        delta = totals[i] - totals[i - 1] if i > 0 else 0
        balance = inc - t
        rows.append([m, round(t, 2), round(delta, 2), round(inc, 2), round(balance, 2)])

    return [
        {"type": "chart", "chart_type": "bar", "title": "Ausgaben vs. Einnahmen",
         "data": chart_data},
        {"type": "table", "columns": ["Monat", "Ausgaben", "Δ", "Einnahmen", "Bilanz"],
         "rows": rows, "title": None},
    ]


def insights_to_messages(data: dict) -> list[dict]:
    """Insights → insight card messages."""
    messages = []
    items = data.get("items") or data.get("insights") or []
    for item in items:
        messages.append({
            "type": "insight",
            "insight_type": item.get("type", "info"),
            "text": item.get("text", str(item)),
        })
    return messages


def merchants_to_table(merchants: list[dict], suggestions: dict[str, str]) -> dict:
    """Uncategorized merchants → table with AI suggestions."""
    rows = []
    for i, m in enumerate(merchants):
        suggestion = suggestions.get(m["merchant"], "Sonstiges")
        rows.append({
            "idx": i,
            "merchant": m["merchant"],
            "display": m["display"],
            "count": m["count"],
            "suggestion": suggestion,
            "chosen": None,
        })
    return {
        "type": "learn_table",
        "merchants": rows,
        "total": len(rows),
    }
