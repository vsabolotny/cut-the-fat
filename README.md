# ✂ Cut the Fat

Persönliche Finanzanalyse im Terminal. Kontoauszüge importieren → KI kategorisiert automatisch → Monatsberichte als Markdown → konkrete Sparempfehlungen.

---

## Features

- **Import** — CSV, Excel (.xlsx/.xls) und PDF-Kontoauszüge
- **KI-Kategorisierung** — Claude Haiku ordnet jeden Händler einer Kategorie zu; bekannte Händler werden gecacht und nie wieder ans API gesendet
- **Kategorien lernen** — interaktiver Q&A-Agent schlägt Kategorien vor, du bestätigst oder korrigierst
- **Dashboard** — Ausgaben nach Kategorie mit Vormonatsvergleich, ASCII-Balkendiagramm
- **Monatsbericht** — vollständiger Bericht als Markdown-Datei (`analytics/JJJJ-MM.md`)
- **KI-Empfehlungen** — 5 konkrete Spartipps von Claude Sonnet, gecacht und automatisch aktualisiert
- **Mehrere Konten** — Girokonto + Kreditkarte kombinieren (Umbuchungen filtern um Doppelzählung zu vermeiden)

---

## Stack

| Schicht | Technologie |
|---|---|
| CLI | Python + Click + Rich |
| Datenbank | SQLite via SQLAlchemy 2.0 async + Alembic |
| KI | Claude Haiku (Kategorisierung) + Claude Sonnet (Empfehlungen) |

---

## Schnellstart

### 1. Voraussetzungen

- Python 3.11+
- Anthropic API Key ([console.anthropic.com](https://console.anthropic.com/))

### 2. Konfiguration

```bash
cp .env.example .env
```

`.env` bearbeiten:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Starten

```bash
./ctf --help
```

---

## Anwendungsfälle

### Kontoauszug importieren

```bash
./ctf upload kontoauszug-dezember.csv
./ctf upload kreditkarte-dezember.pdf
./ctf upload umsaetze.xlsx
```

Unterstützte Formate: **CSV**, **Excel (.xlsx/.xls)**, **PDF**. Die KI kategorisiert automatisch alle Händler. Bekannte Händler werden direkt per gespeicherter Regel zugeordnet — ohne API-Aufruf.

Für zwei PDF-Formate gibt es dedizierte Parser, die statt der generischen Heuristik
greifen und jede Buchung samt Vorzeichen exakt lesen:

| Format | Erkannt an | Datei |
|---|---|---|
| Postbank Girokonto | „Postbank" + „Kontoauszug vom" | `pdf_postbank.py` |
| easybank Kreditkarte (BAWAG) | „easybank Kreditkarte" + „Umsatzübersicht" | `pdf_easybank.py` |

Beide lesen zusätzlich Alten und Neuen Saldo aus, sodass sich ein Import über
`Alter Saldo + Σ Buchungen == Neuer Saldo` prüfen lässt.

---

### Dashboard anzeigen

```bash
./ctf dashboard                  # letzter Monat mit Daten
./ctf dashboard --monat 2025-11  # bestimmter Monat
```

Beispielausgabe:
```
─────────────────── ✂  Cut the Fat — 2025-12 ───────────────────
  Gesamt: 7.063,79 €  ▲ 1.937,92 € vs. Vormonat (37.8%)

  Kategorie              Betrag    Anteil
  Umbuchungen         4.179,98 €   59.2%   ████████████████████
  Versicherungen        923,48 €   13.1%   ████░░░░░░░░░░░░░░░░
  Sonstiges             860,49 €   12.2%   ████░░░░░░░░░░░░░░░░
  Wohnen                428,00 €    6.1%   ██░░░░░░░░░░░░░░░░░░
```

---

### Unkategorisierte Händler lernen

```bash
./ctf learn             # bis zu 20 Händler
./ctf learn --limit 50  # mehr auf einmal
```

Der Q&A-Agent:
1. Holt alle Händler mit Kategorie „Sonstiges"
2. Fragt Claude Haiku nach Vorschlägen (Batch)
3. Du bestätigst mit Enter, wählst eine Nummer oder tippst eine eigene Kategorie
4. Die Regel wird gespeichert und alle passenden Transaktionen sofort aktualisiert

```
  REWE SAGT DANKE (14 Txn)  →  Lebensmittel
   Kategorie [Enter/Zahl/t/q]:
```

---

### KI-Sparempfehlungen

```bash
./ctf insights        # gecachte Empfehlungen anzeigen
./ctf insights --neu  # neu generieren (Cache ignorieren)
```

5 konkrete Spartipps basierend auf den letzten 6 Monaten, generiert von Claude Sonnet. Beispiel:

> ⚠ Sie zahlen gleichzeitig zwei Mobilfunkverträge: Telefónica (~30 €/Monat) und Vodafone (~50 €/Monat). Durch Kündigung eines Vertrags könnten Sie 600 €/Jahr sparen.

---

### Monatsbericht generieren

```bash
./ctf report                     # letzter Monat
./ctf report --monat 2025-11     # bestimmter Monat
./ctf report --alle              # alle verfügbaren Monate
```

Erstellt `analytics/JJJJ-MM.md` mit:
- Gesamtausgaben + Vormonatsvergleich
- Kategorientabelle mit Anteilen
- Monat-über-Monat-Deltas pro Kategorie
- KI-Empfehlungen

Die Dateien sind normales Markdown — lesbar in jedem Editor, versionierbar mit Git.

---

### Girokonto + Kreditkarte kombinieren

Wenn das Girokonto eine Sammelposition „ABRECHNUNG KARTE 1.804 €" zeigt, steckt dahinter die Kreditkartenabrechnung. Um die echten Ausgaben zu sehen:

1. **Girokonto-Auszug importieren** — die Sammelposition landet korrekt unter „Umbuchungen"
2. **Kreditkarten-Auszug importieren** — alle Einzeltransaktionen (Rewe, Netflix, Shell…) werden separat kategorisiert
3. **Beim Analysieren** — Kategorie „Umbuchungen" ignorieren, da diese nur den internen Transfer darstellt; alle echten Ausgaben stecken in den Kreditkartentransaktionen

```bash
./ctf upload girokonto-dez.csv
./ctf upload kreditkarte-dez.pdf
./ctf dashboard  # zeigt jetzt echte Einzelausgaben
```

---

## Projektstruktur

```
cut-the-fat/
├── ctf                          # Einstiegspunkt (Shell-Skript)
├── cli/
│   ├── main.py                  # Click-Gruppe
│   ├── db.py                    # DB-Operationen (async, via asyncio.run())
│   ├── commands/                # upload, dashboard, insights, learn, report
│   └── render/
│       ├── terminal.py          # Rich-Ausgabe
│       └── md_writer.py         # Markdown-Berichte
├── analytics/                   # Generierte Monatsberichte (JJJJ-MM.md)
├── data/statements/             # Originale Kontoauszüge (Kopien)
├── backend/
│   ├── cut_the_fat.db           # SQLite-Datenbank
│   ├── requirements.txt
│   ├── alembic/                 # Datenbankmigrationen
│   └── app/
│       ├── config.py            # Einstellungen (.env)
│       ├── database.py          # SQLAlchemy async Engine
│       ├── models/              # Transaction, Upload, MerchantRule, InsightsCache, Category
│       └── services/
│           ├── categorizer.py        # Claude Haiku Batch-Kategorisierung
│           ├── insights.py           # Claude Sonnet Empfehlungen + Cache
│           ├── category_discovery.py # Neue Kategorien automatisch entdecken
│           └── parser/               # csv_parser, excel_parser, pdf_parser
│                                     # + pdf_postbank, pdf_easybank (bankspezifisch)
└── .claude/commands/            # Claude Code Skills (/upload /dashboard /insights /learn /report)
```

---

## Wie es funktioniert

### Import-Pipeline

```
./ctf upload <datei>
  → SHA-256 Duplikat-Check (Datei bereits importiert?)
  → Parser-Erkennung (CSV / Excel / PDF; bei PDF zuerst die bankspezifischen Parser)
  → Händler normalisieren + Dedup-Hashes berechnen
  → Bekannte Händlerregeln anwenden (kein API-Aufruf)
  → Claude Haiku: neue Kategorien entdecken (falls nötig)
  → Claude Haiku: unbekannte Händler kategorisieren (Batch à 50)
  → Transaktionen in SQLite speichern
  → Originaldatei nach data/statements/ kopieren
```

### Händlerregeln-Cache

Jede Korrektur via `./ctf learn` speichert die Zuordnung `händler_normalisiert → kategorie` in der `merchant_rules`-Tabelle. Beim nächsten Import werden bekannte Händler direkt zugeordnet — ohne API-Kosten.

### Insights-Cache

Empfehlungen sind gehasht auf `SHA-256(aggregierter_ausgaben_json)`. Neuer Import → andere Daten → neuer Hash → nächste `./ctf insights`-Abfrage generiert frische Tipps.

---

## Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(leer)* | Für KI-Features erforderlich. Ohne Key: Kategorie „Sonstiges" als Fallback, regelbasierte Empfehlungen |
| `DATABASE_URL` | `sqlite+aiosqlite:///...` | SQLAlchemy DB-URL (Standard: `backend/cut_the_fat.db`) |
| `CTF_AUTH_TOKEN` | *(leer)* | Shared Secret für die Web-App. Leer = offen (nur localhost). Von der Desktop-App automatisch gesetzt |
| `CTF_COOKIE_AUTH` | *(leer)* | `1` = Cloud-Modus: **alle** Pfade verlangen den Token, Login per `?token=…` setzt ein HttpOnly-Cookie |

---

## Deployment (AWS)

Die Web-App läuft öffentlich hinter CloudFront (EC2 + Docker, ohne eigene
Domain). Einrichtung, Runbook und Sicherheitsmodell:
[`doc/CAT-27-AWS-DEPLOYMENT.md`](doc/CAT-27-AWS-DEPLOYMENT.md).

```bash
deploy/provision-aws.sh   # einmalig: EC2, Elastic IP, CloudFront
deploy/deploy.sh          # Redeploy (per SSM, ohne SSH)
```

> ⚠️ Ohne `CTF_AUTH_TOKEN` + `CTF_COOKIE_AUTH=1` ist die App **völlig offen** —
> für einen öffentlichen Deploy sind beide Pflicht.

---

## Kategorien

`Wohnen` · `Lebensmittel` · `Essen & Trinken` · `Verkehr` · `Freizeit` · `Gesundheit` · `Einkaufen` · `Abonnements` · `Reisen` · `Bildung` · `Haushalt` · `Versicherungen` · `Einnahmen` · `Umbuchungen` · `Sonstiges`

Neue Kategorie hinzufügen: `CATEGORIES` in `backend/app/models/transaction.py` ergänzen. Beim nächsten Start wird sie automatisch in die Datenbank übernommen.

---

## Entwicklung

```bash
# Migrationen ausführen
cd backend && .venv/bin/alembic upgrade head

# Migration erstellen
cd backend && .venv/bin/alembic revision --autogenerate -m "beschreibung"

# Abhängigkeiten installieren
cd backend && .venv/bin/pip install -r requirements.txt
```
