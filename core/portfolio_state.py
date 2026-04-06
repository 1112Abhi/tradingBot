# core/portfolio_state.py - Phase 8: Multi-Strategy Capital Allocation Guard
#
# Thin guard layer — no separate storage.
# Source of truth is the live_position table; reconstructed on restart automatically.
#
# Rules enforced:
#   1. Max 1 open position per strategy
#   2. Max PORTFOLIO_PER_STRATEGY_FRACTION of capital per strategy
#   3. Max PORTFOLIO_TOTAL_FRACTION of total capital across all strategies

import logging
from typing import Tuple

import config


class PortfolioState:
    """
    Capital allocation guard for multi-strategy live execution.

    Reads current open positions from DB on every check — no in-memory state
    that can drift from reality. Survives restarts with zero re-initialisation.
    """

    def __init__(self, db, capital: float = config.BACKTEST_CAPITAL) -> None:
        self.db               = db
        self.capital          = capital
        self.max_total        = capital * config.PORTFOLIO_TOTAL_FRACTION
        self.max_per_strategy = capital * config.PORTFOLIO_PER_STRATEGY_FRACTION

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def can_enter(
        self,
        symbol:         str,
        interval:       str,
        strategy_name:  str,
        position_value: float,
    ) -> Tuple[bool, str]:
        """
        Check whether a new entry is allowed under current allocation rules.

        Returns:
            (True,  "ok")           — entry is allowed
            (False, <reason>)       — entry is rejected with a human-readable reason
        """
        # Rule 1: one position per strategy at a time
        existing = self.db.get_live_position(symbol, interval, strategy_name)
        if existing:
            return False, "already in position"

        # Rule 2: per-strategy capital cap (cap the position value if needed)
        effective_value = min(position_value, self.max_per_strategy)

        # Rule 3: total capital cap
        total_used = self._total_used(symbol, interval)
        if total_used + effective_value > self.max_total:
            pct_used = total_used / self.capital * 100
            return False, (
                f"total cap exceeded — {pct_used:.1f}% already deployed "
                f"(${total_used:,.0f} / ${self.max_total:,.0f} limit)"
            )

        return True, "ok"

    def cap_position_value(self, position_value: float) -> float:
        """Silently cap position_value to the per-strategy limit."""
        return min(position_value, self.max_per_strategy)

    def summary(self, symbol: str, interval: str) -> str:
        """One-line usage summary for logging."""
        positions  = self.db.get_all_live_positions(symbol, interval)
        total_used = sum(p.get("position_value", 0.0) for p in positions)
        pct        = total_used / self.capital * 100
        strategies = [p["strategy"] for p in positions] or ["none"]
        return (
            f"{pct:.1f}% deployed (${total_used:,.0f} / ${self.max_total:,.0f} cap) "
            f"| open: {', '.join(strategies)}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _total_used(self, symbol: str, interval: str) -> float:
        positions = self.db.get_all_live_positions(symbol, interval)
        return sum(p.get("position_value", 0.0) for p in positions)
