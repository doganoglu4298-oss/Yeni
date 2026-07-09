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
        self.last_order_update_time = 0
        # Geliştirilmiş State Tracking
        # price -> {
        #   "side": "BUY" / "SELL",
        #   "size": float,
        #   "status": "open" / "filled",
        #   "entry_price": float,
        #   "target_price": float (opsiyonel)
        # }
        self.active_grid_levels = {}
        self.last_daily_summary_date = None  # Son günlük özet tarihi

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

        # Eğer aktif grid seviyesi varsa, agresif yeniden hesaplama yapma
        if len(self.active_grid_levels) > 0:
            logger.info("Yönetim modu aktif → Mevcut seviyeler takip ediliyor (agresif tarama kapalı)")

            # Basit trailing mantığı (fiyat hareketini takip et)
            for level_price, info in list(self.active_grid_levels.items()):
                if info["status"] == "filled":
                    # Fiyat entry fiyatının lehine hareket ettiyse trailing fırsatı
                    if info["side"] == "BUY" and current_price > info["entry_price"]:
                        trailing_distance = current_price - info["entry_price"]
                        logger.info(f"Trailing fırsatı (BUY): +{trailing_distance:.2f} USDT")
                    elif info["side"] == "SELL" and current_price < info["entry_price"]:
                        trailing_distance = info["entry_price"] - current_price
                        logger.info(f"Trailing fırsatı (SELL): +{trailing_distance:.2f} USDT")

            return

        if not self.grid_strategy.grid_levels:
            self.grid_strategy.calculate_grid_levels(current_price)

        # Dinamik grid güncelleme (sadece aktif seviye yoksa)
        if self.config.grid.dynamic_grid and len(self.active_grid_levels) == 0:
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

        # === Emir Güncelleme Sıklığı Kontrolü (60 saniye) ===
        current_time = time.time()
        if current_time - self.last_order_update_time < 60:
            return

        desired_orders = self.grid_strategy.generate_desired_orders(current_price)

        # Fiyat toleransı ile filtreleme
        price_tolerance = 0.0005
        filtered_orders = []
        existing_prices = [float(o['price']) for o in open_orders] if open_orders else []

        for order in desired_orders:
            too_close = False
            for existing_price in existing_prices:
                if abs(order['price'] - existing_price) / existing_price < price_tolerance:
                    too_close = True
                    break
            if not too_close:
                filtered_orders.append(order)

        self.last_order_update_time = current_time

        if self.config.dry_run:
            logger.info(f"[DRY RUN] {len(filtered_orders)} grid emri üretildi (Açık emir: {open_order_count}/{max_orders})")

            if len(filtered_orders) > 0 and open_order_count == 0:
                if self.telegram and self.config.telegram.enabled:
                    self.telegram.send_message(
                        f"📈 <b>Grid Aktif Oldu</b>\n"
                        f"{len(filtered_orders)} emir üretildi"
                    )
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

                        # Rejim değiştiğinde akıllı pozisyon yönetimi + state temizliği
                        try:
                            self.data.exchange.cancel_all_orders(self.config.symbol.symbol)
                            logger.info("Tüm açık limit emirleri iptal edildi")

                            # State temizliği
                            self.active_grid_levels.clear()

                            positions = self.data.exchange.fetch_positions([self.config.symbol.symbol])
                            for pos in positions:
                                if float(pos.get('contracts', 0)) == 0:
                                    continue

                                unrealized_pnl = float(pos.get('unrealizedPnl', 0))

                                if unrealized_pnl >= 0:
                                    side = 'sell' if pos['side'] == 'long' else 'buy'
                                    self.data.exchange.create_order(
                                        symbol=self.config.symbol.symbol,
                                        type='market',
                                        side=side,
                                        amount=abs(float(pos['contracts']))
                                    )
                                    logger.info(f"Pozisyon kârda/başabaş kapatıldı (PnL: {unrealized_pnl})")
                                else:
                                    logger.info(f"Pozisyon zararda ({unrealized_pnl}). Zararına kapatılmadı.")

                            if self.telegram and self.config.telegram.enabled:
                                self.telegram.send_message("Rejim değişti → Pozisyonlar yönetildi + State temizlendi")

                        except Exception as e:
                            logger.error(f"Rejim değişikliği pozisyon yönetimi hatası: {e}")
                    regime = self.current_regime

                logger.info(f"Piyasa Rejimi: {regime} | {new_regime_info['reason']}")

                # === Günlük Özet (23:15 civarı) ===
                now = datetime.now()
                if now.hour == 23 and now.minute >= 15 and now.minute <= 20:
                    if self.last_daily_summary_date != now.date():
                        try:
                            today_trades = [t for t in self.trades if hasattr(t, 'get') and t.get('timestamp') and t['timestamp'].date() == now.date()]
                            today_pnl = sum(t.get('pnl', 0) for t in today_trades)
                            msg = (
                                f"📊 <b>Günlük Özet</b> ({now.strftime('%d.%m.%Y')})\n"
                                f"Toplam İşlem: {len(today_trades)}\n"
                                f"Günlük PnL: {today_pnl:.2f} USDT\n"
                                f"Güncel Equity: {self.current_equity:.2f} USDT"
                            )
                            if self.telegram and self.config.telegram.enabled:
                                self.telegram.send_message(msg)
                            self.last_daily_summary_date = now.date()
                            logger.info("Günlük özet gönderildi.")
                        except Exception as e:
                            logger.error(f"Günlük özet hatası: {e}")

                # Rejime göre strateji seç
                if regime == "SIDEWAYS":
                    self.run_sideways_strategy(df, current_price)
                    self.passive_grid_counter = 0
                elif regime == "TRENDING":
                    self.run_trending_strategy(df, current_price)
                    self.passive_grid_counter += 1

                    # Grid uzun süre pasif kaldıysa bildir
                    if self.passive_grid_counter >= 30:
                        if self.telegram and self.config.telegram.enabled:
                            self.telegram.send_message(
                                f"⚠️ <b>Grid Pasif</b>\n"
                                f"Grid {self.passive_grid_counter} döngüdür pasif.\n"
                                f"Piyasa trendli görünüyor."
                            )
                        self.passive_grid_counter = 0
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