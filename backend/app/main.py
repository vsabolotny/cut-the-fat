from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, AsyncSessionLocal
from .models import upload, transaction, merchant_rule, insights_cache, category  # noqa: F401 — register models
from .database import Base
from .routers import auth, uploads, transactions, dashboard, insights, categories


async def _seed_categories() -> None:
    """Insert default categories if the table is empty (idempotent)."""
    from sqlalchemy import select, func
    from .models.category import Category
    from .models.transaction import CATEGORIES

    DEFAULT_COLORS = [
        "#6366f1", "#22c55e", "#f97316", "#3b82f6", "#a855f7",
        "#ec4899", "#eab308", "#14b8a6", "#06b6d4", "#8b5cf6",
        "#64748b", "#78716c", "#10b981", "#94a3b8", "#9ca3af",
    ]

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(Category))).scalar_one()
        if count == 0:
            for name, color in zip(CATEGORIES, DEFAULT_COLORS):
                db.add(Category(name=name, color=color))
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Alembic handles migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_categories()
    yield
    await engine.dispose()


app = FastAPI(
    title="Cut the Fat API",
    description="Personal finance cost-cutting advisor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(insights.router)
app.include_router(categories.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
