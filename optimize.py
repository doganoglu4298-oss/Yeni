"""
optimize.py
===========
Grid Stratejisi için Basit Parametre Optimizasyonu (Grid Search)

Bu script ile farklı grid parametrelerini test edip en iyi performansı
veren ayarları bulabilirsin.

Kullanım:
    python optimize.py

Not: Bu basit bir grid search'tir. Daha gelişmiş optimizasyon (Optuna, Bayesian vs.)
ileride eklenebilir.
"""

import pandas as pd
import itertools
from typing import Dict, List
import logging

from config import Config
from backtest import GridBacktester
from data import DataFetcher

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def run_optimization(
    df: pd.DataFrame,
    param_grid: Dict[str, List],
    initial_capital: float = 2000.0
) -> pd.DataFrame:
    """
    Verilen parametre aralıklarında grid search yapar.
    """
    results = []
    keys = list(param_grid.keys())
    combinations = list(itertools.product(*param_grid.values()))

    print(f"Toplam {len(combinations)} kombinasyon test edilecek...\n")

    for i, combo in enumerate(combinations, 1):
        params = dict(zip(keys, combo))

        # Her kombinasyon için yeni config oluştur
        cfg = Config()
        cfg.risk.initial_capital_usdt = initial_capital

        # Grid parametrelerini güncelle
        if "grid_count" in params:
            cfg.grid.grid_count = params["grid_count"]
        if "take_profit_per_grid" in params:
            cfg.grid.take_profit_per_grid = params["take_profit_per_grid"]
        if "order_size_usdt" in params:
            cfg.grid.order_size_usdt = params["order_size_usdt"]

        # Backtest çalıştır
        backtester = GridBacktester(cfg)
        metrics = backtester.run_backtest(df, initial_capital=initial_capital)

        result = {
            **params,
            "total_pnl_pct": metrics.get("total_pnl_pct", 0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
            "total_trades": metrics.get("total_trades", 0),
            "final_equity": metrics.get("final_equity", 0),
        }
        results.append(result)

        if i % 5 == 0 or i == len(combinations):
            print(f"  {i}/{len(combinations)} kombinasyon tamamlandı...")

    return pd.DataFrame(results)


if __name__ == "__main__":
    print("=" * 60)
    print("GRID STRATEJİSİ - PARAMETRE OPTİMİZASYONU")
    print("=" * 60)

    # 1. Veri çek
    cfg = Config()
    fetcher = DataFetcher(cfg)
    print("\nGeçmiş veri çekiliyor (son 600 mum)...")
    df = fetcher.fetch_ohlcv(limit=600)

    # 2. Optimize edilecek parametre aralıkları
    param_grid = {
        "grid_count": [20, 28, 36],
        "take_profit_per_grid": [0.6, 0.8, 1.0, 1.2],
        "order_size_usdt": [15, 25, 35],
    }

    print(f"\nTest edilecek parametreler:")
    for k, v in param_grid.items():
        print(f"  - {k}: {v}")

    # 3. Optimizasyonu çalıştır
    results_df = run_optimization(df, param_grid)

    # 4. Sonuçları sırala (PnL'e göre)
    results_df = results_df.sort_values("total_pnl_pct", ascending=False)

    print("\n" + "=" * 60)
    print("EN İYİ 10 SONUÇ (PnL'e göre sıralı)")
    print("=" * 60)
    print(results_df.head(10).to_string(index=False))

    print("\n" + "=" * 60)
    print("EN KÖTÜ 5 SONUÇ")
    print("=" * 60)
    print(results_df.tail(5).to_string(index=False))

    # En iyi parametreleri kaydet
    best = results_df.iloc[0]
    print("\n" + "=" * 60)
    print("ÖNERİLEN EN İYİ PARAMETRELER")
    print("=" * 60)
    print(f"grid_count           : {int(best['grid_count'])}")
    print(f"take_profit_per_grid : {best['take_profit_per_grid']}")
    print(f"order_size_usdt      : {best['order_size_usdt']}")
    print(f"Beklenen PnL %       : {best['total_pnl_pct']:.2f}%")
    print(f"Max Drawdown         : {best['max_drawdown_pct']:.2f}%")
    print("=" * 60)