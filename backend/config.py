"""
PaciFund Configuration
All settings in one place. Override via .env file.
"""
import os
from dataclasses import dataclass, field


@dataclass
class PacificaConfig:
    base_url: str = "https://api.pacifica.fi"
    testnet_url: str = "https://test-api.pacifica.fi"
    api_key: str = ""
    use_testnet: bool = True

    @property
    def active_url(self) -> str:
        return self.testnet_url if self.use_testnet else self.base_url


@dataclass
class ArbConfig:
    # Minimum funding rate spread to trigger a signal (per 8h period)
    min_spread_threshold: float = 0.0001  # 0.01%
    # Maximum position size as fraction of total capital
    max_position_pct: float = 0.25
    # Stop loss percentage
    stop_loss_pct: float = 0.02  # 2%
    # Take profit percentage
    take_profit_pct: float = 0.05  # 5%
    # Minimum liquidity (USD) required on both sides
    min_liquidity_usd: float = 10_000
    # Supported trading pairs
    pairs: list = field(default_factory=lambda: [
        "BTC-PERP", "ETH-PERP", "SOL-PERP", "ARB-PERP", "AVAX-PERP"
    ])


@dataclass
class AppConfig:
    pacifica: PacificaConfig = field(default_factory=PacificaConfig)
    arb: ArbConfig = field(default_factory=ArbConfig)
    db_path: str = "data/pacifund.db"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"


def load_config() -> AppConfig:
    """Load config with .env overrides."""
    config = AppConfig()
    config.pacifica.api_key = os.getenv("PACIFICA_API_KEY", "")
    config.pacifica.use_testnet = os.getenv("USE_TESTNET", "true").lower() == "true"
    config.arb.min_spread_threshold = float(
        os.getenv("MIN_SPREAD", "0.0001")
    )
    config.arb.max_position_pct = float(
        os.getenv("MAX_POSITION_PCT", "0.25")
    )
    config.db_path = os.getenv("DB_PATH", "data/pacifund.db")
    return config
