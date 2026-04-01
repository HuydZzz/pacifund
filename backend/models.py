"""
PaciFund Data Models
Clean domain objects used across all modules.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Exchange(str, Enum):
    PACIFICA = "pacifica"
    BINANCE = "binance"
    BYBIT = "bybit"
    DYDX = "dydx"


class SignalAction(str, Enum):
    LONG = "long"
    SHORT = "short"


class PositionStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass
class FundingRate:
    """Normalized funding rate from any exchange."""
    exchange: Exchange
    pair: str
    rate: float               # e.g. 0.0003 = 0.03% per period
    next_funding_ts: datetime
    collected_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def annualized(self) -> float:
        """Annualized rate assuming 3 funding periods per day."""
        return self.rate * 3 * 365

    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange.value,
            "pair": self.pair,
            "rate": self.rate,
            "rate_pct": f"{self.rate * 100:.4f}%",
            "annualized_pct": f"{self.annualized * 100:.2f}%",
            "next_funding": self.next_funding_ts.isoformat(),
            "collected_at": self.collected_at.isoformat(),
        }


@dataclass
class ArbSignal:
    """A detected arbitrage opportunity."""
    id: str
    pair: str
    long_exchange: Exchange    # Go long here (funding is negative/lower)
    short_exchange: Exchange   # Go short here (funding is positive/higher)
    long_rate: float
    short_rate: float
    spread: float              # Absolute spread between the two
    estimated_profit_8h: float # Estimated profit per $10k per 8h
    confidence: float          # 0-1 score based on liquidity + spread stability
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    @property
    def annualized_yield(self) -> float:
        return self.spread * 3 * 365

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pair": self.pair,
            "long_exchange": self.long_exchange.value,
            "short_exchange": self.short_exchange.value,
            "long_rate": self.long_rate,
            "short_rate": self.short_rate,
            "spread": self.spread,
            "spread_pct": f"{self.spread * 100:.4f}%",
            "annualized_yield": f"{self.annualized_yield * 100:.2f}%",
            "estimated_profit_8h": round(self.estimated_profit_8h, 2),
            "confidence": round(self.confidence, 2),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Position:
    """A tracked arbitrage position."""
    id: str
    signal_id: str
    pair: str
    long_exchange: Exchange
    short_exchange: Exchange
    size_usd: float
    entry_spread: float
    current_spread: float = 0.0
    pnl_usd: float = 0.0
    funding_collected: float = 0.0
    status: PositionStatus = PositionStatus.PENDING
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

    @property
    def total_return_pct(self) -> float:
        if self.size_usd == 0:
            return 0.0
        return (self.pnl_usd / self.size_usd) * 100

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "signal_id": self.signal_id,
            "pair": self.pair,
            "long_exchange": self.long_exchange.value,
            "short_exchange": self.short_exchange.value,
            "size_usd": round(self.size_usd, 2),
            "entry_spread": self.entry_spread,
            "current_spread": self.current_spread,
            "pnl_usd": round(self.pnl_usd, 2),
            "funding_collected": round(self.funding_collected, 2),
            "total_return_pct": f"{self.total_return_pct:.2f}%",
            "status": self.status.value,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }
