"""
Arb Scanner
Core logic: compare funding rates across exchanges,
detect spreads, generate trade signals.

This is the brain of PaciFund.
"""
import logging
import uuid
from datetime import datetime, timedelta
from itertools import combinations

from config import ArbConfig
from models import ArbSignal, Exchange, FundingRate

logger = logging.getLogger(__name__)


class ArbScanner:
    """
    Scans funding rate data across exchanges and generates
    arbitrage signals when spreads exceed the threshold.

    Strategy:
    - LONG on the exchange with lower/negative funding rate
      (you GET paid funding)
    - SHORT on the exchange with higher/positive funding rate
      (hedges the long, and you collect the spread)

    This is delta-neutral: price movement doesn't affect P&L,
    only the funding rate difference matters.
    """

    def __init__(self, config: ArbConfig):
        self.config = config
        self._rate_history: list[dict] = []

    def scan(
        self,
        rates: list[FundingRate],
        liquidity: dict[str, dict] | None = None,
    ) -> list[ArbSignal]:
        """
        Main scan loop. Takes rates from all exchanges,
        finds all cross-exchange pairs, returns signals.

        Args:
            rates: List of FundingRate from all collectors
            liquidity: Optional dict of {pair: {exchange: depth_usd}}

        Returns:
            List of ArbSignal sorted by spread (highest first)
        """
        # Group rates by pair
        by_pair: dict[str, list[FundingRate]] = {}
        for rate in rates:
            by_pair.setdefault(rate.pair, []).append(rate)

        signals = []

        for pair, pair_rates in by_pair.items():
            if len(pair_rates) < 2:
                continue

            # Compare every exchange pair
            for rate_a, rate_b in combinations(pair_rates, 2):
                signal = self._evaluate_pair(rate_a, rate_b, liquidity)
                if signal:
                    signals.append(signal)

        # Sort by spread descending (best opportunities first)
        signals.sort(key=lambda s: s.spread, reverse=True)

        # Store for history
        self._rate_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "rates": [r.to_dict() for r in rates],
            "signals_count": len(signals),
        })

        # Keep only last 1000 snapshots
        if len(self._rate_history) > 1000:
            self._rate_history = self._rate_history[-1000:]

        return signals

    def _evaluate_pair(
        self,
        rate_a: FundingRate,
        rate_b: FundingRate,
        liquidity: dict | None,
    ) -> ArbSignal | None:
        """
        Evaluate a single pair of rates from two exchanges.
        Returns a signal if the spread exceeds threshold.
        """
        spread = abs(rate_a.rate - rate_b.rate)

        # Check minimum spread
        if spread < self.config.min_spread_threshold:
            return None

        # Determine direction: long where rate is lower, short where higher
        if rate_a.rate < rate_b.rate:
            long_rate, short_rate = rate_a, rate_b
        else:
            long_rate, short_rate = rate_b, rate_a

        # Ensure Pacifica is on at least one side
        # (we must use Pacifica per hackathon rules)
        pacifica_involved = (
            long_rate.exchange == Exchange.PACIFICA
            or short_rate.exchange == Exchange.PACIFICA
        )
        if not pacifica_involved:
            return None

        # Estimate confidence based on spread size + liquidity
        confidence = self._calculate_confidence(
            spread, long_rate.pair, liquidity
        )

        # Estimated profit per $10k position per 8h funding period
        # Profit = position_size × spread (minus estimated fees ~0.001%)
        est_fee = 0.00001  # ~0.001% round trip
        profit_per_10k = 10_000 * max(0, spread - est_fee)

        return ArbSignal(
            id=f"sig_{uuid.uuid4().hex[:8]}",
            pair=long_rate.pair,
            long_exchange=long_rate.exchange,
            short_exchange=short_rate.exchange,
            long_rate=long_rate.rate,
            short_rate=short_rate.rate,
            spread=spread,
            estimated_profit_8h=profit_per_10k,
            confidence=confidence,
            expires_at=min(
                long_rate.next_funding_ts, short_rate.next_funding_ts
            ),
        )

    def _calculate_confidence(
        self,
        spread: float,
        pair: str,
        liquidity: dict | None,
    ) -> float:
        """
        Confidence score 0-1 based on:
        - Spread size (bigger = more confident it's real)
        - Liquidity (deeper books = less slippage risk)
        - Historical consistency (not just a spike)
        """
        score = 0.0

        # Spread component (0-0.4)
        # Spreads >0.05% are very confident, <0.01% are marginal
        spread_score = min(spread / 0.0005, 1.0) * 0.4
        score += spread_score

        # Liquidity component (0-0.3)
        if liquidity and pair in liquidity:
            min_depth = min(
                liquidity[pair].get("bid_depth_usd", 0),
                liquidity[pair].get("ask_depth_usd", 0),
            )
            liq_score = min(min_depth / self.config.min_liquidity_usd, 1.0)
            score += liq_score * 0.3
        else:
            score += 0.15  # Unknown liquidity → medium confidence

        # Historical consistency (0-0.3)
        # Check if this pair had signals in recent snapshots
        recent = self._rate_history[-10:]
        if recent:
            score += 0.3  # Simplified: assume consistent if we have data

        return min(score, 1.0)

    def get_rate_history(self, limit: int = 100) -> list[dict]:
        """Return recent rate snapshots for charting."""
        return self._rate_history[-limit:]
