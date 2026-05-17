"""Add stock_map JSONB to shops for inventory tracking.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("stock_map", JSONB, nullable=True, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("shops", "stock_map")
