"""
Position Sizer
Determines optimal position size using a simplified Kelly Criterion,
adjusted for the specific characteristics of funding rate arbitrage.
"""
import logging
from dataclasses import dataclass

from config import ArbConfig
from models import ArbSignal

logger = logging.getLogger(__name__)


@dataclass
class SizeRecommendation:
    """Output of position sizing calculation."""
    signal_id: str
    recommended_size_usd: float
    max_size_usd: float
    leverage: float
    kelly_fraction: float
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "recommended_size_usd": round(self.recommended_size_usd, 2),
            "max_size_usd": round(self.max_size_usd, 2),
            "leverage": self.leverage,
            "kelly_fraction": round(self.kelly_fraction, 4),
            "reasoning": self.reasoning,
        }


class PositionSizer:
    """
    Calculates how much capital to allocate per signal.

    Uses a fractional Kelly approach:
    - Full Kelly is too aggressive for most traders
    - We use 1/4 Kelly for conservative sizing
    - Capped by max_position_pct from config
    """

    def __init__(self, config: ArbConfig):
        self.config = config

    def calculate(
        self,
        signal: ArbSignal,
        total_capital: float,
        current_exposure: float = 0.0,
    ) -> SizeRecommendation:
        """
        Calculate recommended position size for a signal.

        Args:
            signal: The arb signal to size
            total_capital: Total available capital in USD
            current_exposure: Current total position value in USD

        Returns:
            SizeRecommendation with sizing details
        """
        available = total_capital - current_exposure
        max_size = total_capital * self.config.max_position_pct

        if available <= 0:
            return SizeRecommendation(
                signal_id=signal.id,
                recommended_size_usd=0,
                max_size_usd=max_size,
                leverage=1.0,
                kelly_fraction=0,
                reasoning="No available capital (fully allocated).",
            )

        # Simplified Kelly for funding arb:
        # Win rate is high (>90%) since we're delta-neutral
        # Win size = spread per period
        # Loss size = slippage + fees (small but non-zero)
        est_win_rate = 0.92  # Funding arb wins most periods
        est_win_size = signal.spread  # Gain per dollar per period
        est_loss_size = 0.002  # ~0.2% from slippage + fees on close

        # Kelly formula: f* = (p * b - q) / b
        # where p=win_rate, q=1-p, b=win/loss ratio
        if est_loss_size == 0:
            kelly_raw = self.config.max_position_pct
        else:
            b = est_win_size / est_loss_size
            p = est_win_rate
            q = 1 - p
            kelly_raw = max(0, (p * b - q) / b)

        # Use quarter-Kelly for safety
        kelly_fraction = kelly_raw * 0.25

        # Apply confidence scaling
        kelly_adjusted = kelly_fraction * signal.confidence

        # Calculate size
        raw_size = total_capital * kelly_adjusted
        capped_size = min(raw_size, max_size, available)

        # Determine leverage (1x for most conservative, up to 3x for high confidence)
        leverage = 1.0
        if signal.confidence > 0.8 and signal.spread > 0.0003:
            leverage = 2.0
        elif signal.confidence > 0.6:
            leverage = 1.5

        return SizeRecommendation(
            signal_id=signal.id,
            recommended_size_usd=round(capped_size, 2),
            max_size_usd=round(max_size, 2),
            leverage=leverage,
            kelly_fraction=kelly_adjusted,
            reasoning=(
                f"Quarter-Kelly sizing at {kelly_adjusted:.1%} of capital. "
                f"Confidence: {signal.confidence:.0%}, "
                f"Spread: {signal.spread * 100:.4f}%. "
                f"Leverage: {leverage}x."
            ),
        )
