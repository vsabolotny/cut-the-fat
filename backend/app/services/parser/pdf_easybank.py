"""Parser für easybank-Kreditkartenabrechnungen (BAWAG, PDF).

Layout einer Buchung::

    02.05.2026 04.05.2026 AWS EMEA aws.amazon.co LU Visa   16,07-
                          ORIGINAL UMSATZ USD 25,00
                          WECHSELKURS 1 EUR = 1,172 USD

Das Vorzeichen steht *hinter* dem Betrag: ``-`` = Belastung, ``+`` = Gutschrift
(z. B. der monatliche Lastschrifteinzug vom Girokonto).
"""

import re
from datetime import date
from decimal import Decimal

from .base import RawTransaction

# "02.05.2026 04.05.2026 AWS EMEA aws.amazon.co LU Visa 16,07-"
_BOOKING = re.compile(
    r"^(\d{2})\.(\d{2})\.(\d{4})\s+\d{2}\.\d{2}\.\d{4}\s+(.*?)\s+([\d.]*\d,\d{2})([+-])$"
)
_ALTER_SALDO = re.compile(r"^Alter Saldo vom .*?([\d.]*\d,\d{2})([+-])$")
_NEUER_SALDO = re.compile(r"^Neuer Saldo am .*?([\d.]*\d,\d{2})([+-])$")

# Fortsetzungszeilen zu einer Buchung — keine eigenen Umsätze
_CONTINUATION_PREFIXES = ("ORIGINAL UMSATZ", "WECHSELKURS")

_SIGNATURE = ("easybankKreditkarte", "Umsatzübersicht")


def _amount(raw: str, sign: str) -> Decimal:
    """('1.234,56', '-') -> Decimal('-1234.56')"""
    value = Decimal(raw.replace(".", "").replace(",", "."))
    return -value if sign == "-" else value


def detect(text: str) -> bool:
    """True, wenn der PDF-Text eine easybank-Kreditkartenabrechnung ist."""
    squashed = text.replace(" ", "")
    return all(marker.replace(" ", "") in squashed for marker in _SIGNATURE)


def parse(text: str) -> list[RawTransaction]:
    transactions: list[RawTransaction] = []

    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith(_CONTINUATION_PREFIXES):
            continue
        if _ALTER_SALDO.match(line) or _NEUER_SALDO.match(line):
            continue

        booking = _BOOKING.match(line)
        if not booking:
            continue

        day, month, year, description, raw_amount, sign = booking.groups()
        amount = _amount(raw_amount, sign)
        description = description.strip()
        # "AWS EMEA aws.amazon.co LU Visa" -> der Kartentyp ist kein Teil des Händlers
        merchant = re.sub(r"\s+Visa$", "", description).strip() or description

        transactions.append(
            RawTransaction(
                date=date(int(year), int(month), int(day)),
                merchant=merchant,
                description=description,
                amount=abs(amount),
                type="debit" if amount < 0 else "credit",
            )
        )

    return transactions


def balances(text: str) -> tuple[Decimal | None, Decimal | None]:
    """(Alter Saldo, Neuer Saldo) — für die Reconciliation-Prüfung."""
    alter = neuer = None
    for line in text.split("\n"):
        line = line.strip()
        match = _ALTER_SALDO.match(line)
        if match and alter is None:
            alter = _amount(*match.groups())
            continue
        match = _NEUER_SALDO.match(line)
        if match:
            neuer = _amount(*match.groups())
    return alter, neuer
