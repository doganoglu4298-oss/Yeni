"""
Trading Bot V6 Professional - Optimized V6.1 (Kalite + Sinyal Dengesi)
"""

from __future__ import annotations
import os

# ==========================================================
# APP
# ==========================================================

APP_NAME = "Trading Bot V6 Professional"
VERSION = "6.1.0"

DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"

# ==========================================================
# BINANCE
# ==========================================================

BINANCE_BASE_URL = "https://api.binance.com"

TIMEFRAME = "15m"
CANDLE_LIMIT = 500

REQUEST_TIMEOUT = 15
RETRY_COUNT = 3

SCAN_INTERVAL = 30

# ==========================================================
# PAPER ACCOUNT
# ==========================================================

PAPER_MODE = True
INITIAL_BALANCE = 1000.0
USE_COMPOUND = True
RISK_PER_TRADE = 0.02
LEVERAGE = 5
TRADING_FEE = 0.0004
SLIPPAGE = 0.0002

# ==========================================================
# POSITION MANAGEMENT
# ==========================================================

MAX_OPEN_POSITIONS = 2
COOLDOWN_CANDLES = 4

# ==========================================================
# INDICATORS
# ==========================================================

EMA_FAST = 7
EMA_MID = 25
EMA_SLOW = 50
EMA_TREND = 200

RSI_PERIOD = 14
ATR_PERIOD = 14
VWAP_PERIOD = 20

SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

MIN_VOLUME_RATIO = 0.70
TREND_STRENGTH_THRESHOLD = 8

# ==========================================================
# SIGNAL FILTERS (Dengeli - Kalite + Fırsat)
# ==========================================================

MARKET_SCORE_THRESHOLD = 60
CONFIDENCE_THRESHOLD = 60

# ==========================================================
# RISK MANAGEMENT
# ==========================================================

MAX_DAILY_TRADES = 10
MAX_CONSECUTIVE_LOSSES = 3
MAX_DAILY_LOSS_PERCENT = 5.0

SL_ATR = 1.5
RR = 2.5

# ==========================================================
# TELEGRAM
# ==========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ==========================================================
# JOURNAL
# ==========================================================

JOURNAL_FILE = "journal.csv"
LEARNING_LOG_FILE = "learning_log.csv"

# ==========================================================
# COINS
# ==========================================================

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "LINKUSDT", "AVAXUSDT", "SUIUSDT", "ARBUSDT",
]

# ==========================================================
# POSITION SIZING
# ==========================================================

POSITION_SIZE_MODE = "RISK"
MIN_NOTIONAL = 5.0
MAX_POSITION_PERCENT = 100.0

# ==========================================================
# V7 SETTINGS (Smart Exit)
# ==========================================================

ENABLE_BTC_FILTER = True
ENABLE_BREAK_EVEN = True
BREAK_EVEN_ATR = 1.0
ENABLE_TRAILING_STOP = True
TRAILING_STOP_ATR = 1.8
ENABLE_PARTIAL_TP = False
PARTIAL_TP_PERCENT = 50

# STRATEGY COMPATIBILITY
MIN_MARKET_SCORE = MARKET_SCORE_THRESHOLD
MIN_CONFIDENCE = CONFIDENCE_THRESHOLD
ATR_SL_MULTIPLIER = SL_ATR
ATR_TP_MULTIPLIER = RR

# Cooldown
_tf_value = int(TIMEFRAME[:-1])
_tf_unit = TIMEFRAME[-1].lower()
_tf_in_minutes = _tf_value * 60 if _tf_unit == 'h' else _tf_value
COOLDOWN_MINUTES = COOLDOWN_CANDLES * _tf_in_minutes
