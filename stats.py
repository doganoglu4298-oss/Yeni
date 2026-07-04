"""
Trading Bot V6 Professional
stats.py

Standalone paper-trading performance report.

Run any time (bot can be running or stopped):

    python stats.py

Reads learning_log.csv (one row per CLOSED trade, with a proper header)
and prints win/loss counts, win rate, PnL totals, and a per-symbol
breakdown. Use this to evaluate the strategy before ever connecting it
to a real exchange account.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict

LEARNING_LOG_FILE = "learning_log.csv"


def load_trades(filename: str = LEARNING_LOG_FILE) -> list[dict]:
    if not os.path.exists(filename):
        return []

    with open(filename, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def print_report(trades: list[dict]) -> None:

    if not trades:
        print("Henüz kapanmış bir işlem yok (learning_log.csv boş veya yok).")
        print("Bot çalışıp en az bir pozisyon kapattığında burada veri görünecek.")
        return

    total = len(trades)
    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    breakeven = [t for t in trades if t["result"] == "BREAKEVEN"]

    total_pnl = sum(to_float(t["pnl"]) for t in trades)
    total_pnl_percent = sum(to_float(t["pnl_percent"]) for t in trades)

    win_rate = (len(wins) / total * 100) if total else 0.0

    avg_win_pct = (
        sum(to_float(t["pnl_percent"]) for t in wins) / len(wins)
        if wins else 0.0
    )
    avg_loss_pct = (
        sum(to_float(t["pnl_percent"]) for t in losses) / len(losses)
        if losses else 0.0
    )

    print("=" * 42)
    print("  PAPER TRADING PERFORMANS RAPORU")
    print("=" * 42)
    print(f"Toplam işlem     : {total}")
    print(f"Kazanan (WIN)    : {len(wins)}")
    print(f"Kaybeden (LOSS)  : {len(losses)}")
    print(f"Başabaş (BE)     : {len(breakeven)}")
    print(f"Win rate         : {win_rate:.1f}%")
    print(f"Toplam PnL       : {total_pnl:.4f}")
    print(f"Toplam PnL %     : {total_pnl_percent:.2f}%")
    print(f"Ort. kazanç %    : {avg_win_pct:.2f}%")
    print(f"Ort. kayıp %     : {avg_loss_pct:.2f}%")

    # Per-symbol breakdown
    by_symbol: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": 0.0}
    )

    for t in trades:
        s = by_symbol[t["symbol"]]
        s["total"] += 1
        s["pnl"] += to_float(t["pnl"])
        if t["result"] == "WIN":
            s["wins"] += 1
        elif t["result"] == "LOSS":
            s["losses"] += 1

    print("\n" + "-" * 42)
    print("  SEMBOL BAZLI DAĞILIM")
    print("-" * 42)
    print(f"{'Symbol':<10}{'Trades':>8}{'Win':>6}{'Loss':>6}{'PnL':>12}")

    for symbol, s in sorted(
        by_symbol.items(), key=lambda kv: kv[1]["total"], reverse=True
    ):
        print(
            f"{symbol:<10}{s['total']:>8}{s['wins']:>6}"
            f"{s['losses']:>6}{s['pnl']:>12.4f}"
        )

    print("=" * 42)


if __name__ == "__main__":
    print_report(load_trades())
