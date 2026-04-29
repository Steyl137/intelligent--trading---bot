"""Base strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    signal: Signal
    price: float
    reason: str = ""
    metadata: Optional[dict] = None


class BaseStrategy(ABC):
    """All strategies must implement :meth:`generate_signal`."""

    name: str = "base"

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> TradeSignal:
        """Given a candle DataFrame, return a :class:`TradeSignal`."""
        ...

    def __repr__(self) -> str:
        return f"<Strategy: {self.name}>"
