"""
API Routes
REST + WebSocket endpoints for the PaciFund dashboard.
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from config import load_config
from collectors import PacificaCollector, BinanceCollector
from engine import ArbScanner, PositionSizer
from executor import PacificaExecutor, RiskManager
from models import PositionStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Initialize components
config = load_config()
pacifica_collector = PacificaCollector(
    config.pacifica.active_url, config.pacifica.api_key
)
binance_collector = BinanceCollector()
scanner = ArbScanner(config.arb)
sizer = PositionSizer(config.arb)
risk_mgr = RiskManager(config.arb)
executor = PacificaExecutor(config.pacifica)

# In-memory state (use Redis for production)
state = {
    "total_capital": 10_000.0,
    "auto_mode": False,
    "last_scan": None,
    "active_signals": [],
}


# ──────────────────────────────────────────────
# REST Endpoints
# ──────────────────────────────────────────────


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/scan")
async def run_scan():
    """Trigger a manual scan for arb opportunities."""
    try:
        # Fetch rates from all exchanges
        pacifica_rates = await pacifica_collector.get_all_rates(config.arb.pairs)
        binance_rates = await binance_collector.get_all_rates(config.arb.pairs)

        all_rates = pacifica_rates + binance_rates

        # Run scanner
        signals = scanner.scan(all_rates)

        # Size each signal
        current_exposure = sum(
            p.size_usd for p in executor.get_open_positions()
        )
        sized_signals = []
        for sig in signals:
            sizing = sizer.calculate(
                sig, state["total_capital"], current_exposure
            )
            sized_signals.append({
                "signal": sig.to_dict(),
                "sizing": sizing.to_dict(),
            })

        state["last_scan"] = datetime.utcnow().isoformat()
        state["active_signals"] = sized_signals

        return {
            "scan_time": state["last_scan"],
            "rates": [r.to_dict() for r in all_rates],
            "signals": sized_signals,
            "total_signals": len(signals),
        }
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        return {"error": str(e), "signals": []}


@router.get("/rates")
async def get_rates():
    """Get current funding rates from all exchanges."""
    pacifica_rates = await pacifica_collector.get_all_rates(config.arb.pairs)
    binance_rates = await binance_collector.get_all_rates(config.arb.pairs)
    return {
        "rates": [r.to_dict() for r in pacifica_rates + binance_rates],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/signals")
async def get_signals():
    """Get current active signals."""
    return {
        "signals": state["active_signals"],
        "last_scan": state["last_scan"],
    }


@router.post("/execute/{signal_id}")
async def execute_signal(signal_id: str):
    """Execute a specific signal."""
    # Find the signal
    target = None
    for item in state["active_signals"]:
        if item["signal"]["id"] == signal_id:
            target = item
            break

    if not target:
        return {"error": "Signal not found", "signal_id": signal_id}

    # Reconstruct signal and sizing objects for executor
    # (In production, store these as proper objects)
    from models import ArbSignal, Exchange
    from engine.position_sizer import SizeRecommendation

    sig_data = target["signal"]
    sig = ArbSignal(
        id=sig_data["id"],
        pair=sig_data["pair"],
        long_exchange=Exchange(sig_data["long_exchange"]),
        short_exchange=Exchange(sig_data["short_exchange"]),
        long_rate=sig_data["long_rate"],
        short_rate=sig_data["short_rate"],
        spread=sig_data["spread"],
        estimated_profit_8h=sig_data["estimated_profit_8h"],
        confidence=sig_data["confidence"],
    )

    sizing_data = target["sizing"]
    sizing = SizeRecommendation(
        signal_id=sizing_data["signal_id"],
        recommended_size_usd=sizing_data["recommended_size_usd"],
        max_size_usd=sizing_data["max_size_usd"],
        leverage=sizing_data["leverage"],
        kelly_fraction=sizing_data["kelly_fraction"],
        reasoning=sizing_data["reasoning"],
    )

    # Risk check
    risk = risk_mgr.pre_trade_check(
        sig, sizing.recommended_size_usd,
        state["total_capital"],
        executor.get_open_positions(),
    )

    if not risk.approved:
        return {"error": risk.reason, "risk_score": risk.risk_score}

    # Execute
    position = await executor.execute_signal(
        sig, sizing, auto_mode=state["auto_mode"]
    )
    return {"position": position.to_dict(), "risk": risk.reason}


@router.get("/positions")
async def get_positions(
    status: str = Query(None, description="Filter by status")
):
    """Get all positions, optionally filtered by status."""
    positions = executor.get_all_positions()
    if status:
        positions = [
            p for p in positions
            if p.status.value == status
        ]
    return {
        "positions": [p.to_dict() for p in positions],
        "total": len(positions),
    }


@router.post("/positions/{position_id}/close")
async def close_position(position_id: str):
    """Close an open position."""
    try:
        pos = await executor.close_position(position_id)
        return {"position": pos.to_dict()}
    except ValueError as e:
        return {"error": str(e)}


@router.get("/portfolio")
async def get_portfolio():
    """Get portfolio summary."""
    positions = executor.get_all_positions()
    open_pos = [p for p in positions if p.status == PositionStatus.OPEN]
    closed_pos = [p for p in positions if p.status == PositionStatus.CLOSED]

    total_pnl = sum(p.pnl_usd for p in positions)
    total_funding = sum(p.funding_collected for p in positions)
    total_exposure = sum(p.size_usd for p in open_pos)

    return {
        "total_capital": state["total_capital"],
        "total_pnl": round(total_pnl, 2),
        "total_funding_collected": round(total_funding, 2),
        "total_exposure": round(total_exposure, 2),
        "exposure_pct": round(
            total_exposure / state["total_capital"] * 100, 1
        ) if state["total_capital"] > 0 else 0,
        "open_positions": len(open_pos),
        "closed_positions": len(closed_pos),
        "win_rate": round(
            sum(1 for p in closed_pos if p.pnl_usd > 0)
            / max(len(closed_pos), 1) * 100, 1
        ),
        "auto_mode": state["auto_mode"],
    }


@router.post("/settings")
async def update_settings(
    capital: float = None,
    auto_mode: bool = None,
    min_spread: float = None,
):
    """Update runtime settings."""
    if capital is not None:
        state["total_capital"] = capital
    if auto_mode is not None:
        state["auto_mode"] = auto_mode
    if min_spread is not None:
        config.arb.min_spread_threshold = min_spread
    return {
        "total_capital": state["total_capital"],
        "auto_mode": state["auto_mode"],
        "min_spread": config.arb.min_spread_threshold,
    }


@router.get("/history")
async def get_history(limit: int = 100):
    """Get rate history and trade log."""
    return {
        "rate_history": scanner.get_rate_history(limit),
        "trade_log": executor.get_trade_log(limit),
    }


# ──────────────────────────────────────────────
# WebSocket for live updates
# ──────────────────────────────────────────────

connected_clients: set[WebSocket] = set()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket for live dashboard updates.
    Pushes scan results every 30 seconds.
    """
    await ws.accept()
    connected_clients.add(ws)

    try:
        while True:
            # Run scan
            try:
                pacifica_rates = await pacifica_collector.get_all_rates(
                    config.arb.pairs
                )
                binance_rates = await binance_collector.get_all_rates(
                    config.arb.pairs
                )
                all_rates = pacifica_rates + binance_rates
                signals = scanner.scan(all_rates)

                payload = {
                    "type": "scan_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "rates": [r.to_dict() for r in all_rates],
                    "signals": [s.to_dict() for s in signals],
                    "portfolio": {
                        "open_positions": len(executor.get_open_positions()),
                        "total_pnl": sum(
                            p.pnl_usd for p in executor.get_all_positions()
                        ),
                    },
                }
                await ws.send_text(json.dumps(payload))
            except Exception as e:
                logger.error(f"WS scan error: {e}")

            await asyncio.sleep(30)

    except WebSocketDisconnect:
        connected_clients.discard(ws)
