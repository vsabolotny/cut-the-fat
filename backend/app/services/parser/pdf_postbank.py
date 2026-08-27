"""Parser für Postbank-Girokonto-Kontoauszüge (PDF).

Layout einer Buchung::

    01.06. 01.06. SEPA Lastschrifteinzug von        - 42,40
    2026   2026   VK BODYFIT GmbH
                  Verwendungszweck/ Kundenreferenz
                  AIB--0195-0000502 monatliche Energiepauschale

Das Vorzeichen vor dem Betrag ist maßgeblich: ``-`` = Ausgabe, ``+`` = Eingang.

Der Text muss mit ``x_tolerance=2`` extrahiert werden (siehe
``pdf_parser.extract_bank_text``). Mit dem pdfplumber-Standard von 3 fallen die
Leerzeichen innerhalb der Namen weg (``VKBODYFITGmbH``), und die aus CSV-Importen
aufgebauten ``merchant_rules`` greifen dann nicht mehr.
"""

import re
from datetime import date
from decimal import Decimal

from .base import RawTransaction

# "01.06. 01.06. SEPA Lastschrifteinzug von - 42,40"
_BOOKING = re.compile(
    r"^(\d{2})\.(\d{2})\.\s+\d{2}\.\d{2}\.\s+(.*?)\s*([+-])\s*([\d.]*\d,\d{2})$"
)
# Fortsetzungszeile mit den Jahreszahlen: "2026 2026 VK BODYFIT GmbH"
_YEARS = re.compile(r"^(\d{4})\s+\d{4}\s*(.*)$")

_ALTER_SALDO = re.compile(r"AlterSaldoper\d{2}\.\d{2}\.\d{4}")
_SALDO_BETRAG = re.compile(r"EUR\s*([+-])\s*([\d.]*\d,\d{2})")

# Zeilen, die zwar wie Text aussehen, aber keine Gegenpartei sind
_PURPOSE_MARKER = "Verwendungszweck/Kundenreferenz"
# Ab hier folgen nur noch Überweisungsbelege, keine Buchungen mehr
_ATTACHMENTS_MARKER = "AnlagenzumKontoauszug"

_SIGNATURE = ("Postbank", "Kontoauszugvom")


def _squash(s: str) -> str:
    return s.replace(" ", "")


def _amount(sign: str, digits: str) -> Decimal:
    """('-', '1.234,56') -> Decimal('-1234.56')"""
    value = Decimal(digits.replace(".", "").replace(",", "."))
    return -value if sign == "-" else value


def detect(text: str) -> bool:
    """True, wenn der PDF-Text ein Postbank-Girokonto-Auszug ist."""
    squashed = _squash(text)
    return all(marker in squashed for marker in _SIGNATURE)


def _is_purpose_marker(line: str) -> bool:
    return _squash(line) == _PURPOSE_MARKER


def _merchant_from_purpose(purpose_lines: list[str]) -> str:
    """Bei Kartenzahlungen steht der Händler im Verwendungszweck vor '//'.

    'Lidl sagt Danke//Muenchen/DE 26-06-2026T19:41:24' -> 'Lidl sagt Danke'
    """
    for line in purpose_lines:
        if "//" in line:
            candidate = line.split("//", 1)[0].strip()
            if candidate:
                return candidate
    return purpose_lines[0].strip() if purpose_lines else ""


def _booking_start(lines: list[str], i: int):
    """(Buchungszeile, Jahreszeile) — oder None, wenn hier keine Buchung beginnt.

    Eine echte Buchung hat immer die Jahres-Fortsetzungszeile darunter; ohne diese
    Prüfung würden Belegzeilen im Anlagenteil als Buchungen durchgehen.
    """
    booking = _BOOKING.match(lines[i].strip())
    if not booking or i + 1 >= len(lines):
        return None
    years = _YEARS.match(lines[i + 1].strip())
    return (booking, years) if years else None


def parse(text: str) -> list[RawTransaction]:
    lines = [ln.rstrip() for ln in text.split("\n")]
    transactions: list[RawTransaction] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if _ATTACHMENTS_MARKER in _squash(line):
            break

        start = _booking_start(lines, i)
        if not start:
            i += 1
            continue

        day, month, vorgang, sign, digits = start[0].groups()
        year, second_line = start[1].groups()

        # Folgezeilen bis zur nächsten Buchung einsammeln
        purpose: list[str] = []
        j = i + 2
        while j < len(lines):
            nxt = lines[j].strip()
            if not nxt or _ATTACHMENTS_MARKER in _squash(nxt) or _booking_start(lines, j):
                break
            if not _is_purpose_marker(nxt):
                purpose.append(nxt)
            j += 1

        second_line = second_line.strip()
        if second_line and not _is_purpose_marker(second_line):
            merchant = second_line
        else:
            merchant = _merchant_from_purpose(purpose)
        if not merchant:
            merchant = vorgang.strip() or "Unbekannt"

        amount = _amount(sign, digits)
        description = " ".join([vorgang.strip(), *purpose]).strip()

        transactions.append(
            RawTransaction(
                date=date(int(year), int(month), int(day)),
                merchant=merchant,
                description=description or merchant,
                amount=abs(amount),
                type="debit" if amount < 0 else "credit",
            )
        )
        i = j

    return transactions


def balances(text: str) -> tuple[Decimal | None, Decimal | None]:
    """(Alter Saldo, Neuer Saldo) — für die Reconciliation-Prüfung."""
    lines = [ln.strip() for ln in text.split("\n")]
    alter = neuer = None

    for idx, line in enumerate(lines):
        squashed = _squash(line)
        if alter is None and _ALTER_SALDO.search(squashed):
            for follow in lines[idx : idx + 3]:
                match = _SALDO_BETRAG.search(follow)
                if match:
                    alter = _amount(*match.groups())
                    break
        if "NeuerSaldo" in squashed:
            for follow in lines[idx : idx + 5]:
                match = _SALDO_BETRAG.search(follow)
                if match:
                    neuer = _amount(*match.groups())
                    break

    return alter, neuer
