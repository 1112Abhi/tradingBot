# strategy/risk_manager.py - ATR-based position sizing

from typing import List

import config


def compute_atr(prices: List[float], period: int = config.ATR_PERIOD) -> float:
    """
    Compute ATR using close-to-close true range (no OHLC needed).

    True Range (simplified) = |close[t] - close[t-1]|
    ATR = Wilder-smoothed average over `period` bars.

    Args:
        prices: List of mid/close prices, oldest first.
        period: ATR lookback (default config.ATR_PERIOD).

    Returns:
        ATR value in price units.

    Raises:
        ValueError: if fewer than period+1 prices are provided.
    """
    if len(prices) < period + 1:
        raise ValueError(
            f"compute_atr: need >= {period + 1} prices, got {len(prices)}"
        )

    trs = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]

    # Wilder seed: simple average of first `period` true ranges
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period

    return atr


def compute_position_size(
    capital: float,
    atr: float,
    price: float,
    sl_pct: float = config.BACKTEST_STOP_LOSS_PCT,
) -> float:
    """
    Compute position value using ATR-scaled risk-per-trade sizing.

    Formula:
        base_position = capital * RISK_PER_TRADE / sl_pct
        atr_pct       = atr / price          (ATR as fraction of price)
        scale         = ATR_REFERENCE_PCT / atr_pct
        position      = base_position * scale

    When ATR is at the reference level, scale=1 and position = base.
    When ATR is elevated (high vol), scale < 1 and position shrinks.
    When ATR is low (quiet market), scale > 1 but still capped by MAX_CAPITAL_FRACTION.

    Capped at capital * MAX_CAPITAL_FRACTION (hard ceiling).

    Args:
        capital:  Current capital in dollars.
        atr:      ATR value in price units.
        price:    Current price (to normalise ATR).
        sl_pct:   Stop-loss fraction (e.g. 0.015 for 1.5%).

    Returns:
        Position value in dollars (>= 0).
    """
    if price <= 0 or capital <= 0:
        return 0.0

    atr_pct = atr / price
    if atr_pct <= 0:
        atr_pct = config.ATR_REFERENCE_PCT  # fallback for zero/flat ATR

    base_position = capital * config.RISK_PER_TRADE / sl_pct
    scale         = config.ATR_REFERENCE_PCT / atr_pct
    position      = base_position * scale

    max_position = capital * config.MAX_CAPITAL_FRACTION
    return max(0.0, min(position, max_position))
