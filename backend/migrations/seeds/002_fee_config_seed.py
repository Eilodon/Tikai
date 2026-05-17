"""
DEPRECATED: This seed script is superseded by Alembic migration 0002 + 0006.
DO NOT RUN — migrations handle all fee config seeding correctly.

History: This script had bugs:
- Missing transaction_fee_rate (was 0 instead of 0.06 for 2026-05 config)
- Missing order_processing_fee_per_order (was 0 instead of 3000 for 2025-10 config)
- Missing required fields: effective_from, verified_date, source_url → IntegrityError on commit

Canonical source of truth:
  migrations/versions/0002_add_order_financial_fields_and_fee_config_2026.py
  migrations/versions/0006_fee_config_effective_dates.py

Run: alembic upgrade head
"""

raise RuntimeError(
    "This seed file is deprecated. Run 'alembic upgrade head' instead.\n"
    "See migrations/versions/0002_* and 0006_* for correct fee config seeding."
)
