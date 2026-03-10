Generate and apply an Alembic database migration for any recent model changes.

Steps:
1. Read the current state of all model files in `backend/app/models/` to understand what changed.
2. Run `cd /Users/ecog-vladislav/Projects/cut-the-fat/backend && .venv/bin/alembic revision --autogenerate -m "$ARGUMENTS"` where $ARGUMENTS is the migration description provided by the user (default: "auto migration" if none given).
3. Show the generated migration file content so the user can review it.
4. Ask the user to confirm before applying.
5. If confirmed, run `.venv/bin/alembic upgrade head` and report the result.

If $ARGUMENTS is empty, use "auto migration" as the message.
