"""Test feature gates (FIX GAP-M6)."""

import pytest
from fastapi import HTTPException

from app.core.gates import (
    Feature,
    get_ai_calls_limit,
    get_history_weeks_limit,
    require_feature,
)


class FakeShop:
    def __init__(self, tier="free"):
        self.subscription_tier = tier


class TestGates:
    def test_free_tier_blocks_re_analysis(self):
        shop = FakeShop("free")
        with pytest.raises(HTTPException) as exc:
            require_feature(shop, Feature.RE_ANALYSIS)
        assert exc.value.status_code == 402

    def test_pro_tier_allows_re_analysis(self):
        shop = FakeShop("pro")
        require_feature(shop, Feature.RE_ANALYSIS)  # no raise

    def test_history_weeks_capped_per_tier(self):
        assert get_history_weeks_limit(FakeShop("free")) == 4
        assert get_history_weeks_limit(FakeShop("pro")) == 12
        assert get_history_weeks_limit(FakeShop("business")) == 52

    def test_ai_calls_limit_per_tier(self):
        assert get_ai_calls_limit(FakeShop("free")) == 5
        assert get_ai_calls_limit(FakeShop("pro")) == 10
        assert get_ai_calls_limit(FakeShop("business")) == 15  # F-1B-06: explicit tier limit

    def test_unknown_tier_falls_back_to_free(self):
        assert get_history_weeks_limit(FakeShop("enterprise_xyz")) == 4

    def test_none_tier_falls_back_to_free(self):
        shop = FakeShop(None)
        assert get_history_weeks_limit(shop) == 4
