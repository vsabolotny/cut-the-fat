Run a full health check of the codebase: verify backend imports, run a frontend type check, and run a frontend production build. Report any errors clearly.

Steps:
1. Run `cd /Users/ecog-vladislav/Projects/cut-the-fat/backend && .venv/bin/python -c "from app.main import app; print('Backend imports: OK')"` — report pass/fail
2. Run `cd /Users/ecog-vladislav/Projects/cut-the-fat/frontend && npx tsc --noEmit 2>&1` — report any TypeScript errors
3. Run `cd /Users/ecog-vladislav/Projects/cut-the-fat/frontend && npm run build 2>&1 | tail -8` — report build result and bundle size

Summarize results at the end: how many checks passed, what failed (if anything), and what to fix.
