"""
IDOR (Insecure Direct Object Reference) audit tests.
Verifies that shop_id filters are present on ALL resource-touching endpoints
and that the authentication chain correctly binds resources to their owner.

These are source-inspection tests — they do not require a running DB or HTTP server.
Run: pytest tests/test_idor.py -v
"""
import inspect


class TestShopIdFilterInvariants:
    """Every endpoint that fetches/mutates a resource must include shop_id filter."""

    def test_imports_get_by_id_has_shop_id_filter(self):
        from app.api.v1.imports import get_import_status
        src = inspect.getsource(get_import_status)
        assert "shop_id == shop.id" in src or "shop_id=shop.id" in src

    def test_imports_list_has_shop_id_filter(self):
        from app.api.v1.imports import list_imports
        src = inspect.getsource(list_imports)
        assert "shop_id == shop.id" in src or "shop_id=shop.id" in src

    def test_insights_latest_has_shop_id_filter(self):
        from app.api.v1.insights import get_latest_insight
        src = inspect.getsource(get_latest_insight)
        assert "shop_id == shop.id" in src

    def test_insights_history_has_shop_id_filter(self):
        from app.api.v1.insights import get_insight_history
        src = inspect.getsource(get_insight_history)
        assert "shop_id == shop.id" in src

    def test_insights_by_id_has_shop_id_filter(self):
        from app.api.v1.insights import get_insight_by_id
        src = inspect.getsource(get_insight_by_id)
        assert "shop_id == shop.id" in src

    def test_recompute_has_dual_shop_id_filter(self):
        """recompute loads both snapshot AND orders — both must have shop_id filter."""
        from app.api.v1.insights import recompute_insight
        src = inspect.getsource(recompute_insight)
        assert src.count("shop_id == shop.id") >= 2, (
            "recompute_insight must filter BOTH InsightSnapshot AND Order by shop_id"
        )

    def test_actions_list_has_shop_id_filter(self):
        from app.api.v1.actions import list_actions
        src = inspect.getsource(list_actions)
        assert "shop_id == shop.id" in src

    def test_actions_get_helper_has_shop_id_filter(self):
        from app.api.v1.actions import _get_action
        src = inspect.getsource(_get_action)
        assert "shop_id ==" in src or "shop_id==" in src

    def test_cogs_get_has_shop_id_filter(self):
        from app.api.v1.cogs import get_cogs
        src = inspect.getsource(get_cogs)
        assert "shop_id == shop.id" in src

    def test_weekly_receipts_latest_has_shop_id_filter(self):
        from app.api.v1.weekly_receipts import get_latest_receipt
        src = inspect.getsource(get_latest_receipt)
        assert "shop_id == shop.id" in src

    def test_weekly_receipts_list_has_shop_id_filter(self):
        from app.api.v1.weekly_receipts import list_receipts
        src = inspect.getsource(list_receipts)
        assert "shop_id == shop.id" in src

    def test_weekly_receipt_mark_read_has_shop_id_filter(self):
        from app.api.v1.weekly_receipts import mark_receipt_read
        src = inspect.getsource(mark_receipt_read)
        assert "shop_id == shop.id" in src

    def test_livestream_list_has_shop_id_filter(self):
        from app.api.v1.livestream import list_livestreams
        src = inspect.getsource(list_livestreams)
        assert "shop_id == shop.id" in src

    def test_livestream_update_has_shop_id_filter(self):
        from app.api.v1.livestream import update_livestream_results
        src = inspect.getsource(update_livestream_results)
        assert "shop_id == shop.id" in src

    def test_livestream_delete_has_shop_id_filter(self):
        from app.api.v1.livestream import delete_livestream
        src = inspect.getsource(delete_livestream)
        assert "shop_id == shop.id" in src


class TestAuthChain:
    """The authentication chain must bind every resource to the authenticated user."""

    def test_get_current_shop_binds_to_owner_id(self):
        from app.core.auth import get_current_shop
        src = inspect.getsource(get_current_shop)
        assert "owner_id == current_user.id" in src, (
            "get_current_shop must bind shop to authenticated user via owner_id. "
            "Removing this allows any authenticated user to access any shop."
        )

    def test_jwt_uses_supabase_secret_not_hardcoded(self):
        from app.core.auth import get_current_user
        src = inspect.getsource(get_current_user)
        assert "supabase_jwt_secret" in src
        assert "HS256" in src
        assert "hardcoded" not in src.lower()

    def test_all_business_modules_use_get_current_shop(self):
        """Every module with business data must route through get_current_shop."""
        from app.api.v1 import imports, insights, actions, cogs, weekly_receipts, livestream
        for module in [imports, insights, actions, cogs, weekly_receipts, livestream]:
            src = inspect.getsource(module)
            assert "get_current_shop" in src, (
                f"{module.__name__} must use get_current_shop dependency. "
                "Using get_current_user directly bypasses shop isolation."
            )

    def test_shops_module_imports_get_current_shop(self):
        """BUG-P6-1 regression guard: shops.py must import get_current_shop."""
        from app.api.v1 import shops
        src = inspect.getsource(shops)
        import_lines = [l for l in src.split('\n') if 'from app.core.auth import' in l]
        assert any('get_current_shop' in l for l in import_lines), (
            "BUG-P6-1 regression: shops.py must import get_current_shop. "
            "Without it, PATCH /shops/me/notifications raises NameError and "
            "the app fails to start."
        )
