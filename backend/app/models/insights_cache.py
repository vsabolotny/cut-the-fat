from datetime import datetime
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class InsightsCache(Base):
    __tablename__ = "insights_cache"

    data_hash: Mapped[str] = mapped_column(String, primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
