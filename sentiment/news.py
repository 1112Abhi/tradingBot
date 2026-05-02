# sentiment/news.py — Alpha Vantage News Sentiment
#
# Source: Alpha Vantage NEWS_SENTIMENT endpoint (free, 25 calls/day)
# Updates: Near real-time news articles
#
# Strategy:
#   - Fetch top 50 articles for the given ticker
#   - Filter to articles with relevance_score >= 0.3 (BTC-specific news)
#   - Average ticker_sentiment_score across top-10 most relevant articles
#   - Cache for 4h to stay within 25-call/day free limit (6 calls/day = safe)
#
# Sentiment score range: -1.0 (bearish) to +1.0 (bullish)
# Labels: Bearish, Somewhat-Bearish, Neutral, Somewhat-Bullish, Bullish

import time
from typing import Optional, Tuple

import requests

import config

_API_URL = "https://www.alphavantage.co/query"

# Map AV ticker → crypto symbol for cache key
_TICKER_MAP = {
    "BTCUSDT": "CRYPTO:BTC",
    "ETHUSDT": "CRYPTO:ETH",
    "SOLUSDT": "CRYPTO:SOL",
}

# Cache: {av_ticker: (score, label, fetched_at)}
_cache: dict = {}
_CACHE_TTL_SECONDS    = 4 * 3600
_MIN_RELEVANCE        = 0.3   # ignore articles with low BTC relevance
_MAX_ARTICLES         = 10    # average over top N by relevance


def fetch(symbol: str = "BTCUSDT") -> Tuple[float, str]:
    """
    Return (avg_sentiment_score, label) for the given trading symbol.

    Args:
        symbol: trading symbol e.g. "BTCUSDT" — mapped to AV ticker internally

    Returns:
        score: -1.0 to +1.0 (negative = bearish, positive = bullish)
        label: e.g. "Somewhat-Bearish", "Neutral", "Bullish"

    Raises:
        RuntimeError: if API key missing or call fails.
    """
    av_ticker = _TICKER_MAP.get(symbol, "CRYPTO:BTC")
    now = time.time()
    cached = _cache.get(av_ticker)
    if cached is not None and (now - cached[2]) < _CACHE_TTL_SECONDS:
        return cached[0], cached[1]

    api_key = getattr(config, "ALPHAVANTAGE_API_KEY", None)
    if not api_key:
        raise RuntimeError(
            "ALPHAVANTAGE_API_KEY not set in config.py — news sentiment unavailable"
        )

    try:
        resp = requests.get(
            _API_URL,
            params={
                "function": "NEWS_SENTIMENT",
                "tickers":  av_ticker,
                "limit":    50,
                "apikey":   api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        feed = resp.json().get("feed", [])
    except Exception as exc:
        raise RuntimeError(f"news.fetch({symbol}) failed: {exc}") from exc

    # Extract per-ticker sentiment for relevant articles
    scored = []
    for article in feed:
        for ts in article.get("ticker_sentiment", []):
            if ts.get("ticker") == av_ticker:
                relevance = float(ts.get("relevance_score", 0))
                if relevance >= _MIN_RELEVANCE:
                    scored.append((relevance, float(ts.get("ticker_sentiment_score", 0))))

    # Sort by relevance desc, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:_MAX_ARTICLES]

    if not top:
        score = 0.0
    else:
        score = sum(s for _, s in top) / len(top)

    label = _score_label(score)
    _cache[av_ticker] = (score, label, now)
    return score, label


def score_to_signal(score: float) -> float:
    """
    Convert news sentiment score to signal [-1.0, +1.0].

    Used as tiebreaker (lowest weight in aggregator).
    Contrarian for MR: bad news = buy the dip.
    Confirming for Donchian: good news = breakout continuation.
    """
    return max(-1.0, min(1.0, score))


def _score_label(score: float) -> str:
    if score <= -0.35:
        return "Bearish"
    if score <= -0.15:
        return "Somewhat-Bearish"
    if score <= 0.15:
        return "Neutral"
    if score <= 0.35:
        return "Somewhat-Bullish"
    return "Bullish"
