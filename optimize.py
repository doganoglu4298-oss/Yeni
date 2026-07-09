"""
optimize.py - Basit Backtest Parametre Optimizasyonu

Amaç: Farklı grid_count ve take_profit_per_grid kombinasyonlarını test ederek
en iyi sonuçları bulmak.
"""

from backtest import RealisticGridBacktesterV4
from config import Config
from data import DataFetcher
import pandas as pd

# Test edilecek parametre aralıkları
GRID_COUNTS = [16, 18, 20, 22]
TAKE_PROFITS = [0.55, 0.60, 0.65, 0.70, 0.75]
MAX_OPEN_ORDERS = [6, 8]

def run_optimization():
    cfg = Config()
    cfg.symbol.symbol = "ETHUSDT"
    cfg.risk.initial_capital_usdt = 2000
    cfg.grid.order_size_pct_of_balance = 3.0

    fetcher = DataFetcher(cfg)
    df = fetcher.fetch_ohlcv(limit=2000)

    results = []

    print("Optimizasyon başlıyor...\n")

    for grid_count in GRID_COUNTS:
        for tp in TAKE_PROFITS:
            for max_orders in MAX_OPEN_ORDERS:
                cfg.grid.grid_count = grid_count
                cfg.grid.take_profit_per_grid = tp
                cfg.grid.max_open_orders = max_orders

                bt = RealisticGridBacktesterV4(cfg)
                metrics = bt.run_backtest(df)

                results.append({
                    "grid_count": grid_count,
                    "take_profit": tp,
                    "max_open_orders": max_orders,
                    "total_trades": metrics["total_trades"],
                    "total_pnl": metrics["total_pnl_usdt"],
                    "pnl_pct": metrics["total_pnl_pct"],
                    "win_rate": metrics["win_rate"],
                    "profit_factor": metrics["profit_factor"],
                    "max_drawdown": metrics["max_drawdown_pct"]
                })

    # Sonuçları DataFrame'e çevir
    df_results = pd.DataFrame(results)

    # En iyi kombinasyonları bul (Profit Factor + PnL'ye göre)
    print("\n" + "="*100)
    print("EN İYİ KOMBİNASYONLAR (Profit Factor > 1.0 ve PnL > 0 olanlar)")
    print("="*100)

    good_results = df_results[(df_results["profit_factor"] > 1.0) & (df_results["total_pnl"] > 0)]
    if len(good_results) > 0:
        print(good_results.sort_values("profit_factor", ascending=False).head(10).to_string(index=False))
    else:
        print("Hiçbir kombinasyon kârlı çıkmadı (Profit Factor > 1.0).")

    print("\n" + "="*100)
    print("TÜM KOMBİNASYONLAR (En iyi 15)")
    print("="*100)
    print(df_results.sort_values("profit_factor", ascending=False).head(15).to_string(index=False))

    # En iyi 3 kombinasyonu kaydet
    best_3 = df_results.sort_values("profit_factor", ascending=False).head(3)
    print("\n" + "="*100)
    print("ÖNERİLEN İLK 3 KOMBİNASYON")
    print("="*100)
    for idx, row in best_3.iterrows():
        print(f"\ngrid_count={int(row['grid_count'])}, take_profit={row['take_profit']}, max_open_orders={int(row['max_open_orders'])}")
        print(f"  → Trades: {int(row['total_trades'])}, PnL: {row['total_pnl']:.2f}, PF: {row['profit_factor']}, WinRate: {row['win_rate']}%")

if __name__ == "__main__":
    run_optimization()