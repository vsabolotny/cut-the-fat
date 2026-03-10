Add a new spending category to the app. Categories must be kept in sync between backend and frontend.

The user will name the new category. Follow these steps:

1. Read `backend/app/models/transaction.py` — find the `CATEGORIES` list and add the new category in alphabetical position.
2. Read `frontend/src/api/transactions.ts` — add the same category string to the `CATEGORIES` array and assign it a color in `CATEGORY_COLORS` (pick a hex color that visually distinguishes it from existing ones).
3. Confirm both files are updated with the exact same category name (case-sensitive).
4. Run the backend import check: `cd /Users/ecog-vladislav/Projects/cut-the-fat/backend && .venv/bin/python -c "from app.models.transaction import CATEGORIES; print(CATEGORIES)"`
5. Run the frontend type check: `cd /Users/ecog-vladislav/Projects/cut-the-fat/frontend && npx tsc --noEmit`
6. Report the new category name and its assigned color.

Note: existing transactions already in the DB are not affected — they keep their old category. The new category only applies to future uploads and manual reassignments.
