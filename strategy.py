"""
Trading Bot V6 Professional -> V7 Enhanced
strategy.py

Main trading strategy with V7 enhancements + Volatilite Bazlı Dinamik Eşikler
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config import (
    MIN_MARKET_SCORE,
    MIN_CONFIDENCE,
    ATR_SL_MULTIPLIER,
    ATR_TP_MULTIPLIER,
    MAX_OPEN_POSITIONS,
    COOLDOWN_MINUTES,
    MIN_VOLUME_RATIO,
    TREND_STRENGTH_THRESHOLD,
    INITIAL_BALANCE,
    RISK_PER_TRADE,
    LEVERAGE,
    USE_COMPOUND,
    MIN_NOTIONAL,
    MAX_POSITION_PERCENT,
    ENABLE_BTC_FILTER,
    ENABLE_BREAK_EVEN,
    BREAK_EVEN_ATR,
    ENABLE_TRAILING_STOP,
    TRAILING_STOP_ATR,
)

from models import (
    Position,
    PositionSide,
    MarketRegime,
)

from data import DataManager


class Strategy:

    def __init__(self):

        self.data = DataManager()

        self.positions: list[Position] = []

        self.cooldowns: dict[str, datetime] = {}

        self.last_signal: dict[str, str] = {}

        self.starting_balance = INITIAL_BALANCE
        self.balance = INITIAL_BALANCE

    # ---------------------------------------------------------
    # Volatilite Bazlı Dinamik Eşikler (YENİ)
    # ---------------------------------------------------------
    def get_dynamic_thresholds(self, atr_percent: float) -> tuple[int, int, float]:
        """
        Piyasa volatilitesine göre dinamik eşikler döndürür.
        Yüksek volatilite = daha fazla fırsat (düşük eşik)
        Düşük volatilite = daha kaliteli sinyal (yüksek eşik)
        """
        if atr_percent > 1.8:          # Çok yüksek volatilite
            return 60, 60, 8.0
        elif atr_percent > 1.2:        # Yüksek volatilite
            return 62, 62, 9.0
        elif atr_percent > 0.7:        # Normal volatilite
            return 65, 65, 10.0
        else:                          # Düşük volatilite
            return 70, 70, 12.0

    # ---------------------------------------------------------
    # Position Sizing
    # ---------------------------------------------------------

    def equity(self) -> float:
        return self.balance if USE_COMPOUND else self.starting_balance

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> float:

        equity = self.equity()
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance <= 0 or entry_price <= 0:
            return 0.0

        risk_capital = equity * RISK_PER_TRADE
        quantity = risk_capital / stop_distance

        max_notional = equity * LEVERAGE * (MAX_POSITION_PERCENT / 100)
        notional = quantity * entry_price

        if notional > max_notional > 0:
            quantity = max_notional / entry_price

        min_quantity = MIN_NOTIONAL / entry_price
        if quantity < min_quantity:
            quantity = min_quantity

        return quantity

    def update_balance(self, position: Position) -> None:
        self.balance += position.pnl

    # ---------------------------------------------------------
    # Position Helpers
    # ---------------------------------------------------------

    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.is_open]

    def has_open_position(self, symbol: str) -> bool:
        return any(p.symbol == symbol and p.is_open for p in self.positions)

    def max_position_reached(self) -> bool:
        return len(self.open_positions()) >= MAX_OPEN_POSITIONS

    # ---------------------------------------------------------
    # Cooldown
    # ---------------------------------------------------------

    def in_cooldown(self, symbol: str) -> bool:
        if symbol not in self.cooldowns:
            return False
        return datetime.utcnow() < self.cooldowns[symbol]

    def start_cooldown(self, symbol: str) -> None:
        self.cooldowns[symbol] = datetime.utcnow() + timedelta(minutes=COOLDOWN_MINUTES)

    # ---------------------------------------------------------
    # Candle Helpers
    # ---------------------------------------------------------

    def latest(self, symbol: str) -> pd.Series:
        return self.data.latest(symbol)

    def previous(self, symbol: str) -> pd.Series:
        return self.data.previous(symbol)

    # ---------------------------------------------------------
    # Market Regime
    # ---------------------------------------------------------

    def market_regime(self, row: pd.Series) -> MarketRegime:
        if row["trend_strength"] >= 30:
            return MarketRegime.TREND
        if row["trend_strength"] >= 15:
            return MarketRegime.TRANSITION
        return MarketRegime.RANGE

    # ---------------------------------------------------------
    # BTC Macro Trend Filter
    # ---------------------------------------------------------

    def _is_btc_trend_ok(self, side: PositionSide) -> bool:
        if not ENABLE_BTC_FILTER:
            return True
        try:
            btc_df = self.data.btc_market()
            if btc_df is None or len(btc_df) < 2:
                return True
            latest_btc = btc_df.iloc[-1]
            ema_fast = latest_btc.get('ema_50', 0)
            ema_slow = latest_btc.get('ema_200', 0)
            if side == PositionSide.LONG:
                return ema_fast > ema_slow
            else:
                return ema_fast < ema_slow
        except Exception:
            return True

    # ---------------------------------------------------------
    # Confidence
    # ---------------------------------------------------------

    def confidence(self, row: pd.Series) -> int:
        return min(int(row["market_score"]), 100)

    # ---------------------------------------------------------
    # Trend Analysis
    # ---------------------------------------------------------

    def bullish_trend(self, row: pd.Series) -> bool:
        return (
            row["ema_7"] > row["ema_25"]
            and row["ema_25"] > row["ema_50"]
            and row["ema_50"] > row["ema_200"]
        )

    def bearish_trend(self, row: pd.Series) -> bool:
        return (
            row["ema_7"] < row["ema_25"]
            and row["ema_25"] < row["ema_50"]
            and row["ema_50"] < row["ema_200"]
        )

    def supertrend_bullish(self, row: pd.Series) -> bool:
        return row["supertrend_direction"] == 1

    def supertrend_bearish(self, row: pd.Series) -> bool:
        return row["supertrend_direction"] == -1

    def above_vwap(self, row: pd.Series) -> bool:
        return row["close"] > row["vwap"]

    def below_vwap(self, row: pd.Series) -> bool:
        return row["close"] < row["vwap"]

    # ---------------------------------------------------------
    # Sifting & Filter Helpers
    # ---------------------------------------------------------

    def market_quality_ok(self, row: pd.Series, dynamic_score: int) -> bool:
        return int(row.get("market_score", 0)) >= dynamic_score

    def rsi_long_ok(self, row: pd.Series) -> bool:
        return 40 <= row["rsi"] <= 70

    def rsi_short_ok(self, row: pd.Series) -> bool:
        return 30 <= row["rsi"] <= 60

    def enough_volume(self, row: pd.Series, dynamic_vol: float) -> bool:
        return row.get("volume_ratio", 1.0) >= dynamic_vol

    def enough_trend_strength(self, row: pd.Series, dynamic_trend: float) -> bool:
        return row["trend_strength"] >= dynamic_trend

    def strong_candle(self, row: pd.Series) -> bool:
        body = abs(row["close"] - row["open"])
        high_low = row["high"] - row["low"]
        return body >= (high_low * 0.4) if high_low > 0 else False

    # ---------------------------------------------------------
    # LONG SIGNAL (Dinamik Eşik Kullanımı)
    # ---------------------------------------------------------

    def long_signal(self, symbol: str, previous: pd.Series, current: pd.Series) -> bool:

        if self.in_cooldown(symbol):
            return False
        if self.has_open_position(symbol):
            return False
        if self.max_position_reached():
            return False
        if not self._is_btc_trend_ok(PositionSide.LONG):
            return False

        # === DİNAMİK EŞİKLER ===
        dyn_score, dyn_conf, dyn_trend = self.get_dynamic_thresholds(current.get("atr_percent", 1.0))

        if not self.market_quality_ok(current, dyn_score):
            return False
        if not self.bullish_trend(current):
            return False
        if not self.supertrend_bullish(current):
            return False
        if not self.above_vwap(current):
            return False
        if not self.rsi_long_ok(current):
            return False
        if not self.enough_volume(current, 0.8):
            return False
        if not self.enough_trend_strength(current, dyn_trend):
            return False
        if current["close"] < current["ema_7"]:
            return False

        confidence = self.confidence(current)
        if confidence < dyn_conf:
            return False

        return True

    # ---------------------------------------------------------
    # SHORT SIGNAL (Dinamik Eşik Kullanımı)
    # ---------------------------------------------------------

    def short_signal(self, symbol: str, previous: pd.Series, current: pd.Series) -> bool:

        if self.in_cooldown(symbol):
            return False
        if self.has_open_position(symbol):
            return False
        if self.max_position_reached():
            return False
        if not self._is_btc_trend_ok(PositionSide.SHORT):
            return False

        # === DİNAMİK EŞİKLER ===
        dyn_score, dyn_conf, dyn_trend = self.get_dynamic_thresholds(current.get("atr_percent", 1.0))

        if not self.market_quality_ok(current, dyn_score):
            return False
        if not self.bearish_trend(current):
            return False
        if not self.supertrend_bearish(current):
            return False
        if not self.below_vwap(current):
            return False
        if not self.rsi_short_ok(current):
            return False
        if not self.enough_volume(current, 0.8):
            return False
        if not self.enough_trend_strength(current, dyn_trend):
            return False
        if not self.bearish_close(current):
            return False
        if not self.ema_resistance_holding(previous, current):
            return False
        if not self.ema25_break_confirmed(current):
            return False

        confidence = self.confidence(current)
        if confidence < dyn_conf:
            return False

        return True

    def bearish_close(self, current: pd.Series) -> bool:
        return current["close"] < current["open"]

    def ema_resistance_holding(self, previous: pd.Series, current: pd.Series) -> bool:
        return current["close"] <= current["ema_7"] and current["high"] <= current["ema_7"]

    def ema25_break_confirmed(self, current: pd.Series) -> bool:
        return current["close"] < current["ema_25"]

    # ---------------------------------------------------------
    # Dynamic Market Score
    # ---------------------------------------------------------

    def calculate_market_score(self, previous: pd.Series, current: pd.Series) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        if self.bullish_trend(current) or self.bearish_trend(current):
            score += 20
            reasons.append("EMA Trend")
        if self.supertrend_bullish(current) or self.supertrend_bearish(current):
            score += 15
            reasons.append("Supertrend")
        if self.above_vwap(current) or self.below_vwap(current):
            score += 10
            reasons.append("VWAP")
        if self.rsi_long_ok(current) or self.rsi_short_ok(current):
            score += 10
            reasons.append("RSI")
        if self.enough_volume(current, 0.8):
            score += 15
            reasons.append("Volume")
        if self.enough_trend_strength(current, 10):
            score += 15
            reasons.append("Trend Strength")
        if self.strong_candle(current):
            score += 5
            reasons.append("Strong Candle")

        return min(score, 100), reasons

    # ---------------------------------------------------------
    # Risk Management
    # ---------------------------------------------------------

    def calculate_trade_levels(self, side: PositionSide, current: pd.Series) -> tuple[float, float]:
        entry = float(current["close"])
        atr = float(current["atr"])

        if side == PositionSide.LONG:
            stop_loss = entry - (atr * ATR_SL_MULTIPLIER)
            take_profit = entry + (atr * ATR_TP_MULTIPLIER)
        else:
            stop_loss = entry + (atr * ATR_SL_MULTIPLIER)
            take_profit = entry - (atr * ATR_TP_MULTIPLIER)

        return stop_loss, take_profit

    def risk_reward_ratio(self, entry: float, stop_loss: float, take_profit: float) -> float:
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        return reward / risk if risk > 0 else 0.0

    def trade_allowed(self, symbol: str, side: PositionSide, current: pd.Series) -> bool:
        stop_loss, take_profit = self.calculate_trade_levels(side, current)
        rr = self.risk_reward_ratio(float(current["close"]), stop_loss, take_profit)
        if rr < 1.5:
            return False
        if current["atr"] <= 0:
            return False
        return True

    def create_position(self, symbol: str, side: PositionSide, current: pd.Series) -> Position:
        stop_loss, take_profit = self.calculate_trade_levels(side, current)
        entry_price = float(current["close"])
        quantity = self.calculate_position_size(entry_price, stop_loss)

        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=self.confidence(current),
            market_score=int(current["market_score"]),
            regime=self.market_regime(current),
            entry_atr=float(current["atr"]),
        )

        self.positions.append(position)
        self.start_cooldown(symbol)
        return position

    # ---------------------------------------------------------
    # Smart Exits
    # ---------------------------------------------------------

    def _update_smart_exits(self, position: Position, current: pd.Series) -> None:
        price = float(current["close"])
        atr = position.entry_atr
        if atr <= 0:
            return

        if position.side == PositionSide.LONG:
            if price > position.highest_price:
                position.highest_price = price
            if ENABLE_BREAK_EVEN:
                be_trigger = position.entry_price + (atr * BREAK_EVEN_ATR)
                if position.highest_price >= be_trigger and position.stop_loss < position.entry_price:
                    position.stop_loss = position.entry_price
            if ENABLE_TRAILING_STOP:
                ts_trigger = position.entry_price + (atr * TRAILING_STOP_ATR)
                if position.highest_price >= ts_trigger:
                    new_sl = position.highest_price - (atr * TRAILING_STOP_ATR)
                    if new_sl > position.stop_loss:
                        position.stop_loss = new_sl
        else:
            if price < position.lowest_price:
                position.lowest_price = price
            if ENABLE_BREAK_EVEN:
                be_trigger = position.entry_price - (atr * BREAK_EVEN_ATR)
                if position.lowest_price <= be_trigger and position.stop_loss > position.entry_price:
                    position.stop_loss = position.entry_price
            if ENABLE_TRAILING_STOP:
                ts_trigger = position.entry_price - (atr * TRAILING_STOP_ATR)
                if position.lowest_price <= ts_trigger:
                    new_sl = position.lowest_price + (atr * TRAILING_STOP_ATR)
                    if new_sl < position.stop_loss:
                        position.stop_loss = new_sl

    # ---------------------------------------------------------
    # Position Management
    # ---------------------------------------------------------

    def should_close_position(self, position: Position, current: pd.Series) -> tuple[bool, str]:
        price = float(current["close"])

        if position.side == PositionSide.LONG:
            if price >= position.take_profit:
                return True, "Take Profit"
            if price <= position.stop_loss:
                return True, "Stop Loss"
            if current["supertrend_direction"] == -1:
                return True, "Supertrend Reversal"
            if price < current["ema_7"]:
                return True, "EMA7 Lost"
            if current["market_score"] < MIN_MARKET_SCORE:
                return True, "Market Score"
        else:
            if price <= position.take_profit:
                return True, "Take Profit"
            if price >= position.stop_loss:
                return True, "Stop Loss"
            if current["supertrend_direction"] == 1:
                return True, "Supertrend Reversal"
            if price > current["ema_7"]:
                return True, "EMA7 Lost"
            if current["market_score"] < MIN_MARKET_SCORE:
                return True, "Market Score"

        return False, ""

    def close_position(self, position: Position, current: pd.Series, reason: str) -> Position:
        exit_price = float(current["close"])
        position.close(exit_price, reason)
        return position

    def manage_positions(self, symbols: list[str]) -> None:
        for position in self.open_positions():
            try:
                if position.symbol not in symbols:
                    continue
                current = self.latest(position.symbol)
                self._update_smart_exits(position, current)
                close, reason = self.should_close_position(position, current)
                if close:
                    self.close_position(position, current, reason)
            except Exception as error:
                print(f"[POSITION] {position.symbol}: {error}")

    # ---------------------------------------------------------
    # Trade Execution
    # ---------------------------------------------------------

    def evaluate_symbol(self, symbol: str) -> Optional[Position]:
        symbol = symbol.upper()
        previous, current = self.data.last_two(symbol)
        current = current.copy()

        # ATR yüzde olarak hesapla (dinamik eşik için)
        if current.get("atr", 0) > 0 and current.get("close", 0) > 0:
            current["atr_percent"] = (current["atr"] / current["close"]) * 100
        else:
            current["atr_percent"] = 1.0

        score, reasons = self.calculate_market_score(previous, current)
        current["market_score"] = score

        # LONG
        if self.long_signal(symbol, previous, current):
            if self.trade_allowed(symbol, PositionSide.LONG, current):
                position = self.create_position(symbol, PositionSide.LONG, current)
                print(f"✅ OPENED | {symbol} | LONG | Score={position.market_score}")
                return position

        # SHORT
        if self.short_signal(symbol, previous, current):
            if self.trade_allowed(symbol, PositionSide.SHORT, current):
                position = self.create_position(symbol, PositionSide.SHORT, current)
                print(f"✅ OPENED | {symbol} | SHORT | Score={position.market_score}")
                return position

        return None

    def scan_market(self, symbols: list[str]) -> list[Position]:
        opened_positions = []
        for symbol in symbols:
            try:
                position = self.evaluate_symbol(symbol)
                if position is not None:
                    opened_positions.append(position)
            except Exception as error:
                print(f"[STRATEGY] {symbol}: {error}")
        return opened_positions

    def run(self, symbols: list[str]) -> list[Position]:
        self.manage_positions(symbols)
        new_positions = self.scan_market(symbols)
        for position in new_positions:
            self.log_new_position(position)
        return new_positions

    def summary(self) -> dict:
        return {
            "open_positions": len(self.open_positions()),
            "cooldowns": len(self.cooldowns),
            "total_positions": len(self.positions),
        }

    def reset(self) -> None:
        self.positions.clear()
        self.cooldowns.clear()
        self.last_signal.clear()

    # ---------------------------------------------------------
    # Journal & Learning (kısaltılmış)
    # ---------------------------------------------------------

    JOURNAL_HEADER = ["timestamp", "symbol", "side", "entry_price", "exit_price", "stop_loss", "take_profit", "market_score", "confidence", "pnl", "pnl_percent", "exit_reason", "status"]
    LEARNING_HEADER = ["timestamp", "symbol", "side", "market_score", "confidence", "pnl", "pnl_percent", "result", "exit_reason"]

    def _write_csv_row(self, filename: str, header: list[str], row: list) -> None:
        import os
        file_exists = os.path.exists(filename) and os.path.getsize(filename) > 0
        with open(filename, "a", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(row)

    def log_new_position(self, position: Position) -> None:
        try:
            self._write_csv_row("journal.csv", self.JOURNAL_HEADER, [
                datetime.utcnow().isoformat(), position.symbol, position.side.name,
                position.entry_price, "", position.stop_loss, position.take_profit,
                position.market_score, position.confidence, "", "", "", "OPEN"
            ])
        except Exception as e:
            print(f"[JOURNAL] {e}")

    def log_closed_position(self, position: Position) -> None:
        try:
            self._write_csv_row("journal.csv", self.JOURNAL_HEADER, [
                datetime.utcnow().isoformat(), position.symbol, position.side.name,
                position.entry_price, position.exit_price, position.stop_loss, position.take_profit,
                position.market_score, position.confidence, position.pnl, position.pnl_percent,
                position.exit_reason, "CLOSED"
            ])
        except Exception as e:
            print(f"[JOURNAL] {e}")

    def update_learning_log(self, position: Position) -> None:
        try:
            self._write_csv_row("learning_log.csv", self.LEARNING_HEADER, [
                datetime.utcnow().isoformat(), position.symbol, position.side.name,
                position.market_score, position.confidence, position.pnl, position.pnl_percent,
                position.result.value, position.exit_reason
            ])
        except Exception as e:
            print(f"[LEARNING] {e}")

    def finalize_position(self, position: Position) -> None:
        self.update_balance(position)
        self.log_closed_position(position)
        self.update_learning_log(position)
