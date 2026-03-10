from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class RawTransaction:
    date: date
    merchant: str
    description: str
    amount: Decimal
    type: str  # "debit" or "credit"
