"""
Integrity test: verifies that get_history() totals match raw SQL aggregations.
Run before showing any multi-month dashboard output.

  cd backend && ../.venv/bin/pytest tests/test_history_integrity.py -v
  # or from project root:
  backend/.venv/bin/pytest backend/tests/test_history_integrity.py -v
"""
import asyncio
import sys
from pathlib import Path

# Allow importing cli.db and app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


async def _raw_debit_totals(months_back: int) -> dict[tuple[str, str], float]:
    """Return {(month, category): total} via a plain SQL query (no get_history logic)."""
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text("""
                SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
                FROM transactions
                WHERE type='debit'
                  AND strftime('%Y-%m', date) >= strftime('%Y-%m', date('now', :offset))
                GROUP BY month, category
            """),
            {"offset": f"-{months_back} months"},
        )
        return {(row[0], row[1]): float(row[2]) for row in r.all()}


async def _raw_credit_totals(months_back: int) -> dict[tuple[str, str], float]:
    """Return {(month, category): total} for credits."""
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text("""
                SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
                FROM transactions
                WHERE type='credit'
                  AND strftime('%Y-%m', date) >= strftime('%Y-%m', date('now', :offset))
                GROUP BY month, category
            """),
            {"offset": f"-{months_back} months"},
        )
        return {(row[0], row[1]): float(row[2]) for row in r.all()}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("months_back", [3, 6, 12])
def test_history_debit_totals_match_raw_sql(months_back):
    """get_history() per-category totals must equal a direct GROUP BY query."""
    from cli.db import get_history

    history = get_history(months_back)
    raw = _run(_raw_debit_totals(months_back))

    # Build (month, category) → total from get_history() result
    months = history["months"]
    data = history["data"]

    history_totals: dict[tuple[str, str], float] = {}
    for cat, vals in data.items():
        for i, month in enumerate(months):
            if vals[i] != 0.0:
                history_totals[(month, cat)] = vals[i]

    # Every raw entry must appear in history_totals with matching value
    for (month, cat), expected in raw.items():
        assert (month, cat) in history_totals, (
            f"Missing in get_history(): month={month} category={cat} expected={expected:.2f}"
        )
        actual = history_totals[(month, cat)]
        assert abs(actual - expected) < 0.01, (
            f"Mismatch for month={month} category={cat}: "
            f"get_history()={actual:.2f} raw_sql={expected:.2f}"
        )

    # No extra entries should appear in history that aren't in raw
    for (month, cat), actual in history_totals.items():
        assert (month, cat) in raw, (
            f"Unexpected entry in get_history(): month={month} category={cat} value={actual:.2f}"
        )


@pytest.mark.parametrize("months_back", [3, 6, 12])
def test_history_monthly_totals_match_raw_sql(months_back):
    """monthly_totals in get_history() must equal sum of per-category raw debits."""
    from cli.db import get_history

    history = get_history(months_back)
    raw = _run(_raw_debit_totals(months_back))

    # Sum raw debits per month
    raw_month_totals: dict[str, float] = {}
    for (month, _cat), total in raw.items():
        raw_month_totals[month] = raw_month_totals.get(month, 0.0) + total

    for mt in history["monthly_totals"]:
        month = mt["month"]
        expected = raw_month_totals.get(month, 0.0)
        assert abs(mt["total"] - expected) < 0.01, (
            f"monthly_totals mismatch for {month}: "
            f"get_history()={mt['total']:.2f} raw_sql={expected:.2f}"
        )


@pytest.mark.parametrize("months_back", [3, 6, 12])
def test_history_income_matches_raw_sql(months_back):
    """monthly_income totals in get_history() must equal sum of raw credit amounts."""
    from cli.db import get_history

    history = get_history(months_back)
    raw = _run(_raw_credit_totals(months_back))

    raw_month_income: dict[str, float] = {}
    for (month, _cat), total in raw.items():
        raw_month_income[month] = raw_month_income.get(month, 0.0) + total

    for mi in history["monthly_income"]:
        month = mi["month"]
        expected = raw_month_income.get(month, 0.0)
        assert abs(mi["total"] - expected) < 0.01, (
            f"monthly_income mismatch for {month}: "
            f"get_history()={mi['total']:.2f} raw_sql={expected:.2f}"
        )


def test_no_partial_month_cutoff():
    """
    The first month in get_history(3) must include ALL its transactions,
    not just those after today-minus-3-months (the old day-level cutoff bug).
    Concretely: the first month's total must equal the raw SQL total for that month.
    """
    from cli.db import get_history
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    history = get_history(3)
    if not history["months"]:
        pytest.skip("No data in DB")

    first_month = history["months"][0]

    async def _month_total(m: str) -> float:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text("""
                    SELECT SUM(amount) FROM transactions
                    WHERE type='debit' AND strftime('%Y-%m', date) = :m
                """),
                {"m": m},
            )
            val = r.scalar_one_or_none()
            return float(val) if val else 0.0

    expected = _run(_month_total(first_month))

    # Find what get_history() says for this month
    months = history["months"]
    data = history["data"]
    idx = months.index(first_month)
    actual = sum(vals[idx] for vals in data.values())

    assert abs(actual - expected) < 0.01, (
        f"First month {first_month} total in get_history() is {actual:.2f} "
        f"but raw SQL says {expected:.2f} — possible partial-month cutoff bug"
    )
