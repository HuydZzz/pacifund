"""
Analytics Engine
Computes advanced performance metrics from trading history.

Provides institutional-grade analytics:
- Sharpe, Sortino, Calmar ratios
- Max drawdown, underwater curve
- Win rate, profit factor, expectancy
- Per-pair performance breakdown
- Rolling performance windows
"""
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Complete performance snapshot."""
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_days: int
    win_rate_pct: float
    profit_factor: float
    expectancy_usd: float
    avg_win_usd: float
    avg_loss_usd: float
    largest_win_usd: float
    largest_loss_usd: float
    total_trades: int
    avg_trade_duration_hours: float

    def to_dict(self) -> dict:
        return {
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return_pct": round(self.annualized_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy_usd": round(self.expectancy_usd, 2),
            "avg_win_usd": round(self.avg_win_usd, 2),
            "avg_loss_usd": round(self.avg_loss_usd, 2),
            "largest_win_usd": round(self.largest_win_usd, 2),
            "largest_loss_usd": round(self.largest_loss_usd, 2),
            "total_trades": self.total_trades,
            "avg_trade_duration_hours": round(self.avg_trade_duration_hours, 1),
        }


class AnalyticsEngine:
    """Computes institutional-grade performance metrics."""

    def __init__(self, initial_capital: float = 10_000.0):
        self.initial_capital = initial_capital

    def compute(
        self,
        trades: list,
        equity_curve: list,
    ) -> PerformanceMetrics:
        """
        Compute full performance metrics.

        Args:
            trades: List of trade dicts with 'pnl_usd', 'duration_hours', 'status'
            equity_curve: List of {date, equity} dicts

        Returns:
            PerformanceMetrics object
        """
        if not trades or not equity_curve:
            return self._empty_metrics()

        # Basic stats
        total_trades = len(trades)
        wins = [t for t in trades if t["pnl_usd"] > 0]
        losses = [t for t in trades if t["pnl_usd"] <= 0]

        total_pnl = sum(t["pnl_usd"] for t in trades)
        total_wins = sum(t["pnl_usd"] for t in wins)
        total_losses = abs(sum(t["pnl_usd"] for t in losses))

        # Returns
        final_equity = equity_curve[-1]["equity"]
        total_return_pct = (
            (final_equity - self.initial_capital) / self.initial_capital * 100
        )
        days = len(equity_curve)
        annualized = self._annualize(total_return_pct, days)

        # Daily returns from equity curve
        daily_returns = self._compute_daily_returns(equity_curve)

        # Drawdown
        max_dd, max_dd_duration = self._max_drawdown(equity_curve)

        # Risk-adjusted ratios
        sharpe = self._sharpe(daily_returns)
        sortino = self._sortino(daily_returns)
        calmar = annualized / max_dd if max_dd > 0 else 0.0

        # Trade quality
        win_rate = (len(wins) / total_trades * 100) if total_trades else 0
        profit_factor = (
            total_wins / total_losses if total_losses > 0 else float("inf")
        )
        expectancy = total_pnl / total_trades if total_trades else 0

        return PerformanceMetrics(
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown_pct=max_dd,
            max_drawdown_duration_days=max_dd_duration,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            expectancy_usd=expectancy,
            avg_win_usd=total_wins / len(wins) if wins else 0,
            avg_loss_usd=-total_losses / len(losses) if losses else 0,
            largest_win_usd=max((t["pnl_usd"] for t in wins), default=0),
            largest_loss_usd=min((t["pnl_usd"] for t in losses), default=0),
            total_trades=total_trades,
            avg_trade_duration_hours=(
                sum(t.get("duration_hours", 0) for t in trades) / total_trades
                if total_trades else 0
            ),
        )

    def pair_breakdown(self, trades: list) -> list:
        """Performance breakdown by trading pair."""
        by_pair: dict = {}
        for t in trades:
            pair = t.get("pair", "UNKNOWN")
            if pair not in by_pair:
                by_pair[pair] = {"trades": 0, "pnl": 0.0, "wins": 0}
            by_pair[pair]["trades"] += 1
            by_pair[pair]["pnl"] += t["pnl_usd"]
            if t["pnl_usd"] > 0:
                by_pair[pair]["wins"] += 1

        result = []
        for pair, stats in by_pair.items():
            result.append({
                "pair": pair,
                "total_trades": stats["trades"],
                "total_pnl": round(stats["pnl"], 2),
                "win_rate": round(stats["wins"] / stats["trades"] * 100, 1)
                if stats["trades"] else 0,
            })
        result.sort(key=lambda x: x["total_pnl"], reverse=True)
        return result

    def hourly_performance(self, trades: list) -> list:
        """Average profit by hour of day (for timing analysis)."""
        by_hour: dict = {h: [] for h in range(24)}
        for t in trades:
            hour = t.get("hour", 0)
            by_hour[hour].append(t["pnl_usd"])

        return [
            {
                "hour": h,
                "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0,
                "trade_count": len(pnls),
            }
            for h, pnls in by_hour.items()
        ]

    def strategy_health_score(
        self, metrics: PerformanceMetrics
    ) -> float:
        """
        Overall strategy health score (0-100).
        Weighted combination of key metrics.
        """
        score = 0.0

        # Sharpe ratio (30% weight)
        # Good Sharpe > 2, excellent > 3
        sharpe_score = min(metrics.sharpe_ratio / 3.0, 1.0) * 30
        score += sharpe_score

        # Win rate (20% weight)
        # Arb should have >85% win rate
        win_score = min(metrics.win_rate_pct / 90.0, 1.0) * 20
        score += win_score

        # Max drawdown (25% weight) - inverted
        # Lower is better, penalize >10%
        dd_score = max(0, (10 - metrics.max_drawdown_pct) / 10) * 25
        score += dd_score

        # Profit factor (15% weight)
        # Good > 2, excellent > 4
        pf_score = min(metrics.profit_factor / 4.0, 1.0) * 15
        score += pf_score

        # Total return (10% weight)
        ret_score = min(metrics.annualized_return_pct / 50.0, 1.0) * 10
        score += max(0, ret_score)

        return min(100.0, max(0.0, score))

    # ─── Helpers ────────────────────────────────────

    def _empty_metrics(self) -> PerformanceMetrics:
        return PerformanceMetrics(
            total_return_pct=0, annualized_return_pct=0,
            sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
            max_drawdown_pct=0, max_drawdown_duration_days=0,
            win_rate_pct=0, profit_factor=0, expectancy_usd=0,
            avg_win_usd=0, avg_loss_usd=0,
            largest_win_usd=0, largest_loss_usd=0,
            total_trades=0, avg_trade_duration_hours=0,
        )

    def _compute_daily_returns(self, equity_curve: list) -> list:
        """Convert equity curve to daily percentage returns."""
        returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i-1]["equity"]
            curr = equity_curve[i]["equity"]
            if prev > 0:
                returns.append(((curr - prev) / prev) * 100)
        return returns

    def _max_drawdown(self, equity_curve: list) -> tuple:
        """Compute max drawdown % and its duration in days."""
        if not equity_curve:
            return 0.0, 0

        max_equity = equity_curve[0]["equity"]
        max_dd = 0.0
        max_dd_duration = 0
        current_dd_start = 0

        for i, point in enumerate(equity_curve):
            equity = point["equity"]
            if equity > max_equity:
                max_equity = equity
                current_dd_start = i
            else:
                dd = ((max_equity - equity) / max_equity) * 100
                if dd > max_dd:
                    max_dd = dd
                    max_dd_duration = i - current_dd_start

        return max_dd, max_dd_duration

    def _sharpe(self, daily_returns: list) -> float:
        """Annualized Sharpe ratio."""
        if len(daily_returns) < 2:
            return 0.0
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / len(
            daily_returns
        )
        std = math.sqrt(variance)
        return (mean / std) * math.sqrt(365) if std > 0 else 0.0

    def _sortino(self, daily_returns: list) -> float:
        """
        Annualized Sortino ratio.
        Only penalizes downside volatility (unlike Sharpe).
        """
        if len(daily_returns) < 2:
            return 0.0
        mean = sum(daily_returns) / len(daily_returns)
        downside = [r for r in daily_returns if r < 0]
        if not downside:
            return float("inf")
        downside_var = sum(r ** 2 for r in downside) / len(downside)
        downside_std = math.sqrt(downside_var)
        return (mean / downside_std) * math.sqrt(365) if downside_std > 0 else 0.0

    def _annualize(self, total_return_pct: float, days: int) -> float:
        if days == 0:
            return 0.0
        ratio = 1 + (total_return_pct / 100)
        if ratio <= 0:
            return -100.0
        return (math.pow(ratio, 365 / days) - 1) * 100
