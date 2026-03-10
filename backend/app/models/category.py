from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    color: Mapped[str] = mapped_column(String, nullable=False)
