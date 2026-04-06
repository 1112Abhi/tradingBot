# strategy_factory.py - Strategy Factory

from typing import List
import config
from strategy.base import BaseStrategy
from strategy.ema_crossover import MACrossoverStrategy

# Registry: maps config name → strategy class
# Add new strategies here as a single-line entry
_REGISTRY = {
    "ema_crossover": MACrossoverStrategy,
}


def get_strategies() -> List[BaseStrategy]:
    """
    Build and return the list of active strategy instances.

    Reads ACTIVE_STRATEGIES from config. Raises ValueError for
    any unrecognised name so misconfiguration fails loudly at startup.

    Returns:
        List of instantiated BaseStrategy objects.

    Raises:
        ValueError: If ACTIVE_STRATEGIES is empty or contains an unknown name.
    """
    if not config.ACTIVE_STRATEGIES:
        raise ValueError(
            "ACTIVE_STRATEGIES is empty. Define at least one strategy in config.py."
        )

    strategies: List[BaseStrategy] = []
    for name in config.ACTIVE_STRATEGIES:
        if name not in _REGISTRY:
            raise ValueError(
                f"Unknown strategy '{name}'. "
                f"Available: {list(_REGISTRY.keys())}"
            )
        strategies.append(_REGISTRY[name]())

    return strategies
