"""
Sync wrappers over async query functions for the CLI.
Each public function runs _run() so Click commands can call them synchronously.
"""
import asyncio
import warnings

# cli/__init__.py already put backend/ on sys.path
from app.queries import (
    ensure_initialized as _ensure_initialized,
    get_latest_month as _get_latest_month,
    get_summary as _get_summary,
    get_comparison as _get_comparison,
    get_insights_data as _get_insights_data,
    get_uncategorized_merchants as _get_uncategorized_merchants,
    apply_rule as _apply_rule,
    get_ai_suggestions as _get_ai_suggestions,
    get_all_categories as _get_all_categories,
    get_history as _get_history,
    ingest_file as _ingest_file,
)


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
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return asyncio.run(_wrapper())


def ensure_initialized() -> None:
    _run(_ensure_initialized())


def get_latest_month() -> str | None:
    return _run(_get_latest_month())


def get_summary(month: str) -> dict:
    return _run(_get_summary(month))


def get_comparison(month: str) -> dict:
    return _run(_get_comparison(month))


def get_insights_data(force: bool = False) -> dict:
    return _run(_get_insights_data(force))


def get_uncategorized_merchants() -> list[dict]:
    return _run(_get_uncategorized_merchants())


def apply_rule(merchant_normalized: str, category: str) -> int:
    return _run(_apply_rule(merchant_normalized, category))


def get_ai_suggestions(merchants: list[str], categories: list[str]) -> dict[str, str]:
    return _run(_get_ai_suggestions(merchants, categories))


def get_all_categories() -> list[str]:
    return _run(_get_all_categories())


def get_history(months: int) -> dict:
    return _run(_get_history(months))


def ingest_file(filepath: str, progress_cb=None) -> dict:
    return _run(_ingest_file(filepath, progress_cb))
