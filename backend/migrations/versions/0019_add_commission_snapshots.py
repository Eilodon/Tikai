"""Add commission_snapshots table for historical rate tracking.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commission_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_id", sa.String(100), nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=True),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_commission_snapshots_shop_creator", "commission_snapshots", ["shop_id", "creator_id"])
    op.create_index("ix_commission_snapshots_valid_from", "commission_snapshots", ["shop_id", "creator_id", "valid_from"])


def downgrade() -> None:
    op.drop_index("ix_commission_snapshots_valid_from")
    op.drop_index("ix_commission_snapshots_shop_creator")
    op.drop_table("commission_snapshots")
