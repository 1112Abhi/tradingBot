# backtest/metrics.py - Performance Metrics

from typing import List

# Bars per calendar year for common candle intervals
_BARS_PER_YEAR = {
    "1m":  525_600, "3m":  175_200, "5m":  105_120,
    "15m":  35_040, "30m":  17_520,
    "1h":    8_760, "2h":    4_380, "4h":    2_190,
    "6h":    1_460, "8h":    1_095, "12h":     730,
    "1d":      365, "1w":       52,
}


def compute_metrics(
    trades: List[dict],
    initial_capital: float,
    final_capital: float,
    total_bars: int,
    warmup_bars: int,
    interval: str = "1h",
) -> dict:
    """
    Compute backtest performance metrics from a completed trade list.

    Args:
        trades:          List of closed trade dicts (each has pnl_dollar, pnl_pct).
        initial_capital: Capital at start of backtest.
        final_capital:   Capital at end (after all trades + fees).
        total_bars:      Total bars loaded from DB.
        warmup_bars:     Bars skipped during EMA warmup (not tradeable).
        interval:        Candle interval string (e.g. "1h", "4h") for Sharpe annualisation.

    Returns:
        Dict of metrics ready for DB insert and terminal display.
    """
    tradeable_bars   = total_bars - warmup_bars
    total_trades     = len(trades)
    winning_trades   = sum(1 for t in trades if t["pnl_dollar"] > 0)
    win_rate         = (winning_trades / total_trades * 100) if total_trades else 0.0
    total_return     = (final_capital - initial_capital) / initial_capital * 100
    max_drawdown     = _compute_max_drawdown(trades, initial_capital)
    sharpe           = _compute_sharpe(trades, tradeable_bars, interval)
    total_fees_paid  = round(sum(t.get("fees_paid", 0.0) for t in trades), 4)
    gross_pnl        = round(sum(t.get("gross_pnl", t["pnl_dollar"]) for t in trades), 4)

    return {
        "total_bars":        total_bars,
        "warmup_bars":       warmup_bars,
        "tradeable_bars":    tradeable_bars,
        "total_trades":      total_trades,
        "winning_trades":    winning_trades,
        "win_rate_pct":      round(win_rate, 2),
        "initial_capital":   initial_capital,
        "final_capital":     round(final_capital, 2),
        "gross_pnl":         gross_pnl,
        "total_fees_paid":   total_fees_paid,
        "total_return_pct":  round(total_return, 2),
        "max_drawdown_pct":  round(max_drawdown, 2),
        "sharpe_ratio":      sharpe,
    }


def _compute_max_drawdown(trades: List[dict], initial_capital: float) -> float:
    """
    Compute maximum peak-to-trough drawdown as a percentage.
    Walks the cumulative capital curve trade-by-trade.
    Returns 0.0 if there are no trades.
    """
    if not trades:
        return 0.0

    capital = initial_capital
    peak    = capital
    max_dd  = 0.0

    for trade in trades:
        capital += trade["pnl_dollar"]
        if capital > peak:
            peak = capital
        drawdown = (peak - capital) / peak * 100
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd


def _compute_sharpe(
    trades: List[dict],
    tradeable_bars: int,
    interval: str,
) -> float:
    """
    Compute annualised Sharpe ratio from per-trade returns.

    Annualisation:
        trades_per_year = (total_trades / tradeable_bars) * bars_per_year
        sharpe = (mean_pnl_pct / std_pnl_pct) * sqrt(trades_per_year)

    Returns 0.0 if fewer than 2 trades or zero variance.
    """
    if len(trades) < 2:
        return 0.0

    returns = [t["pnl_pct"] for t in trades]
    n       = len(returns)
    mean_r  = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std_r   = variance ** 0.5

    if std_r == 0.0:
        return 0.0

    bars_per_year   = _BARS_PER_YEAR.get(interval, 8_760)
    trades_per_year = (n / tradeable_bars) * bars_per_year if tradeable_bars else 0.0

    return round(mean_r / std_r * (trades_per_year ** 0.5), 4)
