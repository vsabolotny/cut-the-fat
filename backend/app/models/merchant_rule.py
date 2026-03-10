from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class MerchantRule(Base):
    __tablename__ = "merchant_rules"

    merchant_normalized: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
