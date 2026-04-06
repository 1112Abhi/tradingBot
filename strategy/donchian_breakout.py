# strategy/donchian_breakout.py — Donchian Channel Breakout Strategy
#
# Logic:
#   Entry (BUY):  Close breaks ABOVE the highest high of the last N bars
#                 (previous N bars, not including current — avoids lookahead)
#   Exit (SELL):  Fixed SL / TP / timeout handled by the execution layer
#                 No signal-based exit — hold until mechanical stop
#
# Why Donchian vs Bollinger:
#   BB bands are volatility-adjusted (std-based) — width shrinks in quiet markets
#   Donchian uses raw price extremes — simpler, no vol assumption, more interpretable
#   Comparing both tells us whether volatility adjustment adds edge on ETH 1h

from typing import List

import config
from strategy.base import BaseStrategy, MarketData

DONCHIAN_PERIOD = 20  # Default lookback for channel


class DonchianBreakoutStrategy(BaseStrategy):
    """
    Donchian Channel Breakout — long only.

    Entry (BUY):  current close > max(high[-N:-1])  (breaks above prior N-bar high)
    Exit  (SELL): none — rely on engine SL / TP / timeout
    """

    def __init__(self, period: int = DONCHIAN_PERIOD) -> None:
        self.period = period

    @property
    def name(self) -> str:
        return "donchian_breakout"

    def generate_signal(self, market_data: MarketData) -> str:
        prices   = market_data["prices"]
        position = market_data["position"]

        # Need period + 1 bars (period for channel, +1 for current bar)
        min_required = self.period + 1
        if len(prices) < min_required:
            raise ValueError(
                f"{self.name}: need >= {min_required} prices, got {len(prices)}."
            )

        # Channel high = max of previous N bars (exclude current bar)
        channel_high = max(prices[-(self.period + 1):-1])
        current      = prices[-1]

        # No signal-based exit — engine handles SL/TP
        if position == "LONG":
            return config.SIGNAL_NO_TRADE

        # Entry: close breaks above channel high
        if current > channel_high:
            return config.SIGNAL_BUY

        return config.SIGNAL_NO_TRADE
