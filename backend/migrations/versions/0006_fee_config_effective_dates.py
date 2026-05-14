"""Set effective_to on historical fee configs + add 2025-VN-v2 for order_processing_fee period

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-13

WHY (F-1B-01):
process_import was selecting fee config by most-recent effective_from only.
Historical imports (data from before 2026-05-09) were incorrectly getting the
2026-VN-v3 config (6% transaction_fee + 3000 VND processing fee), overstating costs.

Fix:
1. Set effective_to on "2024-VN-v1" → 2025-10-26 (day before order_processing_fee)
2. Insert "2025-VN-v2" (effective 2025-10-27 to 2026-05-08): adds 3000 VND/order
3. "2026-VN-v3" already correct (effective_from 2026-05-09, effective_to NULL)

After this migration, process_import uses date-aware query:
  WHERE effective_from <= import_period_end
    AND (effective_to IS NULL OR effective_to >= import_period_end)
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Cap 2024-VN-v1 — valid until day before order_processing_fee started
    op.execute("""
        UPDATE fee_configs
        SET effective_to = '2025-10-26'
        WHERE version = '2024-VN-v1'
          AND effective_to IS NULL
    """)

    # 2. Insert 2025-VN-v2 — order_processing_fee 3000 VND/order added 2025-10-27
    # No transaction_fee yet (that started 2026-05-09)
    op.execute("""
        INSERT INTO fee_configs (
            id, version, platform,
            effective_from, effective_to,
            platform_commission_rate,
            transaction_fee_rate,
            order_processing_fee_per_order,
            category_overrides,
            verified_date,
            source_url,
            notes,
            created_at, updated_at
        )
        VALUES (
            gen_random_uuid(),
            '2025-VN-v2',
            'tiktok',
            '2025-10-27',
            '2026-05-08',
            0.1250,
            0.0000,
            3000.00,
            '{"mall": 0.1450}'::jsonb,
            '2026-05-13',
            'https://seller-vn.tiktok.com/university/essay?knowledge_id=10005585',
            'TikTok VN: order_processing_fee 3,000 VND/completed order added 2025-10-27. '
            'Platform commission 12.5% (Marketplace) / 14.5% (Mall). '
            'No transaction_fee yet (added 2026-05-09 in 2026-VN-v3).',
            now(), now()
        )
        ON CONFLICT (version) DO NOTHING
    """)

    # 3. Confirm 2026-VN-v3 effective_to is NULL (should already be, defensive check)
    op.execute("""
        UPDATE fee_configs
        SET effective_to = NULL
        WHERE version = '2026-VN-v3'
    """)


def downgrade() -> None:
    op.execute("DELETE FROM fee_configs WHERE version = '2025-VN-v2'")
    op.execute("UPDATE fee_configs SET effective_to = NULL WHERE version = '2024-VN-v1'")
