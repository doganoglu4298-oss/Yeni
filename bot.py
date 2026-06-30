"""
Trading Bot V6 Professional
bot.py

Main application entry point.
"""

from __future__ import annotations
import logging
import signal
import sys
import time
import math
from datetime import datetime, timezone

# config.py dosyasından gerekli ayarların geldiği varsayılmıştır.
from config import (
    SYMBOLS,
    SCAN_INTERVAL,
    TIMEFRAME,
)

# strategy.py ve telegram_bot.py dosyalarının mevcut olduğu varsayılmıştır.
from strategy import Strategy
from telegram_bot import TelegramNotifier

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Trading Bot
# ---------------------------------------------------------

class TradingBot:

    def __init__(self):
        self.strategy = Strategy()
        self.telegram = TelegramNotifier()
        self.running = True
        self.symbols = SYMBOLS.copy()

    def stop(self, *_) -> None:
        logger.info("Stopping bot...")
        self.running = False

    def startup(self) -> None:
        logger.info("Trading Bot V6 started.")
        self.telegram.notify_startup()

    def shutdown(self) -> None:
        logger.info("Trading Bot stopped.")
        self.telegram.notify_shutdown()

    def install_signal_handlers(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    # ---------------------------------------------------------
    # Startup Validation
    # ---------------------------------------------------------
    def validate_configuration(self) -> None:
        if not self.symbols:
            raise RuntimeError("SYMBOLS list is empty.")
        if SCAN_INTERVAL <= 0:
            raise RuntimeError("SCAN_INTERVAL must be greater than zero.")

    def validate_market_data(self) -> None:
        for symbol in self.symbols:
            if not self.strategy.data.client.has_enough_data(symbol):
                logger.warning("Skipping %s (insufficient data).", symbol)

    def startup_checks(self) -> None:
        logger.info("Running startup checks...")
        self.validate_configuration()
        self.validate_market_data()
        try:
            self.telegram.notify_info("Startup checks completed successfully.")
        except Exception:
            logger.warning("Telegram notification unavailable.")

    def print_summary(self) -> None:
        summary = self.strategy.summary()
        logger.info(
            "Open=%s Total=%s Cooldowns=%s",
            summary["open_positions"],
            summary["total_positions"],
            summary["cooldowns"],
        )

    # ---------------------------------------------------------
    # Market Scan
    # ---------------------------------------------------------
    def scan_market(self) -> None:
        logger.info("Scanning %s symbols...", len(self.symbols))
        self.telegram.notify_scan_started(len(self.symbols))
        try:
            new_positions = self.strategy.run(self.symbols)
            for position in new_positions:
                logger.info("[OPEN] %s %s", position.symbol, position.side.name)
                self.telegram.notify_new_position(position)

            for position in self.strategy.positions:
                if not position.is_open and not getattr(position, "notification_sent", False):
                    self.telegram.notify_closed_position(position)
                    self.strategy.finalize_position(position)
                    position.notification_sent = True

            self.telegram.notify_scan_finished(scanned=len(self.symbols), opened=len(new_positions))
        except Exception as error:
            logger.exception("Market scan failed.")
            self.telegram.notify_error("scan_market", str(error))

    # ---------------------------------------------------------
    # Candle Close Scheduler
    # ---------------------------------------------------------
    def seconds_until_next_candle(self) -> int:
        now = datetime.now(timezone.utc)
        timeframe_map = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400}
        interval = timeframe_map.get(TIMEFRAME, 900)
        current_ts = now.timestamp()
        next_close = (math.floor(current_ts / interval) + 1) * interval
        wait_seconds = int(next_close - current_ts)
        return max(wait_seconds + 2, 2)

    def wait_for_next_candle(self) -> None:
        wait_time = self.seconds_until_next_candle()
        logger.info("Waiting %s seconds for candle close...", wait_time)
        while self.running and wait_time > 0:
            sleep = min(wait_time, 5)
            time.sleep(sleep)
            wait_time -= sleep

    # ---------------------------------------------------------
    # Main Loop
    # ---------------------------------------------------------
    def run_forever(self) -> None:
        self.install_signal_handlers()
        
        self.startup()
        self.startup_checks() 
        
        logger.info("Watching %s symbols.", len(self.symbols))

        while self.running:
            try:
                self.scan_market()
                self.print_summary()
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received.")
                self.running = False
            except Exception as error:
                logger.exception("Unexpected error.")
                self.telegram.notify_error("run_forever", str(error))

            if self.running:
                self.wait_for_next_candle()

        self.shutdown()

# ---------------------------------------------------------
# Main Entry
# ---------------------------------------------------------
def main() -> int:
    bot = TradingBot()
    try:
        bot.run_forever()
        return 0
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user.")
        return 0
    except Exception as error:
        logger.exception("Fatal application error.")
        try:
            bot.telegram.notify_error("Fatal Error", str(error))
        except Exception:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
