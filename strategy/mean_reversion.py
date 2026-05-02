# strategy/mean_reversion.py - Mean Reversion Strategy (Phase 7.7)
#
# Logic:
#   Entry  (BUY):  RSI < MR_RSI_OVERSOLD  AND  price < EMA(50)  (in a down-move, not freefall)
#                  AND (if use_sentiment) sentiment not too bullish
#   Exit  (SELL):  RSI > MR_RSI_EXIT      (momentum recovered)
#                  OR price hits TP / SL  (handled by backtest engine / candle watcher)
#   Hold (NO_TRADE): all other conditions
#
# Design notes:
#   - EMA50 filter: only buy dips that are below the trend line (true mean reversion)
#     avoids catching falling knives in strong uptrends where RSI rarely hits 35
#   - RSI thresholds: 35 (oversold) / 55 (exit) — slightly looser than classic 30/70
#     to generate enough trades on BTC 4h for statistical validity
#   - Sentiment filter (optional): skips entry when market is in extreme greed
#     and boosts conviction sizing when in extreme fear (contrarian confirmation)
#   - No position sizing here — delegated to risk_manager.py (same as EMA strategy)
#   - SL/TP/timeout delegated to engine — strategy only emits BUY / SELL / NO_TRADE

import logging
from typing import List

import config
from strategy.base import BaseStrategy, MarketData

logger = logging.getLogger(__name__)

# Default thresholds — all overridable via constructor for backtesting variants
MR_RSI_PERIOD   = 14    # RSI lookback
MR_RSI_OVERSOLD = 35    # BUY when RSI drops below this
MR_RSI_EXIT     = 55    # SELL when RSI recovers above this
MR_TREND_PERIOD = 50    # EMA period for trend filter


class MeanReversionStrategy(BaseStrategy):
    """
    RSI Mean Reversion with EMA50 trend filter.

    Entry  (BUY):  RSI(14) < 35  AND  price < EMA(50)
                   AND (optional) sentiment not in extreme greed
    Exit  (SELL):  RSI(14) > 55
                   (hard SL/TP/timeout exits handled by the execution layer)

    Args:
        rsi_period:    RSI lookback window (default 14)
        rsi_oversold:  RSI threshold to trigger BUY (default 35)
        rsi_exit:      RSI threshold to trigger SELL (default 55)
        trend_period:  EMA period for trend filter (default 50)
        use_sentiment: if True, skips entry when sentiment composite >= 0.4 (greedy)
        symbol:        trading symbol passed to sentiment aggregator (e.g. "BTCUSDT")
    """

    def __init__(
        self,
        rsi_period:    int   = MR_RSI_PERIOD,
        rsi_oversold:  float = MR_RSI_OVERSOLD,
        rsi_exit:      float = MR_RSI_EXIT,
        trend_period:  int   = MR_TREND_PERIOD,
        use_sentiment: bool  = False,
        symbol:        str   = "BTCUSDT",
    ) -> None:
        self.rsi_period    = rsi_period
        self.rsi_oversold  = rsi_oversold
        self.rsi_exit      = rsi_exit
        self.trend_period  = trend_period
        self.use_sentiment = use_sentiment
        self.symbol        = symbol

    @property
    def name(self) -> str:
        return "mean_reversion"

    def generate_signal(self, market_data: MarketData) -> str:
        prices   = market_data["prices"]
        position = market_data["position"]

        # Need enough bars for EMA50 + RSI(14)
        min_required = max(self.trend_period, self.rsi_period + 1)
        if len(prices) < min_required:
            raise ValueError(
                f"{self.name}: need >= {min_required} prices, got {len(prices)}."
            )

        rsi           = self._rsi(prices, self.rsi_period)
        trend_ema     = self._ema(prices, self.trend_period)
        current_price = prices[-1]

        # EXIT: RSI has recovered — signal-based exit
        if position == "LONG":
            if rsi > self.rsi_exit:
                return config.SIGNAL_SELL
            return config.SIGNAL_NO_TRADE

        # ENTRY: oversold AND price below trend (true dip, not a breakout)
        if rsi < self.rsi_oversold and current_price < trend_ema:
            if self.use_sentiment and self._sentiment_blocks_entry():
                return config.SIGNAL_NO_TRADE
            return config.SIGNAL_BUY

        return config.SIGNAL_NO_TRADE

    def sentiment_sizing_multiplier(self) -> float:
        """
        Return a position sizing multiplier based on current sentiment.
        Called by the execution layer if use_sentiment=True.
        1.2x in extreme fear, 0.8x in greed, 1.0x otherwise.
        """
        if not self.use_sentiment:
            return 1.0
        try:
            from sentiment import aggregator
            result = aggregator.fetch(self.symbol)
            return result.mr_sizing_multiplier()
        except Exception as exc:
            logger.warning("MR sentiment_sizing_multiplier failed: %s", exc)
            return 1.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sentiment_blocks_entry(self) -> bool:
        """Return True if sentiment is too bullish to enter a MR long."""
        try:
            from sentiment import aggregator
            result = aggregator.fetch(self.symbol)
            if result.should_skip_mr_entry():
                logger.info(
                    "MR[%s]: sentiment blocks entry — %s",
                    self.symbol, result.summary(),
                )
                return True
            return False
        except Exception as exc:
            logger.warning("MR sentiment check failed, allowing entry: %s", exc)
            return False  # fail open — don't block trade on API error

    def _ema(self, prices: List[float], period: int) -> float:
        """EMA seeded with SMA of first `period` bars."""
        if len(prices) < period:
            raise ValueError(
                f"{self.name}: need >= {period} prices for EMA, got {len(prices)}."
            )
        k   = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        return ema

    def _rsi(self, prices: List[float], period: int) -> float:
        """
        RSI using Wilder's smoothed average.
        Returns 50.0 for flat price series to avoid division by zero.
        """
        if len(prices) < period + 1:
            raise ValueError(
                f"{self.name}: need >= {period + 1} prices for RSI, got {len(prices)}."
            )

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains  = [d if d > 0 else 0.0 for d in deltas]
        losses = [abs(d) if d < 0 else 0.0 for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_gain == 0.0 and avg_loss == 0.0:
            return 50.0
        if avg_loss == 0.0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
