# Cut the Fat — Claude Code Instructions

## Project overview

Personal finance web app. Single user, local deployment. Uploads bank statements → AI categorizes transactions → surfaces cost-cutting insights.

- **Backend**: `backend/` — Python + FastAPI + SQLAlchemy async + SQLite
- **Frontend**: `frontend/` — React + Vite + TypeScript + Tailwind CSS v4
- **Python venv**: `backend/.venv/` (already created)
- **Entry point**: `./start.sh`

## Running the app

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY and APP_PASSWORD
./start.sh
```

Frontend: http://localhost:5173 | API docs: http://localhost:8000/docs

## Commands to use

| Task | Command |
|---|---|
| Start backend | `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000` |
| Start frontend | `cd frontend && npm run dev` |
| Run migrations | `cd backend && .venv/bin/alembic upgrade head` |
| Make migration | `cd backend && .venv/bin/alembic revision --autogenerate -m "desc"` |
| Backend import check | `cd backend && .venv/bin/python -c "from app.main import app; print('OK')"` |
| Frontend build check | `cd frontend && npm run build` |
| Frontend type check | `cd frontend && npx tsc --noEmit` |
| Install backend deps | `cd backend && .venv/bin/pip install -r requirements.txt` |
| Install frontend deps | `cd frontend && npm install` |

## Architecture decisions

- **No expiry on auth tokens** — HMAC-SHA256 of password, deterministic. To revoke: change `SECRET_KEY` or `APP_PASSWORD` in `.env`.
- **SQLite auto-created** — `Base.metadata.create_all` in FastAPI lifespan handles first run. Alembic handles subsequent migrations.
- **Merchant dedup** — `merchant_normalized = lowercase + strip special chars`. Used as key for `merchant_rules` table. Applied before any Claude API call.
- **Transaction dedup** — `dedup_hash = SHA-256(date|merchant.lower()|amount)`. Prevents re-importing the same transaction from a different upload.
- **Insights cache** — keyed on `SHA-256(aggregated_spend_json)`. Invalidates automatically when data changes. No TTL needed.
- **Vite proxy** — `/api/*` proxied to `localhost:8000` in dev. No CORS configuration needed on frontend.
- **Tailwind CSS v4** — uses `@tailwindcss/vite` plugin. Config is in `vite.config.ts`, not `tailwind.config.js`.

## Key files

| File | Purpose |
|---|---|
| `backend/app/routers/uploads.py` | Upload pipeline orchestrator (parse → deduplicate → categorize → persist) |
| `backend/app/services/categorizer.py` | Claude Haiku batch categorization + merchant rule application |
| `backend/app/services/insights.py` | Claude Sonnet insights generation + SHA-256 cache |
| `backend/app/services/parser/pdf_parser.py` | PDF parsing (table extraction first, regex text fallback) |
| `backend/app/models/transaction.py` | `CATEGORIES` list — single source of truth for valid categories |
| `frontend/src/api/transactions.ts` | `CATEGORIES` and `CATEGORY_COLORS` used across all components |
| `frontend/src/pages/Dashboard.tsx` | Hero page — validates full vertical slice works |

## Categories (canonical)

`Housing, Groceries, Dining, Transportation, Entertainment, Health, Shopping, Subscriptions, Travel, Education, Utilities, Insurance, Income, Transfers, Other`

If adding a new category: update `CATEGORIES` in `backend/app/models/transaction.py` AND `CATEGORIES`/`CATEGORY_COLORS` in `frontend/src/api/transactions.ts`.

## Adding a new bank parser

1. Create `backend/app/services/parser/<bank>_parser.py` implementing `parse_<bank>(content: bytes) -> list[RawTransaction]`
2. Add the file extension or MIME type detection in `backend/app/routers/uploads.py` → `_parse_file()`
3. Test with a real sample file before integrating

## Common gotchas

- **PDF parsing** — `_extract_from_tables()` runs first (works for most structured bank PDFs). If it returns empty, `_extract_from_text()` regex fallback runs. Real-world PDFs vary hugely; expect to tune.
- **Date formats** — `DATE_FORMATS` list in `csv_parser.py` covers common formats. Add new ones there if a bank uses an unusual format.
- **Amount sign** — all `amount` values stored as positive `NUMERIC`. `type` column (`debit`/`credit`) carries the sign semantics. Dashboard queries filter `WHERE type = 'debit'` for expense calculations.
- **TanStack Query invalidation** — after any mutation (upload, category change, delete), call `queryClient.invalidateQueries()` with no args to refresh all dependent queries.
- **Async SQLAlchemy** — always `await db.execute(...)`, never use synchronous ORM patterns. Use `text()` for raw SQL queries.

## What NOT to do

- Do not add a `created_at` to `merchant_rules` — it's intentionally a simple lookup table
- Do not add JWT expiry — this is a personal local tool, token persistence is a feature
- Do not add a separate Postgres setup — SQLite is intentional (zero server, data stays local)
- Do not change the `dedup_hash` algorithm — existing rows would lose their dedup protection
