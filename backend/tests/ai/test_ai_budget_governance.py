from decimal import Decimal

import pytest

from app.services.ai import client as ai_client


class FakeRedis:
    def __init__(self):
        self.hash: dict[str, Decimal] = {}

    async def hget(self, key: str, field: str):
        return self.hash.get(field)

    async def eval(self, script: str, num_keys: int, key: str, *args):
        if "projected > limit" in script:
            amount = Decimal(str(args[0]))
            limit = Decimal(str(args[1]))
            spent = self.hash.get("total_usd", Decimal("0"))
            reserved = self.hash.get("reserved_usd", Decimal("0"))
            projected = spent + reserved + amount
            if projected > limit:
                return [0, str(projected)]
            self.hash["reserved_usd"] = reserved + amount
            return [1, str(projected)]

        if "HINCRBYFLOAT', key, 'total_usd'" in script:
            cost = Decimal(str(args[0]))
            reserved_to_release = Decimal(str(args[3]))
            self.hash["total_usd"] = self.hash.get("total_usd", Decimal("0")) + cost
            self.hash["reserved_usd"] = max(
                self.hash.get("reserved_usd", Decimal("0")) - reserved_to_release,
                Decimal("0"),
            )
            return str(self.hash["total_usd"])

        if "next_reserved = current_reserved - amount" in script:
            amount = Decimal(str(args[0]))
            self.hash["reserved_usd"] = max(
                self.hash.get("reserved_usd", Decimal("0")) - amount,
                Decimal("0"),
            )
            return str(self.hash["reserved_usd"])

        raise AssertionError("unexpected lua script")


@pytest.mark.asyncio
async def test_budget_reservation_blocks_concurrent_overspend(monkeypatch):
    redis = FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.redis.get_redis", fake_get_redis)

    first = await ai_client._reserve_budget("shop-1", "free", Decimal("0.10"))
    assert first == Decimal("0.10")

    with pytest.raises(ValueError, match="AI budget exceeded"):
        await ai_client._reserve_budget("shop-1", "free", Decimal("0.10"))

    assert redis.hash["reserved_usd"] == Decimal("0.10")


@pytest.mark.asyncio
async def test_record_cost_reconciles_reserved_budget(monkeypatch):
    redis = FakeRedis()
    redis.hash["reserved_usd"] = Decimal("0.10")

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.redis.get_redis", fake_get_redis)

    await ai_client._record_cost(
        "shop-1",
        "action_coach",
        Decimal("0.03"),
        reserved_usd=Decimal("0.10"),
    )

    assert redis.hash["total_usd"] == Decimal("0.03")
    assert redis.hash["reserved_usd"] == Decimal("0")


def test_estimated_cost_uses_selected_model_price_table():
    cheap = ai_client._estimate_max_cost(
        ai_client.MODEL_SMALL,
        user_content="x" * 400,
        max_tokens=100,
    )
    expensive = ai_client._estimate_max_cost(
        ai_client.MODEL_STANDARD,
        user_content="x" * 400,
        max_tokens=100,
    )

    assert cheap > 0
    assert expensive > cheap
