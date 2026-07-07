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
try:
    from telegram_bot import TelegramNotifier
except ImportError:
    TelegramNotifier = None

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
        self.passive_grid_counter = 0

        # Telegram entegrasyonu
        try:
            from telegram_bot import TelegramNotifier
            self.telegram = TelegramNotifier(config)
        except Exception as e:
            logger.warning(f"TelegramNotifier yüklenemedi: {e}")
            self.telegram = None

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

        # === Açık Emir Kontrolü ===
        open_orders = []
        try:
            open_orders = self.data.exchange.fetch_open_orders(self.config.symbol.symbol)
            open_order_count = len(open_orders)
        except Exception as e:
            logger.warning(f"Açık emirler çekilemedi: {e}")
            open_order_count = 0

        max_orders = self.config.grid.max_open_orders

        if open_order_count >= max_orders:
            logger.info(f"Açık emir limiti dolu ({open_order_count}/{max_orders}). Yeni emir üretilmiyor.")
            return

        desired_orders = self.grid_strategy.generate_desired_orders(current_price)

        # Aynı fiyatta zaten açık emir varsa filtrele (basit kontrol)
        existing_prices = {float(o['price']) for o in open_orders} if open_orders else set()
        filtered_orders = [o for o in desired_orders if o['price'] not in existing_prices]

        if self.config.dry_run:
            logger.info(f"[DRY RUN] {len(filtered_orders)} grid emri üretildi (Açık emir: {open_order_count}/{max_orders})")

            # Telegram: Grid aktif olduğunda bildir
            if len(filtered_orders) > 0 and open_order_count == 0:
                if self.telegram and self.config.telegram.enabled:
                    self.telegram.send_message(
                        f"📈 <b>Grid Aktif Oldu</b>\n"
                        f"{len(filtered_orders)} emir üretildi"
                    )
        else:
            # TODO: Gerçek emir gönderme + duplicate kontrolü
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

        try:
            while self.running:
                loop_start = time.time()

                # Veri çek
                df = self.data.fetch_recent_data(lookback_minutes=300)
                current_price = self.data.get_current_price()
                balance = self.data.get_account_balance()

                # Rejim tespiti + Koruma (whipsaw önleme)
                new_regime_info = get_market_regime(df, self.config.regime.__dict__)
                new_regime = new_regime_info["regime"]

                if not hasattr(self, 'current_regime'):
                    self.current_regime = new_regime
                    self.last_regime_change_time = time.time()

                time_since_change = time.time() - self.last_regime_change_time
                min_duration = self.config.grid.min_regime_duration_minutes * 60

                if new_regime != self.current_regime and time_since_change < min_duration:
                    regime = self.current_regime
                    remaining = int((min_duration - time_since_change) / 60)
                    logger.info(f"Rejim değişikliği engellendi (koruma aktif). Kalan: {remaining} dk")
                else:
                    if new_regime != self.current_regime:
                        old = self.current_regime
                        self.current_regime = new_regime
                        self.last_regime_change_time = time.time()
                        logger.info(f"Rejim değişti: {old} → {new_regime}")

                        # Rejim değiştiğinde akıllı pozisyon yönetimi
                        try:
                            # 1. Önce tüm açık limit emirlerini iptal et
                            self.data.exchange.cancel_all_orders(self.config.symbol.symbol)
                            logger.info("Tüm açık limit emirleri iptal edildi")

                            # 2. Açık pozisyonları kontrol et (zararına kapatma)
                            positions = self.data.exchange.fetch_positions([self.config.symbol.symbol])
                            for pos in positions:
                                if float(pos.get('contracts', 0)) == 0:
                                    continue

                                unrealized_pnl = float(pos.get('unrealizedPnl', 0))

                                if unrealized_pnl >= 0:
                                    # Kârda veya başabaş → pozisyonu kapat
                                    side = 'sell' if pos['side'] == 'long' else 'buy'
                                    self.data.exchange.create_order(
                                        symbol=self.config.symbol.symbol,
                                        type='market',
                                        side=side,
                                        amount=abs(float(pos['contracts']))
                                    )
                                    logger.info(f"Pozisyon kârda/başabaş kapatıldı (PnL: {unrealized_pnl})")
                                else:
                                    # Zararda → zararına kapatma, koruyucu stop koy
                                    logger.info(f"Pozisyon zararda ({unrealized_pnl}). Zararına kapatılmadı, koruyucu stop aktif.")
                                    # TODO: Break-even stop-loss emri eklenebilir

                            if self.telegram and self.config.telegram.enabled:
                                self.telegram.send_message("Rejim değişti → Akıllı pozisyon yönetimi uygulandı")

                        except Exception as e:
                            logger.error(f"Rejim değişikliği pozisyon yönetimi hatası: {e}")
                    regime = self.current_regime

                logger.info(f"Piyasa Rejimi: {regime} | {new_regime_info['reason']}")

                # Rejime göre strateji seç
                if regime == "SIDEWAYS":
                    self.run_sideways_strategy(df, current_price)
                    self.passive_grid_counter = 0
                elif regime == "TRENDING":
                    self.run_trending_strategy(df, current_price)
                    self.passive_grid_counter += 1

                    # Grid uzun süre pasif kaldıysa bildir
                    if self.passive_grid_counter >= 30:  # ~30 döngü ≈ 4-5 dakika
                        if self.telegram and self.config.telegram.enabled:
                            self.telegram.send_message(
                                f"⚠️ <b>Grid Pasif</b>\n"
                                f"Grid {self.passive_grid_counter} döngüdür pasif.\n"
                                f"Piyasa trendli görünüyor."
                            )
                        self.passive_grid_counter = 0  # Reset
                else:
                    self.run_conservative_strategy(df, current_price)
                    self.passive_grid_counter += 1

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