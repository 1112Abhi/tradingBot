# strategy/donchian_regime.py — Donchian Breakout + R² Regime Filter
#
# Extends DonchianBreakoutStrategy with an explicit regime gate:
#   Entry is only allowed when the market is TRENDING (R² >= threshold).
#   This filters out false breakouts in choppy/ranging markets.
#
# Research result (BTCUSDT 4h, 3yr):
#   Unfiltered:  return=+7.24%   sharpe=0.62  DD=12.57%  trades=159
#   Filtered:    return=+18.51%  sharpe=1.61  DD=5.98%   trades=109
#   Best params: regime_period=30, regime_threshold=0.35
#
# Design:
#   - Inherits Donchian channel logic exactly — no changes to signal logic
#   - Regime check applied ONLY to entries (not exits — engine handles SL/TP)
#   - Regime period and threshold are constructor params for easy tuning

import config
from strategy.base import BaseStrategy, MarketData
from strategy.regime import RegimeDetector, REGIME_TRENDING

# Optimal params from regime_research.py
DEFAULT_DONCHIAN_PERIOD   = 20
DEFAULT_REGIME_PERIOD     = 30
DEFAULT_REGIME_THRESHOLD  = 0.35


class DonchianRegimeStrategy(BaseStrategy):
    """
    Donchian Channel Breakout gated by R² regime filter.

    Entry (BUY):  close > max(prior N bars)  AND  R²(period) >= threshold
    Exit  (SELL): none — engine SL / TP / timeout only

    Args:
        period:           Donchian channel lookback (default 20)
        regime_period:    R² regression window (default 30)
        regime_threshold: R² above this = trending (default 0.35)
    """

    def __init__(
        self,
        period:           int   = DEFAULT_DONCHIAN_PERIOD,
        regime_period:    int   = DEFAULT_REGIME_PERIOD,
        regime_threshold: float = DEFAULT_REGIME_THRESHOLD,
    ) -> None:
        self.period  = period
        self.regime  = RegimeDetector(period=regime_period, threshold=regime_threshold)

    @property
    def name(self) -> str:
        return "donchian_regime"

    def generate_signal(self, market_data: MarketData) -> str:
        prices   = market_data["prices"]
        position = market_data["position"]

        min_required = max(self.period + 1, self.regime.period)
        if len(prices) < min_required:
            raise ValueError(
                f"{self.name}: need >= {min_required} prices, got {len(prices)}."
            )

        # No signal-based exit — engine handles SL/TP
        if position == "LONG":
            return config.SIGNAL_NO_TRADE

        # Donchian breakout signal
        channel_high = max(prices[-(self.period + 1):-1])
        current      = prices[-1]
        if current <= channel_high:
            return config.SIGNAL_NO_TRADE

        # Regime gate — only enter in trending market
        if self.regime.detect(prices) != REGIME_TRENDING:
            return config.SIGNAL_NO_TRADE

        return config.SIGNAL_BUY
