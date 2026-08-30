"""Add users table for the login gate (CAT-28)

Revision ID: 0004_add_users_table
Revises: 0003_add_transaction_date_index
Create Date: 2026-08-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0004_add_users_table"
down_revision = "0003_add_transaction_date_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        if_not_exists=True,
    )
    # Kein Seed: Das Passwort setzt der Nutzer beim ersten Start selbst. Ein
    # Default-Passwort wäre schlimmer als gar kein Login.


def downgrade() -> None:
    op.drop_table("users")
