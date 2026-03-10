import re
from datetime import date, datetime
from io import BytesIO

import pdfplumber

from .base import RawTransaction
from .csv_parser import DATE_FORMATS, _parse_amount

# Patterns for date detection
DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}\s+\w{3}\s+\d{4}|\w{3}\s+\d{1,2},?\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{2,4})\b"
)
# Matches both USD (1,234.56 or $1,234.56) and EUR (1.234,56 or 1234,56) formats
AMOUNT_PATTERN = re.compile(r"[\$€]?[\d\.]+,\d{2}|[\$€]?[\d,]+\.\d{2}")


def _try_parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        import pandas as pd
        return pd.to_datetime(s).date()
    except Exception:
        return None


def _extract_from_tables(pdf) -> list[RawTransaction]:
    """Try table extraction first — works well for structured PDFs."""
    transactions = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if not table or len(table) < 2:
                continue
            # Use first row as header
            headers = [str(h or "").lower().strip() for h in table[0]]
            for row in table[1:]:
                if not row or all(c is None or str(c).strip() == "" for c in row):
                    continue
                row_dict = {headers[i]: str(row[i] or "").strip() for i in range(min(len(headers), len(row)))}

                # Find date (English + German column names)
                txn_date = None
                for key in ["date", "transaction date", "trans date", "posted date",
                            "buchungstag", "buchungsdatum", "wertstellung", "valutadatum"]:
                    if key in row_dict and row_dict[key]:
                        txn_date = _try_parse_date(row_dict[key])
                        if txn_date:
                            break

                if not txn_date:
                    # Try first column
                    if row and row[0]:
                        txn_date = _try_parse_date(str(row[0]))

                if not txn_date:
                    continue

                # Find description (English + German column names)
                desc = ""
                for key in ["description", "merchant", "payee", "details", "memo", "narration",
                            "verwendungszweck", "begunstigter", "auftraggeber", "empfanger", "glaubiger"]:
                    if key in row_dict and row_dict[key]:
                        desc = row_dict[key]
                        break
                if not desc:
                    # Second or third column often has description
                    for i in [1, 2]:
                        if i < len(row) and row[i]:
                            candidate = str(row[i]).strip()
                            if not DATE_PATTERN.match(candidate) and not AMOUNT_PATTERN.match(candidate):
                                desc = candidate
                                break

                if not desc:
                    continue

                # Find amount (English + German column names)
                amount = None
                txn_type = "debit"
                for key in ["debit", "withdrawal", "dr", "charge", "soll", "belastung", "ausgabe"]:
                    if key in row_dict:
                        val = _parse_amount(row_dict[key])
                        if val and val > 0:
                            amount = val
                            txn_type = "debit"
                            break
                if not amount:
                    for key in ["credit", "deposit", "cr", "haben", "gutschrift", "einnahme"]:
                        if key in row_dict:
                            val = _parse_amount(row_dict[key])
                            if val and val > 0:
                                amount = val
                                txn_type = "credit"
                                break
                if not amount:
                    for key in ["amount", "sum", "value", "betrag", "umsatz"]:
                        if key in row_dict and row_dict[key]:
                            raw = row_dict[key]
                            is_neg = raw.lstrip().startswith("-")
                            val = _parse_amount(raw)
                            if val and val > 0:
                                amount = val
                                txn_type = "credit" if is_neg else "debit"
                                break
                if not amount:
                    # Find last numeric-looking cell
                    for cell in reversed(row):
                        if cell:
                            val = _parse_amount(str(cell))
                            if val and val > 0:
                                amount = val
                                break

                if not amount:
                    continue

                transactions.append(RawTransaction(
                    date=txn_date,
                    merchant=desc,
                    description=desc,
                    amount=amount,
                    type=txn_type,
                ))

    return transactions


def _extract_from_text(pdf) -> list[RawTransaction]:
    """Fallback: regex-based text extraction for non-tabular PDFs."""
    transactions = []
    full_text = ""
    for page in pdf.pages:
        text = page.extract_text() or ""
        full_text += text + "\n"

    lines = full_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        date_match = DATE_PATTERN.search(line)
        if not date_match:
            continue

        txn_date = _try_parse_date(date_match.group())
        if not txn_date:
            continue

        amounts = AMOUNT_PATTERN.findall(line)
        if not amounts:
            continue

        # Remove date and amounts from line to get description
        desc = line
        desc = DATE_PATTERN.sub("", desc)
        for a in amounts:
            desc = desc.replace(a, "")
        desc = re.sub(r"\s+", " ", desc).strip()
        if not desc:
            desc = "Transaction"

        raw_amount = amounts[-1]
        is_neg = raw_amount.lstrip().startswith("-")
        amount = _parse_amount(raw_amount)
        if not amount or amount <= 0:
            continue

        transactions.append(RawTransaction(
            date=txn_date,
            merchant=desc,
            description=desc,
            amount=amount,
            type="credit" if is_neg else "debit",
        ))

    return transactions


def parse_pdf(content: bytes) -> list[RawTransaction]:
    """Parse PDF bank statement bytes into RawTransaction list."""
    with pdfplumber.open(BytesIO(content)) as pdf:
        transactions = _extract_from_tables(pdf)
        if not transactions:
            transactions = _extract_from_text(pdf)

    return transactions
