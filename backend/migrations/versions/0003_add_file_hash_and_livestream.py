"""add file_hash to import_sessions and create livestream_sessions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add file_hash to import_sessions for duplicate detection (FIX BUG-NM5)
    op.add_column(
        "import_sessions",
        sa.Column("file_hash", sa.String(64), nullable=True, index=True),
    )

    # Create livestream_sessions table (new feature)
    op.create_table(
        "livestream_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("shop_id", sa.UUID(), sa.ForeignKey("shops.id"), nullable=False, index=True),
        sa.Column("livestream_date", sa.Date(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), default=0),
        sa.Column("platform_live_id", sa.String(100), nullable=True),
        sa.Column("host_cost", sa.Numeric(18, 2), default=0),
        sa.Column("studio_cost", sa.Numeric(18, 2), default=0),
        sa.Column("product_sample_cost", sa.Numeric(18, 2), default=0),
        sa.Column("ads_cost", sa.Numeric(18, 2), default=0),
        sa.Column("other_cost", sa.Numeric(18, 2), default=0),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("attributed_gmv", sa.Numeric(18, 2), nullable=True),
        sa.Column("attributed_orders", sa.Integer(), default=0),
        sa.Column("attributed_net_revenue", sa.Numeric(18, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("livestream_sessions")
    op.drop_column("import_sessions", "file_hash")
