"""Add platform field to orders, fee_configs, import_sessions

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-26

WHY: Multi-platform support (Shopee first, Lazada planned).
- orders.platform: enables per-platform P&L filtering
- fee_configs.platform: allows separate fee structures per platform
- import_sessions.platform: audit trail + frontend badge

All columns use server_default for safe backward compatibility —
existing rows get "tiktok" automatically.
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # orders.platform — "tiktok" | "shopee" | "lazada" | "unknown"
    op.add_column(
        "orders",
        sa.Column(
            "platform",
            sa.String(20),
            nullable=False,
            server_default="tiktok",
            comment="Source platform. Default 'tiktok' for all pre-v2.0.0 rows.",
        ),
    )
    # Composite index for platform-filtered P&L queries
    op.create_index("ix_orders_shop_id_platform", "orders", ["shop_id", "platform"])

    # fee_configs.platform — allows platform-specific fee config records
    op.add_column(
        "fee_configs",
        sa.Column(
            "platform",
            sa.String(20),
            nullable=False,
            server_default="tiktok",
            comment="Platform this fee config applies to.",
        ),
    )

    # import_sessions.platform — tracks which platform the import came from
    op.add_column(
        "import_sessions",
        sa.Column(
            "platform",
            sa.String(20),
            nullable=False,
            server_default="tiktok",
            comment="Platform detected from file headers.",
        ),
    )


def downgrade() -> None:
    op.drop_column("import_sessions", "platform")
    op.drop_index("ix_orders_shop_id_platform", table_name="orders")
    op.drop_column("orders", "platform")
    op.drop_column("fee_configs", "platform")
