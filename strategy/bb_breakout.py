# strategy/bb_breakout.py — Bollinger Band Breakout Strategy
#
# Logic:
#   Entry (BUY):   Close breaks ABOVE upper Bollinger Band
#                  AND volume >= BB_VOLUME_MULT * average volume  (confirms breakout is real)
#                  AND price was below mid-band at least BB_LOOKBACK bars ago  (avoids extended runs)
#   Exit (SELL):   Close drops back BELOW mid-band (20 SMA)
#                  (hard SL/TP/timeout exits handled by the execution layer)
#
# Rationale:
#   Mean Reversion fails at lower timeframes because price oscillates through
#   the SL before reverting. BB Breakout trades WITH momentum — when price
#   breaks above the upper band on volume, it tends to continue for 2-6 bars.
#   The mid-band exit locks in gains without waiting for SL/TP.
#
# Parameters:
#   bb_period      — Bollinger Band period (default 20)
#   bb_std         — Standard deviation multiplier (default 2.0)
#   volume_mult    — Volume must be >= this × 20-bar avg to confirm (default 1.5)
#   lookback       — Price must have been below mid-band within last N bars (default 5)

import math
from typing import List, Optional

import config
from strategy.base import BaseStrategy, MarketData

BB_PERIOD     = 20
BB_STD        = 2.0
BB_VOLUME_MULT = 1.5   # volume filter: 1.5× average
BB_LOOKBACK   = 5      # recent below-midband check window


class BBBreakoutStrategy(BaseStrategy):
    """
    Bollinger Band Breakout with volume confirmation.

    Entry (BUY):  price > upper_band  AND  volume > volume_mult × avg_volume
                  AND  price was below mid_band within last `lookback` bars
    Exit (SELL):  price < mid_band  (momentum exhausted)
    """

    def __init__(
        self,
        bb_period:    int   = BB_PERIOD,
        bb_std:       float = BB_STD,
        volume_mult:  float = BB_VOLUME_MULT,
        lookback:     int   = BB_LOOKBACK,
    ) -> None:
        self.bb_period   = bb_period
        self.bb_std      = bb_std
        self.volume_mult = volume_mult
        self.lookback    = lookback

    @property
    def name(self) -> str:
        return "bb_breakout"

    def generate_signal(self, market_data: MarketData) -> str:
        prices   = market_data["prices"]
        position = market_data["position"]
        volumes  = market_data.get("volumes")

        min_required = self.bb_period + self.lookback
        if len(prices) < min_required:
            raise ValueError(
                f"{self.name}: need >= {min_required} prices, got {len(prices)}."
            )

        mid, upper, lower = self._bollinger(prices, self.bb_period, self.bb_std)
        current_price = prices[-1]

        # EXIT: price drops back below mid-band
        if position == "LONG":
            if current_price < mid:
                return config.SIGNAL_SELL
            return config.SIGNAL_NO_TRADE

        # ENTRY: price breaks above upper band
        if current_price <= upper:
            return config.SIGNAL_NO_TRADE

        # Volume filter: only enter if current volume >= volume_mult × avg
        if volumes is not None and len(volumes) >= self.bb_period:
            avg_vol = sum(volumes[-self.bb_period:-1]) / (self.bb_period - 1)
            cur_vol = volumes[-1]
            if avg_vol > 0 and cur_vol < self.volume_mult * avg_vol:
                return config.SIGNAL_NO_TRADE

        # Confirmation: price must have been below mid-band recently
        # (avoids buying into an already extended up-move)
        recent_prices = prices[-(self.lookback + 1):-1]
        if not any(p < mid for p in recent_prices):
            return config.SIGNAL_NO_TRADE

        return config.SIGNAL_BUY

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bollinger(
        self, prices: List[float], period: int, std_mult: float
    ) -> tuple:
        """
        Compute Bollinger Bands at the current bar.

        Returns:
            (mid, upper, lower) — SMA and ± std_mult * stdev
        """
        window = prices[-period:]
        mid    = sum(window) / period
        variance = sum((p - mid) ** 2 for p in window) / period
        std    = math.sqrt(variance)
        return mid, mid + std_mult * std, mid - std_mult * std
