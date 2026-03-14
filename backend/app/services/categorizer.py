import json
import re
import asyncio
from decimal import Decimal

import anthropic

from ..config import get_settings
from ..models.transaction import CATEGORIES

_SYSTEM_PROMPT_TEMPLATE = """Du bist ein Kategorisierer für Finanztransaktionen. Weise jedem Händlernamen genau eine Kategorie aus dieser Liste zu:
{categories}

Regeln:
- Restaurants, Cafés, Fastfood, Bäckereien → Restaurant
- Supermärkte, Lebensmittelgeschäfte (Edeka, Rewe, Aldi, Lidl usw.) → Lebensmittel
- Netflix, Spotify, Software-Abonnements → Abonnements
- Auto, Werkstatt, Tankstellen, Parken, ÖPNV, Leasing → Mobilität
- Amazon, Kleidung, Elektronik → Einkaufen
- Arzt, Apotheke, Fitnessstudio → Gesundheit
- Miete, Hypothek, WEG → Wohnen
- Strom, Internet, Telefon → Haushalt
- Fluggesellschaften, Hotels → Reisen
- Gehalt, Einnahmen, Erstattungen → Einnahmen
- PayPal-Zahlungen → PayPal
- Kreditkartenabrechnung, Barclays, ABRECHNUNG KARTE → Kreditkarte
- Bei Unsicherheit → Sonstiges

Antworte NUR mit einem JSON-Objekt: {{"Händlername": "Kategorie", ...}}"""


def normalize_merchant(merchant: str) -> str:
    """Lowercase, strip special chars, collapse whitespace."""
    s = merchant.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def categorize_merchants(merchants: list[str], valid_categories: list[str] | None = None) -> dict[str, str]:
    """Categorize a list of unique merchant names via Claude Haiku."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {m: "Sonstiges" for m in merchants}

    if not valid_categories:  # None or empty list
        valid_categories = CATEGORIES

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(categories=", ".join(valid_categories))
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    results = {}

    # Process in batches of 50 (100 entries × ~15 tokens each easily exceeds 1024 tokens)
    batch_size = 50
    for i in range(0, len(merchants), batch_size):
        batch = merchants[i:i + batch_size]
        merchant_list = "\n".join(f"- {m}" for m in batch)

        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Kategorisiere diese Händler:\n{merchant_list}"}
                ],
            )
            text = response.content[0].text.strip()
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                raw = json.loads(json_match.group())
                for merchant, category in raw.items():
                    if category in valid_categories:
                        results[merchant] = category
                    else:
                        results[merchant] = "Sonstiges"
        except Exception as e:
            # Fallback to Sonstiges on any error
            for m in batch:
                if m not in results:
                    results[m] = "Sonstiges"

    # Ensure all merchants have a result
    for m in merchants:
        if m not in results:
            results[m] = "Sonstiges"

    return results
