"""Add ZNS fields to shops table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shops", sa.Column("seller_phone", sa.String(20), nullable=True))
    op.add_column(
        "shops",
        sa.Column(
            "zns_enabled",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("shops", "zns_enabled")
    op.drop_column("shops", "seller_phone")
