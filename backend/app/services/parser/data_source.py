"""
OrderDataSource Protocol — abstract interface for order data ingestion.

Defines the contract between data sources (CSV upload, future TikTok API)
and the P&L engine. Swap CSVOrderSource for TikTokAPIOrderSource in v3.0
without touching pl_calculator.py.
"""

from datetime import date
from typing import Protocol, runtime_checkable

from app.services.parser.base import RawOrderRow


@runtime_checkable
class OrderDataSource(Protocol):
    async def get_orders(
        self,
        shop_id: str,
        start_date: date,
        end_date: date,
    ) -> list[RawOrderRow]: ...

    @property
    def source_label(self) -> str:
        """Human-readable label: 'CSV Upload', 'TikTok API', etc."""
        ...


class CSVOrderSource:
    """Current implementation: parses uploaded CSV bytes."""

    def __init__(self, file_bytes: bytes, filename: str):
        self._file_bytes = file_bytes
        self._filename = filename

    @property
    def source_label(self) -> str:
        return "CSV Upload"

    async def get_orders(self, shop_id: str, start_date: date, end_date: date) -> list[RawOrderRow]:
        import asyncio

        from app.services.parser import parse_order_csv

        result = await asyncio.to_thread(parse_order_csv, self._file_bytes, self._filename)
        return result.rows
