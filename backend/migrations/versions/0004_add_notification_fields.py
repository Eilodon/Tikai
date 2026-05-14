"""Add notification fields to shops and weekly_receipts

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # notification_email: seller's preferred email (may differ from auth email)
    # Falls back to Supabase auth email if null
    op.add_column(
        "shops",
        sa.Column("notification_email", sa.String(255), nullable=True),
    )
    # email_digest_enabled: False by default — seller must opt in
    op.add_column(
        "shops",
        sa.Column(
            "email_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    # Delivery tracking on weekly_receipts table
    op.add_column(
        "weekly_receipts",
        sa.Column(
            "email_sent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "weekly_receipts",
        sa.Column(
            "email_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("weekly_receipts", "email_sent_at")
    op.drop_column("weekly_receipts", "email_sent")
    op.drop_column("shops", "email_digest_enabled")
    op.drop_column("shops", "notification_email")
