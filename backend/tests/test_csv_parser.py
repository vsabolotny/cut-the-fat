"""Tests für den CSV-Parser — deckt alle besprochenen Edge Cases ab."""
import sys
import os
import textwrap
from decimal import Decimal
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.parser.csv_parser import (
    _parse_amount,
    _parse_date,
    _extract_card_merchant,
    parse_csv,
)


# ---------------------------------------------------------------------------
# _parse_amount
# ---------------------------------------------------------------------------

class TestParseAmount:
    def test_simple_decimal(self):
        """5.78 → 5,78 €"""
        assert _parse_amount("5.78") == Decimal("5.78")

    def test_german_thousands_no_decimal(self):
        """-1.990 → 1.990,00 € (Punkt = Tausender-Trennzeichen, kein Komma)"""
        assert _parse_amount("-1.990") == Decimal("1990")

    def test_german_thousands_negative_salary(self):
        """-5.780 → 5.780,00 € (Beispiel Gehalt)"""
        assert _parse_amount("-5.780") == Decimal("5780")

    def test_european_with_decimal(self):
        """1.234,56 → 1234,56 € (Punkt=Tausender, Komma=Dezimal)"""
        assert _parse_amount("1.234,56") == Decimal("1234.56")

    def test_european_small_decimal(self):
        """1,27 → 1,27 € (nur Komma als Dezimalzeichen)"""
        assert _parse_amount("1,27") == Decimal("1.27")

    def test_anglo_thousands(self):
        """1,234.56 → 1234,56 € (Komma=Tausender, Punkt=Dezimal)"""
        assert _parse_amount("1,234.56") == Decimal("1234.56")

    def test_negative_value_becomes_positive(self):
        """Alle Beträge werden als abs() gespeichert, type-Spalte trägt das Vorzeichen."""
        assert _parse_amount("-120.50") == Decimal("120.50")

    def test_none_returns_none(self):
        assert _parse_amount(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_amount("") is None

    def test_nan_returns_none(self):
        import pandas as pd
        assert _parse_amount(pd.NA) is None

    def test_currency_symbol_stripped(self):
        """Beträge mit € oder $ Zeichen"""
        assert _parse_amount("120,00 €") == Decimal("120.00")

    def test_german_round_thousands(self):
        """-2.000 → 2000 (nicht 2.0)"""
        assert _parse_amount("-2.000") == Decimal("2000")

    def test_large_european_amount(self):
        """12.345,67 → 12345,67"""
        assert _parse_amount("12.345,67") == Decimal("12345.67")

    def test_german_thousands_1090(self):
        """-1.090 → 1090 (Mieteinnahme Bundesagentur — Beispiel)"""
        assert _parse_amount("-1.090") == Decimal("1090")


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_german_date_format(self):
        """27.02.2026 → date(2026, 2, 27)"""
        assert _parse_date("27.02.2026") == date(2026, 2, 27)

    def test_german_short_year(self):
        """27.02.26 → date(2026, 2, 27)"""
        assert _parse_date("27.02.26") == date(2026, 2, 27)

    def test_iso_format(self):
        """2026-02-27 → date(2026, 2, 27)"""
        assert _parse_date("2026-02-27") == date(2026, 2, 27)

    def test_us_format(self):
        """02/27/2026 → date(2026, 2, 27)"""
        assert _parse_date("02/27/2026") == date(2026, 2, 27)

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_invalid_returns_none(self):
        assert _parse_date("kein datum") is None

    def test_german_no_leading_zero_month(self):
        """30.1.2026 (kein führendes Null im Monat) → date(2026, 1, 30) — reales Format aus Januar-CSV"""
        assert _parse_date("30.1.2026") == date(2026, 1, 30)

    def test_german_no_leading_zero_day(self):
        """2.12.2025 → date(2025, 12, 2)"""
        assert _parse_date("2.12.2025") == date(2025, 12, 2)


# ---------------------------------------------------------------------------
# _extract_card_merchant
# ---------------------------------------------------------------------------

class TestExtractCardMerchant:
    def test_abrechnung_karte_extracts_merchant(self):
        """ABRECHNUNG KARTE + Beschreibung → echter Händler"""
        merchant = "ABRECHNUNG KARTE"
        desc = "BEISPIEL BAECKEREI//MUENCHEN/DE 03-02-2026T09:00:00 Kartennr. 9999"
        assert _extract_card_merchant(merchant, desc) == "BEISPIEL BAECKEREI"

    def test_kartenzahlung_extracts_merchant(self):
        merchant = "Kartenzahlung"
        desc = "MUSTER AUTO AG//MUSTERSTADT/DE 02-02-2026T10:00:00 Kartennr. 1234"
        assert _extract_card_merchant(merchant, desc) == "MUSTER AUTO AG"

    def test_normal_merchant_unchanged(self):
        """Normaler Händler wird nicht verändert."""
        assert _extract_card_merchant("REWE", "REWE Markt München") == "REWE"

    def test_no_double_slash_falls_back(self):
        """Wenn kein // in Beschreibung, bleibt Placeholder."""
        assert _extract_card_merchant("ABRECHNUNG KARTE", "keine sondersyntax") == "ABRECHNUNG KARTE"

    def test_pos_zahlung_extracts_merchant(self):
        merchant = "POS-Zahlung"
        desc = "MCDONALD S DEUTSCHLAND//MUENCHEN/DE 03-02-2026T12:00:00"
        assert _extract_card_merchant(merchant, desc) == "MCDONALD S DEUTSCHLAND"

    def test_case_insensitive_placeholder(self):
        """Placeholder-Erkennung ist case-insensitiv."""
        merchant = "abrechnung karte"
        desc = "JET OLV//MUENCHEN/DE 24-02-2026T08:00:00"
        assert _extract_card_merchant(merchant, desc) == "JET OLV"


# ---------------------------------------------------------------------------
# parse_csv — Integration: vollständige CSV-Bytes parsen
# ---------------------------------------------------------------------------

class TestParseCsv:
    def _make_csv(self, rows: list[str], header: str) -> bytes:
        lines = [header] + rows
        return "\n".join(lines).encode("utf-8")

    def test_debit_transaction_parsed(self):
        """Ausgabe: positive Zahl im Betrag-Feld → type=debit.
        In diesem Bankformat: positiv = Ausgabe (Lastschrift), negativ = Eingang (Gutschrift)."""
        csv = self._make_csv(
            ["2026-02-03;REWE;Lebensmittel;32,50"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        assert txns[0].merchant == "REWE"
        assert txns[0].amount == Decimal("32.50")
        assert txns[0].type == "debit"

    def test_credit_transaction_parsed(self):
        """Eingang (negative Zahl in CSV) → type=credit."""
        csv = self._make_csv(
            ["2026-02-25;Beispiel GmbH;LOHN / GEHALT 02/26;-5.780"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        assert txns[0].amount == Decimal("5780")
        assert txns[0].type == "credit"

    def test_card_merchant_extracted_from_description(self):
        """Bei Kartenzahlung wird echter Händler aus Verwendungszweck extrahiert."""
        csv = self._make_csv(
            ["2026-02-12;ABRECHNUNG KARTE;BEISPIEL BAECKEREI//MUENCHEN/DE 12-02-2026T09:00:00 Kartennr. 5356;-5,60"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        assert txns[0].merchant == "BEISPIEL BAECKEREI"

    def test_german_date_parsed(self):
        """Deutsches Datum 27.02.2026 wird erkannt."""
        csv = self._make_csv(
            ["27.02.2026;ALDI;Einkauf;-6,23"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        assert txns[0].date == date(2026, 2, 27)

    def test_empty_rows_skipped(self):
        """Leere Zeilen werden ignoriert."""
        csv = self._make_csv(
            ["2026-02-03;REWE;Lebensmittel;-32,50", ";;;"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1

    def test_multiple_transactions(self):
        """Mehrere Zeilen werden alle importiert."""
        csv = self._make_csv(
            [
                "2026-02-03;ALDI;Einkauf;-6,23",
                "2026-02-05;Shell;Tanken;-60,00",
                "2026-02-10;Beispiel GmbH;Gehalt;-5.780",
            ],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 3
        assert txns[2].amount == Decimal("5780")
        assert txns[2].type == "credit"

    def test_wohnen_natalie_miet_credit(self):
        """Mieteinnahme Natalie: -1.990 EUR → credit, 1990 €"""
        csv = self._make_csv(
            ["2026-02-01;Muster Mieter;Miete Februar;-1.990"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        assert txns[0].amount == Decimal("1990")
        assert txns[0].type == "credit"

    def test_bundesagentur_credit(self):
        """Beispiel Behoerde: -1.090 EUR → credit, 1090 €"""
        csv = self._make_csv(
            ["2026-02-12;Muster Behoerde;Kindergeld;-1.090"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert txns[0].amount == Decimal("1090")
        assert txns[0].type == "credit"

    def test_negative_amount_with_euro_symbol(self):
        """-120,00 € → debit, 120 €"""
        csv = self._make_csv(
            ["2026-02-05;VATTENFALL;Strom;120,00 €"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert txns[0].amount == Decimal("120.00")
        assert txns[0].type == "debit"

    def test_zero_amount_parsed_as_debit(self):
        """Betrag 0,00 (positiv) → debit. Parser filtert keine Null-Beträge."""
        csv = self._make_csv(
            ["2026-02-01;REWE;Einkauf;0,00"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        assert txns[0].amount == Decimal("0.00")
        assert txns[0].type == "debit"

    def test_paypal_merchant_kept(self):
        """PayPal-Transaktion behält PayPal als merchant (kein // in description)."""
        csv = self._make_csv(
            ["2026-02-03;PayPal (Europe) S.a r.l.;1234 PP.8599.PP . Spotify AB, Ihr Einkauf;-21.99"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        # PayPal merchant stays as-is (no // in description)
        assert "PayPal" in txns[0].merchant

    def test_speck_alm_card_payment(self):
        """Kartenzahlung Speck Alm — merchant extracted from description via //.
        Positiver Betrag = Ausgabe (debit) in diesem Bankformat."""
        csv = self._make_csv(
            ["2026-02-19;ABRECHNUNG KARTE;MUSTER ALM//MUSTERFELD/DE 19-02-2026T12:00:00 Kartennr. 9999;45,80"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert txns[0].merchant == "MUSTER ALM"
        assert txns[0].type == "debit"

    def test_dedup_hash_unique_per_transaction(self):
        """Jede Transaktion hat einen eindeutigen dedup_hash."""
        csv = self._make_csv(
            [
                "2026-02-03;REWE;Einkauf;-6,23",
                "2026-02-04;REWE;Einkauf;-6,23",
                "2026-02-03;ALDI;Einkauf;-6,23",
            ],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        import hashlib
        hashes = {
            hashlib.sha256(f"{t.date}|{t.merchant.lower()}|{t.amount}".encode()).hexdigest()
            for t in txns
        }
        assert len(hashes) == 3

    def test_date_no_leading_zeros_january(self):
        """30.1.2026 (kein führendes Null) wird korrekt als Januar geparst — reales CSV-Format."""
        csv = self._make_csv(
            ["30.1.2026;Muster Behoerde;Miete;-1.090"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert txns[0].date == date(2026, 1, 30)
        assert txns[0].amount == Decimal("1090")

    def test_paypal_empty_payee(self):
        """PayPal-Eintrag ohne Empfänger in Beschreibung → merchant bleibt PayPal."""
        csv = self._make_csv(
            ["2025-12-02;PayPal (Europe) S.a r.l.;1234567890123 PP.8599.PP . , Ihr Einkauf bei;449,96"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert len(txns) == 1
        assert "PayPal" in txns[0].merchant
        assert txns[0].amount == Decimal("449.96")
        assert txns[0].type == "debit"

    def test_credit_refund_negative_amount(self):
        """Rückerstattung (credit): positiver Betrag + negativer Kontext nicht möglich —
        in diesem Bankformat ist negativ = credit (Eingang)."""
        csv = self._make_csv(
            ["2025-12-05;Muster Theater;Rueckerstattung;-47,00"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert txns[0].type == "credit"
        assert txns[0].amount == Decimal("47.00")

    def test_neue_bamberger_huette_card(self):
        """Kartenzahlung in Österreich (.AT) wird korrekt geparst."""
        csv = self._make_csv(
            ["23.12.2025;ABRECHNUNG KARTE;MusterHuette//Musterort/AT 20-12-2025T21:29:22 Kartennr. 9999;313,10"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert txns[0].merchant == "MusterHuette"
        assert txns[0].amount == Decimal("313.10")
        assert txns[0].date == date(2025, 12, 23)

    def test_large_round_thousands_december(self):
        """-1.990 als Mieteinnahme Dezember → 1990 €, credit"""
        csv = self._make_csv(
            ["29.12.2025;Muster Mieter;Miete Dezember;-1.990"],
            "Buchungstag;Begunstigter Auftraggeber;Verwendungszweck;Betrag",
        )
        txns = parse_csv(csv)
        assert txns[0].amount == Decimal("1990")
        assert txns[0].type == "credit"
