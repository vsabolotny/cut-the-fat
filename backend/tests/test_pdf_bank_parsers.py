"""Tests für die bankspezifischen PDF-Parser (CAT-25).

Die Fixtures sind aus echten Auszügen abgeleitet und anonymisiert. Das Layout
entspricht der Textextraktion mit ``x_tolerance=2`` — dem Wert, den
``pdf_parser.extract_bank_text`` verwendet, damit die Leerzeichen in den
Händlernamen erhalten bleiben.
"""

import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.parser import pdf_easybank, pdf_postbank


POSTBANK_TEXT = """Postbank
Filiale
München 801
Kontoauszug vom 30.05.2026 bis 30.06.2026
Kontoinhaber: Muster Mustermann
Auszug Seite von IBAN Alter Saldo per 29.05.2026
6 1 24 DE00 0000 0000 0000 0000 00 EUR + 1.000,00
Buchung Valuta Vorgang Soll Haben
01.06. 01.06. SEPA Überweisung von + 75,00
2026 2026 Angelika Musterfrau
Verwendungszweck/ Kundenreferenz
Garage Musterstraße
01.06. 01.06. SEPA Lastschrifteinzug von - 42,40
2026 2026 Muster Fitness GmbH
Verwendungszweck/ Kundenreferenz
AIB--0195-0000502 monatliche Energiepauschale
Auszug Seite von IBAN
6 2 24 DE00 0000 0000 0000 0000 00
Buchung Valuta Vorgang Soll Haben
30.06. 30.06. Kartenzahlung - 24,23
2026 2026 Verwendungszweck/ Kundenreferenz
Lidl sagt Danke//Muenchen/DE 26-06-2026T19:41:24
Kartennr. 5356999999997666
Filialnummer Kontonummer Neuer Saldo
362 6039614 00
EUR + 1.008,37
Anlagen zum Kontoauszug
BELASTUNG REF 02PR260603925698
01.07. 01.07. SEPA Lastschrifteinzug von - 99,00
2026 2026 Soll Nicht Geparst Werden GmbH
"""

EASYBANK_TEXT = """Kontoauszug zu Ihrer easybank Kreditkarte vom 2. Juni 2026
Abrechnungszeitraum: 04.05.2026 - 02.06.2026 Alter Saldo: EUR 235,52 -
Umsatzübersicht
Beleg- Buchungs-/ Beschreibung Karte Betrag (EUR)
datum Valutadatum
Alter Saldo vom 3. Mai 2026 235,52-
Hauptkarte/n, Muster Mustermann
02.05.2026 04.05.2026 AWS EMEA aws.amazon.co LU Visa 16,07-
08.05.2026 09.05.2026 GOOGLE*PLAY SUPPORT.GOOGL CA Visa 21,33-
ORIGINAL UMSATZ USD 25,00
WECHSELKURS 1 EUR = 1,172 USD
09.05.2026 09.05.2026 Belastung Entgelt für Auslandseinsatz Visa 0,42-
25.05.2026 27.05.2026 BSP AUTO 465337 75PARIS 12 FR Visa 494,00-
Sonstige Umsätze
30.05.2026 30.05.2026 Per Lastschrift dankend erhalten 235,52+
Neuer Saldo am 2. Juni 2026 531,82-
"""


def _net(txns):
    return sum(
        (t.amount if t.type == "credit" else -t.amount) for t in txns
    )


class TestPostbankPdfParser:
    def test_detect(self):
        assert pdf_postbank.detect(POSTBANK_TEXT)
        assert not pdf_postbank.detect(EASYBANK_TEXT)

    def test_all_bookings_found(self):
        txns = pdf_postbank.parse(POSTBANK_TEXT)
        assert len(txns) == 3

    def test_sign_convention(self):
        einzahlung, lastschrift, karte = pdf_postbank.parse(POSTBANK_TEXT)
        assert einzahlung.type == "credit"
        assert einzahlung.amount == Decimal("75.00")
        assert lastschrift.type == "debit"
        assert lastschrift.amount == Decimal("42.40")
        assert karte.type == "debit"

    def test_date_from_continuation_line(self):
        txns = pdf_postbank.parse(POSTBANK_TEXT)
        assert txns[0].date == date(2026, 6, 1)
        assert txns[2].date == date(2026, 6, 30)

    def test_merchant_from_counterparty_line(self):
        txns = pdf_postbank.parse(POSTBANK_TEXT)
        assert txns[0].merchant == "Angelika Musterfrau"
        assert txns[1].merchant == "Muster Fitness GmbH"

    def test_card_payment_merchant_from_purpose(self):
        """Bei Kartenzahlung steht der Händler im Verwendungszweck vor '//'."""
        karte = pdf_postbank.parse(POSTBANK_TEXT)[2]
        assert karte.merchant == "Lidl sagt Danke"

    def test_page_headers_and_balances_are_not_bookings(self):
        merchants = [t.merchant for t in pdf_postbank.parse(POSTBANK_TEXT)]
        assert not any("Saldo" in m for m in merchants)
        assert not any("IBAN" in m for m in merchants)

    def test_attachment_section_ends_parsing(self):
        """Überweisungsbelege nach 'AnlagenzumKontoauszug' sind keine Buchungen."""
        merchants = [t.merchant for t in pdf_postbank.parse(POSTBANK_TEXT)]
        assert "Soll Nicht Geparst Werden GmbH" not in merchants

    def test_balances_reconcile(self):
        alter, neuer = pdf_postbank.balances(POSTBANK_TEXT)
        assert alter == Decimal("1000.00")
        assert neuer == Decimal("1008.37")
        assert alter + _net(pdf_postbank.parse(POSTBANK_TEXT)) == neuer


class TestEasybankPdfParser:
    def test_detect(self):
        assert pdf_easybank.detect(EASYBANK_TEXT)
        assert not pdf_easybank.detect(POSTBANK_TEXT)

    def test_all_bookings_found(self):
        txns = pdf_easybank.parse(EASYBANK_TEXT)
        assert len(txns) == 5

    def test_trailing_sign_decides_type(self):
        txns = pdf_easybank.parse(EASYBANK_TEXT)
        assert txns[0].type == "debit"
        assert txns[0].amount == Decimal("16.07")
        assert txns[-1].type == "credit"
        assert txns[-1].amount == Decimal("235.52")

    def test_booking_date_is_belegdatum(self):
        assert pdf_easybank.parse(EASYBANK_TEXT)[0].date == date(2026, 5, 2)

    def test_card_suffix_stripped_from_merchant(self):
        assert pdf_easybank.parse(EASYBANK_TEXT)[0].merchant == "AWS EMEA aws.amazon.co LU"

    def test_continuation_lines_ignored(self):
        """ORIGINAL UMSATZ / WECHSELKURS sind keine eigenen Umsätze."""
        descriptions = [t.description for t in pdf_easybank.parse(EASYBANK_TEXT)]
        assert not any("WECHSELKURS" in d for d in descriptions)
        assert not any("ORIGINAL UMSATZ" in d for d in descriptions)

    def test_balance_lines_are_not_bookings(self):
        descriptions = [t.description for t in pdf_easybank.parse(EASYBANK_TEXT)]
        assert not any("Saldo" in d for d in descriptions)

    def test_balances_reconcile(self):
        alter, neuer = pdf_easybank.balances(EASYBANK_TEXT)
        assert alter == Decimal("-235.52")
        assert neuer == Decimal("-531.82")
        assert alter + _net(pdf_easybank.parse(EASYBANK_TEXT)) == neuer
