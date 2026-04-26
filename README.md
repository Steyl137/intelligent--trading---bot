# Intelligent Trading Bot

A modular, extensible Python trading bot supporting **paper** and **live** trading on crypto exchanges via [ccxt](https://github.com/ccxt/ccxt).

---

## Features

| Module | Description |
|---|---|
| **Data** | Fetches OHLCV candles & tickers from 100+ exchanges |
| **Strategy** | Pluggable strategy engine (SMA crossover included) |
| **Risk Manager** | Position sizing, stop-loss, and take-profit |
| **Executor** | Paper trading simulator + live order routing |
| **Bot** | Orchestrates a full trading cycle |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env – set TRADING_MODE=paper to stay safe

# 3. Run a single step
python main.py --mode step

# 4. Run continuously (default 1-hour interval)
python main.py --mode run --interval 3600
```

---

## Project Structure

```
intelligent-trading-bot/
├── config/
│   └── settings.py          # Env-based configuration
├── trading_bot/
│   ├── bot.py               # Main orchestrator
│   ├── data/
│   │   └── fetcher.py       # ccxt-backed OHLCV fetcher
│   ├── strategy/
│   │   ├── base.py          # BaseStrategy + Signal types
│   │   └── sma_crossover.py # SMA crossover implementation
│   ├── risk/
│   │   └── manager.py       # Position sizing & risk checks
│   └── execution/
│       └── executor.py      # Paper & live executors
├── tests/                   # Pytest test suite
├── main.py                  # CLI entry point
├── requirements.txt
└── .env.example
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `EXCHANGE` | `binance` | Any ccxt-supported exchange |
| `API_KEY` / `API_SECRET` | _(empty)_ | Required for live trading |
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `SYMBOL` | `BTC/USDT` | Trading pair |
| `TIMEFRAME` | `1h` | Candle timeframe |
| `STRATEGY` | `sma_crossover` | Strategy name |
| `SMA_FAST` / `SMA_SLOW` | `10` / `30` | SMA periods |
| `MAX_POSITION_PCT` | `0.10` | Max 10% of portfolio per trade |
| `STOP_LOSS_PCT` | `0.02` | 2% stop-loss |
| `TAKE_PROFIT_PCT` | `0.04` | 4% take-profit |
| `PAPER_BALANCE` | `10000` | Starting paper-trade balance |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Adding a New Strategy

1. Create `trading_bot/strategy/my_strategy.py` subclassing `BaseStrategy`.
2. Implement `generate_signal(df) -> TradeSignal`.
3. Register it in `trading_bot/strategy/__init__.py`'s `_REGISTRY`.
4. Set `STRATEGY=my_strategy` in `.env`.

---

## Disclaimer

This project is for **educational purposes only**. Use live trading at your own risk. Always test thoroughly in paper mode first.
