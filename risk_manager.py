"""
risk_manager.py
===============
Vadeli Grid Bot için Risk Yönetimi Modülü

Grid stratejilerinde en büyük tehlike **kontrolsüz pozisyon birikmesi** ve 
**likidasyondur**. Bu modül bot seviyesinde güvenlik sağlar.

Sorumlulukları:
- Bot Stop Loss (grid range dışına çıkınca bot'u durdur)
- Günlük zarar limiti
- Toplam açık pozisyon limiti
- Funding rate koruması
- Büyük zarar sonrası cooldown
- Güvenli pozisyon büyüklüğü hesaplama
"""

import pandas as pd
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Grid Bot için merkezi risk yönetim sınıfı.
    """

    def __init__(self, config):
        self.config = config
        self.risk_config = config.risk
        self.grid_config = config.grid
        self.symbol_config = config.symbol

        # Günlük takip değişkenleri
        self.daily_pnl: float = 0.0
        self.daily_start_balance: float = 0.0
        self.last_reset_day: Optional[datetime] = None
        
        # Cooldown
        self.cooldown_until: Optional[datetime] = None
        
        # Bot stop loss takibi
        self.initial_grid_upper: Optional[float] = None
        self.initial_grid_lower: Optional[float] = None
        self.bot_triggered_stop: bool = False

    # =====================================================================
    # 1. GÜNLÜK RESET
    # =====================================================================
    
    def _reset_daily_stats_if_needed(self, current_balance: float):
        """Her gün başında istatistikleri sıfırlar"""
        today = datetime.now().date()
        
        if self.last_reset_day is None or self.last_reset_day.date() != today:
            self.daily_pnl = 0.0
            self.daily_start_balance = current_balance
            self.last_reset_day = datetime.now()
            logger.info(f"Günlük istatistikler sıfırlandı. Başlangıç bakiyesi: {current_balance:.2f} USDT")

    # =====================================================================
    # 2. BOT SEVİYESİNDE STOP LOSS
    # =====================================================================
    
    def update_grid_range(self, upper: float, lower: float):
        """Grid aralığı değiştiğinde çağrılır (ilk kurulumda önemli)"""
        if self.initial_grid_upper is None:
            self.initial_grid_upper = upper
            self.initial_grid_lower = lower
            logger.info(f"İlk grid aralığı kaydedildi: {lower:.2f} - {upper:.2f}")

    def check_bot_stop_loss(self, current_price: float) -> Tuple[bool, str]:
        """
        Grid aralığının dışına çıkılıp çıkılmadığını kontrol eder.
        Çıkıldıysa bot'u durdurur.
        """
        if not self.grid_config.bot_stop_loss_pct or self.initial_grid_upper is None:
            return False, "Bot stop loss aktif değil"
        
        if self.bot_triggered_stop:
            return True, "Bot stop loss zaten tetiklendi"
        
        upper = self.initial_grid_upper
        lower = self.initial_grid_lower
        stop_pct = self.grid_config.bot_stop_loss_pct / 100.0
        
        # Fiyat grid aralığının üstüne veya altına stop_pct kadar çıktığında tetikle
        upper_trigger = upper * (1 + stop_pct)
        lower_trigger = lower * (1 - stop_pct)
        
        if current_price > upper_trigger:
            self.bot_triggered_stop = True
            msg = f"Bot Stop Loss TETİKLENDİ → Fiyat {current_price:.2f} > Üst sınır + %{self.grid_config.bot_stop_loss_pct}"
            logger.warning(msg)
            return True, msg
        
        if current_price < lower_trigger:
            self.bot_triggered_stop = True
            msg = f"Bot Stop Loss TETİKLENDİ → Fiyat {current_price:.2f} < Alt sınır - %{self.grid_config.bot_stop_loss_pct}"
            logger.warning(msg)
            return True, msg
        
        return False, "Bot stop loss güvenli bölgede"

    # =====================================================================
    # 3. GÜNLÜK ZARAR LİMİTİ
    # =====================================================================
    
    def update_daily_pnl(self, realized_pnl: float, current_balance: float):
        """Her realized işlemden sonra çağrılır"""
        self._reset_daily_stats_if_needed(current_balance)
        self.daily_pnl += realized_pnl

    def check_daily_loss_limit(self, current_balance: float) -> Tuple[bool, str]:
        """Günlük zarar limiti aşıldı mı?"""
        self._reset_daily_stats_if_needed(current_balance)
        
        max_daily_loss = self.risk_config.max_daily_loss_usdt
        max_daily_loss_pct = self.risk_config.daily_loss_limit_pct / 100.0
        
        # USDT bazlı kontrol
        if abs(self.daily_pnl) >= max_daily_loss and self.daily_pnl < 0:
            msg = f"Günlük zarar limiti aşıldı! PnL: {self.daily_pnl:.2f} USDT (Limit: {max_daily_loss} USDT)"
            logger.warning(msg)
            return True, msg
        
        # % bazlı kontrol (opsiyonel)
        if self.daily_start_balance > 0:
            loss_pct = abs(self.daily_pnl) / self.daily_start_balance
            if loss_pct >= max_daily_loss_pct and self.daily_pnl < 0:
                msg = f"Günlük zarar limiti (%{self.risk_config.daily_loss_limit_pct}) aşıldı!"
                logger.warning(msg)
                return True, msg
        
        return False, "Günlük zarar limiti içinde"

    # =====================================================================
    # 4. TOPLAM POZİSYON LİMİTİ (EXPOSURE)
    # =====================================================================
    
    def check_max_exposure(self, current_exposure_usdt: float) -> Tuple[bool, str]:
        """
        Toplam açık pozisyon limiti kontrolü.
        Grid'de pozisyonlar birikebileceği için çok önemli.
        """
        max_exposure = self.grid_config.max_total_exposure_usdt
        
        if current_exposure_usdt > max_exposure:
            msg = f"Max exposure limiti aşıldı! Mevcut: {current_exposure_usdt:.2f} USDT > Limit: {max_exposure} USDT"
            logger.warning(msg)
            return True, msg
        
        return False, "Exposure limiti içinde"

    # =====================================================================
    # 5. FUNDING RATE KORUMASI
    # =====================================================================
    
    def check_funding_rate(self, current_funding_rate: float) -> Tuple[bool, str]:
        """
        Funding rate çok yüksekse grid'i duraklatır.
        Özellikle uzun süre açık pozisyonlarda erozyona yol açar.
        """
        max_funding = self.risk_config.max_funding_rate
        
        if abs(current_funding_rate) > max_funding:
            direction = "LONG" if current_funding_rate > 0 else "SHORT"
            msg = f"Yüksek funding rate! {direction} pozisyonlar için riskli ({current_funding_rate*100:.4f}%)"
            logger.warning(msg)
            return True, msg
        
        return False, "Funding rate normal"

    # =====================================================================
    # 6. COOLDOWN YÖNETİMİ
    # =====================================================================
    
    def trigger_cooldown(self, reason: str = "Büyük zarar"):
        """Büyük zarar sonrası cooldown başlatır"""
        minutes = self.risk_config.cooldown_after_loss_minutes
        self.cooldown_until = datetime.now() + timedelta(minutes=minutes)
        logger.warning(f"Cooldown başlatıldı ({minutes} dakika). Sebep: {reason}")

    def is_in_cooldown(self) -> Tuple[bool, str]:
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            remaining = (self.cooldown_until - datetime.now()).seconds // 60
            return True, f"Cooldown aktif. Kalan süre: {remaining} dakika"
        return False, "Cooldown yok"

    # =====================================================================
    # 7. GENEL GÜVENLİK KONTROLÜ (Ana bot döngüsünde kullanılacak)
    # =====================================================================
    
    def should_pause_trading(
        self, 
        current_price: float,
        current_exposure: float,
        current_funding_rate: float = 0.0,
        current_balance: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Tüm risk kontrollerini tek seferde yapar.
        True dönerse trading duraklatılmalı.
        """
        # 1. Bot stop loss
        triggered, msg = self.check_bot_stop_loss(current_price)
        if triggered:
            return True, msg
        
        # 2. Günlük zarar limiti
        triggered, msg = self.check_daily_loss_limit(current_balance)
        if triggered:
            self.trigger_cooldown("Günlük zarar limiti")
            return True, msg
        
        # 3. Exposure limiti
        triggered, msg = self.check_max_exposure(current_exposure)
        if triggered:
            return True, msg
        
        # 4. Funding rate
        triggered, msg = self.check_funding_rate(current_funding_rate)
        if triggered:
            return True, msg
        
        # 5. Cooldown kontrolü
        in_cooldown, msg = self.is_in_cooldown()
        if in_cooldown:
            return True, msg
        
        return False, "Tüm risk kontrolleri temiz"

    # =====================================================================
    # 8. YARDIMCI
    # =====================================================================
    
    def get_risk_status(self) -> Dict:
        """Risk durumunu özetler"""
        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "bot_stop_loss_triggered": self.bot_triggered_stop,
            "in_cooldown": self.cooldown_until is not None and datetime.now() < self.cooldown_until,
            "initial_grid_range": f"{self.initial_grid_lower} - {self.initial_grid_upper}" if self.initial_grid_upper else "Belirlenmedi"
        }

    def reset_bot_stop_loss(self):
        """Bot stop loss'u manuel resetler (opsiyonel)"""
        self.bot_triggered_stop = False
        self.initial_grid_upper = None
        self.initial_grid_lower = None
        logger.info("Bot stop loss resetlendi.")


# =============================================================================
# Basit Test
# =============================================================================

if __name__ == "__main__":
    from config import Config
    
    cfg = Config()
    rm = RiskManager(cfg)
    
    # Örnek kontroller
    print(rm.check_bot_stop_loss(current_price=75000))
    print(rm.check_daily_loss_limit(current_balance=2000))
    print(rm.check_max_exposure(current_exposure=650))
    print(rm.should_pause_trading(current_price=60000, current_exposure=400, current_funding_rate=0.0003, current_balance=2000))