# Cut the Fat — Claude Code Referenz

Vollständige technische Richtlinien: [`doc/GUIDELINES.md`](doc/GUIDELINES.md)
Feature-Backlog: [`doc/features/BACKLOG.md`](doc/features/BACKLOG.md)

---

## Schnellreferenz

**Einstiegspunkte:**
```bash
./ctf --help        # CLI
./ctf-web           # Web-UI (http://localhost:8765)
./ctf-desktop       # Desktop-App (Tauri + Python-Sidecar)
```

**CLI-Befehle:**
```bash
./ctf upload <datei>        # CSV/Excel/PDF importieren
./ctf dashboard             # Ausgabenübersicht
./ctf insights              # KI-Sparempfehlungen
./ctf learn                 # Händler kategorisieren
./ctf report                # Monatsbericht als Markdown
```

**Entwicklung:**
```bash
cd backend && .venv/bin/alembic upgrade head          # DB-Migration
cd backend && .venv/bin/alembic revision --autogenerate -m "beschreibung"
cd backend && .venv/bin/pip install -r requirements.txt
node scripts/build-sidecar.mjs && node scripts/rename-sidecar.mjs  # Sidecar
```

## Kategorien (kanonisch)

`Wohnen, Lebensmittel, Essen & Trinken, Mobilität, Freizeit, Gesundheit, Drogerie, Shopping, Abonnements, Urlaub, Bildung, Kommunikation, Versicherungen, Kinder, Post & Versand, Business Natalie, Kinder Natalie, Wohnen Natalie, Einnahmen, Einnahmen Natalie, Einkommensteuer, PayPal, Bargeld, Kreditkarte, Eigenüberweisung, Sonstiges`

Neue Kategorie: `CATEGORIES` in `backend/app/models/transaction.py` — wird beim nächsten Start automatisch in die DB gesetzt.

## Unveränderliche Regeln

- `dedup_hash`-Algorithmus (`SHA-256(datum|merchant.lower()|betrag)`) nie ändern
- Python-Backend bleibt Sidecar — kein Neuschreiben in Rust
- SQLite bleibt — kein Postgres, keine Cloud-DB
- Sidecar-Binaries nie committen (`src-tauri/binaries/` ist in `.gitignore`)
- Port nie hardcoden — immer Port-Discovery via Sidecar-stdout-Signal
