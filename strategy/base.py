# strategy/base.py - Base Strategy Interface

from abc import ABC, abstractmethod
from typing import TypedDict, List, Optional


class MarketData(TypedDict, total=False):
    """
    Canonical data contract passed to every strategy.

    Required fields:
        prices:      Ordered price list, oldest first. Must contain at least
                     as many bars as the strategy's longest lookback period.
        entry_price: Price at which the current position was opened.
                     None if no position is held.
        position:    Current position state. "LONG" if in a trade, "NONE" if flat.
        symbol:      Asset identifier (e.g. "bitcoin", "BTCUSDT").
        timestamp:   ISO 8601 UTC timestamp of the most recent bar
                     (e.g. "2026-03-28T10:00:00Z").

    Optional fields:
        volumes:     Ordered volume list matching prices (oldest first).
                     None if not available. Used by volume-aware strategies.
    """
    prices:      List[float]
    entry_price: Optional[float]
    position:    str              # "LONG" | "NONE"
    symbol:      str
    timestamp:   str
    volumes:     Optional[List[float]]


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Signal semantics (every subclass must honour these):
        "BUY"      — Open a long position (only valid when position == "NONE")
        "SELL"     — Exit the current long position (only valid when position == "LONG")
        "NO_TRADE" — Take no action; hold current state

    Position-awareness is handled by the execution layer (state.py / monitor.py),
    not by the strategy itself. Strategies emit intent; the system decides validity.

    Subclasses must implement:
        name             — unique snake_case identifier used in logging and config
        generate_signal  — core signal logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique snake_case strategy identifier (e.g. 'ema_crossover')."""
        ...

    @abstractmethod
    def generate_signal(self, market_data: MarketData) -> str:
        """
        Analyse market_data and return a signal string.

        Args:
            market_data: Fully populated MarketData dict.

        Returns:
            One of "BUY", "SELL", or "NO_TRADE".
        """
        ...
