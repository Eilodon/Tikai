"""Add top_skus_for_cogs to import_sessions

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-14

P0-1 fix: ImportSession now stores top 5 SKUs by GMV after a successful import.
Frontend reads this to pre-populate the post-import COGS entry prompt.
Previously the prompt always received [] and the COGS step never showed data.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_sessions",
        sa.Column(
            "top_skus_for_cogs",
            sa.JSON(),
            nullable=True,
            comment="Top 5 SKUs by GMV for post-import COGS prompt [{sku_id, sku_name, gmv}]",
        ),
    )


def downgrade() -> None:
    op.drop_column("import_sessions", "top_skus_for_cogs")
