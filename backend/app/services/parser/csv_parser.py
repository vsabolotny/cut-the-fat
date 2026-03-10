import re
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
import pandas as pd

from .base import RawTransaction

# Common date formats in bank statements
DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%b %d, %Y",
    "%d-%b-%Y",
    "%d/%b/%Y",
]

# Common column name patterns
DATE_COLS = ["date", "transaction date", "trans date", "posted date", "value date", "posting date"]
MERCHANT_COLS = ["merchant", "description", "payee", "transaction description", "details", "memo", "narration", "particulars", "name"]
AMOUNT_COLS = ["amount", "debit", "credit", "transaction amount", "sum", "value"]
DEBIT_COLS = ["debit", "debit amount", "withdrawal", "withdrawals", "dr", "charge"]
CREDIT_COLS = ["credit", "credit amount", "deposit", "deposits", "cr", "payment"]


def _normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(name).lower().strip())


def _parse_date(val) -> date | None:
    import pandas as pd
    if pd.isna(val):
        return None
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def _parse_amount(val) -> Decimal | None:
    if val is None:
        return None
    try:
        import pandas as pd
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = re.sub(r"[^\d.\-]", "", str(val).replace(",", ""))
    if not s or s == "-":
        return None
    try:
        return abs(Decimal(s))
    except InvalidOperation:
        return None


def parse_csv(content: bytes) -> list[RawTransaction]:
    """Parse CSV bank statement bytes into RawTransaction list."""
    try:
        df = pd.read_csv(BytesIO(content), dtype=str, skip_blank_lines=True)
    except Exception:
        # Try with different encoding
        df = pd.read_csv(StringIO(content.decode("latin-1")), dtype=str, skip_blank_lines=True)

    # Drop fully empty rows
    df.dropna(how="all", inplace=True)

    # Normalize column names
    col_map = {col: _normalize_col(col) for col in df.columns}
    df.rename(columns=col_map, inplace=True)
    cols = list(df.columns)

    # Find date column
    date_col = next((c for c in cols if c in DATE_COLS), None)
    if not date_col:
        date_col = next((c for c in cols if "date" in c), None)
    if not date_col:
        raise ValueError(f"Cannot find date column. Columns: {cols}")

    # Find merchant/description column
    merchant_col = next((c for c in cols if c in MERCHANT_COLS), None)
    if not merchant_col:
        merchant_col = next((c for c in cols if any(k in c for k in ["desc", "merchant", "payee", "detail", "memo"])), None)
    if not merchant_col:
        raise ValueError(f"Cannot find description column. Columns: {cols}")

    # Detect debit/credit split columns vs single amount column
    debit_col = next((c for c in cols if c in DEBIT_COLS), None)
    credit_col = next((c for c in cols if c in CREDIT_COLS), None)
    amount_col = next((c for c in cols if c in AMOUNT_COLS and c not in DEBIT_COLS and c not in CREDIT_COLS), None)

    transactions = []
    for _, row in df.iterrows():
        txn_date = _parse_date(row.get(date_col))
        if not txn_date:
            continue

        merchant = str(row.get(merchant_col, "")).strip()
        if not merchant:
            continue

        if debit_col and credit_col:
            debit_val = _parse_amount(row.get(debit_col))
            credit_val = _parse_amount(row.get(credit_col))
            if debit_val and debit_val > 0:
                amount = debit_val
                txn_type = "debit"
            elif credit_val and credit_val > 0:
                amount = credit_val
                txn_type = "credit"
            else:
                continue
        elif amount_col:
            raw = str(row.get(amount_col, "")).strip()
            if not raw:
                continue
            # Negative = credit for some banks
            is_negative = raw.startswith("-")
            amount = _parse_amount(raw)
            if amount is None:
                continue
            txn_type = "credit" if is_negative else "debit"
        else:
            # Last resort: find any numeric-looking column
            for c in cols:
                if c in (date_col, merchant_col):
                    continue
                val = _parse_amount(row.get(c))
                if val and val > 0:
                    amount = val
                    txn_type = "debit"
                    break
            else:
                continue

        transactions.append(RawTransaction(
            date=txn_date,
            merchant=merchant,
            description=merchant,
            amount=amount,
            type=txn_type,
        ))

    return transactions
