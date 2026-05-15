"""Add start_time and end_time to livestream_sessions.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "livestream_sessions",
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "livestream_sessions",
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("livestream_sessions", "end_time")
    op.drop_column("livestream_sessions", "start_time")
