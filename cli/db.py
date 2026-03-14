"""
Async DB + service wrappers for the CLI.
Each public function runs _run() so commands can call them synchronously.
"""
import asyncio
import hashlib
from pathlib import Path

# cli/__init__.py already put backend/ on sys.path


def _run(coro):
    """Run an async coroutine and dispose the SQLAlchemy engine in the same
    event loop to avoid 'non-checked-in connection' warnings."""
    async def _wrapper():
        try:
            return await coro
        finally:
            try:
                from app.database import engine
                await engine.dispose()
            except Exception:
                pass
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return asyncio.run(_wrapper())


# ---------------------------------------------------------------------------
# DB initialisation
# ---------------------------------------------------------------------------

_DEFAULT_COLORS = [
    "#6366f1", "#22c55e", "#f97316", "#3b82f6", "#a855f7",
    "#ec4899", "#eab308", "#14b8a6", "#06b6d4", "#8b5cf6",
    "#64748b", "#78716c", "#10b981", "#94a3b8", "#9ca3af",
]


async def _ensure_initialized() -> None:
    from app.database import engine, AsyncSessionLocal, Base
    from app.models import upload, transaction, merchant_rule, insights_cache, category  # noqa: register
    from app.models.category import Category
    from app.models.transaction import CATEGORIES
    from sqlalchemy import select, func

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(Category))).scalar_one()
        if count == 0:
            for name, color in zip(CATEGORIES, _DEFAULT_COLORS):
                db.add(Category(name=name, color=color))
            await db.commit()


def ensure_initialized() -> None:
    _run(_ensure_initialized())


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

async def _get_latest_month() -> str | None:
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT strftime('%Y-%m', date) FROM transactions WHERE type='debit' ORDER BY date DESC LIMIT 1")
        )
        row = result.first()
        return row[0] if row else None


def get_latest_month() -> str | None:
    return _run(_get_latest_month())


async def _get_summary(month: str) -> dict:
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE type='debit' AND strftime('%Y-%m', date) = :month
                GROUP BY category ORDER BY total DESC
            """),
            {"month": month},
        )
        rows = result.all()
    cats = [{"category": r[0], "total": float(r[1])} for r in rows]

    async with AsyncSessionLocal() as db2:
        income_result = await db2.execute(
            text("""
                SELECT merchant, category, SUM(amount) as total
                FROM transactions
                WHERE type='credit' AND strftime('%Y-%m', date) = :month
                GROUP BY merchant, category ORDER BY total DESC
            """),
            {"month": month},
        )
        income_rows = income_result.all()
    income = [{"merchant": r[0], "category": r[1], "total": float(r[2])} for r in income_rows]

    return {
        "month": month,
        "total": sum(c["total"] for c in cats),
        "categories": cats,
        "income": income,
        "income_total": sum(i["total"] for i in income),
    }


def get_summary(month: str) -> dict:
    return _run(_get_summary(month))


async def _get_comparison(month: str) -> dict:
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    year, mon = int(month[:4]), int(month[5:])
    prev_year, prev_mon = (year - 1, 12) if mon == 1 else (year, mon - 1)
    prev_month = f"{prev_year:04d}-{prev_mon:02d}"

    async def monthly_totals(m: str, db) -> dict:
        r = await db.execute(
            text("""
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE type='debit' AND strftime('%Y-%m', date) = :month
                GROUP BY category
            """),
            {"month": m},
        )
        return {row[0]: float(row[1]) for row in r.all()}

    async with AsyncSessionLocal() as db:
        curr = await monthly_totals(month, db)
        prev = await monthly_totals(prev_month, db)

    curr_total = sum(curr.values())
    prev_total = sum(prev.values())
    delta = curr_total - prev_total
    return {
        "current_month": month,
        "previous_month": prev_month,
        "current_total": curr_total,
        "previous_total": prev_total,
        "delta": delta,
        "delta_pct": (delta / prev_total * 100) if prev_total else None,
        "current_categories": curr,
        "previous_categories": prev,
    }


def get_comparison(month: str) -> dict:
    return _run(_get_comparison(month))


async def _get_insights_data(force: bool = False) -> dict:
    from app.database import AsyncSessionLocal
    from app.services.insights import get_insights as _svc_get_insights

    async with AsyncSessionLocal() as db:
        return await _svc_get_insights(db, force=force)


def get_insights_data(force: bool = False) -> dict:
    return _run(_get_insights_data(force))


async def _get_uncategorized_merchants() -> list[dict]:
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT merchant_normalized, COUNT(*) as n, MIN(merchant) as sample
                FROM transactions
                WHERE category='Sonstiges' AND type='debit'
                GROUP BY merchant_normalized
                ORDER BY n DESC
            """)
        )
    return [{"merchant": r[0], "count": r[1], "display": r[2]} for r in result.all()]


def get_uncategorized_merchants() -> list[dict]:
    return _run(_get_uncategorized_merchants())


async def _apply_rule(merchant_normalized: str, category: str) -> int:
    from app.database import AsyncSessionLocal
    from app.models.merchant_rule import MerchantRule
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        existing = await db.get(MerchantRule, merchant_normalized)
        if existing:
            existing.category = category
        else:
            db.add(MerchantRule(merchant_normalized=merchant_normalized, category=category))
        result = await db.execute(
            text("UPDATE transactions SET category=:cat, category_source='rule' WHERE merchant_normalized=:m"),
            {"cat": category, "m": merchant_normalized},
        )
        await db.commit()
        return result.rowcount


def apply_rule(merchant_normalized: str, category: str) -> int:
    return _run(_apply_rule(merchant_normalized, category))


async def _get_ai_suggestions(merchants: list[str], categories: list[str]) -> dict[str, str]:
    from app.services.categorizer import categorize_merchants

    return await categorize_merchants(merchants, categories)


def get_ai_suggestions(merchants: list[str], categories: list[str]) -> dict[str, str]:
    return _run(_get_ai_suggestions(merchants, categories))


async def _get_all_categories() -> list[str]:
    from app.database import AsyncSessionLocal
    from app.models.category import Category
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Category.name).order_by(Category.id))
        names = [r[0] for r in result.all()]
    return names if names else []


def get_all_categories() -> list[str]:
    return _run(_get_all_categories())


async def _get_history(months: int) -> dict:
    """Return per-month, per-category totals for the last N months."""
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
                FROM transactions
                WHERE type='debit'
                  AND date >= date('now', :offset)
                GROUP BY month, category
                ORDER BY month ASC
            """),
            {"offset": f"-{months} months"},
        )
        rows = result.all()

    async with AsyncSessionLocal() as db2:
        inc_result = await db2.execute(
            text("""
                SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
                FROM transactions
                WHERE type='credit'
                  AND date >= date('now', :offset)
                GROUP BY month, category
                ORDER BY month ASC
            """),
            {"offset": f"-{months} months"},
        )
        inc_rows = inc_result.all()

    months_list = sorted({r[0] for r in rows} | {r[0] for r in inc_rows})
    categories_list = sorted({r[1] for r in rows})
    month_index = {m: i for i, m in enumerate(months_list)}

    # data[category][month_index] = total (debit)
    data: dict[str, list[float]] = {
        cat: [0.0] * len(months_list) for cat in categories_list
    }
    for row in rows:
        data[row[1]][month_index[row[0]]] = float(row[2])

    monthly_totals = [
        {"month": m, "total": sum(data[cat][i] for cat in categories_list)}
        for i, m in enumerate(months_list)
    ]

    # income per month: total, natalie portion
    income_by_month: dict[str, float] = {m: 0.0 for m in months_list}
    natalie_income_by_month: dict[str, float] = {m: 0.0 for m in months_list}
    for row in inc_rows:
        m, cat, total = row[0], row[1], float(row[2])
        income_by_month[m] = income_by_month.get(m, 0.0) + total
        if "Natalie" in cat:
            natalie_income_by_month[m] = natalie_income_by_month.get(m, 0.0) + total

    monthly_income = [
        {"month": m, "total": income_by_month[m], "natalie": natalie_income_by_month[m]}
        for m in months_list
    ]

    return {
        "months": months_list,
        "categories": categories_list,
        "data": data,
        "monthly_totals": monthly_totals,
        "monthly_income": monthly_income,
    }


def get_history(months: int) -> dict:
    return _run(_get_history(months))


# ---------------------------------------------------------------------------
# File ingest
# ---------------------------------------------------------------------------

async def _ingest_file(filepath: str, progress_cb=None) -> dict:
    import shutil
    from app.database import AsyncSessionLocal
    from app.models.upload import Upload
    from app.models.transaction import Transaction
    from app.models.merchant_rule import MerchantRule
    from app.services.categorizer import normalize_merchant, categorize_merchants
    from app.services.category_discovery import discover_and_save_categories
    from sqlalchemy import select

    path = Path(filepath)
    content = path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()
    filename = path.name
    ext = path.suffix.lower()

    if ext == ".csv":
        from app.services.parser.csv_parser import parse_csv
        raw = parse_csv(content)
    elif ext in (".xlsx", ".xls"):
        from app.services.parser.excel_parser import parse_excel
        raw = parse_excel(content)
    elif ext == ".pdf":
        from app.services.parser.pdf_parser import parse_pdf
        raw = parse_pdf(content)
    else:
        raise ValueError(f"Nicht unterstütztes Dateiformat: {ext}")

    if not raw:
        raise ValueError("Keine Transaktionen in der Datei gefunden.")

    async with AsyncSessionLocal() as db:
        dup = await db.execute(select(Upload).where(Upload.file_hash == file_hash))
        if dup.scalar_one_or_none():
            raise ValueError("Diese Datei wurde bereits importiert.")

        upload = Upload(filename=filename, file_hash=file_hash, status="processing")
        db.add(upload)
        await db.flush()

        rules_r = await db.execute(select(MerchantRule))
        rules = {r.merchant_normalized: r.category for r in rules_r.scalars()}
        hashes = {h for (h,) in (await db.execute(select(Transaction.dedup_hash))).all()}

        to_categorize, with_rule, skipped = [], [], 0
        for txn in raw:
            norm = normalize_merchant(txn.merchant)
            dedup = hashlib.sha256(f"{txn.date}|{txn.merchant.lower()}|{txn.amount}".encode()).hexdigest()
            if dedup in hashes:
                skipped += 1
                continue
            hashes.add(dedup)
            if norm in rules:
                with_rule.append((txn, norm, dedup, rules[norm], "rule"))
            else:
                to_categorize.append((txn, norm, dedup))

        if progress_cb:
            progress_cb("kategorisierung", len(to_categorize))

        all_merchants = list({normalize_merchant(t.merchant) for t in raw})
        valid_cats = await discover_and_save_categories(all_merchants, db)

        unique_merchants = list({t[1] for t in to_categorize})
        cat_map = {}
        if unique_merchants:
            cat_map = await categorize_merchants(unique_merchants, valid_cats)

        all_txns = []
        for txn, norm, dedup, cat, src in with_rule:
            all_txns.append(Transaction(
                upload_id=upload.id, date=txn.date, merchant=txn.merchant,
                merchant_normalized=norm, description=txn.description,
                amount=txn.amount, type=txn.type, category=cat,
                category_source=src, dedup_hash=dedup,
            ))
        for txn, norm, dedup in to_categorize:
            cat = cat_map.get(norm, "Sonstiges")
            all_txns.append(Transaction(
                upload_id=upload.id, date=txn.date, merchant=txn.merchant,
                merchant_normalized=norm, description=txn.description,
                amount=txn.amount, type=txn.type, category=cat,
                category_source="ai", dedup_hash=dedup,
            ))

        db.add_all(all_txns)
        upload.row_count = len(all_txns)
        upload.status = "done"
        await db.commit()

    # Copy original file to data/statements/
    dest_dir = Path(__file__).resolve().parents[1] / "data" / "statements"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if not dest.exists():
        shutil.copy2(str(path), str(dest))

    return {"filename": filename, "imported": len(all_txns), "skipped": skipped, "parsed": len(raw)}


def ingest_file(filepath: str, progress_cb=None) -> dict:
    return _run(_ingest_file(filepath, progress_cb))
