"""
Base Collector
Abstract interface for fetching funding rates from exchanges.
"""
from abc import ABC, abstractmethod
from models import FundingRate


class BaseCollector(ABC):
    """All exchange collectors implement this interface."""

    @abstractmethod
    async def get_funding_rate(self, pair: str) -> FundingRate:
        """Fetch current funding rate for a pair."""
        ...

    @abstractmethod
    async def get_all_rates(self, pairs: list[str]) -> list[FundingRate]:
        """Fetch funding rates for multiple pairs."""
        ...

    @abstractmethod
    async def get_orderbook_depth(self, pair: str) -> dict:
        """Fetch orderbook depth for liquidity estimation."""
        ...
