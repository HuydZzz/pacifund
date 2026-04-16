"""
Notification System
Sends alerts when high-value signals or important events occur.

Supports multiple channels:
- In-app toast notifications (via WebSocket)
- Telegram bot alerts
- Email (via SMTP)
- Discord webhooks

Used for notifying users about:
- New signals above a threshold
- Position executions
- Stop-loss / take-profit triggers
- Risk warnings
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class NotifChannel(str, Enum):
    IN_APP = "in_app"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"


class NotifLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Notification:
    """A notification to be sent."""
    title: str
    message: str
    level: NotifLevel = NotifLevel.INFO
    channels: list = None
    metadata: dict = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.channels is None:
            self.channels = [NotifChannel.IN_APP]
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class NotificationService:
    """
    Central hub for all notifications.
    Maintains a queue and dispatches to configured channels.
    """

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook: Optional[str] = None,
    ):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.discord_webhook = discord_webhook
        self._queue: list[Notification] = []
        self._ws_callbacks: list[Callable] = []

    def register_ws_callback(self, callback: Callable):
        """Register a callback for WebSocket broadcast."""
        self._ws_callbacks.append(callback)

    async def send(self, notif: Notification):
        """Send notification to all configured channels."""
        self._queue.append(notif)
        if len(self._queue) > 100:
            self._queue = self._queue[-100:]

        tasks = []
        for ch in notif.channels:
            if ch == NotifChannel.IN_APP:
                await self._send_in_app(notif)
            elif ch == NotifChannel.TELEGRAM and self.telegram_token:
                tasks.append(self._send_telegram(notif))
            elif ch == NotifChannel.DISCORD and self.discord_webhook:
                tasks.append(self._send_discord(notif))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_in_app(self, notif: Notification):
        """Broadcast via registered WebSocket callbacks."""
        for callback in self._ws_callbacks:
            try:
                await callback(notif.to_dict())
            except Exception as e:
                logger.warning(f"In-app notification failed: {e}")

    async def _send_telegram(self, notif: Notification):
        """Send via Telegram bot."""
        emoji = {
            NotifLevel.INFO: "ℹ️",
            NotifLevel.SUCCESS: "✅",
            NotifLevel.WARNING: "⚠️",
            NotifLevel.CRITICAL: "🚨",
        }[notif.level]

        text = f"{emoji} *{notif.title}*\n\n{notif.message}"

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                await client.post(url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")

    async def _send_discord(self, notif: Notification):
        """Send via Discord webhook."""
        color = {
            NotifLevel.INFO: 0x5b8def,
            NotifLevel.SUCCESS: 0x00d68f,
            NotifLevel.WARNING: 0xffb84d,
            NotifLevel.CRITICAL: 0xff6b6b,
        }[notif.level]

        payload = {
            "embeds": [{
                "title": notif.title,
                "description": notif.message,
                "color": color,
                "timestamp": notif.timestamp.isoformat(),
            }]
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                await client.post(self.discord_webhook, json=payload)
            except Exception as e:
                logger.error(f"Discord send failed: {e}")

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Return recent notifications for the UI."""
        return [n.to_dict() for n in self._queue[-limit:]]


# ─── Pre-built notification templates ─────────────────────────

def signal_detected(pair: str, spread: float, apy: float) -> Notification:
    """Template: new high-value signal detected."""
    return Notification(
        title=f"🔔 New signal: {pair}",
        message=(
            f"Spread detected: {spread * 100:.4f}% per 8h\n"
            f"Annualized yield: {apy * 100:.1f}%\n"
            f"Consider executing this opportunity."
        ),
        level=NotifLevel.INFO,
        metadata={"pair": pair, "spread": spread, "apy": apy},
    )


def position_opened(pair: str, size_usd: float, spread: float) -> Notification:
    """Template: position executed."""
    return Notification(
        title=f"⚡ Position opened: {pair}",
        message=(
            f"Size: ${size_usd:,.0f}\n"
            f"Entry spread: {spread * 100:.4f}%\n"
            f"Status: delta-neutral on Pacifica"
        ),
        level=NotifLevel.SUCCESS,
        metadata={"pair": pair, "size": size_usd, "spread": spread},
    )


def stop_loss_triggered(pair: str, loss_usd: float) -> Notification:
    """Template: stop-loss hit."""
    return Notification(
        title=f"🛑 Stop-loss triggered: {pair}",
        message=(
            f"Position closed at loss: -${abs(loss_usd):,.2f}\n"
            f"Risk manager activated to protect capital."
        ),
        level=NotifLevel.WARNING,
        metadata={"pair": pair, "loss": loss_usd},
    )


def take_profit_hit(pair: str, profit_usd: float) -> Notification:
    """Template: take-profit hit."""
    return Notification(
        title=f"🎯 Take-profit hit: {pair}",
        message=(
            f"Position closed in profit: +${profit_usd:,.2f}\n"
            f"Strategy performing as expected."
        ),
        level=NotifLevel.SUCCESS,
        metadata={"pair": pair, "profit": profit_usd},
    )


def risk_warning(reason: str) -> Notification:
    """Template: risk threshold exceeded."""
    return Notification(
        title="⚠️ Risk warning",
        message=reason,
        level=NotifLevel.WARNING,
    )
