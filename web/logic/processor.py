"""Intent detection + dispatch to handlers."""
import re
from fastapi import WebSocket

from web.handlers import dashboard, compare, history, insights, learn, report, explore

# German month names → month number
MONTH_NAMES = {
    "januar": "01", "februar": "02", "märz": "03", "maerz": "03",
    "april": "04", "mai": "05", "juni": "06", "juli": "07",
    "august": "08", "september": "09", "oktober": "10",
    "november": "11", "dezember": "12",
    "jan": "01", "feb": "02", "mär": "03", "mar": "03",
    "apr": "04", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "okt": "10", "nov": "11", "dez": "12",
}

# Regex to extract month from free text: "2026-01", "Januar", "Januar 2026", "01/2026"
_MONTH_RE = re.compile(
    r"(?P<iso>\d{4}-\d{2})"                             # 2026-01
    r"|(?P<slash>\d{1,2}/\d{4})"                         # 01/2026
    r"|(?P<name>" + "|".join(MONTH_NAMES.keys()) + r")"  # Januar, Feb, ...
    r"(?:\s+(?P<year>\d{4}))?",                           # optional year after name
    re.I,
)


def extract_month(text: str) -> str | None:
    """Try to extract a YYYY-MM month string from user input."""
    m = _MONTH_RE.search(text)
    if not m:
        return None
    if m.group("iso"):
        return m.group("iso")
    if m.group("slash"):
        parts = m.group("slash").split("/")
        return f"{parts[1]}-{int(parts[0]):02d}"
    if m.group("name"):
        name = m.group("name").lower()
        mon = MONTH_NAMES.get(name)
        if mon:
            year = m.group("year") or "2026"  # default to current year
            return f"{year}-{mon}"
    return None


# Named-group patterns for intent detection
INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("dashboard",      re.compile(r"ausgaben|übersicht|dashboard|zeig.*monat", re.I)),
    ("compare",        re.compile(r"vergleich|vs\.?\s*vor", re.I)),
    ("history",        re.compile(r"letzte\s*(?P<months>\d+)?\s*monat|trend|verlauf|historie", re.I)),
    ("insights",       re.compile(r"spar|empfehlung|tipp|wo kann ich|insight", re.I)),
    ("learn",          re.compile(r"unkategorisiert|kategorisieren|lernen|kategorien", re.I)),
    ("report",         re.compile(r"bericht(?:\s+(?:für\s+)?(?P<month>\w+))?|report", re.I)),
    ("recategorize",   re.compile(r"änder[e]?\s+(?P<merchant>.+?)\s+zu\s+(?P<category>.+)", re.I)),
    ("explore_merchant", re.compile(r"was hab.*bei\s+(?P<merchant>.+?)(?:\s+ausgegeben)?$", re.I)),
    ("explore_category", re.compile(r"wieviel\s+(?:für\s+)?(?P<category>.+?)(?:\s+dieses\s+jahr)?$", re.I)),
    ("help",           re.compile(r"hilfe|help|was kannst|hallo|hi\b|hey\b", re.I)),
]

HANDLERS = {
    "dashboard": dashboard.handle,
    "compare": compare.handle,
    "history": history.handle,
    "insights": insights.handle,
    "learn": learn.handle,
    "report": report.handle,
    "recategorize": learn.handle_recategorize,
    "explore_merchant": explore.handle_merchant,
    "explore_category": explore.handle_category,
}


def detect_intent(text: str) -> tuple[str | None, dict]:
    """Return (intent_name, extracted_params) or (None, {})."""
    t = text.strip()
    for name, pattern in INTENT_PATTERNS:
        m = pattern.search(t)
        if m:
            params = {k: v for k, v in m.groupdict().items() if v is not None}
            return name, params
    return None, {}


async def process_message(ws: WebSocket, data: dict):
    """Route incoming WS message to the right handler."""
    msg_type = data.get("type")

    if msg_type == "action":
        action = data.get("action")
        payload = data.get("payload", {})
        if action == "apply_rule":
            await learn.handle_apply_rule(ws, payload)
        elif action == "accept_all_suggestions":
            await learn.handle_accept_all(ws, payload)
        elif action == "save_rules":
            await learn.handle_save(ws, payload)
        return

    text = data.get("content", "").strip()
    if not text:
        return

    context = data.get("context", {})
    intent, params = detect_intent(text)

    # Extract month from free text and inject into context
    month = extract_month(text)
    if month:
        context["month"] = month

    if intent == "help":
        await ws.send_json({
            "type": "text",
            "content": "✂ Das kann ich: Ausgaben, Vergleich, Trend, Spartipps, Kategorien prüfen, Bericht, Händler/Kategorie-Suche. Tippe einfach los!",
        })
        return

    if intent and intent in HANDLERS:
        handler = HANDLERS[intent]
        await handler(ws, params=params, context=context)
    else:
        await ws.send_json({
            "type": "text",
            "content": f'Ich habe „{text}" nicht verstanden. Versuche z.B. „Zeig mir meine Ausgaben" oder „Wo kann ich sparen?"',
        })
        await ws.send_json({
            "type": "actions",
            "buttons": [
                {"label": "📊 Ausgaben", "action": "send", "payload": {"text": "Zeig mir meine Ausgaben"}},
                {"label": "💡 Spartipps", "action": "send", "payload": {"text": "Wo kann ich sparen?"}},
                {"label": "🏷 Kategorien", "action": "send", "payload": {"text": "Unkategorisierte Händler"}},
            ],
        })
