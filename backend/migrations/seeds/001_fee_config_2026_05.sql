-- =============================================================================
-- DEPRECATED: This seed file is superseded by Alembic migration 0002 + 0006.
-- DO NOT RUN — migrations handle all fee config seeding correctly.
--
-- History: This file was created during development to seed the 2026-05 fee
-- config, but it was missing transaction_fee_rate and order_processing_fee_per_order
-- and had NOT NULL constraint violations (verified_date, source_url).
--
-- Canonical source of truth: migrations/versions/0002_*.py and 0006_*.py
-- =============================================================================

-- This file intentionally does nothing.
SELECT 'Use alembic upgrade head instead — see migrations/versions/0002_* and 0006_*' AS note;
