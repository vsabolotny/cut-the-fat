from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: int
    upload_id: int
    date: date
    merchant: str
    merchant_normalized: str
    description: str
    amount: Decimal
    type: str
    category: str
    category_source: str

    model_config = {"from_attributes": True}


class CategoryUpdateRequest(BaseModel):
    category: str


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
