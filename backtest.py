"""
backtest.py
===========
Vadeli Grid Stratejisi için Basit Backtest Motoru

Bu script ile:
- Geçmiş veriler üzerinde grid stratejisini test edebilirsin
- Farklı grid aralıkları, kaldıraç ve parametrelerle optimizasyon yapabilirsin
- Performans metrikleri alabilirsin (PnL, Drawdown, Trade sayısı vs.)

Not: Bu basit bir simülasyondur. Gerçek funding rate, slippage ve likidasyon
henüz tam olarak modellenmemiştir. İleride daha gelişmiş hale getirilebilir.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

from config import Config
from grid_strategy import GridStrategy
from indicators import get_market_regime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GridBacktester:
    """
    Basit Grid Backtest Motoru
    """

    def __init__(self, config: Config):
        self.config = config
        self.strategy = GridStrategy(config)
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.current_equity: float = config.risk.initial_capital_usdt

    def run_backtest(
        self, 
        df: pd.DataFrame, 
        initial_capital: float = None
    ) -> Dict:
        """
        Backtest'i çalıştırır.
        """
        if initial_capital:
            self.current_equity = initial_capital

        self.trades = []
        self.equity_curve = [self.current_equity]

        # Grid seviyelerini hesapla (basit versiyon: ilk fiyatı baz alır)
        first_price = df['close'].iloc[0]
        self.strategy.calculate_grid_levels(first_price)

        logger.info(f"Backtest başlıyor... Toplam mum: {len(df)}")
        logger.info(f"Grid aralığı: {self.strategy.lower_price:.2f} - {self.strategy.upper_price:.2f}")

        for i in range(1, len(df)):
            row = df.iloc[i]
            current_price = row['close']
            timestamp = df.index[i]

            # Basit grid simülasyonu:
            # Fiyat bir grid seviyesini geçtiğinde "fill" olmuş kabul ederiz
            for level in self.strategy.grid_levels:
                if level.filled:
                    continue

                # Fiyat seviyeyi geçti mi?
                if (level.side == "BUY" and current_price <= level.price) or \
                   (level.side == "SELL" and current_price >= level.price):

                    # Trade simüle et
                    trade = {
                        'timestamp': timestamp,
                        'side': level.side,
                        'price': level.price,
                        'size_usdt': level.size_usdt,
                        'pnl': 0.0  # Basit tutuyoruz, gerçek PnL için TP lazım
                    }
                    self.trades.append(trade)
                    level.filled = True

                    # Basit PnL tahmini (her başarılı grid için küçük kâr varsayımı)
                    estimated_profit = level.size_usdt * (self.config.grid.take_profit_per_grid / 100)
                    self.current_equity += estimated_profit

            self.equity_curve.append(self.current_equity)

        return self._calculate_metrics()

    def _calculate_metrics(self) -> Dict:
        """Performans metriklerini hesaplar"""
        if not self.trades:
            return {"error": "Hiç trade oluşmadı"}

        total_trades = len(self.trades)
        final_equity = self.current_equity
        initial_equity = self.equity_curve[0]
        total_pnl = final_equity - initial_equity
        pnl_pct = (total_pnl / initial_equity) * 100

        # Basit drawdown
        peak = initial_equity
        max_drawdown = 0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd

        return {
            "total_trades": total_trades,
            "final_equity": round(final_equity, 2),
            "total_pnl_usdt": round(total_pnl, 2),
            "total_pnl_pct": round(pnl_pct, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "win_rate_estimate": "N/A (basit simülasyon)"
        }

    def print_report(self, metrics: Dict):
        print("\n" + "="*50)
        print("GRID BACKTEST SONUÇLARI")
        print("="*50)
        for key, value in metrics.items():
            print(f"{key:25}: {value}")
        print("="*50)


# =============================================================================
# Kullanım Örneği
# =============================================================================

if __name__ == "__main__":
    from data import DataFetcher

    print("Grid Stratejisi Backtest\n")

    cfg = Config()
    # Backtest için daha geniş aralık ve düşük kaldıraç önerilir
    cfg.grid.use_auto_range = True
    cfg.symbol.leverage = 5

    # Veri çek
    fetcher = DataFetcher(cfg)
    print("Geçmiş veri çekiliyor...")
    df = fetcher.fetch_ohlcv(limit=500)  # Son ~500 mum (5m timeframe için ~40 saat)

    # Backtest çalıştır
    backtester = GridBacktester(cfg)
    metrics = backtester.run_backtest(df)

    backtester.print_report(metrics)
