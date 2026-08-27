"""Tests für das Seeding der Kategorien-Tabelle (CAT-25).

Zwei Fehler in ``ensure_initialized`` sorgten dafür, dass die Kategorien-Tabelle
unvollständig blieb:

1. ``zip(CATEGORIES, _DEFAULT_COLORS)`` brach nach 15 Farben ab — die letzten
   elf kanonischen Kategorien landeten nie in der DB.
2. Das Seeding lief nur bei komplett leerer Tabelle, entgegen der Zusage in
   ``CLAUDE.md``, dass eine neue Kategorie beim nächsten Start ergänzt wird.

Folge: der Prompt in ``category_discovery`` sah eine unvollständige Liste und
erfand Duplikate bereits vorhandener Kategorien ("Restaurants & Lieferdienste"
neben "Essen & Trinken").
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import queries
from app.models.category import Category
from app.models.transaction import CATEGORIES


def _run(coro):
    return asyncio.run(coro)


def _use_fresh_db(tmp_path, monkeypatch):
    # NullPool wie in app.database — jeder _run() öffnet eine eigene Event-Loop,
    # und gepoolte aiosqlite-Verbindungen überleben einen Loop-Wechsel nicht.
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", poolclass=NullPool
    )
    monkeypatch.setattr(queries, "engine", engine)
    monkeypatch.setattr(
        queries, "AsyncSessionLocal", async_sessionmaker(engine, expire_on_commit=False)
    )


def _category_names() -> set[str]:
    async def go():
        async with queries.AsyncSessionLocal() as db:
            return set((await db.execute(select(Category.name))).scalars())

    return _run(go())


def _category_rows() -> list[Category]:
    async def go():
        async with queries.AsyncSessionLocal() as db:
            return (await db.execute(select(Category))).scalars().all()

    return _run(go())


def test_all_canonical_categories_seeded(tmp_path, monkeypatch):
    _use_fresh_db(tmp_path, monkeypatch)
    _run(queries.ensure_initialized())

    assert set(CATEGORIES) <= _category_names()


def test_more_categories_than_colors(tmp_path, monkeypatch):
    """Regression: zip() verschluckte alles jenseits von _DEFAULT_COLORS."""
    assert len(CATEGORIES) > len(queries._DEFAULT_COLORS)

    _use_fresh_db(tmp_path, monkeypatch)
    _run(queries.ensure_initialized())

    rows = _category_rows()
    assert len(rows) >= len(CATEGORIES)
    assert all(c.color for c in rows)


def test_missing_category_added_on_later_start(tmp_path, monkeypatch):
    """Eine neu hinzugefügte Kategorie erreicht auch eine bereits gefüllte DB."""
    _use_fresh_db(tmp_path, monkeypatch)
    _run(queries.ensure_initialized())

    async def drop_last():
        async with queries.AsyncSessionLocal() as db:
            row = (
                await db.execute(select(Category).where(Category.name == CATEGORIES[-1]))
            ).scalar_one()
            await db.delete(row)
            await db.commit()

    _run(drop_last())
    assert CATEGORIES[-1] not in _category_names()

    _run(queries.ensure_initialized())
    assert CATEGORIES[-1] in _category_names()


def test_seeding_is_idempotent(tmp_path, monkeypatch):
    _use_fresh_db(tmp_path, monkeypatch)
    _run(queries.ensure_initialized())
    before = len(_category_rows())

    _run(queries.ensure_initialized())

    assert len(_category_rows()) == before
