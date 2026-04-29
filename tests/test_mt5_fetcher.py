"""Tests for the MT5 historical data fetcher.

Because MetaTrader5 is Windows-only, the tests mock the ``_mt5`` module
reference inside ``trading_bot.data.mt5_fetcher``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import trading_bot.data.mt5_fetcher as mt5_module
from trading_bot.data.mt5_fetcher import MT5Fetcher, _to_mt5_symbol


# ---------------------------------------------------------------------------
# Symbol helper
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_symbol_conversion(self):
        assert _to_mt5_symbol("EUR/USD") == "EURUSD"
        assert _to_mt5_symbol("GBP/JPY") == "GBPJPY"


# ---------------------------------------------------------------------------
# Fixtures – fake MT5 module
# ---------------------------------------------------------------------------

def _make_fake_rates(n: int = 5):
    """Return a structured numpy array mimicking MT5 copy_rates output."""
    dtype = np.dtype([
        ("time", np.int64),
        ("open", np.float64),
        ("high", np.float64),
        ("low", np.float64),
        ("close", np.float64),
        ("tick_volume", np.int64),
        ("spread", np.int32),
        ("real_volume", np.int64),
    ])
    data = np.zeros(n, dtype=dtype)
    base_time = 1_700_000_000
    for i in range(n):
        data[i]["time"] = base_time + i * 3600
        data[i]["open"] = 1.1 + i * 0.001
        data[i]["high"] = 1.1 + i * 0.001 + 0.002
        data[i]["low"] = 1.1 + i * 0.001 - 0.001
        data[i]["close"] = 1.1 + i * 0.001 + 0.0005
        data[i]["tick_volume"] = 1000
    return data


@pytest.fixture()
def fake_mt5(monkeypatch):
    """Patch the internal _mt5 reference with a MagicMock."""
    mock = MagicMock()
    mock.initialize.return_value = True
    mock.TIMEFRAME_H1 = 16385  # arbitrary constant
    mock.TIMEFRAME_M1 = 1
    mock.copy_rates_from_pos.return_value = _make_fake_rates(5)
    mock.copy_rates_from.return_value = _make_fake_rates(5)

    # Fake tick info
    tick = MagicMock()
    tick.bid = 1.10340
    tick.ask = 1.10350
    tick.time = 1_700_000_000
    mock.symbol_info_tick.return_value = tick

    # Fake account info
    account = MagicMock()
    account.balance = 10_000.0
    account.currency = "USD"
    mock.account_info.return_value = account

    monkeypatch.setattr(mt5_module, "_mt5", mock)
    monkeypatch.setattr(mt5_module, "_MT5_AVAILABLE", True)
    return mock


# ---------------------------------------------------------------------------
# MT5Fetcher tests
# ---------------------------------------------------------------------------

class TestMT5Fetcher:
    def test_fetch_ohlcv_returns_dataframe(self, fake_mt5):
        fetcher = MT5Fetcher()
        fetcher._initialized = True
        df = fetcher.fetch_ohlcv("EUR/USD", "1h", limit=5)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 5

    def test_fetch_ohlcv_index_is_utc(self, fake_mt5):
        fetcher = MT5Fetcher()
        fetcher._initialized = True
        df = fetcher.fetch_ohlcv("EUR/USD", "1h")
        assert str(df.index.tz) == "UTC"

    def test_fetch_ohlcv_passes_symbol_to_mt5(self, fake_mt5):
        fetcher = MT5Fetcher()
        fetcher._initialized = True
        fetcher.fetch_ohlcv("GBP/USD", "1h", limit=5)
        call_args = fake_mt5.copy_rates_from_pos.call_args
        assert call_args[0][0] == "GBPUSD"

    def test_fetch_ohlcv_raises_on_none_result(self, fake_mt5):
        fake_mt5.copy_rates_from_pos.return_value = None
        fake_mt5.last_error.return_value = (1, "Symbol not found")
        fetcher = MT5Fetcher()
        fetcher._initialized = True
        with pytest.raises(RuntimeError, match="MT5 copy_rates failed"):
            fetcher.fetch_ohlcv("EUR/USD", "1h")

    def test_fetch_ticker(self, fake_mt5):
        fetcher = MT5Fetcher()
        fetcher._initialized = True
        ticker = fetcher.fetch_ticker("EUR/USD")
        assert ticker["bid"] == pytest.approx(1.10340)
        assert ticker["ask"] == pytest.approx(1.10350)

    def test_fetch_balance(self, fake_mt5):
        fetcher = MT5Fetcher()
        fetcher._initialized = True
        bal = fetcher.fetch_balance()
        assert bal["free"]["USD"] == pytest.approx(10_000.0)

    def test_unavailable_raises_runtime_error(self, monkeypatch):
        monkeypatch.setattr(mt5_module, "_MT5_AVAILABLE", False)
        monkeypatch.setattr(mt5_module, "_mt5", None)
        fetcher = MT5Fetcher()
        with pytest.raises(RuntimeError, match="not installed"):
            fetcher.fetch_ohlcv("EUR/USD", "1h")

    def test_unknown_timeframe_raises(self, fake_mt5):
        fetcher = MT5Fetcher()
        fetcher._initialized = True
        with pytest.raises(ValueError, match="Unknown timeframe"):
            fetcher.fetch_ohlcv("EUR/USD", "3h")
