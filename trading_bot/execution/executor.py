"""Execution engine – paper trading and live order routing."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import ccxt

from trading_bot.risk.manager import OrderSpec

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Record of an executed trade."""

    trade_id: str
    symbol: str
    side: str
    amount: float
    price: float
    stop_loss: float
    take_profit: float
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    pnl: Optional[float] = None


class BaseExecutor(ABC):
    """Abstract executor – paper or live."""

    @abstractmethod
    def execute(self, spec: OrderSpec) -> Trade:
        """Submit an order and return a :class:`Trade` record."""
        ...

    @abstractmethod
    def close_trade(self, trade: Trade, current_price: float) -> Trade:
        """Close an open trade at *current_price*."""
        ...


# ---------------------------------------------------------------------------
# Paper trading executor
# ---------------------------------------------------------------------------

class PaperExecutor(BaseExecutor):
    """Simulates trade execution without touching a real exchange."""

    def __init__(self, starting_balance: float = 10_000.0):
        self.balance = starting_balance
        self.trades: List[Trade] = []
        self._trade_counter = 0

    # ------------------------------------------------------------------
    # BaseExecutor implementation
    # ------------------------------------------------------------------

    def execute(self, spec: OrderSpec) -> Trade:
        cost = spec.amount * spec.price

        if spec.side == "buy" and cost > self.balance:
            logger.warning("Insufficient paper balance (%.2f) for order cost %.2f", self.balance, cost)
            cost = self.balance
            spec = OrderSpec(
                symbol=spec.symbol,
                side=spec.side,
                amount=cost / spec.price,
                price=spec.price,
                stop_loss=spec.stop_loss,
                take_profit=spec.take_profit,
            )

        self._trade_counter += 1
        trade = Trade(
            trade_id=f"PAPER-{self._trade_counter:04d}",
            symbol=spec.symbol,
            side=spec.side,
            amount=spec.amount,
            price=spec.price,
            stop_loss=spec.stop_loss,
            take_profit=spec.take_profit,
        )

        if spec.side == "buy":
            self.balance -= cost
        else:
            self.balance += spec.amount * spec.price

        self.trades.append(trade)
        logger.info("[PAPER] %s %s %.6f @ %.4f | balance: %.2f", spec.side.upper(), spec.symbol, spec.amount, spec.price, self.balance)
        return trade

    def close_trade(self, trade: Trade, current_price: float) -> Trade:
        if trade.side == "buy":
            pnl = (current_price - trade.price) * trade.amount
            self.balance += trade.amount * current_price
        else:
            pnl = (trade.price - current_price) * trade.amount
            self.balance -= trade.amount * current_price

        trade.closed_at = datetime.now(timezone.utc)
        trade.pnl = pnl
        logger.info("[PAPER] Closed trade %s | PnL: %.4f | balance: %.2f", trade.trade_id, pnl, self.balance)
        return trade

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def portfolio_summary(self) -> dict:
        closed = [t for t in self.trades if t.pnl is not None]
        total_pnl = sum(t.pnl for t in closed)
        return {
            "balance": self.balance,
            "total_trades": len(self.trades),
            "closed_trades": len(closed),
            "total_pnl": total_pnl,
        }


# ---------------------------------------------------------------------------
# Live trading executor
# ---------------------------------------------------------------------------

class LiveExecutor(BaseExecutor):
    """Executes real orders on a ccxt-compatible exchange."""

    def __init__(self, exchange: ccxt.Exchange):
        self._exchange = exchange

    def execute(self, spec: OrderSpec) -> Trade:
        logger.info("[LIVE] Placing %s order: %s %.6f @ market", spec.side.upper(), spec.symbol, spec.amount)
        order = self._exchange.create_order(
            symbol=spec.symbol,
            type="market",
            side=spec.side,
            amount=spec.amount,
        )
        fill_price = order.get("average") or order.get("price") or spec.price
        trade = Trade(
            trade_id=str(order["id"]),
            symbol=spec.symbol,
            side=spec.side,
            amount=spec.amount,
            price=float(fill_price),
            stop_loss=spec.stop_loss,
            take_profit=spec.take_profit,
        )
        logger.info("[LIVE] Order filled: %s | fill price: %.4f", trade.trade_id, trade.price)
        return trade

    def close_trade(self, trade: Trade, current_price: float) -> Trade:
        close_side = "sell" if trade.side == "buy" else "buy"
        order = self._exchange.create_order(
            symbol=trade.symbol,
            type="market",
            side=close_side,
            amount=trade.amount,
        )
        fill_price = order.get("average") or order.get("price") or current_price
        if trade.side == "buy":
            pnl = (float(fill_price) - trade.price) * trade.amount
        else:
            pnl = (trade.price - float(fill_price)) * trade.amount

        trade.closed_at = datetime.now(timezone.utc)
        trade.pnl = pnl
        logger.info("[LIVE] Closed %s | PnL: %.4f", trade.trade_id, pnl)
        return trade
