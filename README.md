# Intelligent Trading Bot

A modular, extensible Python trading bot that supports **paper** and **live** trading across multiple forex pairs using either [ccxt](https://github.com/ccxt/ccxt), the [Deriv WebSocket API](https://developers.deriv.com), or [MetaTrader 5](https://www.metatrader5.com) as data / execution backends.

---

## Features

| Module | Description |
|---|---|
| **Data – ccxt** | OHLCV candles & tickers from 100+ crypto exchanges |
| **Data – Deriv** | Real-time OHLCV via Deriv WebSocket API (`frxEURUSD`, …) |
| **Data – MT5** | Historical candles from a local MetaTrader 5 terminal (Windows) |
| **Strategy** | Pluggable strategy engine; SMA crossover bundled |
| **Risk Manager** | Portfolio-% position sizing, stop-loss & take-profit |
| **Executor – Paper** | Simulated execution with shared portfolio balance |
| **Executor – Deriv** | Multiplier contracts (MULTUP / MULTDOWN) via Deriv API |
| **Executor – ccxt** | Live market orders via any ccxt exchange |
| **Multi-bot** | Trade several forex pairs simultaneously in one process |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env – set TRADING_MODE=paper to stay safe

# 3. Single-symbol step
python main.py --mode step

# 4. Multi-pair continuous run
python main.py --mode run --symbols "EUR/USD,GBP/USD,USD/JPY,AUD/USD" --interval 3600

# 5. Portfolio summary
python main.py --mode summary
```

---

## Broker / Data-source Combinations

| `BROKER` | `DATA_SOURCE` | Where data comes from | Where orders go |
|---|---|---|---|
| `ccxt` | `ccxt` | ccxt exchange (original) | ccxt exchange |
| `deriv` | `deriv` | Deriv WebSocket | Deriv multiplier contracts |
| `deriv` | `mt5` | Local MT5 terminal | Deriv multiplier contracts |
| `paper` (any) | any | same as above | simulated paper executor |

---

## Project Structure

```
intelligent-trading-bot/
├── config/
│   └── settings.py              # Env-based configuration
├── trading_bot/
│   ├── bot.py                   # Single-symbol orchestrator
│   ├── multi_bot.py             # Multi-symbol orchestrator
│   ├── data/
│   │   ├── fetcher.py           # ccxt OHLCV fetcher
│   │   ├── deriv_fetcher.py     # Deriv WebSocket fetcher
│   │   └── mt5_fetcher.py       # MetaTrader 5 fetcher
│   ├── strategy/
│   │   ├── base.py              # BaseStrategy + Signal types
│   │   └── sma_crossover.py     # SMA crossover strategy
│   ├── risk/
│   │   └── manager.py           # Position sizing & risk checks
│   └── execution/
│       ├── executor.py          # Paper & ccxt-live executors
│       └── deriv_executor.py    # Deriv multiplier executor
├── tests/                       # Pytest test suite (47 tests)
├── main.py                      # CLI entry point
├── requirements.txt
└── .env.example
```

---

## Configuration (`.env`)

### Core

| Variable | Default | Description |
|---|---|---|
| `BROKER` | `ccxt` | `ccxt` or `deriv` |
| `DATA_SOURCE` | `ccxt` | `ccxt`, `deriv`, or `mt5` |
| `TRADING_MODE` | `paper` | `paper` or `live` |

### Deriv API

Register at <https://app.deriv.com/account/api-token>.

| Variable | Default | Description |
|---|---|---|
| `DERIV_APP_ID` | `1089` | Your Deriv app ID (1089 = demo) |
| `DERIV_TOKEN` | _(empty)_ | OAuth token (required for live trading) |
| `DERIV_MULTIPLIER` | `10` | Contract leverage (10×, 20×, 50×) |

### MetaTrader 5 (Windows only)

Install: `pip install MetaTrader5`

| Variable | Default | Description |
|---|---|---|
| `MT5_LOGIN` | `0` | MT5 account number |
| `MT5_PASSWORD` | _(empty)_ | MT5 password |
| `MT5_SERVER` | _(empty)_ | Broker server, e.g. `MetaQuotes-Demo` |

### Multi-symbol

| Variable | Default | Description |
|---|---|---|
| `SYMBOLS` | `EUR/USD` | Comma-separated pairs, e.g. `EUR/USD,GBP/USD,USD/JPY` |
| `TIMEFRAME` | `1h` | Candle interval: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d` |

### Strategy & Risk

| Variable | Default | Description |
|---|---|---|
| `STRATEGY` | `sma_crossover` | Strategy name |
| `SMA_FAST` / `SMA_SLOW` | `10` / `30` | SMA periods |
| `MAX_POSITION_PCT` | `0.10` | Max 10% of portfolio per trade |
| `STOP_LOSS_PCT` | `0.02` | 2% stop-loss |
| `TAKE_PROFIT_PCT` | `0.04` | 4% take-profit |
| `PAPER_BALANCE` | `10000` | Starting paper-trade balance |

---

## Deriv Forex Symbols

The Deriv API uses `frx`-prefixed symbols internally.  The bot converts automatically:

| Standard | Deriv |
|---|---|
| `EUR/USD` | `frxEURUSD` |
| `GBP/USD` | `frxGBPUSD` |
| `USD/JPY` | `frxUSDJPY` |
| `AUD/USD` | `frxAUDUSD` |
| `USD/CAD` | `frxUSDCAD` |
| `USD/CHF` | `frxUSDCHF` |
| `NZD/USD` | `frxNZDUSD` |

---

## Running Tests

```bash
pytest tests/ -v   # 47 tests, all passing
```

---

## Adding a New Strategy

1. Create `trading_bot/strategy/my_strategy.py` subclassing `BaseStrategy`.
2. Implement `generate_signal(df) -> TradeSignal`.
3. Register in `trading_bot/strategy/__init__.py`'s `_REGISTRY`.
4. Set `STRATEGY=my_strategy` in `.env`.

---

## Disclaimer

This project is for **educational purposes only**. Use live trading at your own risk. Always test thoroughly in paper mode first.
