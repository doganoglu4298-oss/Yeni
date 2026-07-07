"""
bot.py
======
Vadeli Grid Trading Bot - Ana Çalışma Dosyası

Bu dosya tüm modülleri bir araya getirir ve ana trading döngüsünü çalıştırır.

Şu anda:
- Paper trading / dry_run modunda güvenli test yapılabilir
- Live moda geçmek için config'den dry_run=False yapılmalı

Gelecek geliştirmeler:
- Gerçek emir gönderme (ccxt ile)
- Open orders takibi
- Pozisyon güncelleme
- Telegram entegrasyonu
"""

import time
import logging
from datetime import datetime
from typing import Optional

from config import Config
from data import DataFetcher
from grid_strategy import GridStrategy
from risk_manager import RiskManager
from indicators import get_market_regime

# Loglama ayarı
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GridBot:
    """
    Ana Grid Trading Bot Sınıfı
    """

    def __init__(self, config: Config):
        self.config = config
        self.symbol = config.symbol.symbol

        # Modüller
        self.data = DataFetcher(config)
        self.strategy = GridStrategy(config)
        self.risk = RiskManager(config)

        self.running = False
        self.last_loop_time = 0

        logger.info(f"GridBot başlatıldı → {self.symbol} | Mode: {config.mode} | DryRun: {config.dry_run}")

    # =====================================================================
    # ANA DÖNGÜ
    # =====================================================================
    
    def run(self):
        """Ana trading döngüsü"""
        self.running = True
        logger.info("Bot çalışıyor... (Ctrl+C ile durdur)")

        try:
            while self.running:
                loop_start = time.time()

                # 1. Veri çek
                df = self.data.fetch_recent_data(lookback_minutes=300)
                current_price = self.data.get_current_price()
                funding_rate = self.data.get_funding_rate()
                balance = self.data.get_account_balance()

                # 2. Grid seviyelerini ilk seferde veya gerektiğinde hesapla
                if not self.strategy.grid_levels:
                    self.strategy.calculate_grid_levels(current_price)
                    self.risk.update_grid_range(
                        self.strategy.upper_price, 
                        self.strategy.lower_price
                    )

                # 3. Piyasa rejimi kontrolü
                regime = get_market_regime(df, config=self.config.regime.__dict__)
                is_sideways = regime["is_sideways"]

                # 4. Grid aktif olmalı mı?
                grid_active, grid_reason = self.strategy.should_grid_be_active(df)

                # 5. Risk kontrolü
                current_exposure = 0.0  # TODO: Gerçek pozisyon takibi eklenecek
                should_pause, risk_reason = self.risk.should_pause_trading(
                    current_price=current_price,
                    current_exposure=current_exposure,
                    current_funding_rate=funding_rate,
                    current_balance=balance
                )

                # 6. Karar ve Aksiyon
                if should_pause:
                    logger.warning(f"TRADING DURAKLATILDI → {risk_reason}")
                    self._sleep()
                    continue

                if not grid_active:
                    logger.info(f"Grid pasif → {grid_reason}")
                    self._sleep()
                    continue

                # Grid aktif ve risk temiz → Emir üret
                desired_orders = self.strategy.generate_desired_orders(current_price)

                if self.config.dry_run:
                    self._log_dry_run_actions(desired_orders, current_price, regime)
                else:
                    # TODO: Gerçek emir gönderme burada olacak
                    logger.info(f"Gerçek emir gönderilecek (henüz implement edilmedi). Emir sayısı: {len(desired_orders)}")

                # 7. Durum logu
                self._log_status(current_price, regime, grid_active, len(desired_orders))

                self._sleep(loop_start)

        except KeyboardInterrupt:
            logger.info("Bot kullanıcı tarafından durduruldu.")
        except Exception as e:
            logger.error(f"Beklenmedik hata: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("Bot durduruldu.")

    def _sleep(self, loop_start: Optional[float] = None):
        """Döngü arası bekleme"""
        if loop_start:
            elapsed = time.time() - loop_start
            sleep_time = max(0, self.config.data.update_interval_seconds - elapsed)
        else:
            sleep_time = self.config.data.update_interval_seconds
        
        time.sleep(sleep_time)

    def _log_dry_run_actions(self, orders: list, current_price: float, regime: dict):
        """Dry run modunda ne yapılacağını loglar"""
        if not orders:
            return
        
        logger.info(f"[DRY RUN] {len(orders)} adet emir üretildi | Fiyat: {current_price:.2f} | Rejim: {regime['regime']}")
        
        # İlk 3 emri örnek olarak göster
        for i, order in enumerate(orders[:3]):
            logger.info(f"   → {order['side']} @ {order['price']} | {order['quantity_usdt']} USDT")

    def _log_status(self, price: float, regime: dict, grid_active: bool, order_count: int):
        """Periyodik durum özeti"""
        status = self.strategy.get_grid_status()
        risk_status = self.risk.get_risk_status()

        logger.info(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"Fiyat: {price:.2f} | "
            f"Rejim: {regime['regime']} | "
            f"Grid Aktif: {grid_active} | "
            f"Emir Sayısı: {order_count} | "
            f"Daily PnL: {risk_status['daily_pnl']}"
        )

    def stop(self):
        self.running = False


# =============================================================================
# Bot'u Başlatma
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("VADELI GRID TRADING BOT - v1.0 (Paper Trading / Dry Run)")
    print("=" * 60)

    cfg = Config()
    cfg.validate()

    # Güvenlik kontrolü
    if not cfg.dry_run and cfg.mode == "live":
        confirm = input("⚠️  LIVE mod aktif ve dry_run=False! Devam etmek istiyor musun? (yes/no): ")
        if confirm.lower() != "yes":
            print("İptal edildi.")
            exit()

    bot = GridBot(cfg)
    bot.run()