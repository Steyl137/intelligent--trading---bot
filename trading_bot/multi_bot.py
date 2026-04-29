"""Multi-symbol forex bot orchestrator.

:class:`MultiBotOrchestrator` manages a pool of :class:`~trading_bot.bot.TradingBot`
instances – one per forex symbol – and runs them in sequence on each tick.

This lets the bot trade several pairs (e.g. EUR/USD, GBP/USD, USD/JPY) from a
single process, sharing the same strategy, risk parameters, and paper-trading
balance.

Usage example
-------------
::

    from config.settings import Config
    from trading_bot.multi_bot import MultiBotOrchestrator

    orchestrator = MultiBotOrchestrator(
        symbols=["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"],
        config=Config,
    )
    orchestrator.run_forever(interval_seconds=3600)
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from config.settings import Config
from trading_bot.bot import TradingBot
from trading_bot.execution.executor import PaperExecutor
from trading_bot.strategy.base import TradeSignal

logger = logging.getLogger(__name__)


class MultiBotOrchestrator:
    """Runs one :class:`TradingBot` per symbol, sharing paper-trading equity.

    In paper mode all bots share the same :class:`PaperExecutor` instance so
    that position sizing accounts for the combined portfolio correctly.

    Parameters
    ----------
    symbols:
        List of trading pairs in standard notation, e.g.
        ``["EUR/USD", "GBP/USD", "USD/JPY"]``.
    config:
        Configuration class (or object).  Defaults to :class:`~config.settings.Config`.
    """

    def __init__(self, symbols: List[str], config=None):
        cfg = config or Config
        self._cfg = cfg
        self._symbols = list(symbols)
        self._bots: Dict[str, TradingBot] = {}

        # Build one bot per symbol
        shared_executor: PaperExecutor | None = None
        if cfg.TRADING_MODE == "paper":
            # In paper mode share a single PaperExecutor so the portfolio balance
            # is consistent across all symbols
            shared_executor = PaperExecutor(starting_balance=cfg.PAPER_BALANCE)

        for sym in self._symbols:
            bot = TradingBot(config=cfg, symbol=sym, executor=shared_executor)
            self._bots[sym] = bot

        logger.info(
            "MultiBotOrchestrator ready | symbols=%s | mode=%s",
            self._symbols,
            cfg.TRADING_MODE,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def symbols(self) -> List[str]:
        return list(self._symbols)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def step(self) -> Dict[str, TradeSignal]:
        """Run one iteration across all symbols.

        Returns
        -------
        dict
            Mapping of ``symbol → TradeSignal`` for this iteration.
        """
        results: Dict[str, TradeSignal] = {}
        for sym, bot in self._bots.items():
            try:
                signal = bot.step()
                results[sym] = signal
                logger.info(
                    "[%s] %s | price=%.5f | %s",
                    sym,
                    signal.signal.value,
                    signal.price,
                    signal.reason,
                )
            except Exception:
                logger.exception("Error during step for %s", sym)
        return results

    def run_forever(self, interval_seconds: int = 3600) -> None:
        """Block and run :meth:`step` on a fixed interval (seconds)."""
        logger.info(
            "MultiBotOrchestrator starting | interval=%ds | symbols=%s",
            interval_seconds,
            self._symbols,
        )
        while True:
            try:
                self.step()
            except Exception:
                logger.exception("Unexpected error in orchestrator loop")
            time.sleep(interval_seconds)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return combined portfolio summary.

        In paper mode all bots share one executor so the summary is fetched
        from the first bot only to avoid double-counting.
        """
        first_bot = next(iter(self._bots.values()))
        base = first_bot.summary()
        base["symbols"] = self._symbols
        return base

    def open_positions(self) -> Dict[str, Optional[str]]:
        """Return a mapping of ``symbol → trade_id`` for open positions."""
        return {sym: bot.open_trade_id for sym, bot in self._bots.items()}
