"""
backtest.py - Geliştirilmiş Grid Backtest Motoru (v2)

Önceki versiyona göre iyileştirmeler:
- Daha gerçekçi grid dolma ve kar alma mantığı
- Basit işlem ücreti (fee)
- Equity takibi + basit compounding
- Daha anlamlı metrikler
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

from config import Config
from grid_strategy import GridStrategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImprovedGridBacktester:
    def __init__(self, config: Config):
        self.config = config
        self.strategy = GridStrategy(config)
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.current_equity: float = config.risk.initial_capital_usdt
        self.fee_rate = 0.0004  # Yaklaşık %0.04 round-trip

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        self.trades = []
        self.equity_curve = [self.current_equity]
        self.strategy.grid_levels = []

        first_price = df['close'].iloc[0]
        self.strategy.calculate_grid_levels(first_price)

        open_positions = {}  # {level_price: info}

        for i in range(1, len(df)):
            price = df['close'].iloc[i]

            # 1. Açık pozisyonları kontrol et (TP mantığı)
            to_close = []
            for lvl_price, pos in open_positions.items():
                step = (self.strategy.upper_price - self.strategy.lower_price) / max(self.config.grid.grid_count - 1, 1)
                tp_dist = step * 0.55

                if pos['side'] == 'BUY' and price >= lvl_price + tp_dist:
                    pnl = pos['size'] * (tp_dist / lvl_price)
                    fee = pos['size'] * self.fee_rate
                    net = pnl - fee
                    self.current_equity += net
                    self.trades.append({
                        'side': 'BUY', 'entry': lvl_price, 'exit': price,
                        'size': pos['size'], 'pnl': round(net, 2)
                    })
                    to_close.append(lvl_price)

                elif pos['side'] == 'SELL' and price <= lvl_price - tp_dist:
                    pnl = pos['size'] * (tp_dist / lvl_price)
                    fee = pos['size'] * self.fee_rate
                    net = pnl - fee
                    self.current_equity += net
                    self.trades.append({
                        'side': 'SELL', 'entry': lvl_price, 'exit': price,
                        'size': pos['size'], 'pnl': round(net, 2)
                    })
                    to_close.append(lvl_price)

            for p in to_close:
                del open_positions[p]

            # 2. Yeni grid seviyelerini doldur
            for level in self.strategy.grid_levels:
                if level.price in open_positions:
                    continue

                filled = False
                if level.side == "BUY" and price <= level.price:
                    filled = True
                elif level.side == "SELL" and price >= level.price:
                    filled = True

                if filled:
                    size = self.strategy._calculate_order_size(level.price, self.current_equity)
                    open_positions[level.price] = {
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
                "final_equity": round(self.current_equity, 2)
            }

        total_pnl = sum(t['pnl'] for t in self.trades)
        final_eq = self.current_equity
        init_eq = self.equity_curve[0]
        pnl_pct = ((final_eq - init_eq) / init_eq) * 100

        # Max Drawdown
        peak = init_eq
        max_dd = 0
        for eq in self.equity_curve:
            if eq > peak: peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd: max_dd = dd

        return {
            "total_trades": len(self.trades),
            "total_pnl_usdt": round(total_pnl, 2),
            "total_pnl_pct": round(pnl_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "final_equity": round(final_eq, 2),
            "avg_pnl_per_trade": round(total_pnl / len(self.trades), 2)
        }

    def print_report(self, metrics: Dict):
        print("\n" + "="*58)
        print(" GELİŞTİRİLMİŞ GRİD BACKTEST SONUÇLARI (v2) ")
        print("="*58)
        for k, v in metrics.items():
            print(f"{k:28}: {v}")
        print("="*58)


if __name__ == "__main__":
    from data import DataFetcher

    cfg = Config()
    # ETHUSDT için iyileştirilmiş parametreler
    cfg.symbol.symbol = "ETHUSDT"
    cfg.grid.grid_count = 22
    cfg.grid.take_profit_per_grid = 0.75
    cfg.grid.order_size_pct_of_balance = 3.5
    cfg.risk.initial_capital_usdt = 2000

    fetcher = DataFetcher(cfg)
    df = fetcher.fetch_ohlcv(limit=800)

    bt = ImprovedGridBacktester(cfg)
    metrics = bt.run_backtest(df)
    bt.print_report(metrics)
