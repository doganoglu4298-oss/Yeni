"""
backtest.py - Daha Gerçekçi Grid Backtest (v4)

İyileştirmeler:
- Daha uzun veri (2000 mum)
- Gerçekçi dolma koşulları
- Pozisyon takibi + Compounding
- Slippage + daha gerçekçi ücret
- Daha iyi metrikler (Profit Factor dahil)
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


class RealisticGridBacktesterV4:
    def __init__(self, config: Config):
        self.config = config
        self.strategy = GridStrategy(config)
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.current_equity: float = config.risk.initial_capital_usdt
        self.fee_rate = 0.0006          # ~%0.06 round-trip
        self.slippage_pct = 0.0003      # %0.03 ortalama slippage

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        self.trades = []
        self.equity_curve = [self.current_equity]
        self.strategy.grid_levels = []

        first_price = df['close'].iloc[0]
        self.strategy.calculate_grid_levels(first_price)

        pending_orders: Dict[float, Dict] = {}
        filled_positions: Dict[float, Dict] = {}

        for i in range(1, len(df)):
            price = df['close'].iloc[i]
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]

            # 1. Bekleyen emirleri kontrol et
            to_fill = []
            for level_price, order in list(pending_orders.items()):
                filled = False
                fill_price = price

                if order['side'] == "BUY" and low <= level_price * 0.9992:
                    filled = True
                    fill_price = level_price * (1 - self.slippage_pct)
                elif order['side'] == "SELL" and high >= level_price * 1.0008:
                    filled = True
                    fill_price = level_price * (1 + self.slippage_pct)

                if filled:
                    filled_positions[level_price] = {
                        "side": order['side'],
                        "size": order['size'],
                        "entry_price": fill_price,
                        "target": fill_price + (self.strategy.upper_price - self.strategy.lower_price) / self.config.grid.grid_count * 0.7
                    }
                    to_fill.append(level_price)

            for p in to_fill:
                del pending_orders[p]

            # 2. Doldurulmuş pozisyonları kontrol et (TP)
            to_close = []
            for level_price, pos in list(filled_positions.items()):
                tp_hit = False
                exit_price = price

                if pos['side'] == "BUY" and high >= pos['target']:
                    tp_hit = True
                    exit_price = pos['target'] * (1 - self.slippage_pct)
                elif pos['side'] == "SELL" and low <= pos['target']:
                    tp_hit = True
                    exit_price = pos['target'] * (1 + self.slippage_pct)

                if tp_hit:
                    pnl = pos['size'] * ((exit_price - pos['entry_price']) / pos['entry_price'])
                    if pos['side'] == "SELL":
                        pnl = -pnl

                    fee = pos['size'] * self.fee_rate
                    net_pnl = pnl - fee

                    self.current_equity += net_pnl
                    self.trades.append({
                        "entry_price": pos['entry_price'],
                        "exit_price": exit_price,
                        "side": pos['side'],
                        "size": pos['size'],
                        "pnl": round(net_pnl, 2)
                    })
                    to_close.append(level_price)

            for p in to_close:
                del filled_positions[p]

            # 3. Yeni grid emirleri (sadece limit aşılmadıysa)
            if len(pending_orders) + len(filled_positions) < self.config.grid.max_open_orders:
                for level in self.strategy.grid_levels:
                    if level.price in pending_orders or level.price in filled_positions:
                        continue

                    should_place = False
                    if level.side == "BUY" and low <= level.price * 0.9995:
                        should_place = True
                    elif level.side == "SELL" and high >= level.price * 1.0005:
                        should_place = True

                    if should_place:
                        size = self.strategy._calculate_order_size(level.price, self.current_equity)
                        pending_orders[level.price] = {
                            "side": level.side,
                            "size": size,
                            "entry_price": level.price
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
                "win_rate": 0,
                "profit_factor": 0
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
        wins = sum(1 for t in self.trades if t['pnl'] > 0)
        win_rate = (wins / len(self.trades)) * 100

        # Profit Factor
        gross_profit = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        return {
            "total_trades": len(self.trades),
            "total_pnl_usdt": round(total_pnl, 2),
            "total_pnl_pct": round(pnl_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "final_equity": round(final_equity, 2),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
            "avg_pnl_per_trade": round(total_pnl / len(self.trades), 2)
        }

    def print_report(self, metrics: Dict):
        print("\n" + "="*65)
        print(" DAHA GERÇEKÇİ GRİD BACKTEST SONUÇLARI (v4) ")
        print("="*65)
        for k, v in metrics.items():
            print(f"{k:28}: {v}")
        print("="*65)


if __name__ == "__main__":
    cfg = Config()
    cfg.symbol.symbol = "ETHUSDT"
    cfg.grid.grid_count = 20
    cfg.grid.take_profit_per_grid = 0.70
    cfg.grid.order_size_pct_of_balance = 3.0
    cfg.risk.initial_capital_usdt = 2000
    cfg.grid.max_open_orders = 8

    fetcher = DataFetcher(cfg)
    df = fetcher.fetch_ohlcv(limit=2000)

    bt = RealisticGridBacktesterV4(cfg)
    metrics = bt.run_backtest(df)
    bt.print_report(metrics)