"""
Trading Bot V6 Professional
data.py

Handles Binance market data retrieval and preprocessing.
"""

from __future__ import annotations

import time
from typing import Optional

import pandas as pd
import requests

from config import (
    BINANCE_BASE_URL,
    TIMEFRAME,
    CANDLE_LIMIT,
    REQUEST_TIMEOUT,
    RETRY_COUNT,
)

from indicators import IndicatorEngine


class BinanceDataClient:
    """
    Binance Public API client.

    Uses only public market data.
    No API Key required.
    """

    def __init__(
        self,
        base_url: str = BINANCE_BASE_URL,
        timeout: int = REQUEST_TIMEOUT,
        retries: int = RETRY_COUNT,
    ):

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

        self.indicators = IndicatorEngine()

    @property
    def klines_url(self) -> str:
        return f"{self.base_url}/api/v3/klines"

    def _request(
        self,
        url: str,
        params: dict,
    ) -> list:

        last_error = None

        for attempt in range(self.retries):

            try:

                response = requests.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )

                response.raise_for_status()

                return response.json()

            except requests.RequestException as exc:

                last_error = exc

                time.sleep(1)

        raise ConnectionError(
            f"Binance request failed: {last_error}"
        )

    def get_klines(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
        limit: int = CANDLE_LIMIT,
    ) -> list:
        """
        Download raw candle data from Binance.
        """

        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }

        return self._request(
            self.klines_url,
            params,
        )

    def get_dataframe(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
        limit: int = CANDLE_LIMIT,
    ) -> pd.DataFrame:
        """
        Download candles and convert them
        into a clean DataFrame.
        """

        candles = self.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ]

        df = pd.DataFrame(
            candles,
            columns=columns,
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "taker_buy_base",
            "taker_buy_quote",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df["open_time"] = pd.to_datetime(
            df["open_time"],
            unit="ms",
        )

        df["close_time"] = pd.to_datetime(
            df["close_time"],
            unit="ms",
        )

        df.sort_values(
            "open_time",
            inplace=True,
        )

        df.reset_index(
            drop=True,
            inplace=True,
        )

        return df

    def validate_dataframe(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Validate OHLCV dataframe before
        indicator calculations.
        """

        required_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for column in required_columns:

            if column not in df.columns:
                raise ValueError(
                    f"Missing column: {column}"
                )

        if len(df) < 250:
            raise ValueError(
                "Not enough candles."
            )

    def clean_dataframe(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Remove invalid rows and
        prepare dataframe.
        """

        df = df.copy()

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for column in numeric_columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df.dropna(inplace=True)

        df = df[
            (df["volume"] > 0)
            &
            (df["high"] >= df["low"])
            &
            (df["high"] >= df["close"])
            &
            (df["high"] >= df["open"])
            &
            (df["low"] <= df["close"])
            &
            (df["low"] <= df["open"])
        ]

        df.reset_index(
            drop=True,
            inplace=True,
        )

        self.validate_dataframe(df)

        return df

    def get_clean_dataframe(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
        limit: int = CANDLE_LIMIT,
    ) -> pd.DataFrame:
        """
        Download + clean market data.
        """

        df = self.get_dataframe(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        return self.clean_dataframe(df)

    def get_market_data(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
        limit: int = CANDLE_LIMIT,
    ) -> pd.DataFrame:
        """
        Download, clean and calculate
        all technical indicators.
        """

        df = self.get_clean_dataframe(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        df = self.indicators.calculate(df)

        return df

    def get_latest_candle(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
    ) -> pd.Series:
        """
        Return latest candle with
        all indicators calculated.
        """

        df = self.get_market_data(
            symbol=symbol,
            interval=interval,
            limit=CANDLE_LIMIT,
        )

        return df.iloc[-1]

    def get_previous_candle(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
    ) -> pd.Series:
        """
        Return previous candle.
        """

        df = self.get_market_data(
            symbol=symbol,
            interval=interval,
            limit=CANDLE_LIMIT,
        )

        return df.iloc[-2]

    def get_last_two_candles(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
    ) -> tuple[pd.Series, pd.Series]:
        """
        Return previous and latest candle.
        """

        df = self.get_market_data(
            symbol=symbol,
            interval=interval,
            limit=CANDLE_LIMIT,
        )

        return (
            df.iloc[-2],
            df.iloc[-1],
        )

    def has_enough_data(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
    ) -> bool:
        """
        Check if enough candles exist.
        """

        try:

            df = self.get_dataframe(
                symbol=symbol,
                interval=interval,
                limit=CANDLE_LIMIT,
            )

            return len(df) >= 250

        except Exception:
            return False

    def normalize_symbol(
        self,
        symbol: str,
    ) -> str:
        """
        Normalize trading symbol.
        """

        symbol = symbol.upper().strip()

        if not symbol.endswith("USDT"):
            symbol += "USDT"

        return symbol

    def get_market_dataframe(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Shortcut for strategy.py
        """

        symbol = self.normalize_symbol(symbol)

        return self.get_market_data(
            symbol=symbol,
            interval=TIMEFRAME,
            limit=CANDLE_LIMIT,
        )

    def get_multiple_markets(
        self,
        symbols: list[str],
    ) -> dict[str, pd.DataFrame]:
        """
        Download multiple markets.
        """

        markets = {}

        for symbol in symbols:

            try:

                symbol = self.normalize_symbol(symbol)

                markets[symbol] = (
                    self.get_market_dataframe(symbol)
                )

            except Exception as error:

                print(
                    f"[DATA] {symbol}: {error}"
                )

        return markets

    def latest_price(
        self,
        symbol: str,
    ) -> float:
        """
        Return latest close price.
        """

        df = self.get_market_dataframe(symbol)

        return float(df.iloc[-1]["close"])

    def latest_volume(
        self,
        symbol: str,
    ) -> float:
        """
        Return latest volume.
        """

        df = self.get_market_dataframe(symbol)

        return float(df.iloc[-1]["volume"])

    def market_snapshot(
        self,
        symbol: str,
    ) -> dict:
        """
        Returns latest indicator snapshot.
        """

        row = self.get_latest_candle(symbol)

        return {

            "symbol": symbol,

            "price": float(row["close"]),

            "ema7": float(row["ema_7"]),
            "ema25": float(row["ema_25"]),
            "ema50": float(row["ema_50"]),
            "ema200": float(row["ema_200"]),

            "rsi": float(row["rsi"]),

            "atr": float(row["atr"]),

            "vwap": float(row["vwap"]),

            "volume_ratio": float(
                row["volume_ratio"]
            ),

            "trend_strength": float(
                row["trend_strength"]
            ),

            "market_score": int(
                row["market_score"]
            ),

            "supertrend": int(
                row["supertrend_direction"]
            ),
        }


class DataManager:
    """
    Simple cache layer for market data.
    Reduces unnecessary API requests.
    """

    def __init__(self):
        self.client = BinanceDataClient()
        self.cache: dict[str, pd.DataFrame] = {}
        self.btc_cache = None
        self.btc_cache_time = None

    def refresh(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        symbol = self.client.normalize_symbol(symbol)

        df = self.client.get_market_dataframe(symbol)

        self.cache[symbol] = df

        return df

    def get(
        self,
        symbol: str,
        refresh: bool = False,
    ) -> pd.DataFrame:

        symbol = self.client.normalize_symbol(symbol)

        if (
            refresh
            or symbol not in self.cache
        ):

            return self.refresh(symbol)

        return self.cache[symbol]

    def latest(
        self,
        symbol: str,
    ) -> pd.Series:

        return self.get(symbol, refresh=True).iloc[-1]

    def previous(
        self,
        symbol: str,
    ) -> pd.Series:

        return self.get(symbol, refresh=True).iloc[-2]


    def last_two(
        self,
        symbol: str,
    ) -> tuple[pd.Series, pd.Series]:

        df = self.get(symbol, refresh=True)

        return (
            df.iloc[-2],
            df.iloc[-1],
        )

    def btc_market(
        self,
        refresh: bool = False,
    ) -> pd.DataFrame:
        from datetime import datetime, timedelta

        if (
            self.btc_cache is None
            or refresh
            or self.btc_cache_time is None
            or datetime.utcnow() - self.btc_cache_time > timedelta(minutes=1)
        ):
            self.btc_cache = self.client.get_market_dataframe("BTCUSDT")
            self.btc_cache_time = datetime.utcnow()

        return self.btc_cache

    def clear(self) -> None:
        """
        Clear cached data.
        """

        self.cache.clear()


__all__ = [
    "BinanceDataClient",
    "DataManager",
]
