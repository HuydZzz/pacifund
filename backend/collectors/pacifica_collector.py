"""
Pacifica Collector
Fetches funding rates from Pacifica using their Python SDK.

Docs: https://docs.pacifica.fi/api-documentation/api
SDK:  https://github.com/pacifica-fi/python-sdk
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from collectors.base_collector import BaseCollector
from models import Exchange, FundingRate

logger = logging.getLogger(__name__)

# Pair mapping: our internal format → Pacifica API format
PAIR_MAP = {
    "BTC-PERP": "BTC-USD",
    "ETH-PERP": "ETH-USD",
    "SOL-PERP": "SOL-USD",
    "ARB-PERP": "ARB-USD",
    "AVAX-PERP": "AVAX-USD",
}


class PacificaCollector(BaseCollector):
    """
    Collects funding rate data from Pacifica.

    Uses httpx for REST calls. When Pacifica SDK is installed,
    you can swap httpx calls with SDK methods directly.
    """

    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=10.0,
            )
        return self._client

    async def get_funding_rate(self, pair: str) -> FundingRate:
        """Fetch current funding rate for a single pair."""
        client = await self._get_client()
        pacifica_pair = PAIR_MAP.get(pair, pair)

        try:
            # Pacifica API endpoint for funding rates
            # Adjust endpoint path based on actual API docs
            resp = await client.get(f"/v1/funding-rates/{pacifica_pair}")
            resp.raise_for_status()
            data = resp.json()

            return FundingRate(
                exchange=Exchange.PACIFICA,
                pair=pair,
                rate=float(data.get("funding_rate", 0)),
                next_funding_ts=datetime.fromisoformat(
                    data.get("next_funding_time", datetime.utcnow().isoformat())
                ),
            )
        except Exception as e:
            logger.warning(f"Pacifica rate fetch failed for {pair}: {e}")
            # Return zero rate on failure so scanner can still compare
            return FundingRate(
                exchange=Exchange.PACIFICA,
                pair=pair,
                rate=0.0,
                next_funding_ts=datetime.utcnow() + timedelta(hours=8),
            )

    async def get_all_rates(self, pairs: list[str]) -> list[FundingRate]:
        """Fetch rates for all pairs concurrently."""
        tasks = [self.get_funding_rate(p) for p in pairs]
        return await asyncio.gather(*tasks)

    async def get_orderbook_depth(self, pair: str) -> dict:
        """Fetch top-of-book for liquidity estimation."""
        client = await self._get_client()
        pacifica_pair = PAIR_MAP.get(pair, pair)

        try:
            resp = await client.get(f"/v1/orderbook/{pacifica_pair}")
            resp.raise_for_status()
            data = resp.json()

            bids = data.get("bids", [])
            asks = data.get("asks", [])

            # Sum top 10 levels for depth estimate
            bid_depth = sum(float(b[1]) * float(b[0]) for b in bids[:10])
            ask_depth = sum(float(a[1]) * float(a[0]) for a in asks[:10])

            return {
                "pair": pair,
                "bid_depth_usd": bid_depth,
                "ask_depth_usd": ask_depth,
                "mid_price": (float(bids[0][0]) + float(asks[0][0])) / 2
                if bids and asks
                else 0,
                "spread_bps": (
                    (float(asks[0][0]) - float(bids[0][0]))
                    / float(bids[0][0])
                    * 10_000
                    if bids and asks
                    else 0
                ),
            }
        except Exception as e:
            logger.warning(f"Pacifica orderbook fetch failed for {pair}: {e}")
            return {"pair": pair, "bid_depth_usd": 0, "ask_depth_usd": 0}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
