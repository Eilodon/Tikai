"""Initial schema — all tables

Revision ID: 0001
Revises: 
Create Date: 2026-05-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── shops ─────────────────────────────────────────────────────
    op.create_table(
        "shops",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("tiktok_shop_id", sa.String(100), nullable=True),
        sa.Column("subscription_tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("fee_config_version", sa.String(50), nullable=False, server_default="2024-VN-v1"),
        sa.Column("cogs_map", postgresql.JSONB(), nullable=True, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tiktok_shop_id"),
    )
    op.create_index("ix_shops_owner_id", "shops", ["owner_id"])

    # ── fee_configs ───────────────────────────────────────────────
    op.create_table(
        "fee_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("platform_commission_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("category_overrides", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("verified_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index("ix_fee_configs_effective_from", "fee_configs", ["effective_from"])

    # ── import_sessions ───────────────────────────────────────────
    op.create_table(
        "import_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_type", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("encoding_detected", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("can_continue_mode", sa.String(10), nullable=True),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("rows_parsed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", postgresql.JSONB(), nullable=True),
        sa.Column("ai_rescue_message", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_sessions_shop_id_status", "import_sessions", ["shop_id", "status"])

    # ── orders ────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tiktok_order_id", sa.String(100), nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=False),
        sa.Column("sku_name", sa.String(300), nullable=False),
        sa.Column("creator_id", sa.String(100), nullable=True),
        sa.Column("creator_name", sa.String(200), nullable=True),
        sa.Column("gmv", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("platform_commission", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("affiliate_commission", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("voucher_cost", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("shipping_subsidy", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("refund_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("cogs", sa.Numeric(20, 4), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("refund_reason_raw", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_session_id"], ["import_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_shop_id_order_date", "orders", ["shop_id", "order_date"])
    op.create_index("ix_orders_shop_id_sku_id", "orders", ["shop_id", "sku_id"])
    op.create_index("ix_orders_shop_id_creator_id", "orders", ["shop_id", "creator_id"])
    op.create_index("ix_orders_tiktok_order_id", "orders", ["tiktok_order_id"])

    # ── insight_snapshots ─────────────────────────────────────────
    op.create_table(
        "insight_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("gmv_total", sa.Numeric(20, 4), nullable=False),
        sa.Column("net_revenue", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_orders", sa.Integer(), nullable=False),
        sa.Column("total_refunds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refund_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("cash_in_14d", sa.Numeric(20, 4), nullable=True),
        sa.Column("top_leaks_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("top_skus_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("top_creators_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("action_triggers_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rule_engine_version", sa.String(20), nullable=False),
        sa.Column("fee_config_version", sa.String(50), nullable=False),
        sa.Column("cogs_coverage_pct", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("is_net_revenue_mode", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_session_id"], ["import_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insight_snapshots_shop_id_period", "insight_snapshots", ["shop_id", "period_end"])

    # ── ai_actions ────────────────────────────────────────────────
    op.create_table(
        "ai_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("insight_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("rule_trigger", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("why", sa.String(500), nullable=False),
        sa.Column("do_today", sa.String(500), nullable=False),
        sa.Column("expected_impact", sa.String(300), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("source_insight_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_impact_json", postgresql.JSONB(), nullable=True),
        sa.Column("is_confirmed_impact", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confirmed_delta", sa.Numeric(20, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["insight_snapshot_id"], ["insight_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_actions_shop_id_status", "ai_actions", ["shop_id", "status"])

    # ── weekly_receipts ───────────────────────────────────────────
    op.create_table(
        "weekly_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_label", sa.String(100), nullable=False),
        sa.Column("total_confirmed_saved", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("total_estimated_saved", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("actions_completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("headline", sa.String(300), nullable=False),
        sa.Column("confirmed_section", sa.String(1000), nullable=False),
        sa.Column("estimated_section", sa.String(1000), nullable=False),
        sa.Column("next_week_focus", sa.String(500), nullable=False),
        sa.Column("disclaimer", sa.String(500), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Seed initial fee config ───────────────────────────────────
    op.execute("""
        INSERT INTO fee_configs (
            id, version, effective_from, platform_commission_rate,
            category_overrides, verified_date, source_url, notes
        ) VALUES (
            gen_random_uuid(),
            '2024-VN-v1',
            '2024-01-01',
            0.0200,
            '{}',
            '2026-01-01',
            'https://seller-vn.tiktok.com/university/essay?knowledge_id=10005585',
            'Base rate 2% for most categories. Verify category-specific rates separately.'
        )
        ON CONFLICT (version) DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_table("weekly_receipts")
    op.drop_table("ai_actions")
    op.drop_table("insight_snapshots")
    op.drop_table("orders")
    op.drop_table("import_sessions")
    op.drop_table("fee_configs")
    op.drop_table("shops")
