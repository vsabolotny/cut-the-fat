from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from .models import upload, transaction, merchant_rule, insights_cache  # noqa: F401 — register models
from .database import Base
from .routers import auth, uploads, transactions, dashboard, insights


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Alembic handles migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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


@app.get("/health")
async def health():
    return {"status": "ok"}
