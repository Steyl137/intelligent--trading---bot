"""Tests for the SMA crossover strategy."""

import pandas as pd
import pytest

from trading_bot.strategy.sma_crossover import SMACrossoverStrategy
from trading_bot.strategy.base import Signal


def _make_df(closes):
    """Build a minimal OHLCV DataFrame from a list of close prices."""
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000.0] * len(closes),
        }
    )


class TestSMAcrossoverStrategy:
    def setup_method(self):
        self.strategy = SMACrossoverStrategy(fast=3, slow=5)

    def test_hold_when_insufficient_data(self):
        df = _make_df([100.0] * 4)  # less than slow + 1 = 6 rows
        signal = self.strategy.generate_signal(df)
        assert signal.signal == Signal.HOLD

    def test_buy_signal_on_golden_cross(self):
        # fast(3) crosses above slow(5) at the final candle
        # Flat at 10 then sudden spike to 100: fast SMA jumps above slow SMA on last bar
        closes = [10, 10, 10, 10, 10, 10, 10, 10, 10, 100]
        df = _make_df(closes)
        signal = self.strategy.generate_signal(df)
        assert signal.signal == Signal.BUY

    def test_sell_signal_on_death_cross(self):
        # fast(3) crosses below slow(5) at the final candle
        # Flat at 100 then sudden drop to 10
        closes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 10]
        df = _make_df(closes)
        signal = self.strategy.generate_signal(df)
        assert signal.signal == Signal.SELL

    def test_hold_when_no_crossover(self):
        closes = [100.0] * 10
        df = _make_df(closes)
        signal = self.strategy.generate_signal(df)
        assert signal.signal == Signal.HOLD

    def test_raises_on_invalid_periods(self):
        with pytest.raises(ValueError):
            SMACrossoverStrategy(fast=30, slow=10)
