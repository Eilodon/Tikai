"""Add unique constraint on weekly_receipts(shop_id, period_label) to prevent
duplicate receipts and double email sends from concurrent cron workers.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-16
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate receipts (keep latest per shop+period) before constraint.
    op.execute(
        """
        DELETE FROM weekly_receipts
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM weekly_receipts
            GROUP BY shop_id, period_label
        )
        """
    )
    op.create_unique_constraint(
        "uq_weekly_receipts_shop_period",
        "weekly_receipts",
        ["shop_id", "period_label"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_weekly_receipts_shop_period", "weekly_receipts", type_="unique")
