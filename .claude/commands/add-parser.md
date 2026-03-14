Add support for a new bank statement format or fix an existing parser.

The user will describe which bank or format they're having trouble with. Follow these steps:

1. Read `backend/app/services/parser/csv_parser.py` to understand the existing column detection logic.
2. Read `backend/app/services/parser/pdf_parser.py` to understand the table and text extraction approach.
3. Ask the user to paste a sample of their statement (a few rows from CSV, or describe the PDF structure).
4. Based on the sample, identify what's different: unusual column names, date formats, amount encoding, split debit/credit columns, etc.
5. Make the targeted fix:
   - For CSV/Excel: add column name variants to the detection lists (`DATE_COLS`, `MERCHANT_COLS`, `AMOUNT_COLS`, `DEBIT_COLS`, `CREDIT_COLS`) or add a date format to `DATE_FORMATS` in `csv_parser.py`.
   - For PDF: improve the table extraction heuristics or add a regex pattern to the text fallback in `pdf_parser.py`.
   - For a completely new format: create a new parser file following the `RawTransaction` dataclass interface from `base.py`, then register it in `cli/db.py → _ingest_file()` (the `if ext == ...` dispatch block).
6. Run the backend import check: `cd /Users/ecog-vladislav/Projects/cut-the-fat/backend && .venv/bin/python -c "from app.services.parser import csv_parser, pdf_parser, excel_parser; print('OK')"`
7. Report what was changed and why.
