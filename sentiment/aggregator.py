# sentiment/aggregator.py — Multi-Source Sentiment Aggregator
#
# Combines Fear & Greed, Funding Rate, DVOL/Put-Call, and News
# into a single composite score used as a strategy filter.
#
# Weights (sum to 1.0):
#   Fear & Greed : 0.30  — most reliable, multi-source, daily
#   Funding Rate : 0.30  — real-time, strongest short-term contrarian signal
#   DVOL         : 0.20  — options implied vol (panic vs complacency)
#   Put/Call     : 0.10  — options positioning (hedging vs FOMO)
#   News         : 0.10  — weakest signal, tiebreaker only
#
# Composite score range: -1.0 (very bearish) to +1.0 (very bullish)
#
# Strategy application:
#   MR (contrarian):
#     composite < -0.2  → market fearful → HIGH conviction entry → size 1.2x
#     composite > +0.4  → market greedy → SKIP entry (crowd already long)
#
#   Donchian (momentum):
#     composite > +0.3  → momentum aligned → normal entry
#     composite < -0.3  → counter-trend breakout → SKIP or size 0.8x

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from sentiment import deribit, fear_greed, funding_rate, news

logger = logging.getLogger(__name__)

# Source weights (must sum to 1.0)
_WEIGHTS: Dict[str, float] = {
    "fear_greed":   0.30,
    "funding_rate": 0.30,
    "dvol":         0.20,
    "put_call":     0.10,
    "news":         0.10,
}

# Position sizing multipliers
SIZE_HIGH_CONVICTION = 1.2   # extreme fear → increase MR size
SIZE_NORMAL          = 1.0
SIZE_CAUTIOUS        = 0.8   # extreme greed → reduce MR size

# Thresholds
MR_SKIP_ABOVE      =  0.4   # composite > this → skip MR buy (market greedy)
MR_HIGH_CONV_BELOW = -0.2   # composite < this → high conviction MR entry
DONCHIAN_SKIP_BELOW = -0.3  # composite < this → skip Donchian long


@dataclass
class SentimentResult:
    """Structured result from the sentiment aggregator."""
    composite:      float           # -1.0 to +1.0
    components:     Dict[str, float] = field(default_factory=dict)
    errors:         Dict[str, str]   = field(default_factory=dict)

    # Derived convenience fields
    fg_score:       int    = 0       # 0–100
    fg_label:       str    = ""
    funding:        float  = 0.0     # decimal rate
    funding_label:  str    = ""
    dvol:           float  = 0.0
    dvol_label:     str    = ""
    put_call:       float  = 0.0
    news_score:     float  = 0.0
    news_label:     str    = ""

    def mr_sizing_multiplier(self) -> float:
        """Position size multiplier for mean-reversion strategies."""
        if self.composite <= MR_HIGH_CONV_BELOW:
            return SIZE_HIGH_CONVICTION
        if self.composite >= MR_SKIP_ABOVE:
            return SIZE_CAUTIOUS
        return SIZE_NORMAL

    def should_skip_mr_entry(self) -> bool:
        """True when sentiment too bullish — MR long entry is risky."""
        return self.composite >= MR_SKIP_ABOVE

    def should_skip_donchian_long(self) -> bool:
        """True when sentiment too bearish — momentum breakout is counter-trend."""
        return self.composite <= DONCHIAN_SKIP_BELOW

    def summary(self) -> str:
        """One-line human readable summary."""
        comp_str = f"{self.composite:+.2f}"
        parts = [f"composite={comp_str}"]
        if self.fg_label:
            parts.append(f"F&G={self.fg_score}({self.fg_label})")
        if self.funding_label:
            rate_pct = self.funding * 100
            parts.append(f"funding={rate_pct:+.4f}%({self.funding_label})")
        if self.dvol_label:
            parts.append(f"DVOL={self.dvol:.1f}({self.dvol_label})")
        if self.put_call:
            parts.append(f"P/C={self.put_call:.2f}")
        if self.news_label:
            parts.append(f"news={self.news_score:+.2f}({self.news_label})")
        if self.errors:
            parts.append(f"errors={list(self.errors.keys())}")
        return " | ".join(parts)


def fetch(symbol: str = "BTCUSDT") -> SentimentResult:
    """
    Fetch all sentiment sources and return a SentimentResult.

    Gracefully handles partial failures — if one source fails, it is
    excluded from the composite (weights are renormalised automatically).

    Args:
        symbol: trading symbol e.g. "BTCUSDT", "ETHUSDT", "SOLUSDT"

    Returns:
        SentimentResult with composite score and per-source details.
    """
    # Derive Deribit currency from symbol
    deribit_currency = _symbol_to_deribit(symbol)

    result = SentimentResult(composite=0.0)
    signals: Dict[str, float] = {}

    # --- Fear & Greed ---
    try:
        fg_val, fg_label = fear_greed.fetch()
        fg_sig = fear_greed.score_to_signal(fg_val)
        signals["fear_greed"] = fg_sig
        result.fg_score = fg_val
        result.fg_label = fg_label
    except Exception as exc:
        result.errors["fear_greed"] = str(exc)
        logger.warning("Sentiment: fear_greed failed: %s", exc)

    # --- Funding Rate ---
    try:
        funding, funding_label = funding_rate.fetch(symbol)
        funding_sig = funding_rate.score_to_signal(funding)
        signals["funding_rate"] = funding_sig
        result.funding       = funding
        result.funding_label = funding_label
    except Exception as exc:
        result.errors["funding_rate"] = str(exc)
        logger.warning("Sentiment: funding_rate failed: %s", exc)

    # --- Deribit DVOL + Put/Call ---
    try:
        dvol, pc_ratio, dvol_label = deribit.fetch(deribit_currency)
        dvol_sig = deribit.dvol_signal(dvol)
        pc_sig   = deribit.put_call_signal(pc_ratio)
        signals["dvol"]     = dvol_sig
        signals["put_call"] = pc_sig
        result.dvol       = dvol
        result.dvol_label = dvol_label
        result.put_call   = pc_ratio
    except Exception as exc:
        result.errors["deribit"] = str(exc)
        logger.warning("Sentiment: deribit failed: %s", exc)

    # --- News (Alpha Vantage) ---
    try:
        news_score, news_label = news.fetch(symbol)
        news_sig = news.score_to_signal(news_score)
        signals["news"]    = news_sig
        result.news_score  = news_score
        result.news_label  = news_label
    except Exception as exc:
        result.errors["news"] = str(exc)
        logger.warning("Sentiment: news failed: %s", exc)

    # --- Composite: weighted average of available signals ---
    result.components = signals
    if signals:
        total_weight = sum(_WEIGHTS[k] for k in signals if k in _WEIGHTS)
        if total_weight > 0:
            result.composite = sum(
                signals[k] * _WEIGHTS[k]
                for k in signals
                if k in _WEIGHTS
            ) / total_weight

    logger.info("Sentiment[%s]: %s", symbol, result.summary())
    return result


def _symbol_to_deribit(symbol: str) -> str:
    mapping = {"BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "BTC"}
    return mapping.get(symbol, "BTC")
