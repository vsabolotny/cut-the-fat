# Cut the Fat — Technical Guidelines

> Diese Datei ist die verbindliche technische Referenz für alle Entwicklungsarbeit am Projekt.
> Team: Paul Wilke (Fork-Owner) + Vlad Sabolotny (Original-Autor)
> Workflow: Feature-Branches → Pull Requests → Review → Merge in `main`

---

## Produktvision

Privacy-first Finanzanalyse für Einzelpersonen und Familien.
Lokal-first: Daten bleiben auf dem Gerät des Nutzers. Keine Cloud-Pflicht.
Zielgruppe: Deutschsprachige Haushalte und Familien (mittelfristig mehrsprachig).

---

## Drei Ausführungsebenen

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — CLI  (./ctf)                                     │
│  Python + Click + Rich → direkter Service-Aufruf            │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2 — WEB  (./ctf-web)                                 │
│  FastAPI + WebSocket + HTML/JS → Browser oder Docker        │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3 — DESKTOP  (./ctf-desktop)                         │
│  Tauri 2 (Rust) wrappet den Web-Layer als native App        │
│  Python-Binary (PyInstaller) als Sidecar gebundled          │
└─────────────────────────────────────────────────────────────┘
```

Alle Layer teilen `backend/app/services/` und `backend/cut_the_fat.db`.
Die CLI ist die Single Source of Truth für Business-Logik.

---

## Tech-Stack

| Schicht | Technologie | Begründung |
|---|---|---|
| Backend-Services | Python 3.12, async SQLAlchemy, Pydantic | Anthropic SDK, Parser-Ökosystem, bestehende Logik |
| Web-Server | FastAPI + uvicorn + WebSocket | Async, einfach, läuft als Sidecar |
| Frontend | Vanilla HTML/CSS/JS (aktuell) | Kein Build-Schritt, läuft in jedem WebView |
| Desktop-Shell | Tauri 2 (Rust) | 5 MB Binary, kein Chromium, native Updates |
| Datenbank | SQLite (aiosqlite) | Zero-Server, lokal, embedded in Sidecar |
| CLI | Click + Rich | Etabliert, gut lesbar |
| Migrations | Alembic | Standard für SQLAlchemy |
| AI | Anthropic Claude (Haiku für Batch, Sonnet für Insights) | Günstig + leistungsfähig |
| CI/CD | GitHub Actions | Tag-basiertes Release auf allen 3 Plattformen |

### Frontend-Richtung (nächste Phase)
SvelteKit ist die geplante Ablöse für das aktuelle vanilla JS-Frontend.
Begründung: Reaktive Datenbindung für Tabellen/Charts, bessere Komponenten-Struktur,
bleibt im Tauri-WebView lauffähig ohne Server-Side-Rendering.

---

## Repo-Struktur

```
cut-the-fat/
├── ctf                          # CLI-Einstiegspunkt
├── ctf-web                      # Web-Server-Einstiegspunkt
├── ctf-desktop                  # Desktop-App-Einstiegspunkt
│
├── cli/                         # CLI-Layer
│   ├── main.py                  # Click-Gruppe
│   ├── db.py                    # asyncio.run()-Wrapper über Services
│   ├── commands/                # upload.py, dashboard.py, insights.py, learn.py, report.py
│   └── render/                  # terminal.py, md_writer.py, tui_learn.py
│
├── web/                         # Web-Layer
│   ├── app.py                   # FastAPI-Server + Sidecar-Entry
│   ├── handlers/                # Route-Handler (dashboard, insights, learn, report, bugreport...)
│   ├── logic/                   # formatter.py, processor.py
│   └── static/                  # HTML/CSS/JS-Frontend
│
├── src-tauri/                   # Desktop-Layer (Tauri 2 / Rust)
│   ├── src/lib.rs               # Sidecar-Startup, Port-Discovery, IPC-Commands
│   ├── tauri.conf.json          # App-Konfiguration + Auto-Updater
│   ├── capabilities/default.json
│   └── binaries/                # Sidecar-Binaries (gebaut, nie committed)
│
├── scripts/
│   ├── build-sidecar.mjs        # PyInstaller-Wrapper
│   └── rename-sidecar.mjs       # Target-Triple-Rename für Tauri
│
├── backend/                     # Business-Logik (geteilt von allen Layern)
│   ├── cut_the_fat.db
│   ├── alembic/
│   └── app/
│       ├── config.py            # Pydantic Settings, absoluter DB-Pfad
│       ├── database.py          # Async SQLAlchemy Engine
│       ├── models/              # Transaction, Upload, MerchantRule, InsightsCache, Category
│       ├── queries.py           # Geteilte DB-Queries
│       └── services/            # categorizer.py, insights.py, parser/
│
├── analytics/                   # Generierte Monatsberichte (Markdown)
├── doc/
│   ├── GUIDELINES.md            # ← diese Datei
│   ├── features/BACKLOG.md      # Feature-Tickets
│   └── ...                      # PRDs, Pläne
└── .github/workflows/release.yml
```

---

## Architektur-Entscheidungen

### Python-Sidecar-Pattern
Python bleibt das Backend. `web/app.py` wird per PyInstaller zur Single-Binary
kompiliert und von Tauri als Sidecar gestartet.

Kein Neuschreiben in Rust: Anthropic SDK, Pandas/tabula für Parser und die
gesamte bestehende Logik rechtfertigen das nicht. PyInstaller-Binaries sind
50–80 MB — das ist akzeptiert.

### Port-Discovery
Tauri wählt per `portpicker` einen freien Port, übergibt ihn als Argument
an den Sidecar. Der Sidecar schreibt `READY:<port>` auf stdout. Rust fängt
das Signal ab, speichert den Port in `OnceCell<u16>` und gibt ihn per IPC
(`invoke('get_backend_port')`) ans Frontend weiter. Port nie hardcoden.

### Dual-Mode Frontend
Frontend erkennt ob es in Tauri oder im Browser läuft (`window.__TAURI_INTERNALS__`):
- **Tauri:** Port via `invoke('get_backend_port')`, absolute URLs zu `localhost:PORT`
- **Browser:** gleicher Origin, relative URLs

Jeder neue Frontend-Code muss dieses Pattern respektieren.

### DB-Pfad
`config.py` leitet den DB-Pfad von `__file__` ab → immer `backend/cut_the_fat.db`,
unabhängig vom Arbeitsverzeichnis. Nicht ändern.

### Dedup-Mechanismen (nie ändern)
- **Transaction:** `dedup_hash = SHA-256(datum|merchant.lower()|betrag)`
- **Merchant:** `merchant_normalized = lowercase + Sonderzeichen entfernen`
- **Insights-Cache:** Key auf `SHA-256(aggregierter Ausgaben-JSON)`

---

## Release-Pipeline

Releases werden durch Git-Tags ausgelöst: `git tag v1.2.3 && git push fork --tags`

**GitHub Actions (`.github/workflows/release.yml`):**

Stage 1 — Sidecar-Build (Matrix: Linux, macOS, Windows):
- `web/app.py` → PyInstaller Single-Binary → mit Target-Triple umbenennen
- Als Artefakt hochladen

Stage 2 — Tauri-Build (Matrix: Linux, macOS, Windows):
- Sidecar-Artefakte downloaden
- `tauri-action` baut: `.deb`/`.AppImage` (Linux), `.dmg`/`.app` (macOS), `.msi`/`.exe` (Windows)
- Erstellt GitHub Release (Draft) + Update-Artefakte

**Benötigte GitHub Secrets:**
- `TAURI_SIGNING_PRIVATE_KEY` — für Auto-Updater-Signatur

**Auto-Updater aktivieren** (noch offen):
1. `cargo tauri signer generate -w ~/.tauri/cutthefat.key`
2. Public Key → `tauri.conf.json` → `plugins.updater.pubkey`
3. Private Key als GitHub Secret `TAURI_SIGNING_PRIVATE_KEY`
4. `"createUpdaterArtifacts": true` in `tauri.conf.json`

---

## Bug-Reporting

`web/handlers/bugreport.py` erstellt GitHub Issues via API.
Benötigt `GITHUB_TOKEN` in `.env` (Personal Access Token mit `issues: write`).
Ziel-Repo: `paulwilke/cut-the-fat`, überschreibbar via `GITHUB_REPO=owner/name`.

**Sentry (geplant):**
- Python-Sidecar: `sentry-sdk` mit `FastAPIIntegration`
- Frontend: Sentry Browser SDK
- Sentry → GitHub-Integration für automatische Issue-Erstellung

---

## Datentransparenz & EU AI Act

**Grundsatz:** Wenn Nutzerdaten die App verlassen, muss das sichtbar und erklärbar sein.

- Jeder AI-Call ist in der UI mit ⚠️ markiert
- Per Drill-Down zeigt die UI den konkreten Payload (Händler-Liste, Ausgaben-JSON)
- Ohne `ANTHROPIC_API_KEY`: keine externen Calls, expliziter Hinweis in der UI
- Kategorisierung nutzt **nur normalisierte Händlernamen** (keine Beträge, keine Daten)
- Insights nutzen **aggregiertes JSON** (Kategoriesummen, keine Einzeltransaktionen)
- Ziel: Beträge auf ganze Euro runden bevor sie an externe AI gesendet werden

---

## Neuen Bank-Parser hinzufügen

1. `backend/app/services/parser/<bank>_parser.py` → `parse_<bank>(content: bytes) -> list[RawTransaction]`
2. Format-Erkennung in `cli/db.py` → `_ingest_file()` ergänzen
3. Mit echter Beispieldatei testen: `./ctf upload <testdatei>`

---

## Häufige Fallstricke

- **PDF-Parser:** `_extract_from_tables()` zuerst, dann Regex-Fallback
- **Datumsformate:** `DATE_FORMATS` in `csv_parser.py` ergänzen
- **Betragsvorzeichen:** `amount` immer positiv; `type` (`debit`/`credit`) trägt das Vorzeichen
- **lru_cache auf `get_settings()`:** nach `.env`-Änderungen Prozess neu starten
- **Async SQLAlchemy:** immer `await db.execute(...)`, nie synchrone ORM-Muster
- **Tauri CSP:** neue externe Hosts in `tauri.conf.json` → `app.security.csp` eintragen
- **Sidecar fehlt:** `node scripts/build-sidecar.mjs && node scripts/rename-sidecar.mjs`

---

## PRD-Format

Neue Features werden als PRD in `doc/features/PRD_<feature>.md` dokumentiert, bevor Code geschrieben wird.

```markdown
## Kontext
Warum bauen wir das? Welches Problem löst es?

## Produktziele
Was soll das Feature leisten? (2–4 Punkte)

## Nicht-Ziele
Was ist explizit NICHT im Scope?

## Akzeptanzkriterien
Konkrete, testbare Bedingungen für "fertig"

## Technische Notizen
Layer-Zuordnung (CLI / Web / Tauri), neue Abhängigkeiten, Breaking Changes,
Datenschutz-Implikationen (was verlässt das Gerät?)
```

---

## Roadmap

| Phase | Thema | Status |
|---|---|---|
| 1 | CLI (Core Business-Logik) | ✅ fertig |
| 2 | Web-UI (Chat + Dashboard) | ✅ fertig |
| 3 | Tauri Desktop-App + Auto-Updater | 🔄 in Arbeit |
| 4 | Sentry + Bug-Reporting Alpha | ⬜ offen |
| 5 | Alpha-Release + Nutzerfeedback | ⬜ offen |
| 6 | Multi-Nutzer / Familien-Konten | ⬜ Backlog |
| 7 | Steuerliche Kategorien + Jahresübersicht | ⬜ Backlog |
| 8 | Mehrsprachigkeit | ⬜ Backlog |
| 9 | Mobile (PWA oder Tauri Mobile) | ⬜ later |
