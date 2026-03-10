"""Add categories table

Revision ID: 0002_add_categories_table
Revises: 0001_germanify_categories
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_categories_table"
down_revision = "0001_germanify_categories"
branch_labels = None
depends_on = None

DEFAULT_CATEGORIES = [
    ("Wohnen", "#6366f1"),
    ("Lebensmittel", "#22c55e"),
    ("Essen & Trinken", "#f97316"),
    ("Verkehr", "#3b82f6"),
    ("Freizeit", "#a855f7"),
    ("Gesundheit", "#ec4899"),
    ("Einkaufen", "#eab308"),
    ("Abonnements", "#14b8a6"),
    ("Reisen", "#06b6d4"),
    ("Bildung", "#8b5cf6"),
    ("Haushalt", "#64748b"),
    ("Versicherungen", "#78716c"),
    ("Einnahmen", "#10b981"),
    ("Umbuchungen", "#94a3b8"),
    ("Sonstiges", "#9ca3af"),
]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("color", sa.String(), nullable=False),
        if_not_exists=True,
    )
    # Seed defaults only if table is empty
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar()
    if count == 0:
        op.bulk_insert(
            sa.table(
                "categories",
                sa.column("name", sa.String),
                sa.column("color", sa.String),
            ),
            [{"name": name, "color": color} for name, color in DEFAULT_CATEGORIES],
        )


def downgrade() -> None:
    op.drop_table("categories")
