"""Add index on transactions.date

Revision ID: 0003_add_transaction_date_index
Revises: 0002_add_categories_table
Create Date: 2026-03-10

"""
from alembic import op

revision = "0003_add_transaction_date_index"
down_revision = "0002_add_categories_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_transactions_date", "transactions", ["date"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_transactions_date", table_name="transactions")
