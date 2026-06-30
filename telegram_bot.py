"""
Trading Bot V6 Professional
telegram_bot.py

Telegram notification service.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

from models import Position


logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Handles all Telegram messages.
    """

    def __init__(
        self,
        token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
    ):

        self.chat_id = chat_id

        self.bot = Bot(token=token)

    async def send_message(
        self,
        message: str,
    ) -> bool:
        """
        Send Telegram message.
        """

        try:

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )

            return True

        except TelegramError as error:

            logger.error(
                "Telegram Error: %s",
                error,
            )

            return False

    def send(
        self,
        message: str,
    ) -> bool:
        """
        Sync wrapper.
        """

        return asyncio.run(
            self.send_message(message)
        )

    # ---------------------------------------------------------
    # Position Messages
    # ---------------------------------------------------------

    def format_open_position(
        self,
        position: Position,
    ) -> str:
        """
        Format newly opened position.
        """

        emoji = "🟢"

        if position.side.name == "SHORT":
            emoji = "🔴"

        return (
            f"{emoji} *NEW POSITION*\n\n"
            f"*Symbol:* `{position.symbol}`\n"
            f"*Side:* `{position.side.name}`\n"
            f"*Entry:* `{position.entry_price:.6f}`\n"
            f"*Take Profit:* `{position.take_profit:.6f}`\n"
            f"*Stop Loss:* `{position.stop_loss:.6f}`\n\n"
            f"*Market Score:* `{position.market_score}`\n"
            f"*Confidence:* `{position.confidence}%`\n"
            f"*Regime:* `{position.regime.name}`"
        )

    def notify_new_position(
        self,
        position: Position,
    ) -> bool:
        """
        Send open position notification.
        """

        return self.send(
            self.format_open_position(position)
        )

    def format_close_position(
        self,
        position: Position,
    ) -> str:
        """
        Format closed position.
        """

        pnl = position.pnl

        emoji = "🟢"

        if pnl < 0:
            emoji = "🔴"

        return (
            f"{emoji} *POSITION CLOSED*\n\n"
            f"*Symbol:* `{position.symbol}`\n"
            f"*Side:* `{position.side.name}`\n"
            f"*Entry:* `{position.entry_price:.6f}`\n"
            f"*Exit:* `{position.exit_price:.6f}`\n\n"
            f"*PnL:* `{pnl:.6f}`\n"
            f"*Reason:* `{position.close_reason}`"
        )

    def notify_closed_position(
        self,
        position: Position,
    ) -> bool:
        """
        Send close notification.
        """

        return self.send(
            self.format_close_position(position)
        )

    # ---------------------------------------------------------
    # Status Messages
    # ---------------------------------------------------------

    def format_status(
        self,
        strategy_summary: dict,
    ) -> str:
        """
        Format bot status.
        """

        return (
            "🤖 *BOT STATUS*\n\n"
            f"*Open Positions:* `{strategy_summary['open_positions']}`\n"
            f"*Total Positions:* `{strategy_summary['total_positions']}`\n"
            f"*Cooldowns:* `{strategy_summary['cooldowns']}`"
        )

    def notify_status(
        self,
        strategy_summary: dict,
    ) -> bool:

        return self.send(
            self.format_status(strategy_summary)
        )

    def format_positions(
        self,
        positions: list[Position],
    ) -> str:

        if not positions:

            return (
                "📭 *OPEN POSITIONS*\n\n"
                "_No open positions._"
            )

        lines = [
            "📊 *OPEN POSITIONS*",
            "",
        ]

        for position in positions:

            lines.extend([
                f"`{position.symbol}`",
                f"• {position.side.name}",
                f"• Entry: {position.entry_price:.6f}",
                f"• TP: {position.take_profit:.6f}",
                f"• SL: {position.stop_loss:.6f}",
                "",
            ])

        return "\n".join(lines)

    def notify_positions(
        self,
        positions: list[Position],
    ) -> bool:

        return self.send(
            self.format_positions(positions)
        )

    def notify_ping(self) -> bool:
        """
        Simple connectivity check.
        """

        return self.send(
            "✅ Bot is running."
        )

    # ---------------------------------------------------------
    # Error & Summary Messages
    # ---------------------------------------------------------

    def notify_error(
        self,
        title: str,
        error: str,
    ) -> bool:
        """
        Send error notification.
        """

        message = (
            "⚠️ *BOT ERROR*\n\n"
            f"*Module:* `{title}`\n"
            f"*Details:* `{error}`"
        )

        return self.send(message)

    def format_daily_summary(
        self,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
    ) -> str:
        """
        Daily trading summary.
        """

        if total_trades == 0:
            win_rate = 0.0
        else:
            win_rate = (
                wins / total_trades
            ) * 100

        return (
            "📈 *DAILY SUMMARY*\n\n"
            f"*Trades:* `{total_trades}`\n"
            f"*Wins:* `{wins}`\n"
            f"*Losses:* `{losses}`\n"
            f"*Win Rate:* `{win_rate:.1f}%`\n"
            f"*PnL:* `{total_pnl:.2f}`"
        )

    def notify_daily_summary(
        self,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
    ) -> bool:
        """
        Send daily summary.
        """

        return self.send(
            self.format_daily_summary(
                total_trades,
                wins,
                losses,
                total_pnl,
            )
        )

    def notify_startup(self) -> bool:
        """
        Bot startup message.
        """

        return self.send(
            "🚀 *Trading Bot V6 Professional started successfully.*"
        )

    def notify_shutdown(self) -> bool:
        """
        Bot shutdown message.
        """

        return self.send(
            "🛑 *Trading Bot V6 Professional stopped.*"
        )

    # ---------------------------------------------------------
    # Utility Messages
    # ---------------------------------------------------------

    def notify_info(
        self,
        message: str,
    ) -> bool:
        """
        Send general information message.
        """

        return self.send(
            f"ℹ️ {message}"
        )

    def notify_warning(
        self,
        message: str,
    ) -> bool:
        """
        Send warning message.
        """

        return self.send(
            f"⚠️ {message}"
        )

    def notify_success(
        self,
        message: str,
    ) -> bool:
        """
        Send success message.
        """

        return self.send(
            f"✅ {message}"
        )

    def notify_scan_started(
        self,
        symbol_count: int,
    ) -> bool:
        """
        Scan started.
        """

        return self.send(
            f"🔍 Market scan started.\n\n"
            f"Symbols: `{symbol_count}`"
        )

    def notify_scan_finished(
        self,
        scanned: int,
        opened: int,
    ) -> bool:
        """
        Scan completed.
        """

        return self.send(
            f"🏁 Market scan completed.\n\n"
            f"Scanned: `{scanned}`\n"
            f"Opened: `{opened}`"
        )


__all__ = [
    "TelegramNotifier",
]
