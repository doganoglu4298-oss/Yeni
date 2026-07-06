"""
Trading Bot V6 Professional
data.py

Handles Binance market data retrieval and preprocessing.
Optimized with Smart Caching to prevent redundant API calls.
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
    VWAP_PERIOD,
)

from indicators import IndicatorEngine


# ---------------------------------------------------------
# Timeframe Helper
# ---------------------------------------------------------

def _get_timeframe_seconds() -> int:
    """
    Convert config TIMEFRAME (e.g., '15m', '1h') to seconds.
    Used for smart caching logic.
    """
    try:
        val = int(TIMEFRAME[:-1])
        unit = TIMEFRAME[-1].lower()
        if unit == 'm': return val * 60
        if unit == 'h': return val * 3600
        if unit == 'd': return val * 86400
    except Exception:
        pass
    return 900  # Default fallback: 15 minutes


class BinanceDataClient:
    """
    Binance Public API client.
    Uses only public market data. No API Key required.
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

        self.indicators = IndicatorEngine(vwap_period=VWAP_PERIOD)

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
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        return self._request(self.klines_url, params)

    def get_dataframe(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
        limit: int = CANDLE_LIMIT,
    ) -> pd.DataFrame:

        candles = self.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        columns = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ]

        df = pd.DataFrame(candles, columns=columns)

        numeric_columns = [
            "open", "high", "low", "close", "volume",
            "quote_asset_volume", "taker_buy_base", "taker_buy_quote",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        df.sort_values("open_time", inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    def has_enough_data(
        self,
        symbol: str,
        minimum: int = 250,
    ) -> bool:
        """
        Startup check: does this symbol return enough candles to
        safely compute the slower indicators (EMA200 etc.)? Returns
        False instead of raising on any fetch/parsing problem, so one
        bad symbol doesn't crash the whole startup sequence — bot.py's
        validate_market_data() just logs a warning and continues.
        """

        try:
            df = self.get_dataframe(
                symbol=symbol,
                interval=TIMEFRAME,
                limit=CANDLE_LIMIT,
            )
            return len(df) >= minimum
        except Exception:
            return False

    def validate_dataframe(self, df: pd.DataFrame) -> None:
        required_columns = ["open", "high", "low", "close", "volume"]
        for column in required_columns:
            if column not in df.columns:
                raise ValueError(f"Missing column: {column}")

        if len(df) < 250:
            raise ValueError("Not enough candles.")

    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        numeric_columns = ["open", "high", "low", "close", "volume"]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df.dropna(inplace=True)

        df = df[
            (df["volume"] > 0) &
            (df["high"] >= df["low"]) &
            (df["high"] >= df["close"]) &
            (df["high"] >= df["open"]) &
            (df["low"] <= df["close"]) &
            (df["low"] <= df["open"])
        ]

        df.reset_index(drop=True, inplace=True)
        self.validate_dataframe(df)

        return df

    def get_clean_dataframe(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
        limit: int = CANDLE_LIMIT,
    ) -> pd.DataFrame:
        df = self.get_dataframe(symbol=symbol, interval=interval, limit=limit)
        return self.clean_dataframe(df)

    def get_market_data(
        self,
        symbol: str,
        interval: str = TIMEFRAME,
        limit: int = CANDLE_LIMIT,
    ) -> pd.DataFrame:
        df = self.get_clean_dataframe(symbol=symbol, interval=interval, limit=limit)
        df = self.indicators.calculate(df)
        return df

    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.upper().strip()
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        return symbol

    def get_market_dataframe(self, symbol: str) -> pd.DataFrame:
        symbol = self.normalize_symbol(symbol)
        return self.get_market_data(symbol=symbol, interval=TIMEFRAME, limit=CANDLE_LIMIT)


class DataManager:
    """
    Smart cache layer for market data.
    Prevents redundant API calls and heavy indicator recalculations
    within the same candle timeframe.
    """

    def __init__(self):
        self.client = BinanceDataClient()
        
        # Cache structure: { symbol: (fetch_timestamp, dataframe) }
        self.cache: dict[str, tuple[float, pd.DataFrame]] = {}
        
        # BTC specific cache (1 min TTL)
        self.btc_cache: Optional[pd.DataFrame] = None
        self.btc_cache_time: Optional[float] = None
        
        # Timeframe in seconds for smart caching
        self._tf_seconds = _get_timeframe_seconds()

    def get(
        self,
        symbol: str,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Get market data. Uses cache if data is fresh (within current candle).
        """
        symbol = self.client.normalize_symbol(symbol)
        current_time = time.time()

        # Check if we have valid cached data
        if not refresh and symbol in self.cache:
            fetch_time, df = self.cache[symbol]
            
            # If fetched less than timeframe seconds ago, use cache
            if (current_time - fetch_time) < self._tf_seconds:
                return df

        # Fetch new data and update cache
        df = self.client.get_market_dataframe(symbol)
        self.cache[symbol] = (current_time, df)
        
        return df

    def refresh(self, symbol: str) -> pd.DataFrame:
        """Force refresh data from API."""
        symbol = self.client.normalize_symbol(symbol)
        df = self.client.get_market_dataframe(symbol)
        self.cache[symbol] = (time.time(), df)
        return df

    def latest(self, symbol: str) -> pd.Series:
        return self.get(symbol).iloc[-1]

    def previous(self, symbol: str) -> pd.Series:
        return self.get(symbol).iloc[-2]

    def last_two(self, symbol: str) -> tuple[pd.Series, pd.Series]:
        """
        Optimized method to get both previous and latest candles 
        in a single API call / cache hit.
        """
        df = self.get(symbol)
        return df.iloc[-2], df.iloc[-1]

    def btc_market(self, refresh: bool = False) -> pd.DataFrame:
        from datetime import datetime, timedelta

        current_time = time.time()
        
        # Refresh BTC cache if it's older than 60 seconds
        if (
            self.btc_cache is None 
            or refresh 
            or self.btc_cache_time is None 
            or (current_time - self.btc_cache_time) > 60
        ):
            self.btc_cache = self.client.get_market_dataframe("BTCUSDT")
            self.btc_cache_time = current_time

        return self.btc_cache

    def clear(self) -> None:
        self.cache.clear()
        self.btc_cache = None
        self.btc_cache_time = None


__all__ = [
    "BinanceDataClient",
    "DataManager",
]
