"""Strategy registry – maps strategy names to their classes."""

from trading_bot.strategy.base import BaseStrategy, Signal, TradeSignal
from trading_bot.strategy.sma_crossover import SMACrossoverStrategy

_REGISTRY: dict[str, type[BaseStrategy]] = {
    SMACrossoverStrategy.name: SMACrossoverStrategy,
}


def get_strategy(name: str, **kwargs) -> BaseStrategy:
    """Instantiate a strategy by name, forwarding kwargs to its constructor."""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(_REGISTRY)}")
    return cls(**kwargs)


__all__ = ["BaseStrategy", "Signal", "TradeSignal", "SMACrossoverStrategy", "get_strategy"]
