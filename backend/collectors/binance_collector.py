"""
Binance Collector
Fetches funding rates from Binance Futures (public endpoints, no key needed).
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from collectors.base_collector import BaseCollector
from models import Exchange, FundingRate

logger = logging.getLogger(__name__)

PAIR_MAP = {
    "BTC-PERP": "BTCUSDT",
    "ETH-PERP": "ETHUSDT",
    "SOL-PERP": "SOLUSDT",
    "ARB-PERP": "ARBUSDT",
    "AVAX-PERP": "AVAXUSDT",
}


class BinanceCollector(BaseCollector):
    """
    Collects funding rates from Binance Futures.
    Uses public API — no authentication required.
    """

    BASE_URL = "https://fapi.binance.com"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL, timeout=10.0
            )
        return self._client

    async def get_funding_rate(self, pair: str) -> FundingRate:
        """Fetch current funding rate for a single pair."""
        client = await self._get_client()
        symbol = PAIR_MAP.get(pair, pair.replace("-PERP", "USDT"))

        try:
            resp = await client.get(
                "/fapi/v1/premiumIndex", params={"symbol": symbol}
            )
            resp.raise_for_status()
            data = resp.json()

            next_ts = datetime.utcfromtimestamp(
                int(data.get("nextFundingTime", 0)) / 1000
            )

            return FundingRate(
                exchange=Exchange.BINANCE,
                pair=pair,
                rate=float(data.get("lastFundingRate", 0)),
                next_funding_ts=next_ts,
            )
        except Exception as e:
            logger.warning(f"Binance rate fetch failed for {pair}: {e}")
            return FundingRate(
                exchange=Exchange.BINANCE,
                pair=pair,
                rate=0.0,
                next_funding_ts=datetime.utcnow() + timedelta(hours=8),
            )

    async def get_all_rates(self, pairs: list[str]) -> list[FundingRate]:
        """Fetch all rates in one call (Binance supports bulk)."""
        client = await self._get_client()

        try:
            resp = await client.get("/fapi/v1/premiumIndex")
            resp.raise_for_status()
            all_data = resp.json()

            # Build reverse lookup
            reverse_map = {v: k for k, v in PAIR_MAP.items()}
            results = []

            for item in all_data:
                symbol = item.get("symbol", "")
                pair = reverse_map.get(symbol)
                if pair and pair in pairs:
                    next_ts = datetime.utcfromtimestamp(
                        int(item.get("nextFundingTime", 0)) / 1000
                    )
                    results.append(
                        FundingRate(
                            exchange=Exchange.BINANCE,
                            pair=pair,
                            rate=float(item.get("lastFundingRate", 0)),
                            next_funding_ts=next_ts,
                        )
                    )

            # Fill missing pairs with zero
            found_pairs = {r.pair for r in results}
            for pair in pairs:
                if pair not in found_pairs:
                    results.append(
                        FundingRate(
                            exchange=Exchange.BINANCE,
                            pair=pair,
                            rate=0.0,
                            next_funding_ts=datetime.utcnow() + timedelta(hours=8),
                        )
                    )

            return results

        except Exception as e:
            logger.warning(f"Binance bulk rate fetch failed: {e}")
            return await asyncio.gather(
                *[self.get_funding_rate(p) for p in pairs]
            )

    async def get_orderbook_depth(self, pair: str) -> dict:
        """Fetch orderbook for liquidity estimation."""
        client = await self._get_client()
        symbol = PAIR_MAP.get(pair, pair.replace("-PERP", "USDT"))

        try:
            resp = await client.get(
                "/fapi/v1/depth", params={"symbol": symbol, "limit": 10}
            )
            resp.raise_for_status()
            data = resp.json()

            bids = data.get("bids", [])
            asks = data.get("asks", [])

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
            logger.warning(f"Binance orderbook fetch failed for {pair}: {e}")
            return {"pair": pair, "bid_depth_usd": 0, "ask_depth_usd": 0}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
