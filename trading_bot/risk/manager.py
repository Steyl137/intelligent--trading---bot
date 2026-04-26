"""Risk manager – validates and sizes positions before execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OrderSpec:
    """Represents a sized, risk-checked order ready for execution."""

    symbol: str
    side: str          # "buy" | "sell"
    amount: float      # base currency amount
    price: float
    stop_loss: float
    take_profit: float


class RiskManager:
    """Enforces position sizing, stop-loss, and take-profit rules."""

    def __init__(
        self,
        max_position_pct: float = 0.10,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.04,
    ):
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def size_order(
        self,
        symbol: str,
        side: str,
        price: float,
        portfolio_value: float,
    ) -> OrderSpec:
        """Calculate position size and compute stop-loss / take-profit levels."""
        if price <= 0:
            raise ValueError("price must be positive")
        if portfolio_value <= 0:
            raise ValueError("portfolio_value must be positive")

        max_spend = portfolio_value * self.max_position_pct
        amount = max_spend / price

        if side == "buy":
            stop_loss = price * (1 - self.stop_loss_pct)
            take_profit = price * (1 + self.take_profit_pct)
        else:
            stop_loss = price * (1 + self.stop_loss_pct)
            take_profit = price * (1 - self.take_profit_pct)

        spec = OrderSpec(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        logger.info(
            "Order sized: %s %s %.6f @ %.4f | SL: %.4f | TP: %.4f",
            side.upper(),
            symbol,
            amount,
            price,
            stop_loss,
            take_profit,
        )
        return spec

    def check_stop_loss(self, side: str, current_price: float, stop_loss: float) -> bool:
        """Return True if the stop-loss level has been breached."""
        if side == "buy":
            return current_price <= stop_loss
        return current_price >= stop_loss

    def check_take_profit(self, side: str, current_price: float, take_profit: float) -> bool:
        """Return True if the take-profit level has been reached."""
        if side == "buy":
            return current_price >= take_profit
        return current_price <= take_profit
