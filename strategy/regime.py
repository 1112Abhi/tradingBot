# strategy/regime.py — Market Regime Detector
#
# Detects whether the market is currently TRENDING or RANGING using
# linear regression R² over a rolling window of close prices.
#
# Method — Linear Regression R²:
#   Fit a straight line to the last `period` closes.
#   R² measures how well that line explains price movement:
#     R² > threshold → price moving consistently in one direction → TRENDING
#     R² < threshold → price choppy, oscillating                 → RANGING
#
# Why R² vs ADX:
#   ADX requires OHLC (high/low). We only have close prices.
#   R² works purely on closes, is mathematically clean, and is interpretable:
#   "how linear is recent price movement?" — exactly what we need.
#
# Regime implications:
#   TRENDING → favour EMA Crossover, Donchian (momentum strategies)
#   RANGING  → favour Mean Reversion, BB Breakout (oscillation strategies)

from typing import List


REGIME_TRENDING = "trending"
REGIME_RANGING  = "ranging"

DEFAULT_PERIOD    = 20    # lookback window for R² calculation
DEFAULT_THRESHOLD = 0.45  # R² above this → trending (tunable)


class RegimeDetector:
    """
    Classifies market regime as TRENDING or RANGING using linear regression R².

    Usage:
        detector = RegimeDetector(period=20, threshold=0.45)
        regime   = detector.detect(prices)   # "trending" or "ranging"
        r2       = detector.r_squared(prices) # raw score
    """

    def __init__(
        self,
        period:    int   = DEFAULT_PERIOD,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self.period    = period
        self.threshold = threshold

    def detect(self, prices: List[float]) -> str:
        """
        Return REGIME_TRENDING or REGIME_RANGING based on recent prices.

        Args:
            prices: Close prices, oldest first. Must have >= period bars.

        Returns:
            "trending" or "ranging"
        """
        r2 = self.r_squared(prices[-self.period:])
        return REGIME_TRENDING if r2 >= self.threshold else REGIME_RANGING

    def r_squared(self, prices: List[float]) -> float:
        """
        Compute linear regression R² for the given price series.

        R² = 1 → perfect linear trend (strong trending)
        R² = 0 → no linear trend (pure ranging/noise)

        Args:
            prices: Close prices to evaluate (uses all provided bars).

        Returns:
            R² value in [0.0, 1.0]
        """
        n = len(prices)
        if n < 3:
            return 0.0

        x     = list(range(n))
        mx    = sum(x) / n
        my    = sum(prices) / n

        ss_xy = sum((x[i] - mx) * (prices[i] - my) for i in range(n))
        ss_xx = sum((x[i] - mx) ** 2               for i in range(n))
        ss_yy = sum((prices[i] - my) ** 2           for i in range(n))

        if ss_xx == 0 or ss_yy == 0:
            return 0.0

        r = ss_xy / (ss_xx * ss_yy) ** 0.5
        return round(r * r, 6)

    def score_label(self, prices: List[float]) -> str:
        """Human-readable label with R² score. Useful for logging."""
        r2     = self.r_squared(prices[-self.period:])
        regime = REGIME_TRENDING if r2 >= self.threshold else REGIME_RANGING
        return f"{regime} (R²={r2:.3f})"
