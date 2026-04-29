"""Tests for MultiBotOrchestrator and DerivExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from trading_bot.multi_bot import MultiBotOrchestrator
from trading_bot.strategy.base import Signal, TradeSignal
from trading_bot.execution.deriv_executor import DerivExecutor
from trading_bot.risk.manager import OrderSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(closes, n=10):
    closes = list(closes) + [closes[-1]] * max(0, n - len(closes))
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [0.0] * len(closes)}
    )


class _FakeConfig:
    BROKER = "ccxt"
    DATA_SOURCE = "ccxt"
    EXCHANGE = "binance"
    API_KEY = ""
    API_SECRET = ""
    DERIV_APP_ID = "1089"
    DERIV_TOKEN = ""
    MT5_LOGIN = 0
    MT5_PASSWORD = ""
    MT5_SERVER = ""
    TRADING_MODE = "paper"
    SYMBOL = "EUR/USD"
    SYMBOLS = ["EUR/USD", "GBP/USD"]
    TIMEFRAME = "1h"
    STRATEGY = "sma_crossover"
    SMA_FAST = 3
    SMA_SLOW = 5
    MAX_POSITION_PCT = 0.10
    STOP_LOSS_PCT = 0.02
    TAKE_PROFIT_PCT = 0.04
    DERIV_MULTIPLIER = 10
    PAPER_BALANCE = 10_000.0


# ---------------------------------------------------------------------------
# MultiBotOrchestrator
# ---------------------------------------------------------------------------

class TestMultiBotOrchestrator:
    @pytest.fixture()
    def orchestrator(self):
        cfg = _FakeConfig()
        # Patch DataFetcher so no network calls happen
        with patch("trading_bot.bot.get_fetcher") as mock_get_fetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_ohlcv.return_value = _make_df([1.1] * 10)
            mock_get_fetcher.return_value = mock_fetcher
            orc = MultiBotOrchestrator(symbols=["EUR/USD", "GBP/USD"], config=cfg)
        return orc

    def test_creates_bot_per_symbol(self, orchestrator):
        assert set(orchestrator.symbols) == {"EUR/USD", "GBP/USD"}
        assert len(orchestrator._bots) == 2

    def test_shared_paper_executor(self, orchestrator):
        executors = {id(bot._executor) for bot in orchestrator._bots.values()}
        assert len(executors) == 1, "All bots should share the same PaperExecutor"

    def test_step_returns_signals_for_all_symbols(self, orchestrator):
        # Patch each bot's step method
        for bot in orchestrator._bots.values():
            bot.step = MagicMock(return_value=TradeSignal(signal=Signal.HOLD, price=1.1, reason="test"))

        results = orchestrator.step()
        assert set(results.keys()) == {"EUR/USD", "GBP/USD"}

    def test_step_continues_on_single_failure(self, orchestrator):
        bots = list(orchestrator._bots.values())
        bots[0].step = MagicMock(side_effect=RuntimeError("network error"))
        bots[1].step = MagicMock(return_value=TradeSignal(signal=Signal.HOLD, price=1.2, reason="ok"))

        results = orchestrator.step()
        # Only the successful bot should be in results
        assert len(results) == 1

    def test_summary_includes_symbols(self, orchestrator):
        summary = orchestrator.summary()
        assert "symbols" in summary
        assert set(summary["symbols"]) == {"EUR/USD", "GBP/USD"}

    def test_open_positions_all_none_initially(self, orchestrator):
        positions = orchestrator.open_positions()
        assert all(v is None for v in positions.values())


# ---------------------------------------------------------------------------
# DerivExecutor
# ---------------------------------------------------------------------------

_BUY_RESPONSE = {
    "buy": {"contract_id": "12345678", "buy_price": 100.0},
    "req_id": 1,
}
_SELL_RESPONSE = {
    "sell": {"sold_for": 110.0},
    "req_id": 2,
}
_ERROR_RESPONSE = {
    "error": {"message": "NotAuthorized", "code": "NotAuthorized"},
}


def _make_spec(side="buy") -> OrderSpec:
    price = 1.1000
    return OrderSpec(
        symbol="EUR/USD",
        side=side,
        amount=0.09,         # ~$100 stake at 1.1
        price=price,
        stop_loss=price * (0.98 if side == "buy" else 1.02),
        take_profit=price * (1.04 if side == "buy" else 0.96),
    )


class TestDerivExecutor:
    def setup_method(self):
        self.executor = DerivExecutor(app_id="1089", token="test_token")

    def test_execute_buy_returns_trade(self):
        with patch.object(self.executor, "_send_recv", return_value=_BUY_RESPONSE):
            trade = self.executor.execute(_make_spec("buy"))
        assert trade.trade_id == "12345678"
        assert trade.side == "buy"
        assert trade.price == pytest.approx(100.0)

    def test_execute_sell_uses_multdown(self):
        captured = {}

        def fake_send_recv(payload):
            captured["payload"] = payload
            return _BUY_RESPONSE

        with patch.object(self.executor, "_send_recv", side_effect=fake_send_recv):
            self.executor.execute(_make_spec("sell"))

        assert captured["payload"]["parameters"]["contract_type"] == "MULTDOWN"

    def test_execute_error_raises(self):
        with patch.object(self.executor, "_send_recv", return_value=_ERROR_RESPONSE):
            with pytest.raises(RuntimeError, match="Deriv buy failed"):
                self.executor.execute(_make_spec("buy"))

    def test_close_trade_calculates_pnl(self):
        from trading_bot.execution.executor import Trade

        trade = Trade(
            trade_id="12345678",
            symbol="EUR/USD",
            side="buy",
            amount=0.09,
            price=1.1000,
            stop_loss=1.0780,
            take_profit=1.1440,
        )
        with patch.object(self.executor, "_send_recv", return_value=_SELL_RESPONSE):
            closed = self.executor.close_trade(trade, current_price=1.1200)

        assert closed.pnl == pytest.approx((1.1200 - 1.1000) * 0.09)
        assert closed.closed_at is not None

    def test_close_trade_error_raises(self):
        from trading_bot.execution.executor import Trade

        trade = Trade(
            trade_id="999",
            symbol="EUR/USD",
            side="buy",
            amount=0.1,
            price=1.1,
            stop_loss=1.078,
            take_profit=1.144,
        )
        with patch.object(self.executor, "_send_recv", return_value=_ERROR_RESPONSE):
            with pytest.raises(RuntimeError, match="Deriv sell failed"):
                self.executor.close_trade(trade, current_price=1.12)
