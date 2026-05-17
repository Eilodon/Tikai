"""Add fee_discrepancy_notes to insight_snapshots; add ldr_rate/sfcr_rate to shops.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Gap #4: persist fee discrepancy notes alongside each snapshot
    op.add_column(
        "insight_snapshots",
        sa.Column("fee_discrepancy_notes_json", sa.JSON, nullable=False, server_default="[]"),
    )

    # Gap #5: dynamic settlement window based on TikTok shop health metrics
    op.add_column(
        "shops",
        sa.Column("ldr_rate", sa.Numeric(6, 4), nullable=True),
    )
    op.add_column(
        "shops",
        sa.Column("sfcr_rate", sa.Numeric(6, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shops", "sfcr_rate")
    op.drop_column("shops", "ldr_rate")
    op.drop_column("insight_snapshots", "fee_discrepancy_notes_json")
