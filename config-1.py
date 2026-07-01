"""
Trading Bot V6 Professional
Version: 6.0.0
"""

from __future__ import annotations

import os

# ==========================================================
# APP
# ==========================================================

APP_NAME = "Trading Bot V6 Professional"
VERSION = "6.0.0"

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

MIN_VOLUME_RATIO = 1.2
TREND_STRENGTH_THRESHOLD = 25

# ==========================================================
# SIGNAL FILTERS
# ==========================================================

MARKET_SCORE_THRESHOLD = 80
CONFIDENCE_THRESHOLD = 80

# ==========================================================
# RISK MANAGEMENT
# ==========================================================

MAX_CONSECUTIVE_LOSSES = 5
MAX_DAILY_LOSS_PERCENT = 5.0

SL_ATR = 1.5
RR = 2.5

# ==========================================================
# TELEGRAM
# ==========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# ==========================================================
# JOURNAL
# ==========================================================

JOURNAL_FILE = "journal.csv"
LEARNING_LOG_FILE = "learning_log.csv"

# ==========================================================
# COINS
# ==========================================================

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "SUIUSDT",
    "ARBUSDT",
]

# ==========================================================
# POSITION SIZE
# ==========================================================

POSITION_SIZE_MODE = "RISK"
MIN_NOTIONAL = 5.0
MAX_POSITION_PERCENT = 100.0

# ==========================================================
# DATA
# ==========================================================

PRICE_DECIMALS = 6
PERCENT_DECIMALS = 2
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# ==========================================================
# MARKET FILTERS
# ==========================================================

ALLOW_LONG = True
ALLOW_SHORT = True

MIN_ATR_PERCENT = 0.30
MAX_SPREAD_PERCENT = 0.20

# ==========================================================
# TELEGRAM COMMANDS
# ==========================================================

ENABLE_TELEGRAM = True
ENABLE_JOURNAL = True
ENABLE_NOTIFICATIONS = True

# ==========================================================
# LOGGING
# ==========================================================

LOG_LEVEL = "DEBUG" if DEBUG_MODE else "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"

# ==========================================================
# FUTURE (V7 READY)
# ==========================================================

USE_TRAILING_STOP = False
USE_BREAK_EVEN = False
USE_PARTIAL_TP = False
