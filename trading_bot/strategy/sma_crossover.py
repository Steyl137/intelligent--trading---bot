"""Simple Moving Average (SMA) crossover strategy.

Generates a BUY signal when the fast SMA crosses above the slow SMA,
and a SELL signal when the fast SMA crosses below the slow SMA.
"""

from __future__ import annotations

import logging

import pandas as pd

from trading_bot.strategy.base import BaseStrategy, Signal, TradeSignal

logger = logging.getLogger(__name__)


class SMACrossoverStrategy(BaseStrategy):
    """SMA crossover strategy."""

    name = "sma_crossover"

    def __init__(self, fast: int = 10, slow: int = 30):
        if fast >= slow:
            raise ValueError("fast period must be less than slow period")
        self.fast = fast
        self.slow = slow

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["sma_fast"] = df["close"].rolling(self.fast).mean()
        df["sma_slow"] = df["close"].rolling(self.slow).mean()
        return df

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------

    def generate_signal(self, df: pd.DataFrame) -> TradeSignal:
        if len(df) < self.slow + 1:
            return TradeSignal(signal=Signal.HOLD, price=float(df["close"].iloc[-1]), reason="insufficient data")

        df = self._add_indicators(df)
        latest = df.iloc[-1]
        previous = df.iloc[-2]

        current_price = float(latest["close"])

        # Golden cross: fast crosses above slow
        if previous["sma_fast"] <= previous["sma_slow"] and latest["sma_fast"] > latest["sma_slow"]:
            logger.info("BUY signal: SMA golden cross at %.4f", current_price)
            return TradeSignal(
                signal=Signal.BUY,
                price=current_price,
                reason="SMA golden cross",
                metadata={"sma_fast": latest["sma_fast"], "sma_slow": latest["sma_slow"]},
            )

        # Death cross: fast crosses below slow
        if previous["sma_fast"] >= previous["sma_slow"] and latest["sma_fast"] < latest["sma_slow"]:
            logger.info("SELL signal: SMA death cross at %.4f", current_price)
            return TradeSignal(
                signal=Signal.SELL,
                price=current_price,
                reason="SMA death cross",
                metadata={"sma_fast": latest["sma_fast"], "sma_slow": latest["sma_slow"]},
            )

        return TradeSignal(signal=Signal.HOLD, price=current_price, reason="no crossover")
