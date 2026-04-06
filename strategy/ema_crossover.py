# strategy/ema_crossover.py - EMA Crossover Strategy

from typing import List
import config
from strategy.base import BaseStrategy, MarketData


class MACrossoverStrategy(BaseStrategy):
    """
    EMA Crossover with Trend Filter + RSI Entry Filter (V5).

    Entry  (BUY):  fast EMA crosses above slow EMA
                   AND price > trend EMA (uptrend confirmation)
                   AND RSI_BUY_MIN <= RSI <= RSI_BUY_MAX (not overbought, has momentum)
    Exit   (SELL): fast EMA crosses below slow EMA
                   OR price drops below stop-loss level
    Hold   (NO_TRADE): no crossover, no stop triggered, or entry blocked by trend/RSI filter
    """

    def __init__(
        self,
        fast_period: int = config.FAST_PERIOD,
        slow_period: int = config.SLOW_PERIOD,
        trend_period: int = config.TREND_PERIOD,
        stop_loss_pct: float = config.STOP_LOSS_PCT,
        rsi_period: int = config.RSI_PERIOD,
        rsi_buy_min: float = config.RSI_BUY_MIN,
        rsi_buy_max: float = config.RSI_BUY_MAX,
    ) -> None:
        self.fast_period   = fast_period
        self.slow_period   = slow_period
        self.trend_period  = trend_period
        self.stop_loss_pct = stop_loss_pct
        self.rsi_period    = rsi_period
        self.rsi_buy_min   = rsi_buy_min
        self.rsi_buy_max   = rsi_buy_max

    @property
    def name(self) -> str:
        return "ema_crossover"

    def generate_signal(self, market_data: MarketData) -> str:
        prices      = market_data["prices"]
        entry_price = market_data["entry_price"]

        # Need enough data for trend EMA (longest EMA period) + RSI (needs period+1 bars)
        min_required = max(self.trend_period + 1, self.rsi_period + 1)
        if len(prices) < min_required:
            raise ValueError(
                f"{self.name}: need >= {min_required} prices, got {len(prices)}."
            )

        current_price = prices[-1]

        # Stop loss (highest priority — only meaningful when in a position)
        if entry_price is not None:
            if current_price <= entry_price * (1 - self.stop_loss_pct):
                return config.SIGNAL_SELL

        fast_now  = self._ema(prices,       self.fast_period)
        slow_now  = self._ema(prices,       self.slow_period)
        trend_now = self._ema(prices,       self.trend_period)
        fast_prev = self._ema(prices[:-1],  self.fast_period)
        slow_prev = self._ema(prices[:-1],  self.slow_period)

        # BUY: fast crosses above slow AND trend filter AND RSI filter
        if fast_prev <= slow_prev and fast_now > slow_now:
            if current_price > trend_now:
                rsi = self._rsi(prices, self.rsi_period)
                if self.rsi_buy_min <= rsi <= self.rsi_buy_max:
                    return config.SIGNAL_BUY
            # Buy signal suppressed by trend or RSI filter
            return config.SIGNAL_NO_TRADE

        # SELL: fast crosses below slow (RSI filter does NOT apply to exits)
        if fast_prev >= slow_prev and fast_now < slow_now:
            return config.SIGNAL_SELL
        return config.SIGNAL_NO_TRADE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ema(self, prices: List[float], period: int) -> float:
        """Compute EMA seeded with SMA of first `period` bars."""
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
        Compute RSI using Wilder's smoothed average (standard definition).

        Requires at least period+1 prices to compute one RSI value.
        Returns 50.0 for flat price series (no gains or losses) to avoid
        division by zero — 50 is neutral and will not block the BUY signal.
        """
        if len(prices) < period + 1:
            raise ValueError(
                f"{self.name}: need >= {period + 1} prices for RSI, got {len(prices)}."
            )

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Seed: simple average of first `period` gains and losses
        gains  = [d if d > 0 else 0.0 for d in deltas]
        losses = [abs(d) if d < 0 else 0.0 for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Wilder smoothing over remaining deltas
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        # Flat price series: no gains or losses → neutral RSI
        if avg_gain == 0.0 and avg_loss == 0.0:
            return 50.0

        # All gains, no losses → RSI = 100
        if avg_loss == 0.0:
            return 100.0

        rs  = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
