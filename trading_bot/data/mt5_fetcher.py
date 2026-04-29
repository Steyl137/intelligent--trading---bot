"""MetaTrader 5 historical data fetcher.

Wraps the ``MetaTrader5`` Python package to pull OHLCV candle history from a
locally installed MT5 terminal.

**Platform note**: The MetaTrader5 package only works on Windows.  On other
platforms (Linux/macOS) the import will fail gracefully and
:meth:`MT5Fetcher.fetch_ohlcv` will raise :exc:`RuntimeError`.

Symbol mapping
--------------
Standard "EUR/USD" → MT5 "EURUSD"

Timeframe mapping
-----------------
``"1m"``   → ``TIMEFRAME_M1``
``"5m"``   → ``TIMEFRAME_M5``
``"15m"``  → ``TIMEFRAME_M15``
``"30m"``  → ``TIMEFRAME_M30``
``"1h"``   → ``TIMEFRAME_H1``
``"4h"``   → ``TIMEFRAME_H4``
``"1d"``   → ``TIMEFRAME_D1``
``"1w"``   → ``TIMEFRAME_W1``
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Lazily resolved MT5 module reference – may stay None on non-Windows
_mt5 = None
_MT5_AVAILABLE = False


def _load_mt5():
    """Attempt to import MetaTrader5; set module-level flags."""
    global _mt5, _MT5_AVAILABLE
    if _mt5 is not None:
        return
    try:
        import MetaTrader5 as mt5  # type: ignore[import]
        _mt5 = mt5
        _MT5_AVAILABLE = True
    except ImportError:
        logger.warning(
            "MetaTrader5 package not available (Windows-only). "
            "MT5Fetcher will raise RuntimeError on use."
        )


# Timeframe string → MT5 constant name (resolved lazily)
_TF_MAP: dict[str, str] = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "8h": "TIMEFRAME_H8",
    "1d": "TIMEFRAME_D1",
    "1w": "TIMEFRAME_W1",
}


def _to_mt5_symbol(symbol: str) -> str:
    """Convert 'EUR/USD' → 'EURUSD'."""
    return symbol.replace("/", "")


def _to_mt5_timeframe(timeframe: str):
    """Return the MT5 TIMEFRAME_* constant for *timeframe* string."""
    tf_name = _TF_MAP.get(timeframe)
    if tf_name is None:
        raise ValueError(
            f"Unknown timeframe '{timeframe}'. Supported: {list(_TF_MAP)}"
        )
    return getattr(_mt5, tf_name)


class MT5Fetcher:
    """Fetches historical OHLCV data from a local MetaTrader 5 terminal.

    Parameters
    ----------
    login:
        MT5 account number (0 to use currently logged-in account).
    password:
        MT5 account password.
    server:
        MT5 broker server name (e.g. ``"MetaQuotes-Demo"``).
    """

    def __init__(
        self,
        login: int = 0,
        password: str = "",
        server: str = "",
    ):
        _load_mt5()
        self._login = login
        self._password = password
        self._server = server
        self._initialized = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if not _MT5_AVAILABLE:
            raise RuntimeError(
                "MetaTrader5 package is not installed. "
                "Install it with: pip install MetaTrader5  (Windows only)"
            )
        if self._initialized:
            return

        kwargs: dict = {}
        if self._login:
            kwargs["login"] = self._login
        if self._password:
            kwargs["password"] = self._password
        if self._server:
            kwargs["server"] = self._server

        if not _mt5.initialize(**kwargs):
            error = _mt5.last_error()
            raise RuntimeError(f"MT5 initialize() failed: {error}")

        self._initialized = True
        logger.info("MT5Fetcher connected (login=%s, server=%s)", self._login, self._server)

    def shutdown(self) -> None:
        """Disconnect from MT5 terminal."""
        if _MT5_AVAILABLE and self._initialized:
            _mt5.shutdown()
            self._initialized = False

    # ------------------------------------------------------------------
    # Public API  (mirrors DataFetcher interface)
    # ------------------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
        since: Optional[int] = None,
    ) -> pd.DataFrame:
        """Return a DataFrame [open, high, low, close, volume] indexed by UTC timestamp.

        Parameters
        ----------
        symbol:
            Standard pair notation, e.g. ``"EUR/USD"``.
        timeframe:
            Candle interval string, e.g. ``"1h"``, ``"15m"``.
        limit:
            Maximum number of candles to return.
        since:
            Optional Unix epoch (seconds) for range start; ignored when None.
        """
        self._ensure_connected()
        mt5_symbol = _to_mt5_symbol(symbol)
        mt5_tf = _to_mt5_timeframe(timeframe)

        if since is not None:
            utc_from = datetime.fromtimestamp(since, tz=timezone.utc)
            rates = _mt5.copy_rates_from(mt5_symbol, mt5_tf, utc_from, limit)
        else:
            rates = _mt5.copy_rates_from_pos(mt5_symbol, mt5_tf, 0, limit)

        if rates is None or len(rates) == 0:
            error = _mt5.last_error()
            raise RuntimeError(
                f"MT5 copy_rates failed for {mt5_symbol}: {error}"
            )

        df = pd.DataFrame(rates)
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.set_index("timestamp", inplace=True)
        df = df.rename(columns={"tick_volume": "volume"})
        df = df[["open", "high", "low", "close", "volume"]].astype(float)

        logger.debug("MT5Fetcher: %d candles for %s/%s", len(df), symbol, timeframe)
        return df

    def fetch_ticker(self, symbol: str) -> dict:
        """Return latest bid/ask for *symbol* using MT5 symbol_info_tick."""
        self._ensure_connected()
        mt5_symbol = _to_mt5_symbol(symbol)
        tick = _mt5.symbol_info_tick(mt5_symbol)
        if tick is None:
            raise RuntimeError(f"MT5 symbol_info_tick failed for {mt5_symbol}")
        return {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "last": (tick.bid + tick.ask) / 2,
            "timestamp": tick.time,
        }

    def fetch_balance(self) -> dict:
        """Return account balance from MT5 (read-only; does not execute trades)."""
        self._ensure_connected()
        info = _mt5.account_info()
        if info is None:
            raise RuntimeError("MT5 account_info() returned None")
        currency = info.currency
        balance = info.balance
        return {
            "free": {currency: balance},
            "total": {currency: balance},
        }
