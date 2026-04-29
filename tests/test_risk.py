"""Tests for the risk manager."""

import pytest

from trading_bot.risk.manager import RiskManager


class TestRiskManager:
    def setup_method(self):
        self.rm = RiskManager(max_position_pct=0.10, stop_loss_pct=0.02, take_profit_pct=0.04)

    def test_buy_order_sizing(self):
        spec = self.rm.size_order("BTC/USDT", "buy", price=50_000.0, portfolio_value=10_000.0)
        assert spec.side == "buy"
        assert abs(spec.amount - 0.02) < 1e-8  # 1000 / 50000
        assert spec.stop_loss == pytest.approx(50_000.0 * 0.98)
        assert spec.take_profit == pytest.approx(50_000.0 * 1.04)

    def test_sell_order_sizing(self):
        spec = self.rm.size_order("BTC/USDT", "sell", price=50_000.0, portfolio_value=10_000.0)
        assert spec.stop_loss == pytest.approx(50_000.0 * 1.02)
        assert spec.take_profit == pytest.approx(50_000.0 * 0.96)

    def test_invalid_price_raises(self):
        with pytest.raises(ValueError):
            self.rm.size_order("BTC/USDT", "buy", price=0, portfolio_value=1000)

    def test_invalid_portfolio_raises(self):
        with pytest.raises(ValueError):
            self.rm.size_order("BTC/USDT", "buy", price=100, portfolio_value=0)

    def test_stop_loss_triggered_buy(self):
        assert self.rm.check_stop_loss("buy", current_price=48_000, stop_loss=49_000) is True
        assert self.rm.check_stop_loss("buy", current_price=51_000, stop_loss=49_000) is False

    def test_take_profit_triggered_buy(self):
        assert self.rm.check_take_profit("buy", current_price=52_000, take_profit=52_000) is True
        assert self.rm.check_take_profit("buy", current_price=50_000, take_profit=52_000) is False
