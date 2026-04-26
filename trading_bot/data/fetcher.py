"""Market data fetcher backed by ccxt."""

from __future__ import annotations

import logging
from typing import Optional

import ccxt
import pandas as pd

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches OHLCV data from a ccxt-compatible exchange."""

    def __init__(self, exchange_id: str, api_key: str = "", api_secret: str = ""):
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        self._exchange: ccxt.Exchange = exchange_class(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
            }
        )
        logger.info("Initialized exchange: %s", exchange_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
        since: Optional[int] = None,
    ) -> pd.DataFrame:
        """Return a DataFrame with columns [timestamp, open, high, low, close, volume]."""
        raw = self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, since=since)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        logger.debug("Fetched %d candles for %s/%s", len(df), symbol, timeframe)
        return df

    def fetch_ticker(self, symbol: str) -> dict:
        """Return latest ticker information."""
        return self._exchange.fetch_ticker(symbol)

    def fetch_balance(self) -> dict:
        """Return account balance (requires authenticated exchange)."""
        return self._exchange.fetch_balance()
