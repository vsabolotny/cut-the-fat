from pydantic import BaseModel
from decimal import Decimal


class CategoryTotal(BaseModel):
    category: str
    total: Decimal


class MonthlySummary(BaseModel):
    month: str  # YYYY-MM
    total: Decimal
    categories: list[CategoryTotal]


class ComparisonResponse(BaseModel):
    current_month: str
    previous_month: str
    current_total: Decimal
    previous_total: Decimal
    delta: Decimal
    delta_pct: float | None
    category_deltas: list[dict]


class HistoryResponse(BaseModel):
    months: list[str]
    categories: list[str]
    data: dict[str, list[Decimal]]  # category -> list of monthly totals
