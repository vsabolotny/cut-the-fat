# Cut the Fat — Claude Code Anleitung

## Projektübersicht

Persönliche Finanzanalyse. Einzelnutzer, lokale Ausführung. Kontoauszüge importieren → KI kategorisiert Transaktionen → Monatsberichte als Markdown → Sparempfehlungen.

- **CLI**: `./ctf` — Python + Click + Rich
- **Backend-Services**: `backend/app/services/` — Parser, Kategorisierer, Insights
- **Datenbank**: SQLite (`backend/cut_the_fat.db`)
- **Python venv**: `backend/.venv/` (bereits erstellt)
- **Berichte**: `analytics/JJJJ-MM.md` (generiert mit `./ctf report`)

## App starten

```bash
cp .env.example .env   # ANTHROPIC_API_KEY setzen
./ctf --help
```

## Befehle

```bash
./ctf upload <datei>             # CSV/Excel/PDF importieren
./ctf dashboard                  # Ausgabenübersicht (letzter Monat mit Daten)
./ctf dashboard --monat 2025-12  # Bestimmter Monat
./ctf insights                   # KI-Sparempfehlungen
./ctf insights --neu             # Neu generieren (Cache ignorieren)
./ctf learn                      # Unkategorisierte Händler kategorisieren (Q&A)
./ctf learn --limit 50           # Bis zu 50 Händler pro Sitzung
./ctf report                     # Monatsbericht als MD generieren
./ctf report --alle              # Alle Monate generieren
```

## Entwicklungsbefehle

| Aufgabe | Befehl |
|---|---|
| CLI testen | `./ctf --help` |
| Import prüfen | `cd backend && .venv/bin/python -c "import sys; sys.path.insert(0,'backend'); import cli.db; print('OK')"` |
| Migrationen ausführen | `cd backend && .venv/bin/alembic upgrade head` |
| Migration erstellen | `cd backend && .venv/bin/alembic revision --autogenerate -m "beschreibung"` |
| Abhängigkeiten installieren | `cd backend && .venv/bin/pip install -r requirements.txt` |

## Architektur

```
cut-the-fat/
├── ctf                          # Shell-Einstiegspunkt (chmod +x)
├── cli/
│   ├── __init__.py              # sys.path setup für backend/
│   ├── main.py                  # Click-Gruppe: upload/dashboard/insights/learn/report
│   ├── db.py                    # asyncio.run()-Wrapper über async DB + Services
│   ├── commands/                # upload.py, dashboard.py, insights.py, learn.py, report.py
│   └── render/
│       ├── terminal.py          # Rich-Tabellen und Ausgabe
│       └── md_writer.py         # Schreibt analytics/JJJJ-MM.md
├── analytics/                   # Generierte Monatsberichte (Markdown)
├── data/statements/             # Originale Kontoauszüge (Kopien)
├── doc/                         # Projektdokumentation und Pläne
├── backend/
│   ├── cut_the_fat.db           # SQLite-Datenbank
│   ├── requirements.txt
│   ├── alembic/                 # DB-Migrationen
│   └── app/
│       ├── config.py            # Pydantic Settings (liest .env, absoluter DB-Pfad)
│       ├── database.py          # Async SQLAlchemy Engine
│       ├── models/              # Transaction, Upload, MerchantRule, InsightsCache, Category
│       └── services/            # categorizer.py, insights.py, category_discovery.py, parser/
└── .claude/commands/            # Skills: /upload /dashboard /insights /learn /report
```

## Architekturentscheidungen

- **Kein HTTP-Layer** — CLI ruft Services direkt auf, kein FastAPI/REST
- **Async + asyncio.run()** — Services bleiben async; CLI wrappet mit `asyncio.run()`
- **Absoluter DB-Pfad** — `config.py` leitet DB-Pfad von `__file__` ab → immer `backend/cut_the_fat.db`, unabhängig vom Arbeitsverzeichnis
- **Merchant-Dedup** — `merchant_normalized = lowercase + Sonderzeichen entfernen`, Key für `merchant_rules`-Tabelle
- **Transaction-Dedup** — `dedup_hash = SHA-256(datum|merchant.lower()|betrag)`, verhindert Doppelimporte
- **Insights-Cache** — Key auf `SHA-256(aggregierter Ausgaben-JSON)`, invalidiert automatisch bei neuen Daten

## Schlüsseldateien

| Datei | Zweck |
|---|---|
| `cli/db.py` | Alle DB-Operationen als sync-wrappte async-Funktionen |
| `cli/commands/learn.py` | Interaktiver Q&A-Agent für Kategorienlernen |
| `cli/render/md_writer.py` | Markdown-Berichtsgenerator |
| `backend/app/services/categorizer.py` | Claude Haiku Batch-Kategorisierung + Regelanwendung |
| `backend/app/services/insights.py` | Claude Sonnet Insights + SHA-256-Cache |
| `backend/app/services/parser/` | CSV/Excel/PDF-Parser |
| `backend/app/models/transaction.py` | `CATEGORIES` — einzige Quelle der Wahrheit |

## Kategorien (kanonisch, Deutsch)

`Wohnen, Lebensmittel, Essen & Trinken, Verkehr, Freizeit, Gesundheit, Einkaufen, Abonnements, Reisen, Bildung, Haushalt, Versicherungen, Einnahmen, Umbuchungen, Sonstiges`

Neue Kategorie hinzufügen: `CATEGORIES` in `backend/app/models/transaction.py` aktualisieren. Beim nächsten CLI-Start wird sie automatisch in die `categories`-Tabelle gesetzt.

## Neuen Bank-Parser hinzufügen

1. `backend/app/services/parser/<bank>_parser.py` mit `parse_<bank>(content: bytes) -> list[RawTransaction]`
2. Format-Erkennung in `cli/db.py` → `_ingest_file()` ergänzen
3. Mit echter Beispieldatei testen

## Häufige Fehler

- **PDF-Parser** — `_extract_from_tables()` zuerst, dann Regex-Fallback. Echte PDFs variieren stark.
- **Datumsformate** — `DATE_FORMATS` in `csv_parser.py` ergänzen falls nötig
- **Betragsvorzeichen** — alle `amount`-Werte positiv; `type`-Spalte (`debit`/`credit`) trägt das Vorzeichen
- **lru_cache auf get_settings()** — nach `.env`-Änderungen ggf. Prozess neu starten
- **Async SQLAlchemy** — immer `await db.execute(...)`, niemals synchrone ORM-Muster

## Was NICHT tun

- `dedup_hash`-Algorithmus nicht ändern — bestehende Zeilen verlieren Duplikatschutz
- Kein FastAPI wieder hinzufügen — CLI ist der einzige Einstiegspunkt
- Kein Frontend in diesem Repo — wird in späterer Iteration mit anderem Ansatz gebaut
- SQLite nicht durch Postgres ersetzen — Null-Server, Daten bleiben lokal
