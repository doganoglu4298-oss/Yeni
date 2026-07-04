# Trading Bot V6 Professional

## Overview

Trading Bot V6 Professional is a modular cryptocurrency trading bot designed for Binance Futures Paper Trading. It is optimized for Railway deployment and focuses on reliable signal generation, disciplined risk management, and long-term strategy improvement.

## Features

- EMA 7 / 25 / 50 / 200 Trend Analysis
- RSI Filter
- ATR-based Stop Loss & Take Profit
- VWAP Filter
- Supertrend Confirmation
- Volume Filter
- Trend Strength Filter
- Dynamic Market Score
- LONG & SHORT Signal Detection
- Cooldown System
- Maximum Open Position Protection
- Paper Trading
- Telegram Notifications
- Trade Journal
- Learning Log
- Railway Ready

## Project Structure

```
trading-bot-v6/
│
├── config.py
├── models.py
├── indicators.py
├── data.py
├── strategy.py
├── telegram_bot.py
├── bot.py
├── requirements.txt
├── .gitignore
├── README.md
├── journal.csv
└── learning_log.csv
```

## Installation

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file and add:

```
BINANCE_API_KEY=YOUR_API_KEY
BINANCE_API_SECRET=YOUR_API_SECRET
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

## Run

```bash
python bot.py
```

## Deployment

This project is designed to run on Railway.

## Version

Trading Bot V6 Professional

## License

Personal Use Only
