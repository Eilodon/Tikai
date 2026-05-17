"""Add partial unique constraint on commission_snapshots for open records.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-17

Prevents duplicate open snapshots (valid_to IS NULL) for the same
shop/creator/sku combination, which caused BUG-L3 where db.scalar()
only closed the first duplicate instead of all of them.
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial unique index: at most one open snapshot per (shop, creator, sku)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_commission_snapshots_open
        ON commission_snapshots (shop_id, creator_id, COALESCE(sku_id, ''))
        WHERE valid_to IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_commission_snapshots_open")
