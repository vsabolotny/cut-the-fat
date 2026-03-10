from io import BytesIO
from decimal import Decimal
import pandas as pd

from .csv_parser import (
    DATE_COLS, MERCHANT_COLS, AMOUNT_COLS, DEBIT_COLS, CREDIT_COLS,
    _normalize_col, _parse_date, _parse_amount,
)
from .base import RawTransaction


def parse_excel(content: bytes) -> list[RawTransaction]:
    """Parse Excel bank statement bytes into RawTransaction list."""
    # Try to find the sheet with most data
    xl = pd.ExcelFile(BytesIO(content))
    best_df = None
    best_rows = 0

    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet, dtype=str)
            df.dropna(how="all", inplace=True)
            if len(df) > best_rows:
                best_df = df
                best_rows = len(df)
        except Exception:
            continue

    if best_df is None or best_rows == 0:
        raise ValueError("No usable sheets found in Excel file")

    # Write to CSV bytes and reuse CSV parser logic
    buf = BytesIO()
    best_df.to_csv(buf, index=False)
    buf.seek(0)

    from .csv_parser import parse_csv
    return parse_csv(buf.read())
