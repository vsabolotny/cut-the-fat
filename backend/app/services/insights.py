import json
import hashlib
import re
from datetime import datetime, date
from decimal import Decimal

import anthropic
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.insights_cache import InsightsCache
from ..models.transaction import Transaction

INSIGHTS_SYSTEM = """You are a personal finance advisor analyzing someone's spending data.
Generate 5 specific, actionable cost-cutting insights based on the spending data provided.

Format each insight as a JSON object with:
- "id": unique string (insight_1, insight_2, etc.)
- "text": the insight in plain language (1-2 sentences, specific amounts/percentages)
- "type": "warning" (high spend), "info" (observation), or "success" (positive trend)

Return ONLY a JSON array of 5 insight objects. Be specific with dollar amounts and percentages."""


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def _get_aggregated_data(db: AsyncSession) -> dict:
    """Aggregate last 3 months of spending for insights."""
    from sqlalchemy import text

    # Get monthly category totals for last 6 months
    result = await db.execute(
        text("""
            SELECT
                strftime('%Y-%m', date) as month,
                category,
                SUM(amount) as total
            FROM transactions
            WHERE type = 'debit'
              AND date >= date('now', '-6 months')
            GROUP BY month, category
            ORDER BY month DESC
        """)
    )
    monthly_cats = [{"month": r[0], "category": r[1], "total": float(r[2])} for r in result]

    # Top merchants by spend in last 3 months
    result = await db.execute(
        text("""
            SELECT
                merchant_normalized,
                category,
                COUNT(*) as count,
                SUM(amount) as total
            FROM transactions
            WHERE type = 'debit'
              AND date >= date('now', '-3 months')
            GROUP BY merchant_normalized, category
            ORDER BY total DESC
            LIMIT 20
        """)
    )
    top_merchants = [
        {"merchant": r[0], "category": r[1], "count": r[2], "total": float(r[3])}
        for r in result
    ]

    # Subscription-like merchants (appeared every month for 3+ months)
    result = await db.execute(
        text("""
            SELECT
                merchant_normalized,
                COUNT(DISTINCT strftime('%Y-%m', date)) as months,
                AVG(amount) as avg_amount
            FROM transactions
            WHERE type = 'debit'
              AND date >= date('now', '-6 months')
            GROUP BY merchant_normalized
            HAVING months >= 3
            ORDER BY months DESC, avg_amount DESC
            LIMIT 15
        """)
    )
    recurring = [
        {"merchant": r[0], "months": r[1], "avg_amount": float(r[2])}
        for r in result
    ]

    return {
        "monthly_categories": monthly_cats,
        "top_merchants": top_merchants,
        "recurring_charges": recurring,
    }


async def get_insights(db: AsyncSession, force: bool = False) -> dict:
    """Return cached or freshly generated insights."""
    settings = get_settings()

    data = await _get_aggregated_data(db)
    data_json = json.dumps(data, sort_keys=True, default=_decimal_default)
    data_hash = hashlib.sha256(data_json.encode()).hexdigest()

    if not force:
        cached = await db.get(InsightsCache, data_hash)
        if cached:
            return {
                "insights": json.loads(cached.content),
                "generated_at": cached.generated_at,
                "cached": True,
            }

    # No data yet — return placeholder insights
    if not data["monthly_categories"]:
        return {
            "insights": [
                {
                    "id": "insight_1",
                    "text": "Upload your first bank statement to get personalized cost-cutting insights.",
                    "type": "info",
                }
            ],
            "generated_at": datetime.utcnow(),
            "cached": False,
        }

    if not settings.anthropic_api_key:
        insights = _generate_rule_based_insights(data)
        return {"insights": insights, "generated_at": datetime.utcnow(), "cached": False}

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=INSIGHTS_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Here is my spending data for the last 6 months:\n\n{data_json}\n\nGenerate 5 specific cost-cutting insights.",
                }
            ],
        )
        text = response.content[0].text.strip()
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if json_match:
            insights = json.loads(json_match.group())
        else:
            insights = _generate_rule_based_insights(data)
    except Exception:
        insights = _generate_rule_based_insights(data)

    # Cache the result
    existing = await db.get(InsightsCache, data_hash)
    if existing:
        existing.content = json.dumps(insights)
        existing.generated_at = datetime.utcnow()
    else:
        cache_entry = InsightsCache(
            data_hash=data_hash,
            content=json.dumps(insights),
            generated_at=datetime.utcnow(),
        )
        db.add(cache_entry)
    await db.commit()

    return {"insights": insights, "generated_at": datetime.utcnow(), "cached": False}


def _generate_rule_based_insights(data: dict) -> list[dict]:
    """Fallback rule-based insights when no API key is set."""
    insights = []
    monthly = data.get("monthly_categories", [])

    if monthly:
        # Find highest spending category
        totals: dict[str, float] = {}
        for row in monthly:
            totals[row["category"]] = totals.get(row["category"], 0) + row["total"]

        if totals:
            top_cat = max(totals, key=lambda k: totals[k])
            insights.append({
                "id": "insight_1",
                "text": f"Your highest spending category is {top_cat} (${totals[top_cat]:.2f} over the tracked period). Look for opportunities to reduce costs here.",
                "type": "warning",
            })

    recurring = data.get("recurring_charges", [])
    if recurring:
        total_recurring = sum(r["avg_amount"] for r in recurring)
        insights.append({
            "id": "insight_2",
            "text": f"You have {len(recurring)} recurring charges totaling ~${total_recurring:.2f}/month. Review these to cancel unused services.",
            "type": "warning",
        })

    top_merchants = data.get("top_merchants", [])
    subscription_merchants = [m for m in top_merchants if m["category"] == "Subscriptions"]
    if subscription_merchants:
        sub_total = sum(m["total"] for m in subscription_merchants)
        insights.append({
            "id": "insight_3",
            "text": f"You're spending ${sub_total:.2f} on subscriptions. Consider auditing each service to see which ones you actively use.",
            "type": "info",
        })

    dining_merchants = [m for m in top_merchants if m["category"] == "Dining"]
    if dining_merchants:
        dining_total = sum(m["total"] for m in dining_merchants)
        insights.append({
            "id": "insight_4",
            "text": f"Dining out accounts for ${dining_total:.2f} in recent months. Cooking at home more often could significantly reduce this.",
            "type": "info",
        })

    if len(insights) < 5:
        insights.append({
            "id": "insight_5",
            "text": "Upload more months of statements to get deeper trend analysis and more personalized insights.",
            "type": "info",
        })

    return insights[:5]
