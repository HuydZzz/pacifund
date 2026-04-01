"""
Risk Manager
Pre-trade and live-position risk checks.
Prevents the executor from doing anything dangerous.
"""
import logging
from dataclasses import dataclass
from datetime import datetime

from config import ArbConfig
from models import ArbSignal, Position, PositionStatus

logger = logging.getLogger(__name__)


@dataclass
class RiskCheck:
    """Result of a risk check."""
    approved: bool
    reason: str
    risk_score: float  # 0 = safe, 1 = maximum risk


class RiskManager:
    """
    Enforces risk limits before and during trades.

    Pre-trade checks:
    - Max position count
    - Max total exposure
    - Single-pair concentration limit
    - Minimum confidence threshold

    Live checks:
    - Stop-loss triggers
    - Max drawdown
    """

    MAX_OPEN_POSITIONS = 10
    MIN_CONFIDENCE = 0.4
    MAX_SINGLE_PAIR_PCT = 0.4  # No more than 40% in one pair

    def __init__(self, config: ArbConfig):
        self.config = config

    def pre_trade_check(
        self,
        signal: ArbSignal,
        size_usd: float,
        total_capital: float,
        open_positions: list[Position],
    ) -> RiskCheck:
        """
        Run all pre-trade checks before executing a signal.
        Returns RiskCheck with approval/rejection and reason.
        """
        # Check 1: Position count
        active = [p for p in open_positions if p.status == PositionStatus.OPEN]
        if len(active) >= self.MAX_OPEN_POSITIONS:
            return RiskCheck(
                approved=False,
                reason=f"Max open positions ({self.MAX_OPEN_POSITIONS}) reached.",
                risk_score=1.0,
            )

        # Check 2: Minimum confidence
        if signal.confidence < self.MIN_CONFIDENCE:
            return RiskCheck(
                approved=False,
                reason=f"Signal confidence {signal.confidence:.0%} below minimum {self.MIN_CONFIDENCE:.0%}.",
                risk_score=0.7,
            )

        # Check 3: Total exposure
        total_exposure = sum(
            p.size_usd for p in active
        )
        if total_exposure + size_usd > total_capital:
            return RiskCheck(
                approved=False,
                reason="Would exceed 100% capital exposure.",
                risk_score=0.9,
            )

        # Check 4: Single-pair concentration
        pair_exposure = sum(
            p.size_usd for p in active if p.pair == signal.pair
        )
        pair_limit = total_capital * self.MAX_SINGLE_PAIR_PCT
        if pair_exposure + size_usd > pair_limit:
            return RiskCheck(
                approved=False,
                reason=f"Would exceed {self.MAX_SINGLE_PAIR_PCT:.0%} concentration in {signal.pair}.",
                risk_score=0.6,
            )

        # Check 5: Signal not expired
        if signal.expires_at and signal.expires_at < datetime.utcnow():
            return RiskCheck(
                approved=False,
                reason="Signal has expired (past next funding time).",
                risk_score=0.3,
            )

        # All checks passed
        risk_score = self._calculate_portfolio_risk(
            active, size_usd, total_capital
        )
        return RiskCheck(
            approved=True,
            reason="All pre-trade checks passed.",
            risk_score=risk_score,
        )

    def check_stop_loss(self, position: Position) -> bool:
        """Returns True if position should be closed due to stop-loss."""
        if position.size_usd == 0:
            return False
        loss_pct = abs(min(0, position.pnl_usd)) / position.size_usd
        return loss_pct >= self.config.stop_loss_pct

    def check_take_profit(self, position: Position) -> bool:
        """Returns True if position hit take-profit target."""
        if position.size_usd == 0:
            return False
        gain_pct = max(0, position.pnl_usd) / position.size_usd
        return gain_pct >= self.config.take_profit_pct

    def _calculate_portfolio_risk(
        self,
        positions: list[Position],
        new_size: float,
        capital: float,
    ) -> float:
        """0-1 portfolio risk score based on concentration and exposure."""
        total = sum(p.size_usd for p in positions) + new_size
        exposure_ratio = total / capital if capital > 0 else 1.0

        # Count unique pairs
        pairs = {p.pair for p in positions}
        diversity = len(pairs) / max(len(positions), 1)

        # Higher exposure + lower diversity = higher risk
        return min(1.0, exposure_ratio * 0.6 + (1 - diversity) * 0.4)
