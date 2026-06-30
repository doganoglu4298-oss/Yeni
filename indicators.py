"""
Trading Bot V6 Professional
indicators.py

Technical indicator calculations.
Compatible with Python 3.11+
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def validate_dataframe(df: pd.DataFrame) -> None:
    """
    Validate required OHLCV columns.
    """

    required = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {', '.join(sorted(missing))}"
        )


def ema(
    series: pd.Series,
    period: int,
) -> pd.Series:
    """
    Exponential Moving Average.
    """

    return (
        series
        .ewm(
            span=period,
            adjust=False
        )
        .mean()
    )


def sma(
    series: pd.Series,
    period: int,
) -> pd.Series:
    """
    Simple Moving Average.
    """

    return (
        series
        .rolling(period)
        .mean()
    )


def rolling_std(
    series: pd.Series,
    period: int,
) -> pd.Series:
    """
    Rolling standard deviation.
    """

    return (
        series
        .rolling(period)
        .std()
    )


def price_change(
    series: pd.Series,
) -> pd.Series:
    """
    Percentage price change.
    """

    return series.pct_change() * 100


def typical_price(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Typical price.
    """

    validate_dataframe(df)

    return (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3


def calculate_ema(
    df: pd.DataFrame,
    period: int,
    column: str = "close",
) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    """

    validate_dataframe(df)

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    return (
        df[column]
        .ewm(
            span=period,
            adjust=False
        )
        .mean()
    )


def calculate_rsi(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI)
    using Wilder's smoothing.
    """

    validate_dataframe(df)

    close = df["close"]

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


def ema_trend(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate all EMA values used by V6.
    """

    df = df.copy()

    df["ema_7"] = calculate_ema(df, 7)
    df["ema_25"] = calculate_ema(df, 25)
    df["ema_50"] = calculate_ema(df, 50)
    df["ema_200"] = calculate_ema(df, 200)

    return df


def ema_alignment_score(
    row: pd.Series,
) -> int:
    """
    EMA alignment score.

    Returns:
        100 = Perfect Bullish
         50 = Mixed
          0 = Perfect Bearish
    """

    bullish = (
        row["ema_7"]
        > row["ema_25"]
        > row["ema_50"]
        > row["ema_200"]
    )

    bearish = (
        row["ema_7"]
        < row["ema_25"]
        < row["ema_50"]
        < row["ema_200"]
    )

    if bullish:
        return 100

    if bearish:
        return 0

    return 50


def calculate_true_range(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Calculate True Range (TR).
    """

    validate_dataframe(df)

    high = df["high"]
    low = df["low"]
    close = df["close"]

    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr


def calculate_atr(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.Series:
    """
    Calculate Average True Range (ATR)
    using Wilder's smoothing.
    """

    tr = calculate_true_range(df)

    atr = tr.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return atr


def calculate_vwap(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Calculate VWAP.

    Uses cumulative volume.
    """

    validate_dataframe(df)

    tp = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3

    cumulative_tp_volume = (
        tp * df["volume"]
    ).cumsum()

    cumulative_volume = (
        df["volume"]
    ).cumsum()

    return (
        cumulative_tp_volume
        / cumulative_volume
    )


def atr_stop_loss(
    entry_price: float,
    atr: float,
    multiplier: float,
    side: str,
) -> float:
    """
    ATR based Stop Loss.
    """

    if side == "LONG":
        return entry_price - (atr * multiplier)

    return entry_price + (atr * multiplier)


def atr_take_profit(
    entry_price: float,
    atr: float,
    multiplier: float,
    side: str,
) -> float:
    """
    ATR based Take Profit.
    """

    if side == "LONG":
        return entry_price + (atr * multiplier)

    return entry_price - (atr * multiplier)


def calculate_supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """
    Calculate Supertrend indicator.

    Returns:
        supertrend
        supertrend_direction
    """

    validate_dataframe(df)

    df = df.copy()

    atr = calculate_atr(df, period)

    hl2 = (df["high"] + df["low"]) / 2

    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()

    for i in range(1, len(df)):

        if (
            basic_upper.iloc[i] < final_upper.iloc[i - 1]
            or df["close"].iloc[i - 1] > final_upper.iloc[i - 1]
        ):
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if (
            basic_lower.iloc[i] > final_lower.iloc[i - 1]
            or df["close"].iloc[i - 1] < final_lower.iloc[i - 1]
        ):
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

    supertrend = pd.Series(index=df.index, dtype="float64")
    direction = pd.Series(index=df.index, dtype="int64")

    supertrend.iloc[0] = final_lower.iloc[0]
    direction.iloc[0] = 1

    for i in range(1, len(df)):

        previous_supertrend = supertrend.iloc[i - 1]

        if previous_supertrend == final_upper.iloc[i - 1]:

            if df["close"].iloc[i] <= final_upper.iloc[i]:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1

        else:

            if df["close"].iloc[i] >= final_lower.iloc[i]:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1
            else:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1

    df["supertrend"] = supertrend
    df["supertrend_direction"] = direction

    return df


def supertrend_signal(df: pd.DataFrame) -> int:
    """
    Returns:
        1  -> Bullish flip
       -1 -> Bearish flip
        0 -> No signal
    """

    if len(df) < 2:
        return 0

    prev = df["supertrend_direction"].iloc[-2]
    curr = df["supertrend_direction"].iloc[-1]

    if prev == -1 and curr == 1:
        return 1

    if prev == 1 and curr == -1:
        return -1

    return 0


def calculate_volume_ratio(
    df: pd.DataFrame,
    period: int = 20,
) -> pd.Series:
    """
    Current volume / average volume.
    """

    validate_dataframe(df)

    avg_volume = (
        df["volume"]
        .rolling(period)
        .mean()
    )

    return (
        df["volume"] / avg_volume
    )


def volume_filter(
    df: pd.DataFrame,
    threshold: float = 1.20,
) -> pd.Series:
    """
    True if volume is above threshold.
    """

    ratio = calculate_volume_ratio(df)

    return ratio >= threshold


def calculate_trend_strength(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Trend strength based on EMA distance.

    Returns approximately 0-100.
    """

    validate_dataframe(df)

    ema7 = calculate_ema(df, 7)
    ema25 = calculate_ema(df, 25)
    ema50 = calculate_ema(df, 50)

    distance = (
        (ema7 - ema50).abs()
        / ema50
    ) * 100

    slope = (
        ema25.diff().abs()
        / ema25
    ) * 100

    strength = (
        distance * 0.7
        + slope * 30
    )

    return strength.clip(0, 100)


def calculate_momentum_score(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Momentum score (0-100)
    based on RSI and price change.
    """

    validate_dataframe(df)

    rsi = calculate_rsi(df)

    change = (
        df["close"]
        .pct_change(5)
        * 100
    )

    score = (
        (rsi - 50).abs()
        + change.abs() * 2
    )

    return score.clip(0, 100)


def market_score(
    row: pd.Series,
) -> int:
    """
    Final market quality score (0-100).

    Used by strategy.py
    """

    score = 0

    if row["ema_7"] > row["ema_25"]:
        score += 20

    if row["ema_25"] > row["ema_50"]:
        score += 20

    if row["ema_50"] > row["ema_200"]:
        score += 20

    if row["volume_ratio"] >= 1.20:
        score += 20

    if row["trend_strength"] >= 25:
        score += 20

    return min(score, 100)


class IndicatorEngine:
    """
    Calculates all indicators required by V6 strategy.
    """

    def __init__(
        self,
        ema_fast: int = 7,
        ema_mid: int = 25,
        ema_slow: int = 50,
        ema_trend: int = 200,
        rsi_period: int = 14,
        atr_period: int = 14,
        supertrend_period: int = 10,
        supertrend_multiplier: float = 3.0,
    ):
        self.ema_fast = ema_fast
        self.ema_mid = ema_mid
        self.ema_slow = ema_slow
        self.ema_trend = ema_trend

        self.rsi_period = rsi_period
        self.atr_period = atr_period

        self.supertrend_period = supertrend_period
        self.supertrend_multiplier = supertrend_multiplier

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        validate_dataframe(df)

        df = df.copy()

        # EMA
        df["ema_7"] = calculate_ema(df, self.ema_fast)
        df["ema_25"] = calculate_ema(df, self.ema_mid)
        df["ema_50"] = calculate_ema(df, self.ema_slow)
        df["ema_200"] = calculate_ema(df, self.ema_trend)

        # RSI
        df["rsi"] = calculate_rsi(
            df,
            self.rsi_period,
        )

        # ATR
        df["atr"] = calculate_atr(
            df,
            self.atr_period,
        )

        # VWAP
        df["vwap"] = calculate_vwap(df)

        # Supertrend
        df = calculate_supertrend(
            df,
            self.supertrend_period,
            self.supertrend_multiplier,
        )

        # Volume
        df["volume_ratio"] = calculate_volume_ratio(df)

        # Trend
        df["trend_strength"] = calculate_trend_strength(df)

        # Momentum
        df["momentum_score"] = calculate_momentum_score(df)

        # EMA Alignment
        df["ema_alignment"] = df.apply(
            ema_alignment_score,
            axis=1,
        )

        # Market Score
        df["market_score"] = df.apply(
            market_score,
            axis=1,
        )

        return df


__all__ = [
    "IndicatorEngine",
    "calculate_ema",
    "calculate_rsi",
    "calculate_atr",
    "calculate_vwap",
    "calculate_supertrend",
    "calculate_volume_ratio",
    "calculate_trend_strength",
    "calculate_momentum_score",
    "market_score",
]
