"""Rename categories from English to German

Revision ID: 0001_germanify_categories
Revises:
Create Date: 2026-03-10

"""
from alembic import op

revision = "0001_germanify_categories"
down_revision = None
branch_labels = None
depends_on = None

MAPPING = [
    ("Housing", "Wohnen"),
    ("Groceries", "Lebensmittel"),
    ("Dining", "Essen & Trinken"),
    ("Transportation", "Verkehr"),
    ("Entertainment", "Freizeit"),
    ("Health", "Gesundheit"),
    ("Shopping", "Einkaufen"),
    ("Subscriptions", "Abonnements"),
    ("Travel", "Reisen"),
    ("Education", "Bildung"),
    ("Utilities", "Haushalt"),
    ("Insurance", "Versicherungen"),
    ("Income", "Einnahmen"),
    ("Transfers", "Umbuchungen"),
    ("Other", "Sonstiges"),
]


def upgrade() -> None:
    for english, german in MAPPING:
        op.execute(
            f"UPDATE transactions SET category = '{german}' WHERE category = '{english}'"
        )
        op.execute(
            f"UPDATE merchant_rules SET category = '{german}' WHERE category = '{english}'"
        )


def downgrade() -> None:
    for english, german in MAPPING:
        op.execute(
            f"UPDATE transactions SET category = '{english}' WHERE category = '{german}'"
        )
        op.execute(
            f"UPDATE merchant_rules SET category = '{english}' WHERE category = '{german}'"
        )
