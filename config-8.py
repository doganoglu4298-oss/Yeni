"""
Vadeli Grid Trading Bot - Profesyonel Konfigürasyon
====================================================
Bu dosya tamamen sıfırdan, temiz ve modüler olarak tasarlanmıştır.
Tüm önemli parametreler burada merkezi olarak yönetilir.

Kullanım:
- Paper trading için testnet=True yapın
- Gerçek işlem için testnet=False + API key'lerinizi girin
- Grid parametrelerini piyasa koşullarına göre optimize edin
"""

from dataclasses import dataclass, field
from typing import Literal
import os


@dataclass
class BinanceConfig:
    """Binance API ayarları"""
    api_key: str = os.getenv("BINANCE_API_KEY", "YOUR_API_KEY_HERE")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "YOUR_API_SECRET_HERE")
    testnet: bool = True                    # True = Paper trading / Testnet
    recv_window: int = 10000


@dataclass
class SymbolConfig:
    """İşlem yapılan sembol ve piyasa ayarları"""
    symbol: str = "BTCUSDT"                 # Örnek: BTCUSDT Perpetual
    quote_asset: str = "USDT"
    base_asset: str = "BTC"
    leverage: int = 3                       # 30 USDT için muhafazakâr kaldıraç (güvenli)
    margin_mode: Literal["isolated", "cross"] = "isolated"
    position_mode: Literal["one_way", "hedge"] = "one_way"  # Grid için genellikle one_way


@dataclass
class GridConfig:
    """
    Vadeli Grid Stratejisi Parametreleri
    ------------------------------------
    Neutral grid önerilir (hem long hem short emir).
    Güçlü trendlerde zarar yazma riski yüksektir → Regime detection şart!
    """
    # === Temel Grid Ayarları ===
    enabled: bool = True
    direction: Literal["neutral", "long", "short"] = "neutral"
    
    # Fiyat aralığı (manuel veya otomatik)
    use_auto_range: bool = True             # True ise ATR veya volatiliteye göre otomatik belirler
    manual_upper_price: float = 72000.0     # use_auto_range=False ise kullanılır
    manual_lower_price: float = 58000.0
    
    grid_count: int = 18                    # 30 USDT için daha az seviye (güvenli)
    grid_step_type: Literal["arithmetic", "geometric"] = "arithmetic"
    
    # Her grid seviyesinde açılacak pozisyon büyüklüğü
    order_size_usdt: float = 0.0            # Kullanmıyoruz, % bazlı kullanıyoruz
    # Alternatif: sermayenin %'si olarak (compounding için)
    order_size_pct_of_balance: float = 3.5  # 30 USDT için muhafazakâr (%3.5)
    
    # === Gelişmiş Grid Yönetimi ===
    dynamic_grid: bool = True
    recenter_hours: int = 24
    
    take_profit_per_grid: float = 0.65      # Küçük ama gerçekçi kâr hedefi
    # Not: Vadeli grid'de genellikle her emir TP ile kapatılır
    
    # === Risk Limitleri (ÇOK ÖNEMLİ!) ===
    max_total_exposure_usdt: float = 12.0   # 30 USDT için toplam açık pozisyon max 12 USDT
    bot_stop_loss_pct: float = 10.0         # Grid aralığı dışına çıkarsa bot dursun
    max_daily_loss_usdt: float = 5.0        # Günlük max zarar (30 USDT için düşük)
    
    # Trend yakalanırsa pozisyon birikmesin diye
    max_open_grids: int = 12                # Aynı anda max açık grid seviyesi (güvenli)


@dataclass
class RegimeDetectionConfig:
    """
    Piyasa Rejimi Tespiti (Sideways mi Trend mi?)
    ---------------------------------------------
    Grid sadece sideways piyasada çalışsın istiyorsak bu kritik!
    """
    enabled: bool = True
    
    # ADX (Average Directional Index) - Düşükse sideways
    adx_period: int = 14
    adx_threshold: float = 22.0             # ADX < bu değer → sideways kabul et
    
    # Bollinger Band Genişliği (volatilite)
    bb_period: int = 20
    bb_std: float = 2.0
    bb_width_min: float = 0.025             # Band genişliği bu değerin üstündeyse volatil
    
    # Fiyat aralığı kontrolü (son N mum içinde)
    range_lookback_candles: int = 50
    range_threshold_pct: float = 6.5        # Son 50 mum içinde fiyat %6.5'ten az hareket ettiyse sideways
    
    # Ek filtre
    require_both_conditions: bool = True    # True = ADX + Range ikisi de sideways olmalı


@dataclass
class RiskManagerConfig:
    """Genel Risk Yönetimi"""
    initial_capital_usdt: float = 2000.0    # Başlangıç sermayesi (paper trading için)
    
    # Günlük istatistik ve koruma
    daily_loss_limit_pct: float = 5.0       # Günlük max zarar %'si
    max_daily_loss_usdt: float = 5.0        # 30 USDT için düşük tut (güvenli)
    cooldown_after_loss_minutes: int = 45   # Büyük zarar sonrası bekleme süresi
    
    # Funding rate koruması (perpetual futures)
    max_funding_rate: float = 0.0008        # 0.08% üstü funding varsa grid'i duraklat
    
    # Pozisyon yönetimi
    use_trailing_stop_on_grid: bool = False # Grid'de trailing stop kullanılsın mı? (genelde kapalı)
    trailing_stop_activation: float = 1.5   # % kaç kârda trailing başlasın


@dataclass
class DataConfig:
    """Veri çekme ayarları"""
    timeframe: str = "5m"                   # 1m, 3m, 5m, 15m önerilir grid için
    limit_candles: int = 300                # Kaç mum geçmiş veri çekilsin
    update_interval_seconds: int = 8        # Ana döngü kaç saniyede bir çalışsın


@dataclass
class TelegramConfig:
    """Telegram Bildirimleri"""
    enabled: bool = True
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
    
    notify_on_grid_fill: bool = True
    notify_on_bot_stop_loss: bool = True
    notify_daily_summary: bool = True
    notify_regime_change: bool = True


@dataclass
class LoggingConfig:
    """Loglama"""
    level: str = "INFO"                     # DEBUG, INFO, WARNING, ERROR
    log_to_file: bool = True
    log_file_path: str = "logs/grid_bot.log"
    log_trade_journal: bool = True
    journal_file: str = "data/trade_journal.csv"


@dataclass
class Config:
    """Ana Konfigürasyon Sınıfı - Tüm ayarlar burada toplanır"""
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    symbol: SymbolConfig = field(default_factory=SymbolConfig)
    grid: GridConfig = field(default_factory=GridConfig)
    regime: RegimeDetectionConfig = field(default_factory=RegimeDetectionConfig)
    risk: RiskManagerConfig = field(default_factory=RiskManagerConfig)
    data: DataConfig = field(default_factory=DataConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Genel bot ayarları
    mode: Literal["paper", "live"] = "paper"  # paper = simülasyon, live = gerçek para
    dry_run: bool = True                      # True ise emir göndermez, sadece loglar
    
    def validate(self):
        """Konfigürasyon doğrulama"""
        if self.grid.order_size_usdt <= 0 and self.grid.order_size_pct_of_balance <= 0:
            raise ValueError("order_size_usdt veya order_size_pct_of_balance tanımlanmalı!")
        
        if self.symbol.leverage > 20:
            print("⚠️  Uyarı: Grid stratejisinde 20x üzeri kaldıraç çok risklidir!")
        
        if self.grid.bot_stop_loss_pct < 5:
            print("⚠️  Uyarı: Bot stop loss %5'ten düşük ayarlanmamalı.")


# Kullanım örneği
if __name__ == "__main__":
    cfg = Config()
    cfg.validate()
    print("✅ Config başarıyla yüklendi!")
    print(f"Symbol: {cfg.symbol.symbol}")
    print(f"Grid Direction: {cfg.grid.direction}")
    print(f"Leverage: {cfg.symbol.leverage}x")
    print(f"Testnet: {cfg.binance.testnet}")