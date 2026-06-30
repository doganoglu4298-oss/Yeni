"""
Trading Bot V6 Professional
config.py

Global configuration.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================================
# BINANCE API
# ==========================================================

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# ==========================================================
# BINANCE SETTINGS
# ==========================================================

BINANCE_BASE_URL = "https://fapi.binance.com"

# ==========================================================
# TELEGRAM
# ==========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ==========================================================
# TRADING
# ==========================================================

PAPER_TRADING = True

TIMEFRAME = "15m"

SCAN_INTERVAL = 60

# Hata veren değişken buraya eklendi:
CANDLE_LIMIT = 100 

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "SUIUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "ADAUSDT",
]

# ==========================================================
# EMA SETTINGS
# ==========================================================

EMA_FAST = 7
EMA_MID = 25
EMA_SLOW = 50
EMA_TREND = 200

# ==========================================================
# RSI SETTINGS
# ==========================================================

RSI_PERIOD = 14
RSI_LONG_MIN = 55
RSI_SHORT_MAX = 45
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# ==========================================================
# ATR SETTINGS
# ==========================================================

ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 2.5

# ==========================================================
# VWAP SETTINGS
# ==========================================================

USE_VWAP = True

# ==========================================================
# SUPERTREND SETTINGS
# ==========================================================

SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0
USE_SUPERTREND = True

# ==========================================================
# VOLUME FILTER
# ==========================================================

USE_VOLUME_FILTER = True
VOLUME_MA_PERIOD = 20
MIN_VOLUME_RATIO = 1.20

# ==========================================================
# TREND STRENGTH & MARKET SCORE
# ==========================================================

USE_TREND_STRENGTH = True
TREND_STRENGTH_MIN = 70

USE_MARKET_SCORE = True
MIN_MARKET_SCORE = 70

EMA_SCORE = 20
RSI_SCORE = 15
VWAP_SCORE = 15
SUPERTREND_SCORE = 20
VOLUME_SCORE = 15
TREND_SCORE = 15

MAX_MARKET_SCORE = (
    EMA_SCORE + RSI_SCORE + VWAP_SCORE + SUPERTREND_SCORE + VOLUME_SCORE + TREND_SCORE
)

# ==========================================================
# CONFIDENCE FILTER
# ==========================================================

MIN_CONFIDENCE = 70

# ==========================================================
# SIGNAL FILTERS & POSITION MANAGEMENT
# ==========================================================

ALLOW_LONG = True
ALLOW_SHORT = True
REQUIRE_CANDLE_CLOSE = True

USE_ATR_TP_SL = True
TAKE_PROFIT_PERCENT = 5.0
STOP_LOSS_PERCENT = 2.0
RISK_REWARD_RATIO = 2.5

MAX_OPEN_POSITIONS = 3
ALLOW_MULTIPLE_SAME_SYMBOL = False
POSITION_SIZE_USDT = 100

USE_COOLDOWN = True
COOLDOWN_MINUTES = 30

INITIAL_BALANCE = 1000.0
LEVERAGE = 10
TRADING_FEE = 0.0005
SLIPPAGE = 0.0002

# ==========================================================
# LOGGING & DISPLAY
# ==========================================================

ENABLE_JOURNAL = True
JOURNAL_FILE = "journal.csv"
SAVE_ALL_SIGNALS = True
SAVE_REJECTED_SIGNALS = False

LOG_LEVEL = "INFO"
LOG_FILE = "bot.log"
DEBUG_MODE = False

SHOW_SCAN_RESULT = True
SHOW_MARKET_SCORE = True
SHOW_INDICATOR_VALUES = True

BOT_NAME = "Trading Bot V6 Professional"
BOT_VERSION = "6.0.0"
