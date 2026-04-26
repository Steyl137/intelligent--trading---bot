"""Configuration loader – reads from environment / .env file."""

import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default=None, cast=str):
    value = os.getenv(key, default)
    if value is None:
        return None
    return cast(value)


class Config:
    # Exchange
    EXCHANGE: str = _get("EXCHANGE", "binance")
    API_KEY: str = _get("API_KEY", "")
    API_SECRET: str = _get("API_SECRET", "")

    # Mode
    TRADING_MODE: str = _get("TRADING_MODE", "paper")  # "paper" | "live"

    # Market
    SYMBOL: str = _get("SYMBOL", "BTC/USDT")
    TIMEFRAME: str = _get("TIMEFRAME", "1h")

    # Strategy
    STRATEGY: str = _get("STRATEGY", "sma_crossover")
    SMA_FAST: int = _get("SMA_FAST", 10, int)
    SMA_SLOW: int = _get("SMA_SLOW", 30, int)

    # Risk
    MAX_POSITION_PCT: float = _get("MAX_POSITION_PCT", 0.10, float)
    STOP_LOSS_PCT: float = _get("STOP_LOSS_PCT", 0.02, float)
    TAKE_PROFIT_PCT: float = _get("TAKE_PROFIT_PCT", 0.04, float)

    # Paper trading
    PAPER_BALANCE: float = _get("PAPER_BALANCE", 10_000.0, float)
