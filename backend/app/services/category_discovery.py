import json
import re

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.category import Category
from ..models.transaction import CATEGORIES as _DEFAULT_CATEGORIES

# Colors to cycle through for newly discovered categories (distinct from defaults)
_EXTRA_COLORS = [
    "#f43f5e",  # rose
    "#fb923c",  # orange-400
    "#facc15",  # yellow-400
    "#4ade80",  # green-400
    "#2dd4bf",  # teal-400
    "#38bdf8",  # sky-400
    "#c084fc",  # purple-400
    "#f472b6",  # pink-400
    "#a3e635",  # lime-400
    "#34d399",  # emerald-400
]

_DISCOVERY_SYSTEM = """Du analysierst Händlernamen aus einem Kontoauszug, um zu prüfen, ob neue Ausgabenkategorien benötigt werden.

Bestehende Kategorien:
{existing}

Aufgabe: Prüfe die Händlernamen unten und entscheide, ob es Ausgaben gibt, die in KEINE der bestehenden Kategorien passen. Falls ja, schlage neue, kurze und allgemeine Kategorienamen auf Deutsch vor.

Regeln:
- Schlage NUR neue Kategorien vor, wenn die bestehenden wirklich nicht passen
- Kategorienamen: kurz, allgemein, auf Deutsch (z.B. "Tierbedarf", "Haustiere", "Spenden")
- Antworte NUR mit einem JSON-Array von Strings, z.B. ["Tierbedarf"] oder [] wenn keine neuen Kategorien nötig sind"""


async def discover_and_save_categories(
    merchant_names: list[str],
    db: AsyncSession,
) -> list[str]:
    """Ask LLM whether any merchants warrant a new category; persist new ones. Returns full category list."""
    # Load existing categories from DB
    result = await db.execute(select(Category).order_by(Category.id))
    existing: list[Category] = list(result.scalars())
    existing_names = [c.name for c in existing]

    # If the categories table is empty for any reason, fall back to hardcoded defaults
    if not existing_names:
        existing_names = list(_DEFAULT_CATEGORIES)

    if not merchant_names:
        return existing_names

    settings = get_settings()
    if not settings.anthropic_api_key:
        return existing_names

    # Ask LLM for new categories
    sample = merchant_names[:80]  # cap to avoid huge prompts
    merchant_list = "\n".join(f"- {m}" for m in sample)
    system = _DISCOVERY_SYSTEM.format(existing=", ".join(existing_names))

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": f"Händlernamen:\n{merchant_list}"}],
        )
        text = response.content[0].text.strip()
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            return existing_names
        new_names: list[str] = json.loads(json_match.group())
    except Exception:
        return existing_names

    # Filter out duplicates (case-insensitive) and empty strings
    existing_lower = {n.lower() for n in existing_names}
    truly_new = [
        n for n in new_names
        if isinstance(n, str) and n.strip() and n.strip().lower() not in existing_lower
    ]

    if not truly_new:
        return existing_names

    # Assign colors from extra palette, cycling if needed
    used_colors = {c.color for c in existing}
    available = [c for c in _EXTRA_COLORS if c not in used_colors]
    if not available:
        available = _EXTRA_COLORS  # cycle

    added = []
    for i, name in enumerate(truly_new):
        color = available[i % len(available)]
        cat = Category(name=name.strip(), color=color)
        db.add(cat)
        added.append(name.strip())

    await db.flush()  # write without committing (upload handler commits later)
    return existing_names + added
