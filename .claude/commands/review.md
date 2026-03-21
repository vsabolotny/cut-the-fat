Alle Kategoriezuweisungen interaktiv prüfen und korrigieren.

## Zweck

Unterschied zu `/learn`: `/learn` behandelt nur `Sonstiges`-Händler.
`/review` geht durch **alle** Kategorien und prüft ob bestehende Zuweisungen stimmen.

## Verwendung

`/review [--monat JJJJ-MM]`

Ohne `--monat` werden alle Daten geprüft (oder letzter Monat mit Daten).

## Workflow

### Schritt 1 — Kategorieübersicht

Führe SQL aus und zeige alle Kategorien mit Summe + Anzahl Transaktionen:

```sql
SELECT category, COUNT(*) as txn_count, SUM(amount) as total
FROM transactions
WHERE type = 'debit'
GROUP BY category
ORDER BY total DESC
```

Zeige als Rich-Tabelle.

### Schritt 2 — Top-Händler pro Kategorie

Für jede Kategorie: frage den Benutzer ob er diese prüfen möchte (`[Enter]` = ja, `[s]` = skip, `[q]` = quit).

Bei Bestätigung: zeige Top-10-Händler nach Summe:

```sql
SELECT merchant, COUNT(*) as txn_count, SUM(amount) as total
FROM transactions
WHERE category = :cat AND type = 'debit'
GROUP BY merchant
ORDER BY total DESC
LIMIT 10
```

### Schritt 3 — Korrektur

Bei verdächtigem Händler: frage nach der richtigen Kategorie.
Bei Bestätigung:
1. `merchant_rules` eintragen (für zukünftige Imports)
2. Alle bestehenden Transaktionen rückwirkend korrigieren:

```sql
UPDATE transactions
SET category = :neue_kategorie, category_source = 'manual'
WHERE merchant_normalized = :merchant_norm
```

### Schritt 4 — Zusammenfassung

Am Ende: Anzahl korrigierter Händler und Transaktionen ausgeben.

## Kategorieliste (kanonisch)

Wohnen, Lebensmittel, Essen & Trinken, Mobilität, Freizeit, Gesundheit,
Drogerie, Shopping, Abonnements, Urlaub, Bildung, Kommunikation,
Versicherungen, Kinder, Post & Versand, Business Natalie, Kinder Natalie,
Wohnen Natalie, Einnahmen, Einnahmen Natalie, Einkommensteuer,
PayPal, Bargeld, Kreditkarte, Eigenüberweisung, Sonstiges

## Technische Hinweise

- `merchant_normalized` = lowercase, Sonderzeichen entfernt (gleiche Logik wie in `categorizer.py`)
- Nutze `cli/db.py`-Funktionen wo möglich, ansonsten direkte SQL über `get_db_session()`
- Python-Pfad: `cd /Users/ecog-vladislav/Projects/cut-the-fat && backend/.venv/bin/python`
