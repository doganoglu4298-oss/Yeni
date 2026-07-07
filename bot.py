"""
bot.py
======
Regime Based Multi-Strategy Trading Bot

Bot, piyasa rejimine göre 3 farklı strateji çalıştırır:

1. SIDEWAYS   → Neutral Grid Stratejisi
2. TRENDING   → Trend Takip Stratejisi (basit EMA)
3. HIGH_VOL   → Muhafazakâr Mod (risk alma, bekle)

Bu yapı sayesinde her piyasa koşulunda en uygun strateji otomatik seçilir.
"""

import time
import logging
from datetime import datetime
from typing import Optional

from config import Config
from data import DataFetcher
from grid_strategy import GridStrategy
from risk_manager import RiskManager
from indicators import get_market_regime, calculate_ema, calculate_atr

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class RegimeBasedBot:
    def __init__(self, config: Config):
        self.config = config
        self.data = DataFetcher(config)
        self.grid_strategy = GridStrategy(config)
        self.risk = RiskManager(config)
        self.running = False

    # ============================================================
    # 1. SIDEWAYS STRATEJİSİ (Grid)
    # ============================================================
    def run_sideways_strategy(self, df, current_price):
        logger.info(">>> SIDEWAYS modu aktif → Grid stratejisi çalışıyor")

        if not self.grid_strategy.grid_levels:
            self.grid_strategy.calculate_grid_levels(current_price)

        # Dinamik grid güncelleme
        if self.config.grid.dynamic_grid:
            self.grid_strategy.calculate_dynamic_grid_range(
                df, self.config.grid.dynamic_range_lookback_hours
            )
            self.grid_strategy.calculate_grid_levels(current_price)

        desired_orders = self.grid_strategy.generate_desired_orders(current_price)

        if self.config.dry_run:
            logger.info(f"[DRY RUN] {len(desired_orders)} grid emri üretildi")
        else:
            # TODO: Gerçek emir gönderme
            pass

    # ============================================================
    # 2. TRENDING STRATEJİSİ (Geliştirilmiş - EMA + ATR mantığı)
    # ============================================================
    def run_trending_strategy(self, df, current_price):
        logger.info(">>> TRENDING modu aktif → Trend takip stratejisi")

        ema7 = calculate_ema(df, 7).iloc[-1]
        ema25 = calculate_ema(df, 25).iloc[-1]

        # ATR ile volatilite ölçümü (basit trailing stop için)
        atr = calculate_atr(df, period=14).iloc[-1]

        if ema7 > ema25:
            direction = "LONG"
            suggested_stop = current_price - (atr * 1.5)
        else:
            direction = "SHORT"
            suggested_stop = current_price + (atr * 1.5)

        logger.info(
            f"Trend yönü: {direction} | EMA7={ema7:.2f} | EMA25={ema25:.2f} | "
            f"ATR={atr:.2f} | Önerilen Stop ≈ {suggested_stop:.2f}"
        )

        if self.config.dry_run:
            logger.info(f"[DRY RUN] {direction} trend emri simüle edildi (ATR Stop aktif)")
        else:
            # TODO: Gerçek emir + ATR trailing stop
            pass

    # ============================================================
    # 3. HIGH VOL / BELİRSİZ MOD
    # ============================================================
    def run_conservative_strategy(self, df, current_price):
        logger.info(">>> HIGH_VOL modu aktif → Muhafazakâr mod (pozisyon alınmıyor)")
        # Bu modda genellikle hiçbir işlem yapılmaz veya çok küçük pozisyonlar açılır
        pass

    # ============================================================
    # ANA DÖNGÜ
    # ============================================================
    def run(self):
        self.running = True
        logger.info("Regime Based Bot başlatıldı...")

        # Telegram başlangıç mesajı (test için)
        if hasattr(self, 'telegram') and self.config.telegram.enabled:
            try:
                self.telegram.send_message(
                    "✅ <b>Bot Başlatıldı</b>\n"
                    f"Symbol: <b>{self.config.symbol.symbol}</b>\n"
                    f"Mode: {'Paper (Dry Run)' if self.config.dry_run else 'Live'}"
                )
            except Exception as e:
                logger.error(f"Telegram başlangıç mesajı gönderilemedi: {e}")

        try:
            while self.running:
                loop_start = time.time()

                # Veri çek
                df = self.data.fetch_recent_data(lookback_minutes=300)
                current_price = self.data.get_current_price()
                balance = self.data.get_account_balance()

                # Rejim tespiti
                regime_info = get_market_regime(df, self.config.regime.__dict__)
                regime = regime_info["regime"]

                logger.info(f"Piyasa Rejimi: {regime} | {regime_info['reason']}")

                # Rejime göre strateji seç
                if regime == "SIDEWAYS":
                    self.run_sideways_strategy(df, current_price)
                elif regime == "TRENDING":
                    self.run_trending_strategy(df, current_price)
                else:
                    self.run_conservative_strategy(df, current_price)

                # Risk kontrolü (basit)
                should_pause, reason = self.risk.should_pause_trading(
                    current_price=current_price,
                    current_exposure=0.0,
                    current_funding_rate=0.0,
                    current_balance=balance
                )
                if should_pause:
                    logger.warning(f"TRADING DURAKLATILDI → {reason}")

                self._sleep(loop_start)

        except KeyboardInterrupt:
            logger.info("Bot kullanıcı tarafından durduruldu.")
        finally:
            self.running = False

    def _sleep(self, loop_start):
        elapsed = time.time() - loop_start
        sleep_time = max(0, self.config.data.update_interval_seconds - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    cfg = Config()
    bot = RegimeBasedBot(cfg)
    bot.run()
