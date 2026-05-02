# sentiment/funding_rate.py — Binance Perpetual Futures Funding Rate
#
# Source: Binance USDM Futures API (free, no key required)
# Updates: Every 8 hours (00:00, 08:00, 16:00 UTC)
#
# Interpretation (contrarian):
#   Rate >> 0   → longs are paying shorts → market overleveraged long
#                  → mean reversion entries more reliable (crowded trade)
#   Rate ~  0   → neutral positioning
#   Rate << 0   → shorts paying longs → crowded short → contrarian bullish
#
# Typical BTC range: -0.05% to +0.10% per 8h period
# Thresholds (annualised equivalents in percentage points):
#   > +0.05%  → crowded long  (bearish sentiment signal)
#   < -0.03%  → crowded short (bullish sentiment signal)

import time
from typing import Optional, Tuple

import requests

_BASE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"

# Cache per symbol: {symbol: (rate, fetched_at)}
_cache: dict = {}
_CACHE_TTL_SECONDS = 4 * 3600  # funding updates every 8h, we refresh every 4h

# Thresholds (as decimal, not percent)
CROWDED_LONG_THRESHOLD  = 0.0005   # +0.05%
CROWDED_SHORT_THRESHOLD = -0.0003  # -0.03%


def fetch(symbol: str = "BTCUSDT") -> Tuple[float, str]:
    """
    Return (rate: float, label: str) for the latest funding rate.

    Args:
        symbol: Binance perpetual symbol, e.g. "BTCUSDT", "ETHUSDT"

    Returns:
        rate:  funding rate as decimal (e.g. 0.0001 = 0.01%)
        label: "crowded_long", "crowded_short", or "neutral"

    Raises:
        RuntimeError: if API call fails.
    """
    now = time.time()
    cached = _cache.get(symbol)
    if cached is not None and (now - cached[1]) < _CACHE_TTL_SECONDS:
        rate = cached[0]
        return rate, _label(rate)

    try:
        resp = requests.get(
            _BASE_URL,
            params={"symbol": symbol, "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        rate = float(data[0]["fundingRate"])
        _cache[symbol] = (rate, now)
        return rate, _label(rate)
    except Exception as exc:
        raise RuntimeError(f"funding_rate.fetch({symbol}) failed: {exc}") from exc


def score_to_signal(rate: float) -> float:
    """
    Convert funding rate to crowd sentiment in [-1.0, +1.0].

    Positive = crowd long/bullish (skip MR entry — crowd already long).
    Negative = crowd short/bearish (good for MR — contrarian bounce likely).

        Crowded long  (rate > +0.05%) → +0.8  (longs paying shorts → crowd bullish)
        Mild long     (rate > +0.02%) → +0.3
        Neutral                       →  0.0
        Mild short    (rate < -0.01%) → -0.3
        Crowded short (rate < -0.03%) → -0.8  (shorts paying longs → crowd bearish)
    """
    if rate >= CROWDED_LONG_THRESHOLD:
        return 0.8
    if rate >= 0.0002:
        return 0.3
    if rate <= CROWDED_SHORT_THRESHOLD:
        return -0.8
    if rate <= -0.0001:
        return -0.3
    return 0.0


def _label(rate: float) -> str:
    if rate >= CROWDED_LONG_THRESHOLD:
        return "crowded_long"
    if rate <= CROWDED_SHORT_THRESHOLD:
        return "crowded_short"
    return "neutral"
