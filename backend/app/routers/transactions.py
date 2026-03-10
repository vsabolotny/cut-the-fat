from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from io import StringIO
import csv

from ..auth import require_auth
from ..database import get_db
from ..models.transaction import Transaction, CATEGORIES
from ..models.merchant_rule import MerchantRule
from ..schemas.transaction import TransactionResponse, CategoryUpdateRequest, TransactionListResponse

router = APIRouter(prefix="/api/transactions", tags=["transactions"], dependencies=[Depends(require_auth)])


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    month: str | None = Query(None, description="YYYY-MM"),
    category: str | None = Query(None),
    search: str | None = Query(None),
    type: str | None = Query(None, description="debit or credit"),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    filters = []
    if month:
        from sqlalchemy import extract
        year, mon = month.split("-")
        filters.append(extract("year", Transaction.date) == int(year))
        filters.append(extract("month", Transaction.date) == int(mon))
    if category:
        filters.append(Transaction.category == category)
    if type:
        filters.append(Transaction.type == type)
    if search:
        filters.append(
            or_(
                Transaction.merchant.ilike(f"%{search}%"),
                Transaction.description.ilike(f"%{search}%"),
            )
        )

    where = and_(*filters) if filters else True

    total_result = await db.execute(select(func.count()).select_from(Transaction).where(where))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Transaction)
        .where(where)
        .order_by(Transaction.date.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [TransactionResponse.model_validate(t) for t in result.scalars()]
    return TransactionListResponse(items=items, total=total)


@router.patch("/{transaction_id}/category", response_model=TransactionResponse)
async def update_category(
    transaction_id: int,
    request: CategoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    if request.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {request.category}")

    txn = await db.get(Transaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn.category = request.category
    txn.category_source = "manual"

    # Upsert merchant rule
    rule = await db.get(MerchantRule, txn.merchant_normalized)
    if rule:
        rule.category = request.category
    else:
        rule = MerchantRule(merchant_normalized=txn.merchant_normalized, category=request.category)
        db.add(rule)

    await db.commit()
    return TransactionResponse.model_validate(txn)


@router.get("/export")
async def export_transactions(
    month: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    filters = []
    if month:
        from sqlalchemy import extract
        year, mon = month.split("-")
        filters.append(extract("year", Transaction.date) == int(year))
        filters.append(extract("month", Transaction.date) == int(mon))
    if category:
        filters.append(Transaction.category == category)

    where = and_(*filters) if filters else True
    result = await db.execute(select(Transaction).where(where).order_by(Transaction.date.desc()))
    transactions = result.scalars().all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Merchant", "Description", "Amount", "Type", "Category", "Category Source"])
    for t in transactions:
        writer.writerow([t.date, t.merchant, t.description, t.amount, t.type, t.category, t.category_source])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )
