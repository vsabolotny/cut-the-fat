from datetime import date
from decimal import Decimal
from sqlalchemy import Integer, String, Date, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


CATEGORIES = [
    "Housing",
    "Groceries",
    "Dining",
    "Transportation",
    "Entertainment",
    "Health",
    "Shopping",
    "Subscriptions",
    "Travel",
    "Education",
    "Utilities",
    "Insurance",
    "Income",
    "Transfers",
    "Other",
]


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    merchant: Mapped[str] = mapped_column(String, nullable=False)
    merchant_normalized: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String, default="debit")  # debit / credit
    category: Mapped[str] = mapped_column(String, default="Other")
    category_source: Mapped[str] = mapped_column(String, default="ai")  # ai / rule / manual
    dedup_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    upload: Mapped["Upload"] = relationship("Upload", back_populates="transactions")
