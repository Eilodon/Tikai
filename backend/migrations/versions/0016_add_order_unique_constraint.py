"""Add unique constraint on orders(shop_id, tiktok_order_id) to prevent
duplicate insertions on ARQ job retry.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-16
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove any existing duplicates before adding the constraint.
    # Keep the row with the lowest id (first inserted) per (shop_id, tiktok_order_id).
    op.execute(
        """
        DELETE FROM orders
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM orders
            GROUP BY shop_id, tiktok_order_id
        )
        """
    )
    op.create_unique_constraint(
        "uq_orders_shop_tiktok_id",
        "orders",
        ["shop_id", "tiktok_order_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_orders_shop_tiktok_id", "orders", type_="unique")
