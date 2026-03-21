Kategorie-Diagramm über mehrere Monate als Balken+Linien-Chart erstellen.

## Verwendung

`/chart <Kategorie> [--monate N]`

Beispiele:
- `/chart Urlaub` — letzte 3 Monate
- `/chart "Essen & Trinken" --monate 6`

## Was du tun sollst

1. Lies `$ARGUMENTS` aus. Erster Wert = Kategorie. Optional `--monate N` (Standard: 3).
2. Führe eine SQL-Abfrage aus um Monatssummen zu holen:

```python
import asyncio, sys
sys.path.insert(0, 'backend')
from app.database import get_db_session
from sqlalchemy import text

async def get_data(category, months):
    async with get_db_session() as db:
        result = await db.execute(text("""
            SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
            FROM transactions
            WHERE category = :cat AND type = 'debit'
            GROUP BY month
            ORDER BY month DESC
            LIMIT :months
        """), {"cat": category, "months": months})
        rows = result.fetchall()
    return list(reversed(rows))

rows = asyncio.run(get_data("KATEGORIE", MONATE))
```

3. Erstelle ein matplotlib-Diagramm:
   - Balkendiagramm (bar) für die Monatswerte
   - Linie (plot) über die Balken für den Trend
   - Titel: `<Kategorie> — letzte N Monate`
   - Y-Achse: Euro-Beträge mit `€`-Suffix
   - Speichern nach `/tmp/<kategorie_lower>_chart.png`

4. Öffne die Datei mit `open /tmp/<kategorie_lower>_chart.png`

5. Gib eine kurze Zusammenfassung: Gesamtausgaben, Durchschnitt/Monat, höchster Monat.

## Hinweise

- matplotlib ist installiert in `backend/.venv/bin/python`
- Führe das Script aus mit: `cd /Users/ecog-vladislav/Projects/cut-the-fat && backend/.venv/bin/python /tmp/ctf_chart.py`
- Schreibe das Script nach `/tmp/ctf_chart.py` und führe es dann aus
