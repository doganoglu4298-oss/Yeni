"""
indicators.py
=============
Vadeli Grid Bot için indikatörler ve piyasa rejimi tespiti.

Bu modül özellikle Grid stratejisi için kritik olan "Sideways mı, Trend mi?" 
sorusuna cevap verir. Güçlü trendlerde grid çalıştırmak zararlıdır.

Kullanılan kütüphaneler:
- pandas + numpy (zorunlu)
- Opsiyonel: pandas_ta (daha hızlı ve kapsamlı indikatörler için)

Tüm fonksiyonlar DataFrame alır ve Series/DataFrame döndürür.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 1. TEMEL İNDİKATÖRLER
# =============================================================================

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range (ATR)
    Volatilite ölçüsü. Dinamik grid aralığı için çok kullanışlıdır.
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average Directional Index (ADX)
    Trend gücünü ölçer. 
    - ADX < 20-25 → Sideways / Zayıf trend
    - ADX > 25-30 → Güçlü trend
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # +DM ve -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    # True Range
    tr = calculate_atr(df, period=1)  # 1 periyotluk TR
    
    # Smoothed +DM, -DM, TR
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / tr.rolling(window=period).mean())
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / tr.rolling(window=period).mean())
    
    # DX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    
    # ADX = DX'in ortalaması
    adx = dx.rolling(window=period).mean()
    return adx


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands + Band Width
    Band genişliği volatiliteyi gösterir. Dar bant = düşük volatilite (sideways eğilimi)
    """
    close = df['close']
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    
    # Band Width = (Upper - Lower) / SMA
    band_width = (upper - lower) / sma
    
    return pd.DataFrame({
        'bb_upper': upper,
        'bb_middle': sma,
        'bb_lower': lower,
        'bb_width': band_width
    })


def calculate_price_range(df: pd.DataFrame, lookback: int = 50) -> float:
    """
    Son N mum içindeki fiyat aralığı (yüzde olarak)
    Küçük aralık = sideways piyasa işareti
    """
    if len(df) < lookback:
        lookback = len(df)
    
    recent = df.tail(lookback)
    high_max = recent['high'].max()
    low_min = recent['low'].min()
    
    if low_min == 0:
        return 0.0
    
    range_pct = ((high_max - low_min) / low_min) * 100
    return round(range_pct, 2)


# =============================================================================
# 2. PİYASA REJİMİ TESPİTİ (EN ÖNEMLİ KISIM)
# =============================================================================

def is_sideways_market(
    df: pd.DataFrame, 
    adx_period: int = 14,
    adx_threshold: float = 22.0,
    bb_period: int = 20,
    bb_std: float = 2.0,
    bb_width_min: float = 0.025,
    range_lookback: int = 50,
    range_threshold_pct: float = 6.5,
    require_both: bool = True
) -> Tuple[bool, str, Dict]:
    """
    Ana fonksiyon: Piyasanın sideways (yatay) olup olmadığını tespit eder.
    
    Returns:
        is_sideways (bool)
        reason (str)          → Açıklama
        details (dict)        → Detaylı skorlar
    """
    if len(df) < max(adx_period, bb_period, range_lookback) + 5:
        return False, "Yetersiz veri", {}
    
    # İndikatörleri hesapla
    adx = calculate_adx(df, period=adx_period).iloc[-1]
    bb = calculate_bollinger_bands(df, period=bb_period, std_dev=bb_std)
    bb_width = bb['bb_width'].iloc[-1]
    price_range_pct = calculate_price_range(df, lookback=range_lookback)
    
    # Karar kuralları
    adx_sideways = adx < adx_threshold
    bb_wide_enough = bb_width > bb_width_min
    range_small = price_range_pct < range_threshold_pct
    
    details = {
        "adx": round(adx, 2),
        "bb_width": round(bb_width, 4),
        "price_range_pct": price_range_pct,
        "adx_sideways": adx_sideways,
        "bb_wide_enough": bb_wide_enough,
        "range_small": range_small
    }
    
    if require_both:
        # Hem ADX düşük hem de fiyat aralığı dar olmalı
        is_sideways = adx_sideways and range_small
        if is_sideways:
            reason = f"Sideways → ADX={adx:.1f} < {adx_threshold} ve Range={price_range_pct:.1f}% < {range_threshold_pct}%"
        else:
            reason = f"Trend → ADX={adx:.1f} veya Range={price_range_pct:.1f}%"
    else:
        # Veya şartı
        is_sideways = (adx_sideways and bb_wide_enough) or range_small
        reason = "Loose condition met" if is_sideways else "No sideways condition met"
    
    return is_sideways, reason, details


def get_market_regime(df: pd.DataFrame, config: Optional[dict] = None) -> Dict:
    """
    Daha gelişmiş rejim analizi.
    İleride buraya 'strong_trend', 'ranging', 'breakout' gibi sınıflar eklenebilir.
    """
    if config is None:
        config = {}
    
    is_sideways, reason, details = is_sideways_market(
        df,
        adx_period=config.get("adx_period", 14),
        adx_threshold=config.get("adx_threshold", 22.0),
        bb_period=config.get("bb_period", 20),
        bb_std=config.get("bb_std", 2.0),
        bb_width_min=config.get("bb_width_min", 0.025),
        range_lookback=config.get("range_lookback_candles", 50),
        range_threshold_pct=config.get("range_threshold_pct", 6.5),
        require_both=config.get("require_both_conditions", True)
    )
    
    regime = "SIDEWAYS" if is_sideways else "TRENDING"
    
    return {
        "regime": regime,
        "is_sideways": is_sideways,
        "reason": reason,
        "details": details
    }


# =============================================================================
# 3. YARDIMCI FONKSİYONLAR (İleride kullanılacak)
# =============================================================================

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI - İleride overbought/oversold filtreleri için"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
    """EMA"""
    return df['close'].ewm(span=period, adjust=False).mean()


if __name__ == "__main__":
    # Basit test
    print("indicators.py modülü yüklendi. Test için gerçek veri ile çalıştırın.")