# Cut the Fat — Chat-Frontend Plan (DRAFT)

> Status: Draft v1 — 2026-04-04

## Context

Die CLI-App ist funktional komplett (Upload, Dashboard, Insights, Learn, Report), aber die Terminal-Bedienung ist für den täglichen Gebrauch umständlich. Ziel: eine Browser-basierte Chat-App, die alle Funktionen über natürliche Konversation zugänglich macht. Der User will Finanztransparenz durch intuitive Analyse und Korrektur.

**Kernidee**: Ein einzelner Chat-Kanal ersetzt alle CLI-Befehle. Der Bot versteht deutsche Eingaben und antwortet mit Text, Tabellen, Charts und Action-Buttons.

---

## Tech Stack

| Komponente | Technologie | Begründung |
|---|---|---|
| HTTP/WebSocket | **FastAPI + Uvicorn** | Async-native, passt perfekt zu bestehenden async Services |
| Frontend | **Vanilla HTML + CSS + JS** | Single-User, kein Build-Step, <1000 Zeilen JS |
| Charts | **Chart.js** (CDN) | Leichtgewichtig, browser-nativ |
| Markdown | **Marked.js** (CDN) | Für formatierte Bot-Antworten |

Kein React/Vue/Svelte — der Overhead lohnt sich nicht bei ~6 Gesprächspfaden und einem Nutzer.

---

## Architektur

```
Browser (localhost:8000)
  ├── GET /                → index.html (Chat-UI)
  ├── WS  /ws/chat         → Haupt-WebSocket (bidirektional)
  └── POST /api/upload      → Datei-Upload (multipart)

web/app.py (FastAPI)
  ├── web/chat_router.py    → Intent-Erkennung (Keyword-Regex)
  ├── web/handlers/          → Ein Handler pro Gesprächspfad
  └── web/services.py        → Async DB-Calls (ruft _-Funktionen aus cli/db.py)

Backend-Services (unverändert)
  ├── backend/app/services/*
  ├── backend/app/models/*
  └── backend/app/database.py
```

**Schlüsselentscheidungen:**
- WebSocket für bidirektionalen Chat (Text + Progress + Buttons)
- File-Upload via REST (nicht über WebSocket — stabiler)
- `web/services.py` ruft die async `_`-Funktionen aus `cli/db.py` direkt auf
- Kein Auth (localhost, Single-User)
- CLI bleibt parallel funktionsfähig

---

## WebSocket-Protokoll

```
Client → Server:
  { "type": "text", "content": "Zeig mir meine Ausgaben" }
  { "type": "action", "action": "set_category", "payload": {...} }
  { "type": "upload_complete", "upload_id": "..." }

Server → Client:
  { "type": "text", "content": "Markdown-Text..." }
  { "type": "table", "columns": [...], "rows": [...], "title": "..." }
  { "type": "chart", "chart_type": "bar|pie|line", "data": {...} }
  { "type": "actions", "prompt": "...", "buttons": [{label, action, payload}] }
  { "type": "progress", "message": "...", "done": false }
```

---

## Gesprächspfade (User Cases)

### 1. Upload & Import
```
User: [Datei per Drag&Drop]
Bot:  ⏳ "Verarbeite Kontoauszug..."
Bot:  ✅ "45 Transaktionen importiert, 3 Duplikate übersprungen"
Bot:  📋 Tabelle: 5 unkategorisierte Händler mit KI-Vorschlägen
Bot:  🔘 Buttons pro Händler: [Shopping] [Essen & Trinken] [Sonstiges]
User: [Klickt Buttons oder "Alle annehmen"]
Bot:  ✅ "5 Händler kategorisiert, 23 Transaktionen aktualisiert"
```

### 2. Ausgabenübersicht
```
User: "Zeig mir meine Ausgaben"
Bot:  📊 Pie-Chart: Kategorien des aktuellen Monats
Bot:  📋 Tabelle: Kategorie | Betrag | Anteil
Bot:  "Gesamtausgaben: 2.345,67 € (+12% vs. Vormonat)"

User: "Vergleich mit letztem Monat"
Bot:  📋 Vergleichstabelle mit ▲/▼ Deltas

User: "Letzte 6 Monate"
Bot:  📊 Balkendiagramm: Monatstrend
Bot:  📋 Monatstabelle: Monat | Ausgaben | Δ | Einnahmen | Bilanz
```

### 3. Kategorien korrigieren
```
User: "Ändere Amazon zu Shopping"
Bot:  ✅ "12 Transaktionen von 'amazon' → Shopping umkategorisiert"

User: "Zeig unkategorisierte Händler"
Bot:  📋 Tabelle + Buttons pro Händler
User: [Klickt Kategorie-Buttons]
Bot:  ✅ Bestätigung pro Änderung
```

### 4. Sparempfehlungen
```
User: "Wo kann ich sparen?"
Bot:  💡 5 KI-Empfehlungen mit konkreten €-Beträgen
      (⚠ Warnungen, ℹ Infos, ✅ Erfolge)

User: "Neu generieren"
Bot:  ⏳ → 💡 Frische Analyse
```

### 5. Bericht
```
User: "Bericht für März"
Bot:  📄 Markdown-Bericht inline + Download-Link
Bot:  "Gespeichert: analytics/2026-03.md"

User: "Alle Berichte"
Bot:  ⏳ Progress → ✅ Liste der generierten Dateien
```

### 6. Exploration (NEU — nur im Web)
```
User: "Was habe ich bei REWE ausgegeben?"
Bot:  📋 Tabelle: Datum | Betrag | Kategorie (letzte 20 Txn)
Bot:  "Gesamt: 456,78 € in 23 Transaktionen"

User: "Wieviel für Essen & Trinken dieses Jahr?"
Bot:  📊 Liniendiagramm: Monatsvergleich
Bot:  "Gesamt 2026: 1.234,56 € (Ø 205,76 €/Monat)"
```

### 7. Willkommen & Hilfe
```
[App-Start]
Bot:  "✂ Cut the Fat — Was möchtest du tun?"
Bot:  🔘 [Ausgaben anzeigen] [Datei importieren] [Sparempfehlungen] [Kategorien prüfen]

User: "Hilfe"
Bot:  Übersicht aller Funktionen mit Beispiel-Eingaben
```

---

## Neue Dateien

```
web/
├── __init__.py
├── app.py                 # FastAPI: routes, static files, startup
├── chat_router.py         # Intent-Regex-Matcher → Handler-Dispatch
├── ws_manager.py          # WebSocket-Verbindung verwalten
├── services.py            # Ruft cli/db.py async-Funktionen + neue Queries
├── handlers/
│   ├── __init__.py
│   ├── upload.py          # POST /api/upload + Chat-Follow-up
│   ├── dashboard.py       # Summary, Vergleich, Historie → Tabellen + Charts
│   ├── insights.py        # KI-Empfehlungen
│   ├── learn.py           # Unkategorisierte Händler + Buttons
│   ├── report.py          # Bericht generieren + anzeigen
│   └── explore.py         # Händler/Kategorie-Suche (NEUE Queries)
└── static/
    ├── index.html         # Single-Page Chat-UI
    ├── style.css          # Chat-Styling (responsive)
    └── chat.js            # WebSocket-Client, Rendering, Drag&Drop
ctf-web                    # Shell-Launcher: uvicorn web.app:app
```

---

## Intent-Erkennung (chat_router.py)

Einfacher Regex-Matcher — kein NLP nötig bei 7 klar abgegrenzten Pfaden:

```python
INTENTS = {
    "dashboard":     [r"ausgaben", r"übersicht", r"dashboard", r"zeig.*monat"],
    "compare":       [r"vergleich", r"vs\.?\s*vormonat", r"letzt.*monat"],
    "history":       [r"letzte.*\d+.*monat", r"trend", r"verlauf"],
    "insights":      [r"spar", r"empfehlung", r"tipp", r"wo kann ich"],
    "learn":         [r"unkategorisiert", r"kategorisieren", r"lernen"],
    "report":        [r"bericht", r"report"],
    "recategorize":  [r"änder.*zu\s", r"kategorie.*ändern"],
    "explore":       [r"was hab.*bei", r"wieviel.*für", r"suche"],
    "help":          [r"hilfe", r"help", r"was kannst"],
}
```

Bei mehrdeutiger Eingabe: Rückfrage mit Buttons.

---

## Implementierungsphasen

### Phase 1: Grundgerüst + Dashboard
- `web/app.py` — FastAPI, Static Files, WebSocket-Endpoint
- `web/ws_manager.py` — Single-Connection Manager
- `web/services.py` — Wrapper über `cli/db.py` async-Funktionen
- `web/chat_router.py` — Intent-Matcher
- `web/handlers/dashboard.py` — Summary + Vergleich + Historie
- `web/static/` — Chat-UI mit Text + Tabellen-Rendering
- `ctf-web` Launcher

**Ergebnis:** "Zeig mir meine Ausgaben" → formatierte Tabelle im Browser

### Phase 2: Upload + Kategorien
- `POST /api/upload` Endpoint
- `web/handlers/upload.py` — Verarbeitung + Progress
- `web/handlers/learn.py` — Unkategorisierte Händler + Action-Buttons
- Drag&Drop + Button-Rendering im Frontend
- Recategorize-Handler ("Ändere X zu Y")

**Ergebnis:** Kontoauszug importieren + Händler kategorisieren via Chat

### Phase 3: Charts + Insights + Exploration
- Chart.js Integration (Pie, Bar, Line)
- `web/handlers/insights.py` — KI-Empfehlungen
- `web/handlers/explore.py` — Neue Queries (Händler-Suche, Kategorie-Drill-down)
- Charts in Dashboard + Historie einbauen

**Ergebnis:** Visuelle Analyse + KI-Sparempfehlungen

### Phase 4: Reports + Polish
- `web/handlers/report.py` — Markdown-Bericht + Download
- Willkommensnachricht + Quick-Action-Buttons
- Konversations-Kontext (letzter besprochener Monat merken)
- Mobile-responsive CSS
- Deutsche Fehlermeldungen

**Ergebnis:** Feature-complete Chat-App

---

## Kritische Dateien (zu modifizieren)

| Datei | Änderung |
|---|---|
| `cli/db.py` | Async-Funktionen exportierbar machen (ggf. `_` Prefix entfernen oder `__all__` setzen) |
| `cli/__init__.py` | sys.path Setup — muss auch für web/ funktionieren |
| `CLAUDE.md` | "Kein FastAPI" Regel aktualisieren |
| `backend/requirements.txt` | `fastapi`, `uvicorn`, `websockets` hinzufügen (falls nicht schon vorhanden) |

## Zu wiederverwendende Funktionen

| Funktion | Datei | Verwendung |
|---|---|---|
| `_get_summary()` | `cli/db.py:83` | Dashboard |
| `_get_comparison()` | `cli/db.py:126` | Vergleich |
| `_get_history()` | `cli/db.py:250` | Trend |
| `_get_insights_data()` | `cli/db.py:169` | Insights |
| `_ingest_file()` | `cli/db.py:330` | Upload |
| `_apply_rule()` | `cli/db.py:202` | Kategorie-Korrektur |
| `_get_uncategorized_merchants()` | `cli/db.py:181` | Learn |
| `_get_ai_suggestions()` | `cli/db.py:225` | KI-Vorschläge |
| `_get_all_categories()` | `cli/db.py:235` | Kategorie-Liste |
| `fmt_eur()` | `cli/render/terminal.py` | €-Formatierung |

---

## Verifikation

1. `./ctf-web` starten → Browser öffnet `localhost:8000`
2. "Zeig mir meine Ausgaben" tippen → Tabelle + Chart erscheint
3. Datei per Drag&Drop hochladen → Import-Bestätigung + Kategorisierungs-Buttons
4. Buttons klicken → Kategorie wird gespeichert
5. "Wo kann ich sparen?" → KI-Empfehlungen erscheinen
6. `./ctf dashboard` parallel testen → CLI funktioniert weiterhin
7. Mobile-Ansicht im DevTools prüfen
