"""
Pacifica Executor
Places and manages trades on Pacifica.
Integrates with the Pacifica Python SDK for order execution.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx

from config import PacificaConfig
from engine.position_sizer import SizeRecommendation
from models import (
    ArbSignal,
    Exchange,
    Position,
    PositionStatus,
)

logger = logging.getLogger(__name__)


class PacificaExecutor:
    """
    Executes trades on Pacifica and manages open positions.

    Two modes:
    - Manual: generates trade plan for user to confirm
    - Auto: executes immediately (with risk checks pre-applied)

    Uses Pacifica REST API. When SDK is available, swap the
    _place_order internals with SDK calls.
    """

    def __init__(self, config: PacificaConfig):
        self.config = config
        self._positions: dict[str, Position] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._trade_log: list[dict] = []

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.config.active_url,
                headers=headers,
                timeout=15.0,
            )
        return self._client

    async def execute_signal(
        self,
        signal: ArbSignal,
        sizing: SizeRecommendation,
        auto_mode: bool = False,
    ) -> Position:
        """
        Execute a trade based on a signal and sizing recommendation.

        Creates a Position object, places orders on Pacifica side,
        and returns the position for tracking.
        """
        position = Position(
            id=f"pos_{uuid.uuid4().hex[:8]}",
            signal_id=signal.id,
            pair=signal.pair,
            long_exchange=signal.long_exchange,
            short_exchange=signal.short_exchange,
            size_usd=sizing.recommended_size_usd,
            entry_spread=signal.spread,
        )

        if not auto_mode:
            # Manual mode: return position as PENDING for user to confirm
            position.status = PositionStatus.PENDING
            self._positions[position.id] = position
            self._log_trade("SIGNAL_PENDING", position, signal)
            return position

        # Auto mode: execute immediately
        try:
            # Determine which side is on Pacifica
            if signal.long_exchange == Exchange.PACIFICA:
                side = "buy"
            elif signal.short_exchange == Exchange.PACIFICA:
                side = "sell"
            else:
                raise ValueError("Pacifica must be on one side of the trade")

            # Place market order on Pacifica
            order_result = await self._place_order(
                pair=signal.pair,
                side=side,
                size_usd=sizing.recommended_size_usd,
                leverage=sizing.leverage,
            )

            if order_result.get("success"):
                position.status = PositionStatus.OPEN
                self._log_trade("POSITION_OPENED", position, signal)
            else:
                position.status = PositionStatus.FAILED
                self._log_trade(
                    "POSITION_FAILED",
                    position,
                    signal,
                    error=order_result.get("error"),
                )

        except Exception as e:
            logger.error(f"Execution failed for {position.id}: {e}")
            position.status = PositionStatus.FAILED
            self._log_trade("POSITION_FAILED", position, signal, error=str(e))

        self._positions[position.id] = position
        return position

    async def confirm_position(self, position_id: str) -> Position:
        """Confirm a PENDING position (manual mode)."""
        pos = self._positions.get(position_id)
        if not pos or pos.status != PositionStatus.PENDING:
            raise ValueError(f"Position {position_id} not found or not pending")

        # Execute the trade
        side = (
            "buy"
            if pos.long_exchange == Exchange.PACIFICA
            else "sell"
        )

        try:
            result = await self._place_order(
                pair=pos.pair,
                side=side,
                size_usd=pos.size_usd,
                leverage=1.0,
            )
            if result.get("success"):
                pos.status = PositionStatus.OPEN
            else:
                pos.status = PositionStatus.FAILED
        except Exception as e:
            logger.error(f"Confirm failed for {position_id}: {e}")
            pos.status = PositionStatus.FAILED

        return pos

    async def close_position(self, position_id: str) -> Position:
        """Close an open position."""
        pos = self._positions.get(position_id)
        if not pos or pos.status != PositionStatus.OPEN:
            raise ValueError(f"Position {position_id} not found or not open")

        try:
            # Close = place opposite order
            side = (
                "sell"
                if pos.long_exchange == Exchange.PACIFICA
                else "buy"
            )
            result = await self._place_order(
                pair=pos.pair,
                side=side,
                size_usd=pos.size_usd,
                leverage=1.0,
            )
            if result.get("success"):
                pos.status = PositionStatus.CLOSED
                pos.closed_at = datetime.utcnow()
        except Exception as e:
            logger.error(f"Close failed for {position_id}: {e}")

        return pos

    async def _place_order(
        self,
        pair: str,
        side: str,
        size_usd: float,
        leverage: float = 1.0,
    ) -> dict:
        """
        Place a market order on Pacifica.

        This is the integration point with Pacifica's API/SDK.
        Replace the internals with actual SDK calls:

            from pacifica_sdk import PacificaClient
            client = PacificaClient(api_key=self.config.api_key)
            order = client.place_order(
                pair=pair, side=side, size=size_usd, leverage=leverage
            )
        """
        client = await self._get_client()

        try:
            resp = await client.post(
                "/v1/orders",
                json={
                    "pair": pair,
                    "side": side,
                    "type": "market",
                    "size": size_usd,
                    "leverage": leverage,
                },
            )
            data = resp.json()
            return {
                "success": resp.status_code == 200,
                "order_id": data.get("order_id"),
                "filled_price": data.get("filled_price"),
                "error": data.get("error"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_position(self, position_id: str) -> Optional[Position]:
        return self._positions.get(position_id)

    def get_open_positions(self) -> list[Position]:
        return [
            p for p in self._positions.values()
            if p.status == PositionStatus.OPEN
        ]

    def get_all_positions(self) -> list[Position]:
        return list(self._positions.values())

    def get_trade_log(self, limit: int = 50) -> list[dict]:
        return self._trade_log[-limit:]

    def _log_trade(
        self,
        event: str,
        position: Position,
        signal: ArbSignal,
        error: str | None = None,
    ):
        entry = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "position_id": position.id,
            "signal_id": signal.id,
            "pair": signal.pair,
            "spread": signal.spread,
            "size_usd": position.size_usd,
        }
        if error:
            entry["error"] = error
        self._trade_log.append(entry)
        logger.info(f"Trade event: {event} | {position.id} | {signal.pair}")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
