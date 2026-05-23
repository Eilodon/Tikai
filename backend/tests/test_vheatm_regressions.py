import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.api.v1.cogs import COGSItem, COGSEntryItem
from datetime import date

def test_cogs_item_validation():
    # Test COGSItem with gt=0 works correctly for valid inputs
    item = COGSItem(sku_id="SKU1", sku_name="Product 1", cogs_per_unit=Decimal("10.5"))
    assert item.cogs_per_unit == Decimal("10.5")

    # Test COGSItem rejects zero or negative
    with pytest.raises(ValidationError):
        COGSItem(sku_id="SKU2", sku_name="Product 2", cogs_per_unit=Decimal("0"))

    with pytest.raises(ValidationError):
        COGSItem(sku_id="SKU3", sku_name="Product 3", cogs_per_unit=Decimal("-5"))

def test_cogs_entry_item_validation():
    # Test COGSEntryItem with gt=0 works correctly for valid inputs
    entry = COGSEntryItem(sku_id="SKU1", cogs_per_unit=Decimal("100"), effective_date=date.today())
    assert entry.cogs_per_unit == Decimal("100")

    # Test COGSEntryItem rejects zero
    with pytest.raises(ValidationError):
        COGSEntryItem(sku_id="SKU2", cogs_per_unit=Decimal("0"), effective_date=date.today())
