# Cut the Fat — Chat-Frontend Plan (DRAFT v2)

> Status: Draft v2 — 2026-04-04
> Changelog v1 → v2: State Management, WS-Reconnect, Named Groups in Intent-Erkennung, Progressive Disclosure, Pinned Dashboard, Upload Job-ID Pattern, Sicherheit, Refactoring cli/db.py, Dateistruktur überarbeitet

## Context

Die CLI-App ist funktional komplett (Upload, Dashboard, Insights, Learn, Report), aber die Terminal-Bedienung ist für den täglichen Gebrauch umständlich. Ziel: eine Browser-basierte Chat-App, die alle Funktionen über natürliche Konversation zugänglich macht. Der User will Finanztransparenz durch intuitive Analyse und Korrektur.

**Kernidee**: Ein einzelner Chat-Kanal ersetzt alle CLI-Befehle. Der Bot versteht deutsche Eingaben und antwortet mit Text, Tabellen, Charts und Action-Buttons.

---

## Tech Stack

| Komponente | Technologie | Begründung |
|---|---|---|
| HTTP/WebSocket | **FastAPI + Uvicorn** (bind `127.0.0.1`) | Async-native, passt zu bestehenden async Services |
| Frontend | **Vanilla HTML + JS** | Single-User, kein Build-Step |
| CSS | **Pico.css** (CDN) + custom overrides | Minimalistisches System-Design, Dark Mode out-of-the-box, spart ~400 Zeilen CSS |
| Charts | **Chart.js** (CDN) | Leichtgewichtig, browser-nativ |
| Markdown | **Marked.js** (CDN) | Für formatierte Bot-Antworten |

Kein React/Vue/Svelte — der Overhead lohnt sich nicht bei ~7 Gesprächspfaden und einem Nutzer.

---

## Architektur

```
Browser (localhost:8080)
  ├── GET /                → index.html (Chat-UI)
  ├── WS  /ws/chat         → Haupt-WebSocket (bidirektional, Auto-Reconnect)
  └── POST /api/upload      → Datei-Upload (multipart) → gibt job_id zurück

web/app.py (FastAPI, bind 127.0.0.1 only)
  ├── web/logic/
  │   ├── processor.py      → Intent-Erkennung + Dispatch (Named Groups)
  │   └── formatter.py      → Rohdaten → Chat-JSON (Table/Chart/Actions)
  ├── web/handlers/          → Ein Handler pro Gesprächspfad
  └── web/data.py            → Async Daten-Layer (getrennt von CLI-Formatierung)

Shared Data Layer (NEU — Refactoring)
  ├── backend/app/queries.py → Reine Daten-Funktionen (Dicts/Lists, kein ANSI)
  
Backend-Services (unverändert)
  ├── backend/app/services/*
  ├── backend/app/models/*
  └── backend/app/database.py
```

### Schlüsselentscheidungen

- **WebSocket mit Auto-Reconnect + Heartbeat** — Laptop Sleep/Wake überlebt die Verbindung. Client sendet alle 30s ein Ping, reconnectet bei Timeout automatisch.
- **File-Upload via REST mit `job_id`** — `POST /api/upload` gibt sofort `{ "job_id": "..." }` zurück. Der Server sendet anschließend Progress-Updates über den WebSocket-Kanal mit dieser `job_id`. Kein UI-Freeze bei großen Dateien.
- **Client-Side State via `data-*` Attribute** — `#app` speichert `data-current-month`, `data-last-intent`, etc. Folgefragen wie "Vergleich" nutzen automatisch den zuletzt angezeigten Monat.
- **Localhost-only** — Uvicorn bindet auf `127.0.0.1`, nicht auf `0.0.0.0`. Kein Auth nötig.
- **CLI bleibt parallel funktionsfähig** — beide nutzen denselben Daten-Layer.

---

## Refactoring: Daten vs. Darstellung trennen

### Problem
`cli/db.py` enthält Daten-Funktionen (`_get_summary()`, `_get_comparison()`, etc.), die rohe Dicts zurückgeben — das ist gut. Aber die `cli/render/terminal.py` Schicht formatiert diese direkt mit Rich/ANSI. Das Web-Frontend braucht dieselben Rohdaten, aber als Chart.js/Table-JSON.

### Lösung
1. **`backend/app/queries.py`** (NEU) — Extrahiere die reinen DB-Query-Funktionen aus `cli/db.py` hierhin. Rückgabewerte sind immer `dict`/`list` — keine Formatierung, kein ANSI.
2. **`cli/db.py`** — Wird zum dünnen Wrapper: importiert aus `queries.py`, wrappet mit `asyncio.run()` für die CLI.
3. **`web/data.py`** — Importiert direkt aus `queries.py`, ruft async-Funktionen nativ auf (kein `asyncio.run()`).
4. **`web/logic/formatter.py`** — Konvertiert Rohdaten in Chat-JSON-Nachrichten (Table, Chart, Text).

```
queries.py (Rohdaten)
  ├── cli/db.py → asyncio.run() → cli/render/terminal.py (Rich)
  └── web/data.py → async nativ → web/logic/formatter.py (JSON)
```

---

## WebSocket-Protokoll

```
Client → Server:
  { "type": "text", "content": "Zeig mir meine Ausgaben" }
  { "type": "text", "content": "Vergleich", "context": { "month": "2026-03" } }
  { "type": "action", "action": "set_category", "payload": {...} }
  { "type": "upload_complete", "job_id": "abc-123" }
  { "type": "ping" }

Server → Client:
  { "type": "text", "content": "Markdown-Text..." }
  { "type": "table", "columns": [...], "rows": [...], "title": "...", "total_rows": 45 }
  { "type": "chart", "chart_type": "bar|pie|line", "data": {...} }
  { "type": "actions", "prompt": "...", "buttons": [{label, action, payload}] }
  { "type": "progress", "job_id": "abc-123", "message": "...", "done": false }
  { "type": "pinned", "content_type": "chart|table", "data": {...} }
  { "type": "pong" }
```

Neu in v2:
- `context` Feld — Client schickt aktuellen Kontext (Monat, letzter Intent) mit
- `job_id` — verknüpft Upload-Progress mit der REST-Antwort
- `total_rows` — ermöglicht "Mehr anzeigen..." Button
- `pinned` — Dashboard/Chart bleibt oben fixiert
- `ping`/`pong` — Heartbeat für Verbindungsstabilität

---

## Intent-Erkennung (processor.py)

### Regex mit Named Groups

```python
INTENT_PATTERNS = {
    "dashboard":     [r"ausgaben", r"übersicht", r"dashboard", r"zeig.*monat"],
    "compare":       [r"vergleich", r"vs\.?\s*vormonat"],
    "history":       [r"letzte\s+(?P<months>\d+)\s*monat", r"trend", r"verlauf"],
    "insights":      [r"spar", r"empfehlung", r"tipp", r"wo kann ich"],
    "learn":         [r"unkategorisiert", r"kategorisieren", r"lernen"],
    "report":        [r"bericht(?:\s+(?:für\s+)?(?P<month>\w+))?", r"report"],
    "recategorize":  [r"änder[e]?\s+(?P<merchant>.+?)\s+zu\s+(?P<category>.+)"],
    "explore_merchant": [r"was hab.*bei\s+(?P<merchant>.+?)(\s+ausgegeben)?$"],
    "explore_category": [r"wieviel\s+(?:für\s+)?(?P<category>.+?)(\s+dieses\s+jahr)?$"],
    "help":          [r"hilfe", r"help", r"was kannst", r"hallo", r"hi\b", r"hey"],
}
```

### Kontext-Auflösung
1. Regex matcht Intent + extrahiert Parameter (Monat, Händler, Kategorie)
2. Fehlende Parameter werden aus Client-Context (`data-current-month`) aufgefüllt
3. Folgefragen ("Vergleich") nutzen den Monat des letzten Dashboard-Aufrufs

### Fallback-Strategie
Wenn kein Intent matcht → **immer** Quick-Action-Buttons anzeigen:
```
Bot: "Ich bin nicht sicher, was du meinst. Meintest du eines davon?"
Bot: 🔘 [Ausgaben] [Spartipps] [Kategorien] [Hilfe]
```
Niemals eine nackte Fehlermeldung.

---

## Gesprächspfade (User Cases)

### 1. Upload & Import
```
User: [Datei per Drag&Drop]
Bot:  ⏳ "Verarbeite Kontoauszug..." (Progress via job_id über WS)
Bot:  ⏳ "KI kategorisiert 17 Händler..."
Bot:  ✅ "45 Transaktionen importiert, 3 Duplikate übersprungen"
Bot:  📋 Top 5 unkategorisierte Händler mit KI-Vorschlägen + Buttons
Bot:  🔘 [Alle KI-Vorschläge annehmen] [Mehr anzeigen... (12 weitere)]
User: [Klickt "Alle annehmen" oder einzelne Buttons]
Bot:  ✅ "17 Händler kategorisiert, 38 Transaktionen aktualisiert"
```

**Progressive Disclosure**: Nur Top 5 sofort sichtbar. "Mehr anzeigen..." lädt die nächsten 10 nach. Verhindert endlos langen Chat.

### 2. Ausgabenübersicht
```
User: "Zeig mir meine Ausgaben"
Bot:  📌 PINNED: Pie-Chart + Gesamt oben fixiert
Bot:  📋 Tabelle: Kategorie | Betrag | Anteil (Top 10, "Mehr anzeigen...")
Bot:  "Gesamtausgaben: 2.345,67 € (+12% vs. Vormonat)"
      → setzt data-current-month="2026-03"

User: "Vergleich"
      → nutzt automatisch 2026-03 aus Context
Bot:  📋 Vergleichstabelle mit ▲/▼ Deltas

User: "Letzte 6 Monate"
Bot:  📌 PINNED: Balkendiagramm (ersetzt vorheriges Pinned)
Bot:  📋 Monatstabelle: Monat | Ausgaben | Δ | Einnahmen | Bilanz
```

**Pinned Messages**: Dashboard-Chart bleibt oben im Chat fixiert, während man darunter weiter chattet. Wird erst durch ein neues Dashboard/Chart ersetzt.

### 3. Kategorien korrigieren
```
User: "Ändere Amazon zu Shopping"
      → Named Groups: merchant="Amazon", category="Shopping"
Bot:  ✅ "12 Transaktionen von 'amazon' → Shopping umkategorisiert"

User: "Zeig unkategorisierte Händler"
Bot:  📋 Top 5 Händler + Buttons pro Zeile
Bot:  🔘 [Mehr anzeigen... (8 weitere)]
User: [Klickt Kategorie-Buttons]
Bot:  ✅ Bestätigung pro Änderung
```

### 4. Sparempfehlungen
```
User: "Wo kann ich sparen?"
Bot:  ⏳ "KI analysiert deine Ausgaben..." (Progress über WS)
Bot:  💡 5 KI-Empfehlungen mit konkreten €-Beträgen
      (⚠ Warnungen, ℹ Infos, ✅ Erfolge)

User: "Neu generieren"
Bot:  ⏳ → 💡 Frische Analyse (Cache ignoriert)
```

### 5. Bericht
```
User: "Bericht für März"
      → Named Group: month="März" → aufgelöst zu "2026-03"
Bot:  📄 Markdown-Bericht inline + Download-Link
Bot:  "Gespeichert: analytics/2026-03.md"

User: "Alle Berichte"
Bot:  ⏳ Progress pro Monat → ✅ Liste der generierten Dateien
```

### 6. Exploration
```
User: "Was habe ich bei REWE ausgegeben?"
      → Named Group: merchant="REWE"
Bot:  📋 Tabelle: Datum | Betrag | Kategorie (Top 10)
Bot:  🔘 [Mehr anzeigen... (13 weitere)]
Bot:  "Gesamt: 456,78 € in 23 Transaktionen"

User: "Wieviel für Essen & Trinken dieses Jahr?"
      → Named Group: category="Essen & Trinken"
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

## UI/UX Design-Prinzipien

### Pinned Messages
- Dashboard-Charts und -Tabellen werden als "Pinned" oben im Chat fixiert
- Nur 1 Pinned-Element gleichzeitig — neues ersetzt altes
- User kann Pinned schließen (X-Button)
- Pinned scrollt nicht mit dem Chat mit

### Progressive Disclosure
- Tabellen zeigen initial max. 5-10 Zeilen
- "Mehr anzeigen..." Button lädt nächste Seite
- Verhindert Chat-Überflutung bei 45+ Transaktionen
- `total_rows` im Protokoll ermöglicht dem Client die Anzeige von "5 von 45"

### Kontext-Speicherung (Client-Side State)
```html
<div id="app"
  data-current-month="2026-03"
  data-last-intent="dashboard"
  data-last-merchant="">
```
- Wird bei jedem Bot-Response aktualisiert
- Client schickt relevanten Context im `context`-Feld der WebSocket-Nachricht mit
- Ermöglicht natürliche Folgefragen ohne Parameter-Wiederholung

---

## Neue Dateien

```
web/
├── __init__.py
├── app.py                    # FastAPI: routes, static files, WS-endpoint, 127.0.0.1 bind
├── ws_manager.py             # WebSocket: connection, heartbeat, auto-reconnect handling
├── data.py                   # Async Daten-Layer (importiert aus queries.py)
├── logic/
│   ├── __init__.py
│   ├── processor.py          # Intent-Erkennung (Named Groups) + Dispatch
│   └── formatter.py          # Rohdaten → Chat-JSON (Table/Chart/Actions/Pinned)
├── handlers/
│   ├── __init__.py
│   ├── upload.py             # POST /api/upload (job_id) + WS-Progress
│   ├── dashboard.py          # Summary, Vergleich, Historie → Pinned Charts + Tabellen
│   ├── insights.py           # KI-Empfehlungen
│   ├── learn.py              # Unkategorisierte Händler + Progressive Disclosure
│   ├── report.py             # Bericht generieren + Download
│   └── explore.py            # Händler/Kategorie-Suche
└── static/
    ├── index.html            # Chat-UI mit Pinned-Area + Drop-Zone
    ├── style.css             # Pico.css overrides + Chat-spezifische Styles
    └── chat.js               # WS-Client (reconnect, heartbeat), Rendering, State

backend/app/
├── queries.py                # NEU: Reine async DB-Queries (Rohdaten, kein ANSI)

ctf-web                       # Shell-Launcher: uvicorn web.app:app --host 127.0.0.1
```

---

## Implementierungsphasen

### Phase 0: Refactoring (Vorarbeit)
- **`backend/app/queries.py`** erstellen — DB-Query-Funktionen aus `cli/db.py` extrahieren
- **`cli/db.py`** umschreiben — importiert aus `queries.py`, behält sync-Wrapper
- Tests: CLI funktioniert identisch wie vorher
- `CLAUDE.md` aktualisieren: "Kein FastAPI" → "Web-UI unter web/, CLI bleibt Einstiegspunkt"

**Ergebnis:** Saubere Trennung Daten ↔ Darstellung, Web kann Daten-Layer direkt nutzen

### Phase 1: Grundgerüst + Dashboard
- `web/app.py` — FastAPI, Static Files, WebSocket mit Heartbeat
- `web/ws_manager.py` — Connection + Auto-Reconnect Handling
- `web/data.py` — importiert `queries.py`
- `web/logic/processor.py` — Intent-Matcher mit Named Groups
- `web/logic/formatter.py` — Rohdaten → Chat-JSON
- `web/handlers/dashboard.py` — Summary + Vergleich + Historie
- `web/static/` — Chat-UI mit Pinned-Area, State-Management, Pico.css
- `ctf-web` Launcher

**Ergebnis:** "Zeig mir meine Ausgaben" → Pinned Chart + Tabelle im Browser

### Phase 2: Upload + Kategorien
- `POST /api/upload` mit `job_id`-Rückgabe
- `web/handlers/upload.py` — Verarbeitung + Progress via WS
- `web/handlers/learn.py` — Unkategorisierte Händler + Progressive Disclosure
- Drag&Drop + Button-Rendering + "Mehr anzeigen..." im Frontend
- Recategorize-Handler mit Named Groups

**Ergebnis:** Kontoauszug importieren + Händler kategorisieren via Chat

### Phase 3: Charts + Insights + Exploration
- Chart.js Integration (Pie, Bar, Line) mit Pinned-Support
- `web/handlers/insights.py` — KI-Empfehlungen mit Progress
- `web/handlers/explore.py` — Händler/Kategorie-Suche mit Progressive Disclosure
- Kontext-basierte Folgefragen

**Ergebnis:** Visuelle Analyse + KI-Sparempfehlungen + Drill-down

### Phase 4: Reports + Polish
- `web/handlers/report.py` — Markdown-Bericht inline + Download
- Willkommensnachricht + Quick-Action-Buttons
- Mobile-responsive Anpassungen
- Deutsche Fehlermeldungen + Fallback-Buttons bei unbekanntem Input
- WebSocket-Reconnect UI-Feedback ("Verbindung wird wiederhergestellt...")

**Ergebnis:** Feature-complete Chat-App

---

## Sicherheit

| Maßnahme | Detail |
|---|---|
| Localhost-only | Uvicorn: `--host 127.0.0.1` — nicht im LAN erreichbar |
| Upload-Validierung | Dateiendung (.csv/.xlsx/.pdf) + Größenlimit (10 MB) server-seitig |
| Kein Auth | Single-User, nur localhost — akzeptabel |
| CORS | Nicht nötig — alles same-origin |

---

## Kritische Dateien (zu modifizieren)

| Datei | Änderung |
|---|---|
| `cli/db.py` | Query-Logik nach `backend/app/queries.py` extrahieren, sync-Wrapper behalten |
| `cli/__init__.py` | sys.path Setup — muss auch für web/ funktionieren |
| `CLAUDE.md` | "Kein FastAPI" → "Web-UI unter web/, CLI bleibt Einstiegspunkt" |
| `backend/requirements.txt` | `fastapi`, `uvicorn[standard]`, `websockets` hinzufügen |

## Zu wiederverwendende Funktionen (nach Refactoring in queries.py)

| Funktion | Herkunft | Verwendung |
|---|---|---|
| `get_summary()` | `queries.py` | Dashboard |
| `get_comparison()` | `queries.py` | Vergleich |
| `get_history()` | `queries.py` | Trend |
| `get_insights_data()` | `queries.py` | Insights |
| `ingest_file()` | `queries.py` | Upload |
| `apply_rule()` | `queries.py` | Kategorie-Korrektur |
| `get_uncategorized_merchants()` | `queries.py` | Learn |
| `get_ai_suggestions()` | `queries.py` | KI-Vorschläge |
| `get_all_categories()` | `queries.py` | Kategorie-Liste |

---

## Verifikation

1. **Phase 0**: `./ctf dashboard` + `./ctf insights` funktionieren identisch nach Refactoring
2. **Phase 1**: `./ctf-web` starten → `localhost:8080` → "Zeig mir meine Ausgaben" → Pinned Chart + Tabelle
3. **Phase 2**: Datei Drag&Drop → Progress-Balken → Import-Ergebnis → Top 5 Händler mit Buttons
4. **Phase 3**: "Wo kann ich sparen?" → KI-Empfehlungen. "Was bei REWE?" → Drill-down
5. **Phase 4**: Laptop schließen + öffnen → WebSocket reconnectet → Chat-Historie bleibt
6. **Parallel**: `./ctf dashboard` zeigt dieselben Daten wie Web-UI
