"""Main bot orchestrator – ties together data, strategy, risk, and execution."""

from __future__ import annotations

import logging
import time
from typing import Optional

import ccxt

from config.settings import Config
from trading_bot.data import get_fetcher
from trading_bot.execution.executor import BaseExecutor, LiveExecutor, PaperExecutor, Trade
from trading_bot.execution.deriv_executor import DerivExecutor
from trading_bot.risk.manager import RiskManager
from trading_bot.strategy import Signal, TradeSignal, get_strategy
from trading_bot.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class TradingBot:
    """Orchestrates one trading cycle: fetch → signal → risk-check → execute.

    The data source and executor are chosen based on ``config.BROKER`` and
    ``config.DATA_SOURCE``:

    * ``BROKER=ccxt``  + ``DATA_SOURCE=ccxt``  → original ccxt behaviour
    * ``BROKER=deriv`` + ``DATA_SOURCE=deriv`` → Deriv WebSocket throughout
    * ``BROKER=deriv`` + ``DATA_SOURCE=mt5``   → MT5 for history, Deriv for execution
    * ``BROKER=paper`` (any DATA_SOURCE)       → paper simulation
    """

    def __init__(self, config=None, symbol: str = None, executor: BaseExecutor = None):
        cfg = config or Config

        self.symbol: str = symbol or cfg.SYMBOL
        self.timeframe: str = cfg.TIMEFRAME
        self.trading_mode: str = cfg.TRADING_MODE
        self._broker: str = cfg.BROKER
        self._data_source: str = cfg.DATA_SOURCE

        # Data fetcher
        self._fetcher = self._build_fetcher(cfg)

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

        # Executor – caller may inject a shared executor (e.g. for multi-symbol paper trading)
        self._executor: BaseExecutor = executor if executor is not None else self._build_executor(cfg)

        # State – one open position per bot instance
        self._open_trade: Optional[Trade] = None

        logger.info(
            "TradingBot ready | mode=%s | broker=%s | data=%s | symbol=%s | strategy=%s",
            self.trading_mode,
            self._broker,
            self._data_source,
            self.symbol,
            self._strategy.name,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def open_trade_id(self) -> Optional[str]:
        """Return the trade_id of the current open position, or None."""
        return self._open_trade.trade_id if self._open_trade else None


    # ------------------------------------------------------------------

    def _build_fetcher(self, cfg):
        source = cfg.DATA_SOURCE
        if source == "ccxt":
            return get_fetcher(
                "ccxt",
                exchange_id=cfg.EXCHANGE,
                api_key=cfg.API_KEY,
                api_secret=cfg.API_SECRET,
            )
        if source == "deriv":
            return get_fetcher(
                "deriv",
                app_id=cfg.DERIV_APP_ID,
                token=cfg.DERIV_TOKEN,
            )
        if source == "mt5":
            return get_fetcher(
                "mt5",
                login=cfg.MT5_LOGIN,
                password=cfg.MT5_PASSWORD,
                server=cfg.MT5_SERVER,
            )
        raise ValueError(f"Unknown DATA_SOURCE '{source}'")

    def _build_executor(self, cfg) -> BaseExecutor:
        if cfg.TRADING_MODE == "paper":
            return PaperExecutor(starting_balance=cfg.PAPER_BALANCE)

        broker = cfg.BROKER
        if broker == "deriv":
            return DerivExecutor(
                app_id=cfg.DERIV_APP_ID,
                token=cfg.DERIV_TOKEN,
                multiplier=cfg.DERIV_MULTIPLIER,
            )
        if broker == "ccxt":
            exchange_class = getattr(ccxt, cfg.EXCHANGE)
            exchange = exchange_class(
                {
                    "apiKey": cfg.API_KEY,
                    "secret": cfg.API_SECRET,
                    "enableRateLimit": True,
                }
            )
            return LiveExecutor(exchange)
        raise ValueError(f"Unknown BROKER '{broker}'")

    def _portfolio_value(self) -> float:
        if isinstance(self._executor, PaperExecutor):
            return self._executor.balance
        try:
            balance = self._fetcher.fetch_balance()
            quote = self.symbol.split("/")[1]
            free = balance.get("free", {})
            return float(free.get(quote, 0) or free.get("USD", 0))
        except Exception:
            logger.warning("Could not fetch live balance; using 0")
            return 0.0

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
            logger.info(
                "Closing trade %s – %s triggered at %.5f",
                trade.trade_id,
                reason,
                current_price,
            )
            self._executor.close_trade(trade, current_price)
            self._open_trade = None

    def step(self) -> TradeSignal:
        """Run a single bot iteration. Returns the signal generated."""
        df = self._fetcher.fetch_ohlcv(self.symbol, self.timeframe)
        current_price = float(df["close"].iloc[-1])

        self._check_exit(current_price)

        signal: TradeSignal = self._strategy.generate_signal(df)
        logger.debug(
            "[%s] Signal: %s | reason: %s", self.symbol, signal.signal.value, signal.reason
        )

        if self._open_trade is None:
            if signal.signal == Signal.BUY:
                spec = self._risk.size_order(
                    self.symbol, "buy", current_price, self._portfolio_value()
                )
                self._open_trade = self._executor.execute(spec)
            elif signal.signal == Signal.SELL:
                spec = self._risk.size_order(
                    self.symbol, "sell", current_price, self._portfolio_value()
                )
                self._open_trade = self._executor.execute(spec)

        return signal

    def run_forever(self, interval_seconds: int = 3600) -> None:
        """Block and run :meth:`step` on a fixed interval."""
        logger.info("Starting bot loop (interval=%ds)", interval_seconds)
        while True:
            try:
                self.step()
            except Exception:
                logger.exception("Error during bot step for %s", self.symbol)
            time.sleep(interval_seconds)

    def summary(self) -> dict:
        """Return a portfolio summary (paper mode only)."""
        if isinstance(self._executor, PaperExecutor):
            return self._executor.portfolio_summary()
        return {}

