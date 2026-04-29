"""Deriv WebSocket API data fetcher.

Connects to the Deriv WebSocket API (wss://ws.binaryws.com/websockets/v3)
to retrieve OHLCV candle history and latest tick prices for forex instruments.

Deriv symbol format examples
-----------------------------
EUR/USD  →  frxEURUSD
GBP/USD  →  frxGBPUSD
USD/JPY  →  frxUSDJPY
AUD/USD  →  frxAUDUSD

Timeframe → granularity mapping (seconds)
------------------------------------------
1m  →   60     5m  →  300    15m  →   900
30m →  1800    1h  → 3600    4h   → 14400
1d  → 86400
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Deriv WebSocket endpoint
_WS_URL = "wss://ws.binaryws.com/websockets/v3"

# Standard timeframe string → granularity in seconds
_TIMEFRAME_MAP: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "8h": 28800,
    "1d": 86400,
}


def _to_deriv_symbol(symbol: str) -> str:
    """Convert standard 'EUR/USD' format to Deriv 'frxEURUSD' format."""
    return "frx" + symbol.replace("/", "")


def _granularity(timeframe: str) -> int:
    """Return granularity in seconds; raise ValueError for unknown timeframes."""
    gran = _TIMEFRAME_MAP.get(timeframe)
    if gran is None:
        raise ValueError(
            f"Unknown timeframe '{timeframe}'. Supported: {list(_TIMEFRAME_MAP)}"
        )
    return gran


class DerivFetcher:
    """Fetches OHLCV data and tick prices from the Deriv WebSocket API.

    Parameters
    ----------
    app_id:
        Deriv application ID.  Use ``1089`` for the public demo app.
    token:
        Optional OAuth token for authenticated endpoints (balance, trading).
    """

    def __init__(self, app_id: str = "1089", token: str = ""):
        self._app_id = app_id
        self._token = token
        self._ws_url = f"{_WS_URL}?app_id={app_id}"
        logger.info("DerivFetcher initialised (app_id=%s)", app_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_recv(self, payload: dict) -> dict:
        """Open a short-lived WebSocket connection, send *payload*, return response."""
        from websockets.sync.client import connect  # lazy import

        with connect(self._ws_url) as ws:
            if self._token:
                # Authorise first then repeat the real request
                ws.send(json.dumps({"authorize": self._token, "req_id": 0}))
                auth_resp = json.loads(ws.recv())
                if "error" in auth_resp:
                    raise RuntimeError(
                        f"Deriv auth failed: {auth_resp['error']['message']}"
                    )
            ws.send(json.dumps(payload))
            return json.loads(ws.recv())

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
            Optional Unix epoch (seconds) for the start of the range.
        """
        deriv_symbol = _to_deriv_symbol(symbol)
        granularity = _granularity(timeframe)

        request: dict = {
            "ticks_history": deriv_symbol,
            "end": "latest",
            "count": limit,
            "style": "candles",
            "granularity": granularity,
            "req_id": 1,
        }
        if since is not None:
            request["start"] = since

        response = self._send_recv(request)

        if "error" in response:
            raise RuntimeError(
                f"Deriv ticks_history error: {response['error']['message']}"
            )

        candles = response.get("candles", [])
        if not candles:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            )

        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["epoch"], unit="s", utc=True)
        df.set_index("timestamp", inplace=True)
        df = df[["open", "high", "low", "close"]].astype(float)
        df["volume"] = 0.0  # Deriv does not provide volume for forex

        logger.debug(
            "DerivFetcher: %d candles for %s/%s", len(df), symbol, timeframe
        )
        return df

    def fetch_ticker(self, symbol: str) -> dict:
        """Return latest bid/ask for *symbol* as a dict."""
        deriv_symbol = _to_deriv_symbol(symbol)
        response = self._send_recv(
            {
                "ticks_history": deriv_symbol,
                "end": "latest",
                "count": 1,
                "style": "ticks",
                "req_id": 2,
            }
        )
        if "error" in response:
            raise RuntimeError(
                f"Deriv tick error: {response['error']['message']}"
            )
        history = response.get("history", {})
        prices = history.get("prices", [])
        times = history.get("times", [])
        if prices:
            price = float(prices[-1])
            return {
                "symbol": symbol,
                "last": price,
                "bid": price,
                "ask": price,
                "timestamp": int(times[-1]) if times else None,
            }
        return {"symbol": symbol, "last": None}

    def fetch_balance(self) -> dict:
        """Return account balance (requires a valid DERIV_TOKEN)."""
        response = self._send_recv({"balance": 1, "req_id": 3})
        if "error" in response:
            raise RuntimeError(
                f"Deriv balance error: {response['error']['message']}"
            )
        bal = response.get("balance", {})
        currency = bal.get("currency", "USD")
        amount = float(bal.get("balance", 0))
        return {"free": {currency: amount}, "total": {currency: amount}}
