from datetime import datetime
from pydantic import BaseModel


class InsightItem(BaseModel):
    id: str
    text: str
    type: str  # warning / info / success


class InsightsResponse(BaseModel):
    insights: list[InsightItem]
    generated_at: datetime | None = None
    cached: bool = False
