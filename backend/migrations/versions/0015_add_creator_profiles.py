"""Add creator_profiles table for Creator CRM.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "shop_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shops.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("creator_id", sa.String(100), nullable=False, index=True),
        sa.Column("creator_name", sa.String(200), nullable=False),
        # Performance metrics (auto-updated from imports)
        sa.Column("gmv_30d", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_revenue_30d", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("revenue_efficiency_30d", sa.Numeric(10, 6), nullable=True),
        sa.Column("avg_refund_rate", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("total_orders_lifetime", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_order_date", sa.Date, nullable=True),
        sa.Column("total_commission_paid", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column(
            "commission_on_refunded_orders",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
        # CRM fields (manual)
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("negotiated_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("internal_note", sa.String(1000), nullable=True),
        sa.Column("contact_zalo", sa.String(50), nullable=True),
        sa.Column("contact_email", sa.String(200), nullable=True),
        # Computed (stored)
        sa.Column("performance_label", sa.String(20), nullable=False, server_default="break_even"),
        sa.Column("suggested_max_commission", sa.Numeric(6, 4), nullable=True),
        # Timestamps
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
        sa.UniqueConstraint("shop_id", "creator_id", name="uq_creator_profiles_shop_creator"),
    )


def downgrade() -> None:
    op.drop_table("creator_profiles")
