Inspect the current state of the SQLite database: show row counts, recent uploads, category distribution, and any anomalies.

Run these queries against the database at `backend/cut_the_fat.db`:

1. Check the database exists:
   `ls -lh /Users/ecog-vladislav/Projects/cut-the-fat/backend/cut_the_fat.db`

2. Run a summary query:
   ```bash
   cd /Users/ecog-vladislav/Projects/cut-the-fat/backend && .venv/bin/python -c "
   import asyncio
   from app.database import AsyncSessionLocal
   from sqlalchemy import text

   async def main():
       async with AsyncSessionLocal() as db:
           r = await db.execute(text('SELECT COUNT(*) FROM transactions'))
           print(f'Total transactions: {r.scalar()}')
           r = await db.execute(text('SELECT COUNT(*) FROM uploads'))
           print(f'Total uploads: {r.scalar()}')
           r = await db.execute(text('SELECT COUNT(*) FROM merchant_rules'))
           print(f'Merchant rules: {r.scalar()}')
           r = await db.execute(text('SELECT category, COUNT(*) as n, SUM(amount) as total FROM transactions WHERE type=\"debit\" GROUP BY category ORDER BY total DESC'))
           print('\nCategory breakdown:')
           for row in r.all():
               print(f'  {row[0]:<20} {row[1]:>5} txns  \${float(row[2]):>10.2f}')
           r = await db.execute(text('SELECT filename, uploaded_at, row_count, status FROM uploads ORDER BY uploaded_at DESC LIMIT 5'))
           print('\nRecent uploads:')
           for row in r.all():
               print(f'  {row[0]}  {row[1]}  {row[2]} rows  [{row[3]}]')

   asyncio.run(main())
   "
   ```

3. Report any anomalies: uploads with `status = 'error'`, transactions with `category = 'Sonstiges'` that have high amounts (potential miscategorization), or duplicate merchant_rules.
