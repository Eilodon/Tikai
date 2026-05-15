"""Add trial_expires_at and push_subscription_json to shops.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("trial_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shops",
        sa.Column("push_subscription_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shops", "push_subscription_json")
    op.drop_column("shops", "trial_expires_at")
