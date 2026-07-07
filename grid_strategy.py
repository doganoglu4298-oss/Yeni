"""
grid_strategy.py
================
Vadeli Grid Trading Stratejisi - Çekirdek Mantık

Bu modül şu işleri yapar:
- Grid seviyelerini hesaplar (üst/alt sınır + adım)
- Neutral / Long / Short grid emir mantığını yönetir
- Mevcut piyasa rejimine göre grid aktif/pasif karar verir
- Her grid seviyesinde açılacak pozisyon büyüklüğünü belirler

Gelecekte buraya eklenecekler:
- Dinamik grid yeniden merkezleme
- Funding rate bazlı filtre
- Partial fill yönetimi
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

from indicators import is_sideways_market, get_market_regime

logger = logging.getLogger(__name__)


@dataclass
class GridLevel:
    """Tek bir grid seviyesini temsil eder"""
    price: float
    side: str              # "BUY" veya "SELL"
    size_usdt: float
    filled: bool = False
    order_id: Optional[str] = None


class GridStrategy:
    """
    Vadeli Grid Stratejisi Sınıfı
    """

    def __init__(self, config):
        """
        config: Config sınıfı (config.py'den)
        """
        self.config = config
        self.grid_config = config.grid
        self.regime_config = config.regime
        self.symbol_config = config.symbol
        
        self.grid_levels: List[GridLevel] = []
        self.upper_price: float = 0.0
        self.lower_price: float = 0.0
        self.current_price: float = 0.0
        
        self.is_active: bool = False
        self.last_regime_check: Optional[Dict] = None

    # =====================================================================
    # 1. GRID SEVİYELERİNİ HESAPLAMA
    # =====================================================================
    
    def calculate_grid_levels(self, current_price: float) -> List[GridLevel]:
        """
        Mevcut fiyata göre grid seviyelerini hesaplar.
        """
        self.current_price = current_price
        
        if self.grid_config.use_auto_range:
            # Basit otomatik aralık (ileride ATR ile geliştirilecek)
            atr_multiplier = 8.0
            # Şimdilik sabit volatilite varsayımı ile örnek aralık
            self.upper_price = current_price * (1 + 0.12)   # %12 üst
            self.lower_price = current_price * (1 - 0.12)   # %12 alt
        else:
            self.upper_price = self.grid_config.manual_upper_price
            self.lower_price = self.grid_config.manual_lower_price
        
        # Grid adımlarını hesapla
        if self.grid_config.grid_step_type == "arithmetic":
            step = (self.upper_price - self.lower_price) / (self.grid_config.grid_count - 1)
            prices = [self.lower_price + i * step for i in range(self.grid_config.grid_count)]
        else:
            # Geometric (daha ileri seviye)
            ratio = (self.upper_price / self.lower_price) ** (1 / (self.grid_config.grid_count - 1))
            prices = [self.lower_price * (ratio ** i) for i in range(self.grid_config.grid_count)]
        
        levels: List[GridLevel] = []
        
        for price in prices:
            # Neutral grid → Hem BUY hem SELL emirleri
            if self.grid_config.direction == "neutral":
                # Fiyatın altında BUY, üstünde SELL
                if price < current_price:
                    side = "BUY"
                else:
                    side = "SELL"
            elif self.grid_config.direction == "long":
                side = "BUY"
            else:  # short
                side = "SELL"
            
            # Her seviyede açılacak pozisyon büyüklüğü
            size = self._calculate_order_size(price)
            
            levels.append(GridLevel(
                price=round(price, 2),
                side=side,
                size_usdt=size
            ))
        
        self.grid_levels = levels
        logger.info(f"Grid seviyeleri hesaplandı. Toplam {len(levels)} seviye. "
                    f"Aralık: {self.lower_price:.2f} - {self.upper_price:.2f}")
        return levels

    def _calculate_order_size(self, price: float, current_equity: float = None) -> float:
        """
        Her grid seviyesinde açılacak pozisyon büyüklüğü (USDT).
        current_equity verilirse bakiyeye göre dinamik boyut hesaplar (compounding).
        """
        if current_equity is None or current_equity < 10:
            current_equity = 30.0  # Minimum başlangıç

        if self.grid_config.order_size_pct_of_balance > 0:
            # Bakiyenin %'si kadar (örneğin %2-3 risk)
            size = current_equity * (self.grid_config.order_size_pct_of_balance / 100)
        else:
            # Sabit boyut + basit compounding
            base = self.grid_config.order_size_usdt
            # Kâr arttıkça boyut artsın (basit ölçekleme)
            multiplier = max(current_equity / 30, 1.0)
            size = base * multiplier
            size = min(size, current_equity * 0.15)  # Max %15'i geçmesin

        return max(round(size, 2), 3.0)  # Minimum 3 USDT

    # =====================================================================
    # 2. PİYASA REJİMİ KONTROLÜ
    # =====================================================================
    
    def should_grid_be_active(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Grid'in çalışıp çalışmayacağına karar verir.
        Regime detection + basit güvenlik kontrolleri.
        """
        if not self.grid_config.enabled:
            return False, "Grid devre dışı bırakılmış"
        
        # Regime tespiti
        regime_result = get_market_regime(df, config=self.regime_config.__dict__)
        self.last_regime_check = regime_result
        
        is_sideways = regime_result["is_sideways"]
        reason = regime_result["reason"]
        
        if not is_sideways:
            return False, f"Trend piyasası → Grid kapalı | {reason}"
        
        # Ek güvenlik: Çok dar aralıkta grid çalıştırma
        if self.upper_price - self.lower_price < self.current_price * 0.03:
            return False, "Grid aralığı çok dar"
        
        return True, f"Grid aktif | {reason}"

    # =====================================================================
    # 3. EMİR ÜRETME
    # =====================================================================
    
    def generate_desired_orders(self, current_price: float) -> List[Dict]:
        """
        Şu anda piyasaya verilmesi gereken emirleri döndürür.
        (Ana bot döngüsünde kullanılacak)
        """
        if not self.grid_levels:
            self.calculate_grid_levels(current_price)
        
        desired_orders = []
        
        for level in self.grid_levels:
            # Zaten doldurulmuş seviyeleri atla (basit versiyon)
            if level.filled:
                continue
            
            order = {
                "symbol": self.symbol_config.symbol,
                "side": level.side,
                "type": "LIMIT",
                "price": level.price,
                "quantity_usdt": level.size_usdt,
                "grid_price_level": level.price
            }
            desired_orders.append(order)
        
        return desired_orders

    # =====================================================================
    # 4. DURUM BİLGİSİ
    # =====================================================================
    
    def get_grid_status(self) -> Dict:
        """Grid'in mevcut durumu hakkında özet bilgi"""
        total_levels = len(self.grid_levels)
        filled_count = sum(1 for l in self.grid_levels if l.filled)
        
        return {
            "is_active": self.is_active,
            "total_levels": total_levels,
            "filled_levels": filled_count,
            "upper_price": round(self.upper_price, 2),
            "lower_price": round(self.lower_price, 2),
            "current_price": round(self.current_price, 2),
            "last_regime": self.last_regime_check.get("regime") if self.last_regime_check else "N/A"
        }

    def reset_grid(self):
        """Grid'i sıfırlar (yeniden merkezleme için kullanılır)"""
        self.grid_levels = []
        self.is_active = False
        logger.info("Grid sıfırlandı.")


# =============================================================================
# Basit Kullanım Örneği (Test için)
# =============================================================================

if __name__ == "__main__":
    from config import Config
    
    cfg = Config()
    strategy = GridStrategy(cfg)
    
    # Sahte veri ile test
    fake_data = pd.DataFrame({
        'high': np.random.uniform(58000, 62000, 100),
        'low': np.random.uniform(57000, 61000, 100),
        'close': np.random.uniform(57500, 61500, 100)
    })
    
    # Grid hesapla
    levels = strategy.calculate_grid_levels(current_price=60000)
    print(f"Toplam grid seviyesi: {len(levels)}")
    
    # Rejim kontrolü
    active, msg = strategy.should_grid_be_active(fake_data)
    print(f"Grid aktif mi? {active} → {msg}")
    
    status = strategy.get_grid_status()
    print("Grid Durumu:", status)
