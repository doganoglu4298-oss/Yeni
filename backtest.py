"""
backtest.py - Geliştirilmiş Gerçekçi Grid Backtest (v3)

Özellikler:
- Mum mum ilerleyerek gerçekçi simülasyon
- Birden fazla açık grid seviyesi takibi
- Her seviye için ayrı TP mantığı
- Gerçekçi ücret (fee) hesabı
- Equity curve + Max Drawdown
- Daha anlamlı metrikler (Win Rate dahil)
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

from config import Config
from grid_strategy import GridStrategy
from data import DataFetcher

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class RealisticGridBacktester:
    def __init__(self, config: Config):
        self.config = config
        self.strategy = GridStrategy(config)
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.current_equity: float = config.risk.initial_capital_usdt
        self.fee_rate = 0.0004  # ~%0.04 round trip

    def run_backtest(self, df: pd.DataFrame, initial_capital: float = None) -> Dict:
        if initial_capital:
            self.current_equity = initial_capital

        self.trades = []
        self.equity_curve = [self.current_equity]
        self.strategy.grid_levels = []

        # İlk grid aralığını oluştur
        first_price = df['close'].iloc[0]
        self.strategy.calculate_grid_levels(first_price)

        open_grids: Dict[float, Dict] = {}  # price -> {side, size, entry_price}

        for i in range(1, len(df)):
            price = df['close'].iloc[i]
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]

            # 1. Açık grid seviyelerini kontrol et (TP)
            to_close = []
            for level_price, grid_info in list(open_grids.items()):
                step = (self.strategy.upper_price - self.strategy.lower_price) / max(self.config.grid.grid_count - 1, 1)
                tp_distance = step * 0.55

                filled = False
                exit_price = price

                if grid_info['side'] == 'BUY':
                    if high >= level_price + tp_distance:
                        filled = True
                        exit_price = level_price + tp_distance
                else:  # SELL
                    if low <= level_price - tp_distance:
                        filled = True
                        exit_price = level_price - tp_distance

                if filled:
                    pnl = grid_info['size'] * ((exit_price - grid_info['entry_price']) / grid_info['entry_price'])
                    if grid_info['side'] == 'SELL':
                        pnl = -pnl

                    fee = grid_info['size'] * self.fee_rate
                    net_pnl = pnl - fee

                    self.current_equity += net_pnl
                    self.trades.append({
                        'entry_price': grid_info['entry_price'],
                        'exit_price': exit_price,
                        'side': grid_info['side'],
                        'size': grid_info['size'],
                        'pnl': round(net_pnl, 2)
                    })
                    to_close.append(level_price)

            for p in to_close:
                del open_grids[p]

            # 2. Yeni grid seviyelerini doldur
            for level in self.strategy.grid_levels:
                if level.price in open_grids:
                    continue

                filled = False
                if level.side == "BUY" and low <= level.price:
                    filled = True
                elif level.side == "SELL" and high >= level.price:
                    filled = True

                if filled:
                    size = self.strategy._calculate_order_size(level.price, self.current_equity)
                    open_grids[level.price] = {
                        'side': level.side,
                        'size': size,
                        'entry_price': level.price
                    }

            self.equity_curve.append(self.current_equity)

        return self._calculate_metrics()

    def _calculate_metrics(self) -> Dict:
        if not self.trades:
            return {
                "total_trades": 0,
                "total_pnl_usdt": 0,
                "total_pnl_pct": 0,
                "max_drawdown_pct": 0,
                "final_equity": round(self.current_equity, 2),
                "win_rate": 0
            }

        total_pnl = sum(t['pnl'] for t in self.trades)
        final_equity = self.current_equity
        initial_equity = self.equity_curve[0]
        pnl_pct = ((final_equity - initial_equity) / initial_equity) * 100

        # Max Drawdown
        peak = initial_equity
        max_dd = 0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Win Rate
        winning_trades = sum(1 for t in self.trades if t['pnl'] > 0)
        win_rate = (winning_trades / len(self.trades)) * 100

        return {
            "total_trades": len(self.trades),
            "total_pnl_usdt": round(total_pnl, 2),
            "total_pnl_pct": round(pnl_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "final_equity": round(final_equity, 2),
            "win_rate": round(win_rate, 1),
            "avg_pnl_per_trade": round(total_pnl / len(self.trades), 2)
        }

    def print_report(self, metrics: Dict):
        print("\n" + "="*60)
        print(" GERÇEKÇİ GRİD BACKTEST SONUÇLARI (v3) ")
        print("="*60)
        for k, v in metrics.items():
            print(f"{k:28}: {v}")
        print("="*60)


if __name__ == "__main__":
    cfg = Config()
    cfg.symbol.symbol = "ETHUSDT"
    cfg.grid.grid_count = 22
    cfg.grid.take_profit_per_grid = 0.75
    cfg.grid.order_size_pct_of_balance = 3.5
    cfg.risk.initial_capital_usdt = 2000

    fetcher = DataFetcher(cfg)
    df = fetcher.fetch_ohlcv(limit=1000)

    bt = RealisticGridBacktester(cfg)
    metrics = bt.run_backtest(df)
    bt.print_report(metrics)