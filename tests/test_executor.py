"""Tests for the paper executor."""

import pytest

from trading_bot.execution.executor import PaperExecutor
from trading_bot.risk.manager import OrderSpec


def _make_spec(side="buy", price=50_000.0, amount=0.002) -> OrderSpec:
    if side == "buy":
        stop_loss = price * 0.98
        take_profit = price * 1.04
    else:
        stop_loss = price * 1.02
        take_profit = price * 0.96
    return OrderSpec(symbol="BTC/USDT", side=side, amount=amount, price=price, stop_loss=stop_loss, take_profit=take_profit)


class TestPaperExecutor:
    def setup_method(self):
        self.executor = PaperExecutor(starting_balance=10_000.0)

    def test_buy_reduces_balance(self):
        spec = _make_spec("buy", price=50_000.0, amount=0.1)
        trade = self.executor.execute(spec)
        assert self.executor.balance == pytest.approx(10_000.0 - 50_000.0 * 0.1)
        assert trade.side == "buy"

    def test_sell_increases_balance(self):
        spec = _make_spec("sell", price=50_000.0, amount=0.1)
        self.executor.execute(spec)
        assert self.executor.balance == pytest.approx(10_000.0 + 50_000.0 * 0.1)

    def test_close_trade_calculates_pnl(self):
        spec = _make_spec("buy", price=50_000.0, amount=0.002)
        trade = self.executor.execute(spec)
        self.executor.close_trade(trade, current_price=55_000.0)
        assert trade.pnl == pytest.approx((55_000.0 - 50_000.0) * 0.002)
        assert trade.closed_at is not None

    def test_portfolio_summary(self):
        spec = _make_spec("buy", price=50_000.0, amount=0.002)
        trade = self.executor.execute(spec)
        self.executor.close_trade(trade, current_price=52_000.0)
        summary = self.executor.portfolio_summary()
        assert summary["total_trades"] == 1
        assert summary["closed_trades"] == 1
        assert summary["total_pnl"] == pytest.approx(4.0)

    def test_insufficient_balance_clamps_order(self):
        spec = _make_spec("buy", price=50_000.0, amount=1.0)  # costs 50_000 > balance of 10_000
        trade = self.executor.execute(spec)
        assert trade.amount == pytest.approx(10_000.0 / 50_000.0)
        assert self.executor.balance == pytest.approx(0.0)
