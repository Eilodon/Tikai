"""Add cash_in_30d and cash_pending_total to insight_snapshots

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-14

WHY:
Feature 6 (Cash Flow Forecast UI) needs cash_in_30d and cash_pending_total
to show sellers a fuller cash flow timeline beyond just the 14-day window.
These are nullable — old snapshots will show None (handled gracefully by frontend).
"""
from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "insight_snapshots",
        sa.Column("cash_in_30d", sa.Numeric(20, 4), nullable=True),
    )
    op.add_column(
        "insight_snapshots",
        sa.Column("cash_pending_total", sa.Numeric(20, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("insight_snapshots", "cash_pending_total")
    op.drop_column("insight_snapshots", "cash_in_30d")
