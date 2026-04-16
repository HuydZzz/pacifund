"""
Bybit Collector
Fetches funding rates from Bybit Perpetuals (public API, no auth needed).
Adds a third data source for more arbitrage opportunities.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from backend.collectors.base_collector import BaseCollector
from backend.models import Exchange, FundingRate

logger = logging.getLogger(__name__)

PAIR_MAP = {
    "BTC-PERP": "BTCUSDT",
    "ETH-PERP": "ETHUSDT",
    "SOL-PERP": "SOLUSDT",
    "ARB-PERP": "ARBUSDT",
    "AVAX-PERP": "AVAXUSDT",
    "OP-PERP": "OPUSDT",
    "MATIC-PERP": "MATICUSDT",
}


class BybitCollector(BaseCollector):
    """
    Collects funding rates from Bybit.
    Public API — no authentication needed.
    """

    BASE_URL = "https://api.bybit.com"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL, timeout=10.0
            )
        return self._client

    async def get_funding_rate(self, pair: str) -> FundingRate:
        client = await self._get_client()
        symbol = PAIR_MAP.get(pair, pair.replace("-PERP", "USDT"))

        try:
            resp = await client.get(
                "/v5/market/tickers",
                params={"category": "linear", "symbol": symbol},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("retCode") != 0:
                raise ValueError(data.get("retMsg"))

            ticker = data["result"]["list"][0]
            next_ts = datetime.utcfromtimestamp(
                int(ticker.get("nextFundingTime", 0)) / 1000
            )

            return FundingRate(
                exchange=Exchange.BYBIT,
                pair=pair,
                rate=float(ticker.get("fundingRate", 0)),
                next_funding_ts=next_ts,
            )
        except Exception as e:
            logger.warning(f"Bybit fetch failed for {pair}: {e}")
            return FundingRate(
                exchange=Exchange.BYBIT,
                pair=pair,
                rate=0.0,
                next_funding_ts=datetime.utcnow() + timedelta(hours=8),
            )

    async def get_all_rates(self, pairs: list[str]) -> list[FundingRate]:
        """Fetch all rates concurrently."""
        tasks = [self.get_funding_rate(p) for p in pairs]
        return await asyncio.gather(*tasks)

    async def get_orderbook_depth(self, pair: str) -> dict:
        client = await self._get_client()
        symbol = PAIR_MAP.get(pair, pair.replace("-PERP", "USDT"))

        try:
            resp = await client.get(
                "/v5/market/orderbook",
                params={"category": "linear", "symbol": symbol, "limit": 10},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("retCode") != 0:
                raise ValueError(data.get("retMsg"))

            ob = data["result"]
            bids = ob.get("b", [])
            asks = ob.get("a", [])

            bid_depth = sum(float(b[0]) * float(b[1]) for b in bids)
            ask_depth = sum(float(a[0]) * float(a[1]) for a in asks)

            return {
                "pair": pair,
                "bid_depth_usd": bid_depth,
                "ask_depth_usd": ask_depth,
                "mid_price": (float(bids[0][0]) + float(asks[0][0])) / 2
                if bids and asks
                else 0,
            }
        except Exception as e:
            logger.warning(f"Bybit orderbook failed for {pair}: {e}")
            return {"pair": pair, "bid_depth_usd": 0, "ask_depth_usd": 0}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
