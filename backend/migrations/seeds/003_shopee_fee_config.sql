-- Shopee VN fee config (v1 — verify against Shopee Seller Center VN before going live)
-- Source: https://sellercenter.shopee.vn/portal/edu/article/detail/73867
--
-- Base platform commission: 2% (varies by category — see category_overrides)
-- Transaction fee: 2% of order value (applied differently from TikTok)
-- Order processing fee: Shopee does NOT charge per-order fixed fee (unlike TikTok's 3,000 VND)
--
-- IMPORTANT: These rates are approximate. Shopee's fee structure varies by:
-- 1. Seller level (Normal / Preferred / Mall)
-- 2. Category
-- 3. Campaign participation
-- Verify with your Shopee Seller Center → Fees & Charges before relying on these numbers.

INSERT INTO fee_configs (
    id,
    version,
    platform,
    effective_from,
    effective_to,
    platform_commission_rate,
    transaction_fee_rate,
    order_processing_fee_per_order,
    category_overrides,
    verified_date,
    source_url,
    notes
) VALUES (
    gen_random_uuid(),
    '2026-SHOPEE-VN-v1',
    'shopee',
    '2026-01-01',
    NULL,
    0.0200,   -- 2% base platform commission
    0.0200,   -- 2% transaction fee (buyer-paid)
    0.00,     -- no fixed per-order fee (Shopee bundles differently from TikTok)
    '{"fashion": "0.0300", "electronics": "0.0100", "beauty": "0.0250", "food": "0.0150"}'::jsonb,
    '2026-05-26',
    'https://sellercenter.shopee.vn/portal/edu/article/detail/73867',
    'Shopee VN base rates for cross-platform P&L comparison. '
    'Rates vary by seller level (Normal/Preferred/Mall) and category. '
    'Verify category overrides against Shopee portal before going live. '
    'Commission bundles: Shopee does not separate affiliate commission from platform commission '
    'in the same way TikTok does — affiliate_commission in exports = 0 typically.'
)
ON CONFLICT (version) DO NOTHING;
