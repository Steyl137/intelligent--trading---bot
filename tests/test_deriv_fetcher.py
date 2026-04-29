"""Tests for the Deriv WebSocket data fetcher."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from trading_bot.data.deriv_fetcher import DerivFetcher, _to_deriv_symbol, _granularity


# ---------------------------------------------------------------------------
# Symbol / timeframe helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_symbol_conversion(self):
        assert _to_deriv_symbol("EUR/USD") == "frxEURUSD"
        assert _to_deriv_symbol("GBP/USD") == "frxGBPUSD"
        assert _to_deriv_symbol("USD/JPY") == "frxUSDJPY"

    def test_granularity_known(self):
        assert _granularity("1h") == 3600
        assert _granularity("15m") == 900
        assert _granularity("1d") == 86400

    def test_granularity_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown timeframe"):
            _granularity("3h")


# ---------------------------------------------------------------------------
# DerivFetcher – fetch_ohlcv
# ---------------------------------------------------------------------------

_CANDLES_RESPONSE = {
    "candles": [
        {"epoch": 1_700_000_000 + i * 3600, "open": str(1.1 + i * 0.001),
         "high": str(1.1 + i * 0.001 + 0.002), "low": str(1.1 + i * 0.001 - 0.001),
         "close": str(1.1 + i * 0.001 + 0.0005)}
        for i in range(10)
    ],
    "req_id": 1,
}

_EMPTY_CANDLES_RESPONSE = {"candles": [], "req_id": 1}

_ERROR_RESPONSE = {"error": {"message": "InvalidSymbol", "code": "InvalidSymbol"}, "req_id": 1}


class TestDerivFetcherOHLCV:
    def setup_method(self):
        self.fetcher = DerivFetcher(app_id="1089", token="")

    def _patch_send_recv(self, response: dict):
        return patch.object(self.fetcher, "_send_recv", return_value=response)

    def test_returns_dataframe(self):
        with self._patch_send_recv(_CANDLES_RESPONSE):
            df = self.fetcher.fetch_ohlcv("EUR/USD", "1h", limit=10)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 10

    def test_index_is_utc_datetime(self):
        with self._patch_send_recv(_CANDLES_RESPONSE):
            df = self.fetcher.fetch_ohlcv("EUR/USD", "1h")
        assert str(df.index.tz) == "UTC"

    def test_empty_candles_returns_empty_df(self):
        with self._patch_send_recv(_EMPTY_CANDLES_RESPONSE):
            df = self.fetcher.fetch_ohlcv("EUR/USD", "1h")
        assert df.empty

    def test_error_response_raises(self):
        with self._patch_send_recv(_ERROR_RESPONSE):
            with pytest.raises(RuntimeError, match="ticks_history error"):
                self.fetcher.fetch_ohlcv("EUR/USD", "1h")

    def test_volume_is_zero(self):
        with self._patch_send_recv(_CANDLES_RESPONSE):
            df = self.fetcher.fetch_ohlcv("EUR/USD", "1h")
        assert (df["volume"] == 0).all()


# ---------------------------------------------------------------------------
# DerivFetcher – fetch_ticker
# ---------------------------------------------------------------------------

_TICK_RESPONSE = {
    "history": {"prices": ["1.10345"], "times": [1_700_000_000]},
    "req_id": 2,
}


class TestDerivFetcherTicker:
    def setup_method(self):
        self.fetcher = DerivFetcher(app_id="1089", token="")

    def test_returns_price(self):
        with patch.object(self.fetcher, "_send_recv", return_value=_TICK_RESPONSE):
            ticker = self.fetcher.fetch_ticker("EUR/USD")
        assert ticker["last"] == pytest.approx(1.10345)
        assert ticker["symbol"] == "EUR/USD"

    def test_error_response_raises(self):
        with patch.object(self.fetcher, "_send_recv", return_value=_ERROR_RESPONSE):
            with pytest.raises(RuntimeError, match="tick error"):
                self.fetcher.fetch_ticker("EUR/USD")


# ---------------------------------------------------------------------------
# DerivFetcher – fetch_balance
# ---------------------------------------------------------------------------

_BALANCE_RESPONSE = {
    "balance": {"balance": 5000.0, "currency": "USD"},
    "req_id": 3,
}


class TestDerivFetcherBalance:
    def setup_method(self):
        self.fetcher = DerivFetcher(app_id="1089", token="test_token")

    def test_returns_balance(self):
        with patch.object(self.fetcher, "_send_recv", return_value=_BALANCE_RESPONSE):
            bal = self.fetcher.fetch_balance()
        assert bal["free"]["USD"] == pytest.approx(5000.0)
