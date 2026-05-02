# strategy/donchian_regime.py — Donchian Breakout + R² Regime Filter
#
# Extends DonchianBreakoutStrategy with an explicit regime gate:
#   Entry is only allowed when the market is TRENDING (R² >= threshold).
#   This filters out false breakouts in choppy/ranging markets.
#
# Sentiment gate (optional):
#   Skips breakout longs when composite sentiment is too bearish (counter-trend).
#   Donchian benefits from momentum confirmation — don't buy breakouts into fear.
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

import logging

import config
from strategy.base import BaseStrategy, MarketData
from strategy.regime import RegimeDetector, REGIME_TRENDING

logger = logging.getLogger(__name__)

# Optimal params from regime_research.py
DEFAULT_DONCHIAN_PERIOD   = 20
DEFAULT_REGIME_PERIOD     = 30
DEFAULT_REGIME_THRESHOLD  = 0.35


class DonchianRegimeStrategy(BaseStrategy):
    """
    Donchian Channel Breakout gated by R² regime filter.

    Entry (BUY):  close > max(prior N bars)  AND  R²(period) >= threshold
                  AND (optional) sentiment not too bearish
    Exit  (SELL): none — engine SL / TP / timeout only

    Args:
        period:           Donchian channel lookback (default 20)
        regime_period:    R² regression window (default 30)
        regime_threshold: R² above this = trending (default 0.35)
        use_sentiment:    if True, skips entry when sentiment composite <= -0.3
        symbol:           trading symbol for sentiment lookup (e.g. "BTCUSDT")
    """

    def __init__(
        self,
        period:           int   = DEFAULT_DONCHIAN_PERIOD,
        regime_period:    int   = DEFAULT_REGIME_PERIOD,
        regime_threshold: float = DEFAULT_REGIME_THRESHOLD,
        use_sentiment:    bool  = False,
        symbol:           str   = "BTCUSDT",
    ) -> None:
        self.period        = period
        self.regime        = RegimeDetector(period=regime_period, threshold=regime_threshold)
        self.use_sentiment = use_sentiment
        self.symbol        = symbol

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

        # Sentiment gate — skip if counter-trend (market too fearful for a breakout)
        if self.use_sentiment and self._sentiment_blocks_entry():
            return config.SIGNAL_NO_TRADE

        return config.SIGNAL_BUY

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sentiment_blocks_entry(self) -> bool:
        """Return True if sentiment is too bearish for a breakout long."""
        try:
            from sentiment import aggregator
            result = aggregator.fetch(self.symbol)
            if result.should_skip_donchian_long():
                logger.info(
                    "DonchianRegime[%s]: sentiment blocks entry — %s",
                    self.symbol, result.summary(),
                )
                return True
            return False
        except Exception as exc:
            logger.warning("DonchianRegime sentiment check failed, allowing entry: %s", exc)
            return False  # fail open — don't block trade on API error
