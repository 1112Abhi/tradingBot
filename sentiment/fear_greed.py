# sentiment/fear_greed.py — Crypto Fear & Greed Index
#
# Source: Alternative.me public API (free, no key required)
# Updates: Daily (~00:00 UTC)
# Scale:   0 (Extreme Fear) → 100 (Extreme Greed)
#
# Thresholds used:
#   0–24   → Extreme Fear   (contrarian bullish for MR)
#   25–44  → Fear
#   45–55  → Neutral
#   56–74  → Greed
#   75–100 → Extreme Greed  (contrarian bearish / avoid MR longs)

import time
from typing import Optional, Tuple

import requests

_API_URL = "https://api.alternative.me/fng/?limit=1"

# Labels as returned by the API
LABEL_EXTREME_FEAR  = "Extreme Fear"
LABEL_FEAR          = "Fear"
LABEL_NEUTRAL       = "Neutral"
LABEL_GREED         = "Greed"
LABEL_EXTREME_GREED = "Extreme Greed"

# Cache: (value, label, fetched_at_unix)
_cache: Optional[Tuple[int, str, float]] = None
_CACHE_TTL_SECONDS = 4 * 3600  # refresh every 4h (index updates daily)


def fetch() -> Tuple[int, str]:
    """
    Return (score: int, label: str) from Fear & Greed index.
    Uses a 4h in-memory cache to avoid hammering the API.

    Returns:
        score: 0–100
        label: e.g. "Fear", "Extreme Greed"

    Raises:
        RuntimeError: if the API call fails after 1 attempt.
    """
    global _cache

    now = time.time()
    if _cache is not None and (now - _cache[2]) < _CACHE_TTL_SECONDS:
        return _cache[0], _cache[1]

    try:
        resp = requests.get(_API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()["data"][0]
        value = int(data["value"])
        label = data["value_classification"]
        _cache = (value, label, now)
        return value, label
    except Exception as exc:
        raise RuntimeError(f"fear_greed.fetch failed: {exc}") from exc


def score_to_signal(value: int) -> float:
    """
    Convert F&G score to crowd sentiment in [-1.0, +1.0].

    Positive = crowd bullish (bad for MR entry, good for Donchian momentum).
    Negative = crowd bearish/fearful (good for MR contrarian entry).

        Extreme Fear  → -1.0  (crowd very bearish → MR high conviction)
        Fear          → -0.5
        Neutral       →  0.0
        Greed         → +0.5
        Extreme Greed → +1.0  (crowd very bullish → skip MR entry)
    """
    if value <= 24:
        return -1.0
    if value <= 44:
        return -0.5
    if value <= 55:
        return 0.0
    if value <= 74:
        return 0.5
    return 1.0
