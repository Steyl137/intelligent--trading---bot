"""Configuration loader – reads from environment / .env file."""

import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default=None, cast=str):
    value = os.getenv(key, default)
    if value is None:
        return None
    return cast(value)


def _get_list(key: str, default: str = "") -> list:
    """Read a comma-separated env var into a list of stripped strings."""
    raw = os.getenv(key, default)
    return [s.strip() for s in raw.split(",") if s.strip()]


class Config:
    # ---------------------------------------------------------------
    # Broker selection
    # ---------------------------------------------------------------
    # "ccxt"  – use ccxt exchange (original behaviour)
    # "deriv" – use Deriv WebSocket API for data + execution
    BROKER: str = _get("BROKER", "ccxt")

    # Data source for historical candles (overrides BROKER for data only)
    # "ccxt" | "deriv" | "mt5"
    DATA_SOURCE: str = _get("DATA_SOURCE", "ccxt")

    # ---------------------------------------------------------------
    # ccxt / generic exchange credentials
    # ---------------------------------------------------------------
    EXCHANGE: str = _get("EXCHANGE", "binance")
    API_KEY: str = _get("API_KEY", "")
    API_SECRET: str = _get("API_SECRET", "")

    # ---------------------------------------------------------------
    # Deriv API credentials
    # ---------------------------------------------------------------
    DERIV_APP_ID: str = _get("DERIV_APP_ID", "1089")   # 1089 = demo app
    DERIV_TOKEN: str = _get("DERIV_TOKEN", "")          # OAuth token

    # ---------------------------------------------------------------
    # MetaTrader 5 credentials (Windows only)
    # ---------------------------------------------------------------
    MT5_LOGIN: int = _get("MT5_LOGIN", 0, int)
    MT5_PASSWORD: str = _get("MT5_PASSWORD", "")
    MT5_SERVER: str = _get("MT5_SERVER", "")

    # ---------------------------------------------------------------
    # Trading mode
    # ---------------------------------------------------------------
    TRADING_MODE: str = _get("TRADING_MODE", "paper")  # "paper" | "live"

    # ---------------------------------------------------------------
    # Market – single symbol (legacy / simple mode)
    # ---------------------------------------------------------------
    SYMBOL: str = _get("SYMBOL", "EUR/USD")
    TIMEFRAME: str = _get("TIMEFRAME", "1h")

    # ---------------------------------------------------------------
    # Multi-symbol forex mode
    # ---------------------------------------------------------------
    # Comma-separated list, e.g. "EUR/USD,GBP/USD,USD/JPY"
    SYMBOLS: list = _get_list("SYMBOLS", "EUR/USD")

    # ---------------------------------------------------------------
    # Strategy
    # ---------------------------------------------------------------
    STRATEGY: str = _get("STRATEGY", "sma_crossover")
    SMA_FAST: int = _get("SMA_FAST", 10, int)
    SMA_SLOW: int = _get("SMA_SLOW", 30, int)

    # ---------------------------------------------------------------
    # Risk management
    # ---------------------------------------------------------------
    MAX_POSITION_PCT: float = _get("MAX_POSITION_PCT", 0.10, float)
    STOP_LOSS_PCT: float = _get("STOP_LOSS_PCT", 0.02, float)
    TAKE_PROFIT_PCT: float = _get("TAKE_PROFIT_PCT", 0.04, float)

    # Deriv multiplier contract leverage (10x, 20x, 50x, …)
    DERIV_MULTIPLIER: int = _get("DERIV_MULTIPLIER", 10, int)

    # ---------------------------------------------------------------
    # Paper trading
    # ---------------------------------------------------------------
    PAPER_BALANCE: float = _get("PAPER_BALANCE", 10_000.0, float)

