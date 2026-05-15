"""Add category column to shops table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-15

Shop category drives leak-detector refund baselines via industry_data.py
so the benchmark panel and leak detector always compare against the same numbers.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("category", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shops", "category")
