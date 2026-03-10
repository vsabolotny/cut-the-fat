from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..auth import require_auth
from ..database import get_db
from ..schemas.dashboard import MonthlySummary, CategoryTotal, ComparisonResponse, HistoryResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])


@router.get("/summary", response_model=MonthlySummary)
async def get_summary(
    month: str | None = Query(None, description="YYYY-MM, defaults to current month"),
    db: AsyncSession = Depends(get_db),
) -> MonthlySummary:
    if not month:
        from datetime import datetime
        month = datetime.utcnow().strftime("%Y-%m")

    result = await db.execute(
        text("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE type = 'debit'
              AND strftime('%Y-%m', date) = :month
            GROUP BY category
            ORDER BY total DESC
        """),
        {"month": month},
    )
    rows = result.all()
    categories = [CategoryTotal(category=r[0], total=Decimal(str(r[1]))) for r in rows]
    total = sum(c.total for c in categories)
    return MonthlySummary(month=month, total=total, categories=categories)


@router.get("/comparison", response_model=ComparisonResponse)
async def get_comparison(
    month: str | None = Query(None, description="YYYY-MM of current month"),
    db: AsyncSession = Depends(get_db),
) -> ComparisonResponse:
    from datetime import datetime

    if not month:
        now = datetime.utcnow()
        month = now.strftime("%Y-%m")

    # Parse month to get previous month
    year, mon = int(month[:4]), int(month[5:])
    if mon == 1:
        prev_year, prev_mon = year - 1, 12
    else:
        prev_year, prev_mon = year, mon - 1
    prev_month = f"{prev_year:04d}-{prev_mon:02d}"

    async def get_monthly_totals(m: str) -> dict:
        result = await db.execute(
            text("""
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE type = 'debit'
                  AND strftime('%Y-%m', date) = :month
                GROUP BY category
            """),
            {"month": m},
        )
        return {r[0]: Decimal(str(r[1])) for r in result.all()}

    curr_cats = await get_monthly_totals(month)
    prev_cats = await get_monthly_totals(prev_month)

    current_total = sum(curr_cats.values(), Decimal(0))
    previous_total = sum(prev_cats.values(), Decimal(0))
    delta = current_total - previous_total
    delta_pct = float(delta / previous_total * 100) if previous_total else None

    all_categories = set(curr_cats) | set(prev_cats)
    category_deltas = [
        {
            "category": cat,
            "current": float(curr_cats.get(cat, 0)),
            "previous": float(prev_cats.get(cat, 0)),
            "delta": float(curr_cats.get(cat, 0) - prev_cats.get(cat, 0)),
        }
        for cat in sorted(all_categories)
    ]

    return ComparisonResponse(
        current_month=month,
        previous_month=prev_month,
        current_total=current_total,
        previous_total=previous_total,
        delta=delta,
        delta_pct=delta_pct,
        category_deltas=category_deltas,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    result = await db.execute(
        text("""
            SELECT
                strftime('%Y-%m', date) as month,
                category,
                SUM(amount) as total
            FROM transactions
            WHERE type = 'debit'
              AND date >= date('now', :months_ago)
            GROUP BY month, category
            ORDER BY month ASC
        """),
        {"months_ago": f"-{months} months"},
    )
    rows = result.all()

    months_set = sorted({r[0] for r in rows})
    categories_set = sorted({r[1] for r in rows})

    data: dict[str, list[Decimal]] = {
        cat: [Decimal(0)] * len(months_set) for cat in categories_set
    }
    month_index = {m: i for i, m in enumerate(months_set)}

    for row in rows:
        month, category, total = row
        if category in data and month in month_index:
            data[category][month_index[month]] = Decimal(str(total))

    return HistoryResponse(
        months=months_set,
        categories=categories_set,
        data={cat: vals for cat, vals in data.items()},
    )
