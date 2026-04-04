import re
from datetime import date, datetime
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
    "%d.%m.%Y",   # German: 27.2.2026
    "%d.%m.%y",   # German short year
]

# Merchant field values that are actually card-payment placeholders.
# The real merchant is in the description/Verwendungszweck before the first "//".
_CARD_PLACEHOLDERS = {
    "abrechnung karte",
    "kartenzahlung",
    "card payment",
    "pos-zahlung",
    "pos zahlung",
}


def _extract_card_merchant(merchant: str, description: str) -> str:
    """If merchant is a card-payment placeholder, extract real merchant from description."""
    if merchant.lower().strip() not in _CARD_PLACEHOLDERS:
        return merchant
    # Description format: "REAL MERCHANT//CITY/DE DATE Kartennr. ..."
    if "//" in description:
        real = description.split("//")[0].strip()
        if real:
            return real
    return merchant


# Common column name patterns (normalized to lowercase)
DATE_COLS = [
    "date", "transaction date", "trans date", "posted date", "value date",
    "posting date",
    # German
    "buchungstag", "buchungsdatum", "wertstellung", "valutadatum",
]
MERCHANT_COLS = [
    "merchant", "description", "payee", "transaction description", "details",
    "memo", "narration", "particulars", "name",
    # German
    "begunstigter  auftraggeber", "begunstigter auftraggeber",
    "auftraggeber  begunstigter", "empfanger", "glaubiger",
    "verwendungszweck",
]
AMOUNT_COLS = [
    "amount", "transaction amount", "sum",
    # German
    "betrag", "umsatz",
]
DEBIT_COLS = [
    "debit", "debit amount", "withdrawal", "withdrawals", "dr", "charge",
    # German
    "soll", "belastung", "ausgabe",
]
CREDIT_COLS = [
    "credit", "credit amount", "deposit", "deposits", "cr", "payment",
    # German
    "haben", "gutschrift", "einnahme",
]


def _normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(name).lower().strip())


def _parse_date(val) -> date | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


def _parse_amount(val) -> Decimal | None:
    """Parse amount handling both Anglo (1,234.56) and European (1.234,56) formats."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass

    s = str(val).strip()
    if not s:
        return None

    # Strip currency symbols so they don't interfere with format detection
    s = s.replace("€", "").replace("$", "").replace("£", "").strip()

    # Detect European format: comma is decimal separator, dot is thousands separator.
    # Heuristic: if there's a comma and it's followed by exactly 1 or 2 digits at the end.
    european = bool(re.search(r",\d{1,2}$", s))
    # German thousands-only: dot followed by exactly 3 digits at end, no comma → e.g. "-1.990" = 1990
    german_thousands = not european and bool(re.search(r"\.\d{3}$", s)) and "," not in s

    if european:
        # Remove dots (thousands separators), replace comma with dot (decimal)
        s = s.replace(".", "").replace(",", ".")
    elif german_thousands:
        # Remove dots (thousands separators), no decimal part
        s = s.replace(".", "")
    else:
        # Remove commas (thousands separators), keep dot as decimal
        s = s.replace(",", "")

    # Strip everything except digits, dot, and leading minus
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s == "-":
        return None

    try:
        return abs(Decimal(s))
    except InvalidOperation:
        return None


def _detect_separator(content: bytes) -> str:
    """Sniff the column separator from the first line."""
    try:
        first_line = content.lstrip(b"\xef\xbb\xbf").split(b"\n")[0].decode("utf-8", errors="replace")
    except Exception:
        return ","
    semicolons = first_line.count(";")
    commas = first_line.count(",")
    tabs = first_line.count("\t")
    return max([(";", semicolons), (",", commas), ("\t", tabs)], key=lambda x: x[1])[0]


def _read_df(content: bytes) -> pd.DataFrame:
    """Try several encoding + separator combinations, always skipping bad lines.
    Auto-detects header row by skipping leading rows where most columns are unnamed."""
    sep = _detect_separator(content)
    read_kwargs = dict(
        dtype=str,
        sep=sep,
        skip_blank_lines=True,
        on_bad_lines="skip",
        encoding_errors="replace",
    )
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        for skip in (0, 1, 2, 3):
            try:
                df = pd.read_csv(BytesIO(content), encoding=enc, skiprows=skip, **read_kwargs)
                if len(df.columns) < 2:
                    continue
                # Check if this looks like a real header: at most half the columns should be "unnamed"
                unnamed = sum(1 for c in df.columns if str(c).lower().startswith("unnamed"))
                if unnamed <= len(df.columns) // 2:
                    return df
            except Exception:
                continue
    raise ValueError("Could not parse CSV with any known encoding")


def parse_csv(content: bytes) -> list[RawTransaction]:
    """Parse CSV bank statement bytes into RawTransaction list."""
    df = _read_df(content)
    df.dropna(how="all", inplace=True)

    # Normalize column names
    col_map = {col: _normalize_col(col) for col in df.columns}
    df.rename(columns=col_map, inplace=True)
    cols = list(df.columns)

    # Find date column
    date_col = next((c for c in cols if c in DATE_COLS), None)
    if not date_col:
        date_col = next((c for c in cols if "date" in c or "tag" in c or "datum" in c), None)
    if not date_col:
        raise ValueError(f"Cannot find date column. Columns: {cols}")

    # Find merchant/description column — prefer counterparty name over purpose text
    merchant_col = next((c for c in cols if c in MERCHANT_COLS), None)
    if not merchant_col:
        merchant_col = next(
            (c for c in cols if any(k in c for k in ["desc", "merchant", "payee", "detail", "memo", "zweck", "empf"])),
            None,
        )
    if not merchant_col:
        raise ValueError(f"Cannot find description column. Columns: {cols}")

    # For German statements: prefer counterparty name (Begünstigter) as merchant,
    # use Verwendungszweck as description if both exist
    desc_col = None
    counterparty_col = next(
        (c for c in cols if "beg" in c or "auftraggeber" in c or "empf" in c), None
    )
    purpose_col = next((c for c in cols if "zweck" in c), None)
    if counterparty_col and purpose_col:
        merchant_col = counterparty_col
        desc_col = purpose_col

    # Detect debit/credit split columns vs single amount column
    debit_col = next((c for c in cols if c in DEBIT_COLS), None)
    credit_col = next((c for c in cols if c in CREDIT_COLS), None)
    amount_col = next(
        (c for c in cols if c in AMOUNT_COLS and c not in DEBIT_COLS and c not in CREDIT_COLS), None
    )

    transactions = []
    for _, row in df.iterrows():
        txn_date = _parse_date(row.get(date_col))
        if not txn_date:
            continue

        merchant = str(row.get(merchant_col, "")).strip()
        if not merchant or merchant.lower() in ("nan", "none", ""):
            continue

        description = merchant
        if desc_col:
            raw_desc = str(row.get(desc_col, "")).strip()
            if raw_desc and raw_desc.lower() not in ("nan", "none", ""):
                description = raw_desc

        # For card payments the real merchant is in the description
        merchant = _extract_card_merchant(merchant, description)

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
            if not raw or raw.lower() in ("nan", "none"):
                continue
            is_negative = raw.lstrip().startswith("-")
            amount = _parse_amount(raw)
            if amount is None:
                continue
            txn_type = "credit" if is_negative else "debit"
        else:
            # Last resort: find any numeric-looking column
            found = False
            for c in cols:
                if c in (date_col, merchant_col):
                    continue
                val = _parse_amount(row.get(c))
                if val and val > 0:
                    amount = val
                    txn_type = "debit"
                    found = True
                    break
            if not found:
                continue

        transactions.append(RawTransaction(
            date=txn_date,
            merchant=merchant,
            description=description,
            amount=amount,
            type=txn_type,
        ))

    return transactions
