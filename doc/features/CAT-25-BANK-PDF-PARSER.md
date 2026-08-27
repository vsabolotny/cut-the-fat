# CAT-25 — Postbank- & easybank-PDF-Parser + Auswertung Mai–Juli 2026

## Goal

Kontoauszüge Mai–Juli 2026 aus drei Quellen importierbar machen und daraus eine
Ausgabenanalyse erzeugen:

| Quelle | Format | Dateien |
|---|---|---|
| Postbank Girokonto | PDF (`Kontoauszug_362603961400EUR_*_KK_*.pdf`) | 3 |
| easybank Kreditkarte (BAWAG) | PDF (`Kontoauszug_2007541044_*.pdf`) | 3 |
| PayPal | CSV (`*-CSR-*.CSV`) | 1 |

Der generische `parse_pdf` liefert für beide PDF-Formate unbrauchbare Daten:
Tagesdaten (`31.05.`) werden als Beträge gelesen, Vorzeichen ignoriert, aus
24 Seiten werden 8 Transaktionen. Beide Formate brauchen dedizierte Parser.

## Behavior

### Postbank Girokonto (Kontoauszug)

Zeilenlayout je Buchung — pdfplumber entfernt Leerzeichen innerhalb von Wörtern:

```
01.06. 01.06. SEPALastschrifteinzugvon          -42,40
2026   2026   VKBODYFITGmbH
              Verwendungszweck/Kundenreferenz
              AIB--0195-0000502monatlicheEnergie…
```

- Zeile 1: `TT.MM. TT.MM. <Vorgang> <±Betrag>` — Vorzeichen ist explizit
  (`-` = Ausgabe, `+` = Eingang).
- Zeile 2: `JJJJ JJJJ <Gegenpartei>` → Merchant.
- Bei `Kartenzahlung` steht die Gegenpartei nicht in Zeile 2, sondern im
  Verwendungszweck vor `//` (`LidlsagtDanke//Muenchen/DE…`) → Merchant von dort.
- Seitenköpfe (`Auszug Seite von IBAN`, `Buchung Valuta Vorgang Soll Haben`),
  `AlterSaldo`, `NeuerSaldo`, `Übertrag` sind keine Buchungen.
- Ab `AnlagenzumKontoauszug` endet der Buchungsteil.

### easybank Kreditkarte

```
02.05.2026 04.05.2026 AWS EMEA aws.amazon.co LU Visa   16,07-
                      ORIGINAL UMSATZ USD 25,00
                      WECHSELKURS 1 EUR = 1,172 USD
```

- Zeile: `<Belegdatum> <Buchungsdatum> <Beschreibung> <Betrag><±>` —
  nachgestelltes `-` = Belastung, `+` = Gutschrift (Lastschrifteinzug vom Giro).
- `ORIGINAL UMSATZ` / `WECHSELKURS` sind Fortsetzungszeilen, keine Buchungen.
- `Alter Saldo` / `Neuer Saldo` sind Salden, keine Buchungen.

### PayPal CSV

Jede Zahlung erscheint doppelt: die Zahlung selbst (negatives Brutto) und die
Gegenbuchung `Bankgutschrift auf PayPal-Konto` (positives Brutto), mit der das
Girokonto belastet wird. Die Gegenbuchung ist kein Einkommen und wird
unterdrückt. Merchant kommt aus der Spalte `Name`, nicht aus `Beschreibung`.

## Technical approach

- `backend/app/services/parser/pdf_postbank.py` — `detect()` + `parse()`
- `backend/app/services/parser/pdf_easybank.py` — `detect()` + `parse()`
- `pdf_parser.parse_pdf()` extrahiert einmal den Text, probiert die
  spezialisierten Parser in Reihenfolge und fällt sonst auf die bisherige
  Tabellen-/Text-Heuristik zurück. Bestehendes Verhalten für alle anderen PDFs
  bleibt unverändert.
- Reconciliation als Korrektheitsgarantie: `Alter Saldo + Σ Buchungen == Neuer
  Saldo`. Beide Parser lesen beide Salden mit und der Test prüft die Gleichung.

## Doppelzählung

Das Girokonto ist die Ground Truth des Cashflows. Kreditkarte und PayPal
erscheinen dort als monatliche bzw. einzelne Sammellastschriften — die
Detailauszüge schlüsseln dieselben Beträge nur auf. Die Auswertung nutzt daher
das Girokonto für Summen und die Detailquellen für die Aufschlüsselung der
Sammelposten (Kategorien `Kreditkarte` und `PayPal`).

## Out of scope

- Account-/Source-Dimension in `transactions` (Dashboard summiert quellenübergreifend)
- Kategorisierungs-Engine, Web-/Desktop-UI
- Excel-Parser

## Test plan

- Postbank: Buchungserkennung, Vorzeichen, Kartenzahlung-Merchant aus `//`,
  Seitenkopf-/Saldo-Zeilen ignoriert, Anlagen-Abschnitt beendet Parsing
- easybank: Vorzeichen-Suffix, Fortsetzungszeilen ignoriert, Saldo-Zeilen ignoriert
- PayPal: `Bankgutschrift auf PayPal-Konto` unterdrückt, Merchant aus `Name`
- Reconciliation je Format über anonymisierte Fixtures
- Regression: Vorzeichen-Konvention `negativ = debit` (Fix der 10 veralteten Tests)
