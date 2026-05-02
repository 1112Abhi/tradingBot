# sentiment/deribit.py — Deribit Options Sentiment (DVOL + Put/Call Ratio)
#
# Source: Deribit public REST API (free, no key required)
# Updates: Real-time
#
# DVOL (Deribit Volatility Index) — crypto equivalent of VIX:
#   Measures 30-day implied volatility of BTC/ETH options
#   High DVOL = fear/panic in options market
#   Low  DVOL = complacency
#   Typical BTC range: 40–120
#   Thresholds: < 50 = low vol (complacency), > 80 = high fear
#
# Put/Call OI Ratio:
#   > 1.0  → more put OI than call OI → market is hedging → contrarian bullish
#   < 0.5  → retail FOMO buying calls → crowded → contrarian bearish
#   0.5–1.0 → neutral

import time
from typing import Optional, Tuple

import requests

_DVOL_URL    = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
_OPTIONS_URL = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"

# Cache per currency: {currency: (dvol, put_call_ratio, fetched_at)}
_cache: dict = {}
_CACHE_TTL_SECONDS = 4 * 3600

# DVOL thresholds
DVOL_HIGH_FEAR    = 80   # panic — MR entries more contrarian
DVOL_LOW_COMPLACE = 50   # complacency — Donchian breakouts less reliable

# Put/Call ratio thresholds
PC_RATIO_BEARISH = 0.4   # too many calls (FOMO) → bearish contrarian
PC_RATIO_BULLISH = 1.0   # heavy put buying (hedging) → bullish contrarian


def fetch(currency: str = "BTC") -> Tuple[float, float, str]:
    """
    Return (dvol, put_call_ratio, label) for the given currency.

    Args:
        currency: "BTC" or "ETH"

    Returns:
        dvol:           implied volatility index value (e.g. 46.1)
        put_call_ratio: puts OI / calls OI (e.g. 0.50)
        label:          "high_fear", "low_vol", or "neutral"

    Raises:
        RuntimeError: if either API call fails.
    """
    now = time.time()
    cached = _cache.get(currency)
    if cached is not None and (now - cached[2]) < _CACHE_TTL_SECONDS:
        dvol, pc, _ = cached
        return dvol, pc, _dvol_label(dvol)

    dvol        = _fetch_dvol(currency)
    put_call    = _fetch_put_call_ratio(currency)
    _cache[currency] = (dvol, put_call, now)
    return dvol, put_call, _dvol_label(dvol)


def dvol_signal(dvol: float) -> float:
    """
    Convert DVOL to crowd sentiment in [-1.0, +1.0].

    Positive = crowd complacent/bullish. Negative = crowd panicking/fearful.

    High DVOL (>80, panic)    → -0.8  (fear in market → crowd bearish → good for MR)
    Low DVOL  (<50, complace) → +0.3  (complacency → crowd bullish → caution for MR)
    Normal range              →  0.0
    """
    if dvol >= DVOL_HIGH_FEAR:
        return -0.8
    if dvol <= DVOL_LOW_COMPLACE:
        return 0.3
    return 0.0


def put_call_signal(put_call_ratio: float) -> float:
    """
    Convert put/call OI ratio to crowd sentiment in [-1.0, +1.0].

    Positive = crowd buying calls (bullish). Negative = crowd buying puts (bearish).

    High PC (>1.0) → heavy put buying → crowd hedging/bearish → -0.6
    Low PC  (<0.4) → heavy call buying (FOMO) → crowd bullish  → +0.6
    """
    if put_call_ratio >= PC_RATIO_BULLISH:
        return -0.6   # heavy hedging → crowd bearish
    if put_call_ratio <= PC_RATIO_BEARISH:
        return 0.6    # FOMO calls → crowd bullish
    return 0.0


def _fetch_dvol(currency: str) -> float:
    now_ms   = int(time.time() * 1000)
    start_ms = now_ms - 3600 * 1000  # last 1h
    try:
        resp = requests.get(
            _DVOL_URL,
            params={
                "currency":        currency,
                "start_timestamp": start_ms,
                "end_timestamp":   now_ms,
                "resolution":      3600,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()["result"]["data"]
        if not data:
            raise ValueError("Empty DVOL response")
        # data rows: [timestamp, open, high, low, close]
        return float(data[-1][4])  # last close
    except Exception as exc:
        raise RuntimeError(f"deribit._fetch_dvol({currency}) failed: {exc}") from exc


def _fetch_put_call_ratio(currency: str) -> float:
    try:
        resp = requests.get(
            _OPTIONS_URL,
            params={"currency": currency, "kind": "option"},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json().get("result", [])
        call_oi = sum(
            x.get("open_interest", 0)
            for x in result
            if x.get("instrument_name", "").endswith("-C")
        )
        put_oi = sum(
            x.get("open_interest", 0)
            for x in result
            if x.get("instrument_name", "").endswith("-P")
        )
        if call_oi == 0:
            return 1.0  # default neutral if no data
        return put_oi / call_oi
    except Exception as exc:
        raise RuntimeError(
            f"deribit._fetch_put_call_ratio({currency}) failed: {exc}"
        ) from exc


def _dvol_label(dvol: float) -> str:
    if dvol >= DVOL_HIGH_FEAR:
        return "high_fear"
    if dvol <= DVOL_LOW_COMPLACE:
        return "low_vol"
    return "neutral"
