"""
0002_add_order_financial_fields_and_fee_config_2026

FIX P0-3: Add quantity, transaction_fee, order_processing_fee to orders table.
FIX P1-FeeConfig: Seed 2026-VN-v3 with current TikTok VN rates (verified 09/05/2026).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── orders: add missing financial fields ─────────────────────────────────
    # All columns server_default safe — existing rows get sensible zero values.

    op.add_column(
        "orders",
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Units sold in this order. COGS = cogs_per_unit * quantity.",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "transaction_fee",
            sa.Numeric(20, 4),
            nullable=False,
            server_default="0",
            comment="Phí Giao Dịch 6% buyer-paid (TikTok VN from 09/05/2026)",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "order_processing_fee",
            sa.Numeric(20, 4),
            nullable=False,
            server_default="0",
            comment="Phí Xử Lý Đơn Hàng 3,000 VND/order (from 27/10/2025)",
        ),
    )

    # ── fee_configs: add transaction_fee_rate + order_processing_fee_per_order ──
    # These fields support FeeConfig-based estimation when export doesn't include fees.
    op.add_column(
        "fee_configs",
        sa.Column(
            "transaction_fee_rate",
            sa.Numeric(6, 4),
            nullable=False,
            server_default="0",
            comment="Rate applied to buyer-paid GMV. 0.06 = 6%.",
        ),
    )
    op.add_column(
        "fee_configs",
        sa.Column(
            "order_processing_fee_per_order",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
            comment="Fixed fee per completed order in VND. 3000 = 3,000 VND.",
        ),
    )

    # ── Seed 2026-VN-v3: current TikTok VN rates (verified 09/05/2026) ───────
    # Source: https://seller-vn.tiktok.com/university/essay?knowledge_id=10005585
    # Platform commission: 12.5% (Marketplace), 14.5% (Mall) from 02/03/2026
    # Transaction fee: 6% buyer-paid from 09/05/2026
    # Order processing fee: 3,000 VND/delivered order from 27/10/2025
    op.execute("""
        INSERT INTO fee_configs (
            id,
            version,
            effective_from,
            effective_to,
            platform_commission_rate,
            transaction_fee_rate,
            order_processing_fee_per_order,
            category_overrides,
            verified_date,
            source_url,
            notes,
            created_at,
            updated_at
        )
        VALUES (
            gen_random_uuid(),
            '2026-VN-v3',
            '2026-05-09',
            NULL,
            0.1250,
            0.0600,
            3000.00,
            '{"mall": 0.1450}'::jsonb,
            '2026-05-09',
            'https://seller-vn.tiktok.com/university/essay?knowledge_id=10005585',
            'Platform commission 12.5% (Marketplace) / 14.5% (Mall) from 02/03/2026. '
            'Transaction fee 6% from 09/05/2026. '
            'Order processing fee 3,000 VND/completed order from 27/10/2025. '
            'Set as default for new shops.',
            now(),
            now()
        )
        ON CONFLICT DO NOTHING;
    """)

    # Update shops.fee_config_version server_default to new version
    op.alter_column(
        "shops",
        "fee_config_version",
        server_default="2026-VN-v3",
    )


def downgrade() -> None:
    op.drop_column("orders", "transaction_fee")
    op.drop_column("orders", "order_processing_fee")
    op.drop_column("orders", "quantity")
    op.drop_column("fee_configs", "transaction_fee_rate")
    op.drop_column("fee_configs", "order_processing_fee_per_order")
    op.execute("DELETE FROM fee_configs WHERE version = '2026-VN-v3'")
    op.alter_column("shops", "fee_config_version", server_default="2024-VN-v1")
