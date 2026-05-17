"""Add ix_orders_shop_id_sku_name index for COGS DISTINCT queries

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-14

WHY:
cogs.py GET /v1/cogs uses DISTINCT(shop_id, sku_name) ORDER BY sku_name LIMIT 500.
Without an index on (shop_id, sku_name), PostgreSQL performs a full table scan and
sort before applying the LIMIT — expensive for shops with 10k+ orders.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_orders_shop_id_sku_name",
        "orders",
        ["shop_id", "sku_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_orders_shop_id_sku_name", table_name="orders")
