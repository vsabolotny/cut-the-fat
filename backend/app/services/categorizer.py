import json
import re
import asyncio
from decimal import Decimal

import anthropic

from ..config import get_settings
from ..models.transaction import CATEGORIES

SYSTEM_PROMPT = """You are a financial transaction categorizer. Given merchant names, assign each to exactly one category from this list:
Housing, Groceries, Dining, Transportation, Entertainment, Health, Shopping, Subscriptions, Travel, Education, Utilities, Insurance, Income, Transfers, Other

Rules:
- Restaurants, cafes, fast food → Dining
- Supermarkets, grocery stores → Groceries
- Netflix, Spotify, software subscriptions → Subscriptions
- Uber, Lyft, gas stations, parking → Transportation
- Amazon, clothing, electronics → Shopping
- Doctor, pharmacy, gym → Health
- Rent, mortgage → Housing
- Electricity, internet, phone bills → Utilities
- Airlines, hotels → Travel
- Income, salary, refunds → Income
- Bank transfers, ATM → Transfers
- If uncertain → Other

Respond ONLY with a JSON object: {"merchant_name": "Category", ...}"""


def normalize_merchant(merchant: str) -> str:
    """Lowercase, strip special chars, collapse whitespace."""
    s = merchant.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def categorize_merchants(merchants: list[str]) -> dict[str, str]:
    """Categorize a list of unique merchant names via Claude Haiku."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {m: "Other" for m in merchants}

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    results = {}

    # Process in batches of 100
    batch_size = 100
    for i in range(0, len(merchants), batch_size):
        batch = merchants[i:i + batch_size]
        merchant_list = "\n".join(f"- {m}" for m in batch)

        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": f"Categorize these merchants:\n{merchant_list}"}
                ],
            )
            text = response.content[0].text.strip()
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                raw = json.loads(json_match.group())
                for merchant, category in raw.items():
                    if category in CATEGORIES:
                        results[merchant] = category
                    else:
                        results[merchant] = "Other"
        except Exception as e:
            # Fallback to Other on any error
            for m in batch:
                if m not in results:
                    results[m] = "Other"

    # Ensure all merchants have a result
    for m in merchants:
        if m not in results:
            results[m] = "Other"

    return results
