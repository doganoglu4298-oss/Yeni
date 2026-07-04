"""
Trading Bot V6 Professional
strategy.py

Main trading strategy.
"""

from __future__ import annotations

import csv
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

        # Paper account balance. Used for risk-based position sizing.
        self.starting_balance = INITIAL_BALANCE
        self.balance = INITIAL_BALANCE

    # ---------------------------------------------------------
    # Position Sizing
    # ---------------------------------------------------------

    def equity(self) -> float:
        """
        Balance used as the basis for risk sizing.

        If USE_COMPOUND is True, position size grows/shrinks with the
        current (realized) balance. Otherwise every trade risks a fixed
        percentage of the original starting balance.
        """

        return self.balance if USE_COMPOUND else self.starting_balance

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Risk-based position sizing.

        Risks RISK_PER_TRADE (fraction of equity) on the distance between
        entry and stop loss, capped by MAX_POSITION_PERCENT of leveraged
        equity, and floored by MIN_NOTIONAL.
        """

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
        """
        Apply a closed position's realized PnL to the paper balance.
        """

        self.balance += position.pnl

    # ---------------------------------------------------------
    # Position Helpers
    # ---------------------------------------------------------

    def open_positions(self) -> list[Position]:

        return [
            position
            for position in self.positions
            if position.is_open
        ]

    def has_open_position(
        self,
        symbol: str,
    ) -> bool:

        return any(
            position.symbol == symbol
            and position.is_open
            for position in self.positions
        )

    def max_position_reached(self) -> bool:

        return (
            len(self.open_positions())
            >= MAX_OPEN_POSITIONS
        )

    # ---------------------------------------------------------
    # Cooldown
    # ---------------------------------------------------------

    def in_cooldown(
        self,
        symbol: str,
    ) -> bool:

        if symbol not in self.cooldowns:
            return False

        return (
            datetime.utcnow()
            <
            self.cooldowns[symbol]
        )

    def start_cooldown(
        self,
        symbol: str,
    ) -> None:

        self.cooldowns[symbol] = (
            datetime.utcnow()
            +
            timedelta(
                minutes=COOLDOWN_MINUTES
            )
        )

    # ---------------------------------------------------------
    # Candle Helpers
    # ---------------------------------------------------------

    def latest(
        self,
        symbol: str,
    ) -> pd.Series:

        return self.data.latest(symbol)

    def previous(
        self,
        symbol: str,
    ) -> pd.Series:

        return self.data.previous(symbol)

    # ---------------------------------------------------------
    # Market Regime
    # ---------------------------------------------------------

    def market_regime(
        self,
        row: pd.Series,
    ) -> MarketRegime:

        if row["trend_strength"] >= 30:
            return MarketRegime.TREND

        if row["trend_strength"] >= 15:
            return MarketRegime.TRANSITION

        return MarketRegime.RANGE

    # ---------------------------------------------------------
    # Confidence
    # ---------------------------------------------------------

    def confidence(
        self,
        row: pd.Series,
    ) -> int:

        confidence = int(row["market_score"])

        return min(confidence, 100)

    # ---------------------------------------------------------
    # Trend Analysis
    # ---------------------------------------------------------

    def bullish_trend(
        self,
        row: pd.Series,
    ) -> bool:
        """
        Strong bullish trend.
        """

        return (
            row["ema_7"] > row["ema_25"]
            and row["ema_25"] > row["ema_50"]
            and row["ema_50"] > row["ema_200"]
        )

    def bearish_trend(
        self,
        row: pd.Series,
    ) -> bool:
        """
        Strong bearish trend.
        """

        return (
            row["ema_7"] < row["ema_25"]
            and row["ema_25"] < row["ema_50"]
            and row["ema_50"] < row["ema_200"]
        )

    def supertrend_bullish(
        self,
        row: pd.Series,
    ) -> bool:

        return row["supertrend_direction"] == 1

    def supertrend_bearish(
        self,
        row: pd.Series,
    ) -> bool:

        return row["supertrend_direction"] == -1

    def above_vwap(
        self,
        row: pd.Series,
    ) -> bool:

        return row["close"] > row["vwap"]

    def below_vwap(
        self,
        row: pd.Series,
    ) -> bool:

        return row["close"] < row["vwap"]

    # ---------------------------------------------------------
    # Sifting & Filter Helpers
    # ---------------------------------------------------------

    def market_quality_ok(self, row: pd.Series) -> bool:
        return int(row.get("market_score", 0)) >= MIN_MARKET_SCORE

    def rsi_long_ok(self, row: pd.Series) -> bool:
        return 40 <= row["rsi"] <= 70

    def rsi_short_ok(self, row: pd.Series) -> bool:
        return 30 <= row["rsi"] <= 60

    def enough_volume(self, row: pd.Series) -> bool:
        return row.get("volume_ratio", 1.0) >= MIN_VOLUME_RATIO

    def enough_trend_strength(self, row: pd.Series) -> bool:
        return row["trend_strength"] >= TREND_STRENGTH_THRESHOLD

    def strong_candle(self, row: pd.Series) -> bool:
        body = abs(row["close"] - row["open"])
        high_low = row["high"] - row["low"]
        return body >= (high_low * 0.4) if high_low > 0 else False

    def signal_quality(self, previous: pd.Series, current: pd.Series) -> int:
        quality = int(current["market_score"])
        if 50 <= current["rsi"] <= 65 or 35 <= current["rsi"] <= 50:
            quality += 25
        if current.get("volume_ratio", 1.0) > 1.5:
            quality += 25
        return min(quality, 100)

    # ---------------------------------------------------------
    # LONG SIGNAL
    # ---------------------------------------------------------

    def ema_support_holding(
        self,
        prev: pd.Series,
        current: pd.Series,
    ) -> bool:
        """
        EMA7 destek olarak korunuyor mu?
        """

        return (
            current["close"] >= current["ema_7"]
            and current["low"] >= current["ema_7"]
        )

    def long_signal(
        self,
        symbol: str,
        previous: pd.Series,
        current: pd.Series,
    ) -> bool:

        # Cooldown
        if self.in_cooldown(symbol):
            print(f"{symbol} ⏳ Cooldown")
            return False

        # Aynı coinde açık işlem
        if self.has_open_position(symbol):
            print(f"{symbol} 📌 Position already open")
            return False

        # Maksimum pozisyon
        if self.max_position_reached():
            print("📌 Max open positions reached")
            return False

        # Market Score
        if not self.market_quality_ok(current):
            print(f"{symbol} ❌ LONG : Market Score ({current['market_score']})")
            return False

        # Trend
        if not self.bullish_trend(current):
            print(f"{symbol} ❌ LONG : EMA Trend")
            return False

        # Supertrend
        if not self.supertrend_bullish(current):
            print(f"{symbol} ❌ LONG : Supertrend")
            return False

        # VWAP
        if not self.above_vwap(current):
            print(f"{symbol} ❌ LONG : VWAP")
            return False

        # RSI
        if not self.rsi_long_ok(current):
            print(f"{symbol} ❌ LONG : RSI ({current['rsi']:.1f})")
            return False

        # Volume
        if not self.enough_volume(current):
            print(f"{symbol} ❌ LONG : Volume ({current['volume_ratio']:.2f})")
            return False

        # Trend Strength
        if not self.enough_trend_strength(current):
            print(f"{symbol} ❌ LONG : Trend ({current['trend_strength']:.2f})")
            return False

        # Mum EMA7 altında kapandıysa
        if current["close"] < current["ema_7"]:
            return False

        confidence = self.confidence(current)

        if confidence < MIN_CONFIDENCE:
            print(f"{symbol} ❌ LONG : Confidence ({confidence})")
            return False

        return True

    # ---------------------------------------------------------
    # SHORT SIGNAL
    # ---------------------------------------------------------

    def ema_resistance_holding(
        self,
        previous: pd.Series,
        current: pd.Series,
    ) -> bool:
        """
        EMA7 artık direnç olarak çalışıyor mu?
        """

        return (
            current["close"] <= current["ema_7"]
            and current["high"] <= current["ema_7"]
        )

    def ema25_break_confirmed(
        self,
        current: pd.Series,
    ) -> bool:
        """
        EMA25 altında mum kapanışı.
        """

        return current["close"] < current["ema_25"]

    def bearish_close(
        self,
        current: pd.Series,
    ) -> bool:
        """
        Güçlü kırmızı mum.
        """

        return (
            current["close"]
            <
            current["open"]
        )

    def short_signal(
        self,
        symbol: str,
        previous: pd.Series,
        current: pd.Series,
    ) -> bool:

        # Cooldown
        if self.in_cooldown(symbol):
            print(f"{symbol} ⏳ Cooldown")
            return False

        # Aynı coinde açık işlem
        if self.has_open_position(symbol):
            print(f"{symbol} 📌 Position already open")
            return False

        # Maksimum pozisyon
        if self.max_position_reached():
            print("📌 Max open positions reached")
            return False

        # Market Score
        if not self.market_quality_ok(current):
            print(f"{symbol} ❌ SHORT : Market Score ({current['market_score']})")
            return False

        # EMA Trend
        if not self.bearish_trend(current):
            print(f"{symbol} ❌ SHORT : EMA Trend")
            return False

        # Supertrend
        if not self.supertrend_bearish(current):
            print(f"{symbol} ❌ SHORT : Supertrend")
            return False

        # VWAP
        if not self.below_vwap(current):
            print(f"{symbol} ❌ SHORT : VWAP")
            return False

        # RSI
        if not self.rsi_short_ok(current):
            print(f"{symbol} ❌ SHORT : RSI ({current['rsi']:.1f})")
            return False

        # Volume
        if not self.enough_volume(current):
            print(f"{symbol} ❌ SHORT : Volume ({current['volume_ratio']:.2f})")
            return False

        # Trend Strength
        if not self.enough_trend_strength(current):
            print(f"{symbol} ❌ SHORT : Trend ({current['trend_strength']:.2f})")
            return False

        # Kırmızı mum
        if not self.bearish_close(current):
            print(f"{symbol} ❌ SHORT : Bearish Candle")
            return False

        # EMA7 artık direnç mi?
        if not self.ema_resistance_holding(
            previous,
            current,
        ):
            print(f"{symbol} ❌ SHORT : EMA7 Resistance")
            return False

        # EMA25 altında kapanış
        if not self.ema25_break_confirmed(
            current,
        ):
            print(f"{symbol} ❌ SHORT : EMA25 Break")
            return False

        confidence = self.confidence(current)

        if confidence < MIN_CONFIDENCE:
            print(f"{symbol} ❌ SHORT : Confidence ({confidence})")
            return False

        return True

    # ---------------------------------------------------------
    # Dynamic Market Score
    # ---------------------------------------------------------

    def calculate_market_score(
        self,
        previous: pd.Series,
        current: pd.Series,
    ) -> tuple[int, list[str]]:
        """
        Dynamic market quality score.
        Returns:
            (score, reasons)
        """

        score = 0
        reasons = []

        # EMA Trend (20)
        if self.bullish_trend(current) or self.bearish_trend(current):
            score += 20
            reasons.append("EMA Trend")

        # Supertrend (15)
        if (
            self.supertrend_bullish(current)
            or self.supertrend_bearish(current)
        ):
            score += 15
            reasons.append("Supertrend")

        # VWAP (10)
        if (
            self.above_vwap(current)
            or self.below_vwap(current)
        ):
            score += 10
            reasons.append("VWAP")

        # RSI (10)
        if (
            self.rsi_long_ok(current)
            or self.rsi_short_ok(current)
        ):
            score += 10
            reasons.append("RSI")

        # Volume (15)
        if self.enough_volume(current):
            score += 15
            reasons.append("Volume")

        # Trend Strength (15)
        if self.enough_trend_strength(current):
            score += 15
            reasons.append("Trend Strength")

        # Strong Candle (5)
        if self.strong_candle(current):
            score += 5
            reasons.append("Strong Candle")

        # EMA7 Hold / Reject (5)
        if (
            self.ema_support_holding(previous, current)
            or self.ema_resistance_holding(previous, current)
        ):
            score += 5
            reasons.append("EMA7 Confirmation")

        # EMA25 Confirmation (5)
        if (
            (current["close"] > current["ema_25"] and self.bullish_trend(current))
            or (current["close"] < current["ema_25"] and self.bearish_trend(current))
        ):
            score += 5
            reasons.append("EMA25 Confirmation")

        return score, reasons

    # ---------------------------------------------------------
    # Risk Management
    # ---------------------------------------------------------

    def calculate_trade_levels(
        self,
        side: PositionSide,
        current: pd.Series,
    ) -> tuple[float, float]:
        """
        Calculate ATR based TP and SL.
        """

        entry = float(current["close"])
        atr = float(current["atr"])

        if side == PositionSide.LONG:

            stop_loss = (
                entry
                - (atr * ATR_SL_MULTIPLIER)
            )

            take_profit = (
                entry
                + (atr * ATR_TP_MULTIPLIER)
            )

        else:

            stop_loss = (
                entry
                + (atr * ATR_SL_MULTIPLIER)
            )

            take_profit = (
                entry
                - (atr * ATR_TP_MULTIPLIER)
            )

        return stop_loss, take_profit

    def risk_reward_ratio(
        self,
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> float:

        risk = abs(entry - stop_loss)

        reward = abs(take_profit - entry)

        if risk == 0:
            return 0.0

        return reward / risk

    def trade_allowed(
        self,
        symbol: str,
        side: PositionSide,
        current: pd.Series,
    ) -> bool:
        """
        Final risk validation before opening a trade.
        """

        stop_loss, take_profit = self.calculate_trade_levels(
            side,
            current,
        )

        rr = self.risk_reward_ratio(
            float(current["close"]),
            stop_loss,
            take_profit,
        )

        # Minimum 1.5 Risk/Reward
        if rr < 1.5:
            print(f"❌ RR FAIL : {rr:.2f}")
            return False

        # ATR çok düşükse piyasa sıkışık olabilir
        if current["atr"] <= 0:
            print("❌ ATR FAIL")
            return False

        # Trend gücü çok zayıfsa işlem açma
        if not self.enough_trend_strength(current):
            print(
                f"❌ TRADE BLOCKED : "
                f"Trend={current['trend_strength']:.2f}"
            )
            return False

        return True

    def create_position(
        self,
        symbol: str,
        side: PositionSide,
        current: pd.Series,
    ) -> Position:
        """
        Create a new paper position.
        """

        stop_loss, take_profit = self.calculate_trade_levels(
            side,
            current,
        )

        entry_price = float(current["close"])

        quantity = self.calculate_position_size(
            entry_price,
            stop_loss,
        )

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
        )

        self.positions.append(position)

        self.start_cooldown(symbol)

        return position

    # ---------------------------------------------------------
    # Position Management
    # ---------------------------------------------------------

    def should_close_position(
        self,
        position: Position,
        current: pd.Series,
    ) -> tuple[bool, str]:

        price = float(current["close"])

        # LONG
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

        # SHORT
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

    def close_position(
        self,
        position: Position,
        current: pd.Series,
        reason: str,
    ) -> Position:

        exit_price = float(current["close"])

        # Position.close() sets exit_price, closed_at, status (-> is_open
        # becomes False automatically), exit_reason, pnl and pnl_percent
        # (correctly scaled by quantity) in one consistent place.
        position.close(exit_price, reason)

        print(
            f"🏁 CLOSED | "
            f"{position.symbol} | "
            f"{position.side.name} | "
            f"PnL={position.pnl:.4f} | "
            f"{reason}"
        )

        return position

    def manage_positions(
        self,
        symbols: list[str],
    ) -> None:

        for position in self.open_positions():

            try:

                if position.symbol not in symbols:
                    continue

                current = self.latest(position.symbol)

                close, reason = self.should_close_position(
                    position,
                    current,
                )

                if close:

                    # Only mark the position as closed here. finalize_position()
                    # (journal/learning log + balance update) is called exactly
                    # once, from bot.py, right after the close notification is
                    # sent — calling it here too would double-count PnL and
                    # write duplicate journal rows.
                    self.close_position(
                        position,
                        current,
                        reason,
                    )

            except Exception as error:

                print(f"[POSITION] {position.symbol}: {error}")

    # ---------------------------------------------------------
    # Trade Execution
    # ---------------------------------------------------------

    def evaluate_symbol(
        self,
        symbol: str,
    ) -> Optional[Position]:
        """
        Evaluate one symbol and open a paper position
        if all conditions are satisfied.
        """

        symbol = symbol.upper()

        previous = self.previous(symbol)
        current = self.latest(symbol).copy()

        score, reasons = self.calculate_market_score(
            previous,
            current,
        )
        current["market_score"] = score

        print(
            f"{symbol} | "
            f"Score={score} | "
            f"Reasons={', '.join(reasons)}"
        )

        # Görsel Loglama
        trend = "🟢" if self.bullish_trend(current) else (
            "🔴" if self.bearish_trend(current) else "⚪"
        )
        supertrend = (
            "🟢"
            if current["supertrend_direction"] == 1
            else "🔴"
        )
        vwap = (
            "🟢"
            if current["close"] > current["vwap"]
            else "🔴"
        )

        print(
            f"\n{symbol}"
            f"\n Score : {current['market_score']}"
            f"\n RSI   : {current['rsi']:.1f}"
            f"\n Trend : {current['trend_strength']:.2f}"
            f"\n Vol   : {current['volume_ratio']:.2f}"
            f"\n EMA   : {trend}"
            f"\n ST    : {supertrend}"
            f"\n VWAP  : {vwap}"
        )

        # LONG
        if self.long_signal(symbol, previous, current):

            if self.trade_allowed(
                symbol,
                PositionSide.LONG,
                current,
            ):

                position = self.create_position(
                    symbol,
                    PositionSide.LONG,
                    current,
                )

                position.signal_quality = self.signal_quality(
                    previous,
                    current,
                )

                print(
                    f"✅ OPENED | {symbol} | "
                    f"{position.side.name} | "
                    f"Score={position.market_score} | "
                    f"Conf={position.confidence}"
                )

                return position

        # SHORT
        if self.short_signal(symbol, previous, current):

            if self.trade_allowed(
                symbol,
                PositionSide.SHORT,
                current,
            ):

                position = self.create_position(
                    symbol,
                    PositionSide.SHORT,
                    current,
                )

                position.signal_quality = self.signal_quality(
                    previous,
                    current,
                )

                print(
                    f"✅ OPENED | {symbol} | "
                    f"{position.side.name} | "
                    f"Score={position.market_score} | "
                    f"Conf={position.confidence}"
                )

                return position

        return None

    def scan_market(
        self,
        symbols: list[str],
    ) -> list[Position]:
        """
        Scan all symbols and return
        newly opened positions.
        """

        opened_positions = []

        print(
            "\n"
            "===================================="
        )
        print(
            f"🔍 NEW SCAN : {datetime.utcnow()}"
        )
        print(
            "===================================="
        )

        for symbol in symbols:

            try:

                position = self.evaluate_symbol(symbol)

                if position is not None:
                    
                    print(
                        "\n"
                        "=============================\n"
                        f"🚀 {position.side.name} SIGNAL\n"
                        f"Coin : {symbol}\n"
                        f"Entry: {position.entry_price}\n"
                        f"Score: {position.market_score}\n"
                        f"Conf : {position.confidence}\n"
                        "============================="
                    )
                    
                    opened_positions.append(position)

            except Exception as error:

                print(
                    f"[STRATEGY] {symbol}: {error}"
                )

        print(
            "\n"
            "===================================="
        )

        print(
            f"✅ Scan Finished | Signals : {len(opened_positions)}"
        )

        print(
            "====================================\n"
        )

        return opened_positions

    # ---------------------------------------------------------
    # Journal & Learning
    # ---------------------------------------------------------

    JOURNAL_HEADER = [
        "timestamp", "symbol", "side", "entry_price", "exit_price",
        "stop_loss", "take_profit", "market_score", "confidence",
        "pnl", "pnl_percent", "exit_reason", "status",
    ]

    LEARNING_HEADER = [
        "timestamp", "symbol", "side", "market_score", "confidence",
        "pnl", "pnl_percent", "result", "exit_reason",
    ]

    def _write_csv_row(
        self,
        filename: str,
        header: list[str],
        row: list,
    ) -> None:
        """
        Append a row to a CSV file, writing the header first if the
        file doesn't exist yet (or is empty). Keeping every row on the
        same schema (with blank fields where not applicable) makes the
        file loadable as a single table in pandas/Excel later.
        """

        import os

        file_exists = (
            os.path.exists(filename)
            and os.path.getsize(filename) > 0
        )

        with open(
            filename,
            "a",
            encoding="utf-8",
            newline="",
        ) as file:

            writer = csv.writer(file)

            if not file_exists:
                writer.writerow(header)

            writer.writerow(row)

    def log_new_position(
        self,
        position: Position,
    ) -> None:
        """
        Save newly opened paper trade.
        """

        try:

            self._write_csv_row(
                "journal.csv",
                self.JOURNAL_HEADER,
                [
                    datetime.utcnow().isoformat(),
                    position.symbol,
                    position.side.name,
                    position.entry_price,
                    "",  # exit_price (not known yet)
                    position.stop_loss,
                    position.take_profit,
                    position.market_score,
                    position.confidence,
                    "",  # pnl
                    "",  # pnl_percent
                    "",  # exit_reason
                    "OPEN",
                ],
            )

        except Exception as error:

            print(
                f"[JOURNAL] {error}"
            )

    def log_closed_position(
        self,
        position: Position,
    ) -> None:
        """
        Save closed trade.
        """

        try:

            self._write_csv_row(
                "journal.csv",
                self.JOURNAL_HEADER,
                [
                    datetime.utcnow().isoformat(),
                    position.symbol,
                    position.side.name,
                    position.entry_price,
                    position.exit_price,
                    position.stop_loss,
                    position.take_profit,
                    position.market_score,
                    position.confidence,
                    position.pnl,
                    position.pnl_percent,
                    position.exit_reason,
                    "CLOSED",
                ],
            )

        except Exception as error:

            print(
                f"[JOURNAL] {error}"
            )

    def update_learning_log(
        self,
        position: Position,
    ) -> None:
        """
        Store finished trade for later analysis.
        """

        result = position.result.value

        try:

            self._write_csv_row(
                "learning_log.csv",
                self.LEARNING_HEADER,
                [
                    datetime.utcnow().isoformat(),
                    position.symbol,
                    position.side.name,
                    position.market_score,
                    position.confidence,
                    position.pnl,
                    position.pnl_percent,
                    result,
                    position.exit_reason,
                ],
            )

        except Exception as error:

            print(
                f"[LEARNING] {error}"
            )

    def finalize_position(
        self,
        position: Position,
    ) -> None:
        """
        Save completed trade.
        """

        self.update_balance(
            position
        )

        self.log_closed_position(
            position
        )

        self.update_learning_log(
            position
        )

    # ---------------------------------------------------------
    # Main Loop
    # ---------------------------------------------------------

    def run(
        self,
        symbols: list[str],
    ) -> list[Position]:
        """
        Main strategy execution.
        """

        print(
            "\n========== BOT LOOP =========="
        )

        # Önce mevcut pozisyonları yönet
        self.manage_positions(symbols)

        # Yeni işlemleri tara
        new_positions = self.scan_market(symbols)

        # Açılan işlemleri kaydet
        for position in new_positions:

            self.log_new_position(position)

        print(
            "========== LOOP END ==========\n"
        )

        return new_positions

    def summary(self) -> dict:
        """
        Strategy summary.
        """

        open_positions = self.open_positions()

        return {

            "open_positions": len(open_positions),

            "cooldowns": len(self.cooldowns),

            "total_positions": len(self.positions),

        }

    def reset(self) -> None:
        """
        Reset strategy state.
        """

        self.positions.clear()

        self.cooldowns.clear()

        self.last_signal.clear()
