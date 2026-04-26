"""Main bot orchestrator – ties together data, strategy, risk, and execution."""

from __future__ import annotations

import logging
from typing import Optional

import ccxt

from config.settings import Config
from trading_bot.data.fetcher import DataFetcher
from trading_bot.execution.executor import BaseExecutor, LiveExecutor, PaperExecutor, Trade
from trading_bot.risk.manager import RiskManager
from trading_bot.strategy import Signal, TradeSignal, get_strategy
from trading_bot.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class TradingBot:
    """Orchestrates one trading cycle: fetch → signal → risk-check → execute."""

    def __init__(self, config: Config = None):
        cfg = config or Config

        self.symbol: str = cfg.SYMBOL
        self.timeframe: str = cfg.TIMEFRAME
        self.trading_mode: str = cfg.TRADING_MODE

        # Data
        self._fetcher = DataFetcher(
            exchange_id=cfg.EXCHANGE,
            api_key=cfg.API_KEY,
            api_secret=cfg.API_SECRET,
        )

        # Strategy
        strategy_kwargs: dict = {}
        if cfg.STRATEGY == "sma_crossover":
            strategy_kwargs = {"fast": cfg.SMA_FAST, "slow": cfg.SMA_SLOW}
        self._strategy: BaseStrategy = get_strategy(cfg.STRATEGY, **strategy_kwargs)

        # Risk manager
        self._risk = RiskManager(
            max_position_pct=cfg.MAX_POSITION_PCT,
            stop_loss_pct=cfg.STOP_LOSS_PCT,
            take_profit_pct=cfg.TAKE_PROFIT_PCT,
        )

        # Executor
        self._executor: BaseExecutor = self._build_executor(cfg)

        # State
        self._open_trade: Optional[Trade] = None

        logger.info(
            "TradingBot ready | mode=%s | symbol=%s | strategy=%s",
            self.trading_mode,
            self.symbol,
            self._strategy.name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_executor(self, cfg) -> BaseExecutor:
        if cfg.TRADING_MODE == "live":
            exchange_class = getattr(ccxt, cfg.EXCHANGE)
            exchange = exchange_class({"apiKey": cfg.API_KEY, "secret": cfg.API_SECRET, "enableRateLimit": True})
            return LiveExecutor(exchange)
        return PaperExecutor(starting_balance=cfg.PAPER_BALANCE)

    def _portfolio_value(self) -> float:
        if isinstance(self._executor, PaperExecutor):
            return self._executor.balance
        # For live: fetch balance and convert to quote currency value
        balance = self._fetcher.fetch_balance()
        quote = self.symbol.split("/")[1]
        return float(balance.get("free", {}).get(quote, 0))

    # ------------------------------------------------------------------
    # Trading cycle
    # ------------------------------------------------------------------

    def _check_exit(self, current_price: float) -> None:
        """Close open trade if stop-loss or take-profit is hit."""
        if self._open_trade is None:
            return

        trade = self._open_trade
        hit_sl = self._risk.check_stop_loss(trade.side, current_price, trade.stop_loss)
        hit_tp = self._risk.check_take_profit(trade.side, current_price, trade.take_profit)

        if hit_sl or hit_tp:
            reason = "stop-loss" if hit_sl else "take-profit"
            logger.info("Closing trade %s – %s triggered at %.4f", trade.trade_id, reason, current_price)
            self._executor.close_trade(trade, current_price)
            self._open_trade = None

    def step(self) -> TradeSignal:
        """Run a single bot iteration. Returns the signal generated."""
        df = self._fetcher.fetch_ohlcv(self.symbol, self.timeframe)
        current_price = float(df["close"].iloc[-1])

        # Check exit conditions first
        self._check_exit(current_price)

        signal: TradeSignal = self._strategy.generate_signal(df)
        logger.debug("Signal: %s | reason: %s", signal.signal.value, signal.reason)

        # Only trade if no open position
        if self._open_trade is None:
            if signal.signal == Signal.BUY:
                spec = self._risk.size_order(self.symbol, "buy", current_price, self._portfolio_value())
                self._open_trade = self._executor.execute(spec)
            elif signal.signal == Signal.SELL:
                spec = self._risk.size_order(self.symbol, "sell", current_price, self._portfolio_value())
                self._open_trade = self._executor.execute(spec)

        return signal

    def run_forever(self, interval_seconds: int = 3600) -> None:
        """Block and run :meth:`step` on a fixed interval."""
        import time

        logger.info("Starting bot loop (interval=%ds)", interval_seconds)
        while True:
            try:
                self.step()
            except Exception:
                logger.exception("Error during bot step")
            time.sleep(interval_seconds)

    def summary(self) -> dict:
        """Return a summary of the bot state (paper mode only)."""
        if isinstance(self._executor, PaperExecutor):
            return self._executor.portfolio_summary()
        return {}
