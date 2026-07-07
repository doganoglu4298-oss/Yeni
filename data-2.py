"""
data.py
=======
Binance Futures için veri çekme modülü.

Özellikler:
- Historical kline (mum) verisi çekme
- Gerçek zamanlı fiyat + funding rate çekme
- Basit cache mekanizması (rate limit koruması için)
- Paper trading ve live için aynı arayüz

Kütüphane: ccxt (önerilen) veya binance-connector
Şu an ccxt kullanacağız (daha esnek ve popüler).
"""

import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Binance Futures veri çekme sınıfı.
    """

    def __init__(self, config):
        self.config = config
        self.binance_config = config.binance
        self.symbol_config = config.symbol
        self.data_config = config.data

        # Exchange bağlantısı
        if self.binance_config.testnet:
            self.exchange = ccxt.binance({
                'apiKey': self.binance_config.api_key,
                'secret': self.binance_config.api_secret,
                'options': {'defaultType': 'future'},
                'enableRateLimit': True,
            })
            self.exchange.set_sandbox_mode(True)
            logger.info("Binance Testnet (Futures) bağlantısı kuruldu.")
        else:
            self.exchange = ccxt.binance({
                'apiKey': self.binance_config.api_key,
                'secret': self.binance_config.api_secret,
                'options': {'defaultType': 'future'},
                'enableRateLimit': True,
            })
            logger.info("Binance Live (Futures) bağlantısı kuruldu.")

        self.symbol = self.symbol_config.symbol
        self.cache: Dict = {}  # Basit cache

    # =====================================================================
    # HISTORICAL DATA (Backtest ve Regime Tespiti için)
    # =====================================================================
    
    def fetch_ohlcv(
        self, 
        symbol: Optional[str] = None, 
        timeframe: Optional[str] = None, 
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Historical OHLCV (mum) verisi çeker.
        """
        symbol = symbol or self.symbol
        timeframe = timeframe or self.data_config.timeframe
        limit = limit or self.data_config.limit_candles

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.debug(f"{len(df)} mum veri çekildi: {symbol} {timeframe}")
            return df
            
        except Exception as e:
            logger.error(f"OHLCV çekme hatası: {e}")
            raise

    def fetch_recent_data(self, lookback_minutes: int = 300) -> pd.DataFrame:
        """
        Son X dakika veriyi çeker (regime detection için ideal).
        """
        # Basit hesaplama: 5m timeframe için ~60 mum = 5 saat
        limit = max(100, int(lookback_minutes / 5) + 10)
        return self.fetch_ohlcv(limit=limit)

    # =====================================================================
    # REAL-TIME DATA
    # =====================================================================
    
    def get_current_price(self, symbol: Optional[str] = None) -> float:
        """Anlık fiyat"""
        symbol = symbol or self.symbol
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Anlık fiyat çekme hatası: {e}")
            raise

    def get_funding_rate(self, symbol: Optional[str] = None) -> float:
        """Mevcut funding rate"""
        symbol = symbol or self.symbol
        try:
            # ccxt ile funding rate
            funding = self.exchange.fetch_funding_rate(symbol)
            return float(funding.get('fundingRate', 0.0))
        except Exception as e:
            logger.warning(f"Funding rate çekilemedi: {e}. Varsayılan 0.0 kullanılıyor.")
            return 0.0

    def get_account_balance(self) -> float:
        """USDT bakiyesi"""
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            return float(usdt.get('free', 0.0))
        except Exception as e:
            logger.error(f"Bakiye çekme hatası: {e}")
            return 0.0

    # =====================================================================
    # CACHE (Rate limit koruması)
    # =====================================================================
    
    def get_cached_price(self, max_age_seconds: int = 5) -> Optional[float]:
        """Cache'li fiyat (çok sık API çağrısı yapmamak için)"""
        key = "current_price"
        now = time.time()
        
        if key in self.cache:
            cached_time, cached_value = self.cache[key]
            if now - cached_time < max_age_seconds:
                return cached_value
        
        price = self.get_current_price()
        self.cache[key] = (now, price)
        return price

    # =====================================================================
    # YARDIMCI
    # =====================================================================
    
    def test_connection(self) -> bool:
        """Bağlantı testi"""
        try:
            self.exchange.fetch_time()
            logger.info("Binance bağlantı testi başarılı.")
            return True
        except Exception as e:
            logger.error(f"Bağlantı testi başarısız: {e}")
            return False


# =============================================================================
# Basit Kullanım Örneği
# =============================================================================

if __name__ == "__main__":
    from config import Config
    
    cfg = Config()
    fetcher = DataFetcher(cfg)
    
    print("Bağlantı testi:", fetcher.test_connection())
    
    # Örnek veri çek
    df = fetcher.fetch_ohlcv(limit=50)
    print(f"Son 50 mum çekildi. Son kapanış: {df['close'].iloc[-1]}")
    
    price = fetcher.get_current_price()
    print(f"Anlık fiyat: {price}")
    
    funding = fetcher.get_funding_rate()
    print(f"Funding Rate: {funding}")