"""Add cogs_entries table for time-series COGS tracking.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cogs_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "shop_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shops.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku_id", sa.String(100), nullable=False),
        sa.Column("cogs_per_unit", sa.Numeric(18, 4), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_cogs_entries_shop_sku_date",
        "cogs_entries",
        ["shop_id", "sku_id", "effective_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_cogs_entries_shop_sku_date", table_name="cogs_entries")
    op.drop_table("cogs_entries")
