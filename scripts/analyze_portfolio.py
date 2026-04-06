#!/usr/bin/env python3
"""
analyze_portfolio.py — Portfolio analysis: EMA Crossover vs Mean Reversion.

Compares two independently backtested strategies on the same dataset,
simulates a 50/50 combined portfolio, and evaluates complementarity.

Usage:
    python analyze_portfolio.py
    python analyze_portfolio.py --ema-run <run_id> --mr-run <run_id>
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import sqlite3
from datetime import datetime, timezone

import config

# Default run IDs (BTCUSDT 4h, 3yr, Phase 7.5/7.7)
DEFAULT_EMA_RUN = "86e32169-f2fb-46a5-ae74-e7fff7b88abe"
DEFAULT_MR_RUN  = "d4460323-ba55-4f4f-a0d3-e43bf3e34315"

CAPITAL         = config.BACKTEST_CAPITAL   # $10,000
HALF_CAPITAL    = CAPITAL / 2               # 50/50 split


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_trades(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """Load all trades for a run ordered by entry time."""
    rows = conn.execute(
        """
        SELECT entry_ts, exit_ts, pnl_dollar, pnl_pct, exit_reason,
               entry_price, exit_price
        FROM backtest_trades
        WHERE run_id = ?
        ORDER BY entry_ts
        """,
        (run_id,),
    ).fetchall()
    cols = ["entry_ts", "exit_ts", "pnl_dollar", "pnl_pct", "exit_reason",
            "entry_price", "exit_price"]
    return [dict(zip(cols, r)) for r in rows]


def load_run_meta(conn: sqlite3.Connection, run_id: str) -> dict:
    row = conn.execute(
        "SELECT strategy, total_trades, total_return_pct, win_rate_pct, "
        "max_drawdown_pct, sharpe_ratio, gross_pnl, total_fees_paid "
        "FROM backtest_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    cols = ["strategy", "total_trades", "total_return_pct", "win_rate_pct",
            "max_drawdown_pct", "sharpe_ratio", "gross_pnl", "total_fees_paid"]
    return dict(zip(cols, row))


# ---------------------------------------------------------------------------
# Equity curve
# ---------------------------------------------------------------------------

def build_equity_curve(trades: list[dict], initial_capital: float) -> list[tuple]:
    """
    Returns list of (exit_ts, cumulative_capital) tuples.
    Capital starts at initial_capital; each trade's pnl_dollar is added at exit.
    """
    capital = initial_capital
    curve   = [("start", capital)]
    for t in trades:
        capital += t["pnl_dollar"]
        curve.append((t["exit_ts"], capital))
    return curve


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m   = _mean(values)
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return var ** 0.5


def pearson_correlation(a: list[float], b: list[float]) -> float:
    """Pearson correlation between two equal-length lists."""
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a, b   = a[:n], b[:n]
    ma, mb = _mean(a), _mean(b)
    num    = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    denom  = (_std(a) * _std(b) * (n - 1))
    return round(num / denom, 4) if denom else 0.0


def equity_curve_correlation(curve_a: list[tuple], curve_b: list[tuple]) -> float:
    """
    Correlate equity curves sampled at shared timestamps.
    Uses linear interpolation via step-function (last known value).
    """
    # Build timeline of all exit timestamps from both curves
    ts_a = {t: v for t, v in curve_a if t != "start"}
    ts_b = {t: v for t, v in curve_b if t != "start"}
    all_ts = sorted(set(ts_a) | set(ts_b))

    def interpolate(ts_map: dict, timestamps: list) -> list[float]:
        last = list(ts_map.values())[0] if ts_map else CAPITAL
        out  = []
        for ts in timestamps:
            if ts in ts_map:
                last = ts_map[ts]
            out.append(last)
        return out

    vals_a = interpolate(ts_a, all_ts)
    vals_b = interpolate(ts_b, all_ts)
    return pearson_correlation(vals_a, vals_b)


# ---------------------------------------------------------------------------
# Combined portfolio simulation
# ---------------------------------------------------------------------------

def simulate_combined(ema_trades: list[dict], mr_trades: list[dict]) -> dict:
    """
    Simulate 50/50 portfolio: both strategies run simultaneously on half capital each.
    PnL is scaled by 0.5 (each strategy gets half the capital).
    Combined equity curve merges all trade exits chronologically.
    """
    # Scale each trade's pnl_dollar by 0.5
    events = []
    for t in ema_trades:
        events.append({"ts": t["exit_ts"], "pnl": t["pnl_dollar"] * 0.5, "src": "ema"})
    for t in mr_trades:
        events.append({"ts": t["exit_ts"], "pnl": t["pnl_dollar"] * 0.5, "src": "mr"})
    events.sort(key=lambda e: e["ts"])

    capital  = CAPITAL
    peak     = capital
    max_dd   = 0.0
    returns  = []

    for e in events:
        pnl     = e["pnl"]
        ret_pct = pnl / capital * 100 if capital else 0.0
        capital += pnl
        returns.append(ret_pct)
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100
        if dd > max_dd:
            max_dd = dd

    total_return = (capital - CAPITAL) / CAPITAL * 100
    n_trades     = len(events)
    n_wins       = sum(1 for e in events if e["pnl"] > 0)

    # Annualised Sharpe (4h bars, ~2190/yr, estimate from trade frequency)
    sharpe = _compute_sharpe(returns, n_trades)

    return {
        "total_trades":     n_trades,
        "win_rate_pct":     n_wins / n_trades * 100 if n_trades else 0,
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio":     round(sharpe, 4),
        "final_capital":    round(capital, 2),
        "events":           events,
    }


def _compute_sharpe(returns: list[float], n_trades: int) -> float:
    if len(returns) < 2:
        return 0.0
    m     = _mean(returns)
    s     = _std(returns)
    if s == 0:
        return 0.0
    # Annualise: assume 3yr window ~2190*3=6570 bars, trades_per_year from sample
    bars_per_year   = 2190
    trades_per_year = n_trades / 3  # rough: 3yr dataset
    return m / s * (trades_per_year ** 0.5)


# ---------------------------------------------------------------------------
# Drawdown analysis
# ---------------------------------------------------------------------------

def compute_drawdown_periods(trades: list[dict], initial_capital: float) -> list[dict]:
    """Return list of drawdown episodes: {start, end, depth_pct}."""
    capital  = initial_capital
    peak     = capital
    in_dd    = False
    dd_start = None
    dd_peak  = capital
    periods  = []

    for t in trades:
        capital += t["pnl_dollar"]
        if capital > peak:
            if in_dd:
                depth = (dd_peak - min(capital, dd_peak)) / dd_peak * 100
                periods.append({"start": dd_start, "end": t["exit_ts"], "depth_pct": round(depth, 2)})
                in_dd = False
            peak = capital
        else:
            if not in_dd:
                in_dd    = True
                dd_start = t["entry_ts"]
                dd_peak  = peak

    return periods


# ---------------------------------------------------------------------------
# Regime tagging (simple heuristic: 50-bar EMA slope)
# ---------------------------------------------------------------------------

def tag_regime(conn: sqlite3.Connection, trades: list[dict]) -> list[dict]:
    """
    Tag each trade as 'trending' or 'sideways' based on EMA50 slope at entry.
    Slope = (EMA50_now - EMA50_20bars_ago) / EMA50_20bars_ago
    Threshold: |slope| > 0.005 (0.5%) → trending, else sideways.
    """
    bars = conn.execute(
        "SELECT timestamp, mid FROM prices WHERE symbol='BTCUSDT' AND interval='4h' ORDER BY timestamp"
    ).fetchall()
    bar_list = [{"timestamp": r[0], "mid": r[1]} for r in bars]
    ts_idx   = {b["timestamp"]: i for i, b in enumerate(bar_list)}

    def ema(prices: list, period: int) -> float:
        if len(prices) < period:
            return prices[-1]
        k   = 2.0 / (period + 1)
        val = sum(prices[:period]) / period
        for p in prices[period:]:
            val = p * k + val * (1 - k)
        return val

    tagged = []
    for t in trades:
        idx = ts_idx.get(t["entry_ts"])
        if idx is None or idx < 70:
            t["regime"] = "unknown"
        else:
            prices_now  = [b["mid"] for b in bar_list[max(0, idx-50):idx+1]]
            prices_lag  = [b["mid"] for b in bar_list[max(0, idx-70):idx-19]]
            ema_now     = ema(prices_now, 50)
            ema_lag     = ema(prices_lag, 50)
            slope       = (ema_now - ema_lag) / ema_lag if ema_lag else 0
            t["regime"] = "trending" if abs(slope) > 0.005 else "sideways"
        tagged.append(t)
    return tagged


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

W = 65

def _header(title: str) -> None:
    print()
    print("=" * W)
    print(f"  {title}")
    print("=" * W)


def _row(label: str, value: str) -> None:
    print(f"  {label:<30}{value}")


def _section(title: str) -> None:
    print()
    print(f"  {title}")
    print(f"  {'─'*50}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ema-run", default=DEFAULT_EMA_RUN)
    parser.add_argument("--mr-run",  default=DEFAULT_MR_RUN)
    args = parser.parse_args()

    conn      = sqlite3.connect(config.BACKTEST_DB)
    ema_meta  = load_run_meta(conn, args.ema_run)
    mr_meta   = load_run_meta(conn, args.mr_run)
    ema_trades = load_trades(conn, args.ema_run)
    mr_trades  = load_trades(conn, args.mr_run)

    ema_curve = build_equity_curve(ema_trades, CAPITAL)
    mr_curve  = build_equity_curve(mr_trades,  CAPITAL)

    # ── 1. Individual results ───────────────────────────────────────────
    _header("INDIVIDUAL STRATEGY RESULTS — BTCUSDT 4h (3yr)")
    _section("EMA Crossover (EMA 12/26 + EMA50 trend filter)")
    _row("Trades",        f"{ema_meta['total_trades']}")
    _row("Win rate",      f"{ema_meta['win_rate_pct']:.1f}%")
    _row("Total return",  f"{ema_meta['total_return_pct']:+.2f}%")
    _row("Max drawdown",  f"{ema_meta['max_drawdown_pct']:.2f}%")
    _row("Sharpe ratio",  f"{ema_meta['sharpe_ratio']:.4f}")

    _section("Mean Reversion (RSI14 < 35 + EMA50 filter)")
    _row("Trades",        f"{mr_meta['total_trades']}")
    _row("Win rate",      f"{mr_meta['win_rate_pct']:.1f}%")
    _row("Total return",  f"{mr_meta['total_return_pct']:+.2f}%")
    _row("Max drawdown",  f"{mr_meta['max_drawdown_pct']:.2f}%")
    _row("Sharpe ratio",  f"{mr_meta['sharpe_ratio']:.4f}")

    # ── 2. Correlation ──────────────────────────────────────────────────
    _header("CORRELATION ANALYSIS")

    ema_returns = [t["pnl_pct"] for t in ema_trades]
    mr_returns  = [t["pnl_pct"] for t in mr_trades]

    # Trade-level: pad shorter list with zeros for alignment (different trade counts)
    max_n   = max(len(ema_returns), len(mr_returns))
    ema_pad = ema_returns + [0.0] * (max_n - len(ema_returns))
    mr_pad  = mr_returns  + [0.0] * (max_n - len(mr_returns))
    trade_corr = pearson_correlation(ema_pad, mr_pad)

    eq_corr = equity_curve_correlation(ema_curve, mr_curve)

    _section("Pearson Correlation")
    _row("Trade returns (padded)", f"{trade_corr:+.4f}")
    _row("Equity curves",          f"{eq_corr:+.4f}")
    print()
    print()
    print("  Note: equity curve correlation is structurally high when both")
    print("  strategies profit in the same bull market — trade-level")
    print("  correlation is the more meaningful diversification metric.")
    if abs(trade_corr) < 0.3:
        print(f"  ✓ Trade correlation {trade_corr:+.4f} — strategies are largely INDEPENDENT")
    elif abs(trade_corr) < 0.6:
        print(f"  ~ Trade correlation {trade_corr:+.4f} — moderate overlap in signal timing")
    else:
        print(f"  ✗ Trade correlation {trade_corr:+.4f} — strategies fire together often")

    # ── 3. Combined portfolio ───────────────────────────────────────────
    _header("COMBINED PORTFOLIO (50/50 CAPITAL SPLIT)")
    combined = simulate_combined(ema_trades, mr_trades)

    _section("Combined vs Individual")
    print(f"  {'Metric':<25} {'EMA':>10} {'MR':>10} {'Combined':>10}")
    print(f"  {'─'*55}")
    print(f"  {'Trades':<25} {ema_meta['total_trades']:>10} {mr_meta['total_trades']:>10} {combined['total_trades']:>10}")
    print(f"  {'Win rate':<25} {ema_meta['win_rate_pct']:>9.1f}% {mr_meta['win_rate_pct']:>9.1f}% {combined['win_rate_pct']:>9.1f}%")
    print(f"  {'Total return':<25} {ema_meta['total_return_pct']:>9.2f}% {mr_meta['total_return_pct']:>9.2f}% {combined['total_return_pct']:>9.2f}%")
    print(f"  {'Max drawdown':<25} {ema_meta['max_drawdown_pct']:>9.2f}% {mr_meta['max_drawdown_pct']:>9.2f}% {combined['max_drawdown_pct']:>9.2f}%")
    print(f"  {'Sharpe ratio':<25} {ema_meta['sharpe_ratio']:>10.4f} {mr_meta['sharpe_ratio']:>10.4f} {combined['sharpe_ratio']:>10.4f}")
    print(f"  {'Final capital':<25} ${CAPITAL + CAPITAL*ema_meta['total_return_pct']/100:>9,.0f} ${CAPITAL + CAPITAL*mr_meta['total_return_pct']/100:>9,.0f} ${combined['final_capital']:>9,.0f}")

    # ── 4. Drawdown analysis ────────────────────────────────────────────
    _header("DRAWDOWN ANALYSIS")
    ema_dds = compute_drawdown_periods(ema_trades, CAPITAL)
    mr_dds  = compute_drawdown_periods(mr_trades,  CAPITAL)

    _section("EMA Crossover — Significant Drawdown Periods (>1%)")
    ema_sig = sorted([d for d in ema_dds if d["depth_pct"] > 0.5], key=lambda d: d["depth_pct"], reverse=True)
    for d in ema_sig[:5]:
        print(f"  {d['start'][:10]} → {d['end'][:10]}  depth: {d['depth_pct']:.2f}%")

    _section("Mean Reversion — Significant Drawdown Periods (>1%)")
    mr_sig = sorted([d for d in mr_dds if d["depth_pct"] > 0.5], key=lambda d: d["depth_pct"], reverse=True)
    for d in mr_sig[:5]:
        print(f"  {d['start'][:10]} → {d['end'][:10]}  depth: {d['depth_pct']:.2f}%")

    # Check overlap
    _section("Drawdown Overlap Check")
    overlap_count = 0
    for e in ema_sig:
        for m in mr_sig:
            if e["start"] <= m["end"] and m["start"] <= e["end"]:
                overlap_count += 1
    total_pairs = len(ema_sig) * len(mr_sig)
    pct_overlap = overlap_count / total_pairs * 100 if total_pairs else 0
    print(f"  EMA drawdown periods    : {len(ema_sig)}")
    print(f"  MR drawdown periods     : {len(mr_sig)}")
    print(f"  Overlapping periods     : {overlap_count} / {total_pairs} ({pct_overlap:.0f}%)")
    if pct_overlap < 30:
        print("  ✓ Low overlap — strategies struggle at DIFFERENT times")
    elif pct_overlap < 60:
        print("  ~ Moderate overlap — partial diversification benefit")
    else:
        print("  ✗ High overlap — drawdowns coincide, limited diversification")

    # ── 5. Regime analysis ──────────────────────────────────────────────
    _header("REGIME BEHAVIOUR")
    ema_tagged = tag_regime(conn, ema_trades)
    mr_tagged  = tag_regime(conn, mr_trades)

    def regime_stats(trades: list[dict], label: str) -> None:
        _section(f"{label} — Performance by Market Regime")
        for regime in ("trending", "sideways", "unknown"):
            subset = [t for t in trades if t.get("regime") == regime]
            if not subset:
                continue
            n    = len(subset)
            wins = sum(1 for t in subset if t["pnl_dollar"] > 0)
            pnl  = sum(t["pnl_dollar"] for t in subset)
            print(f"  {regime:<10}: {n:>3} trades  {wins/n*100:>5.1f}% win  ${pnl:>+8,.2f} net")

    regime_stats(ema_tagged, "EMA Crossover")
    regime_stats(mr_tagged,  "Mean Reversion")

    # ── 6. Key observations ─────────────────────────────────────────────
    _header("KEY OBSERVATIONS")
    print()

    combined_sharpe  = combined["sharpe_ratio"]
    avg_ind_sharpe   = (ema_meta["sharpe_ratio"] + mr_meta["sharpe_ratio"]) / 2
    combined_dd      = combined["max_drawdown_pct"]
    avg_ind_dd       = (ema_meta["max_drawdown_pct"] + mr_meta["max_drawdown_pct"]) / 2
    combined_return  = combined["total_return_pct"]
    avg_ind_return   = (ema_meta["total_return_pct"] + mr_meta["total_return_pct"]) / 2

    print(f"  Avg individual Sharpe   : {avg_ind_sharpe:.4f}")
    print(f"  Combined Sharpe         : {combined_sharpe:.4f}  "
          f"({'↑ improved' if combined_sharpe > avg_ind_sharpe else '↓ lower than avg'})")
    print()
    print(f"  Avg individual DD       : {avg_ind_dd:.2f}%")
    print(f"  Combined DD             : {combined_dd:.2f}%  "
          f"({'↓ reduced' if combined_dd < avg_ind_dd else '↑ higher than avg'})")
    print()
    print(f"  Avg individual return   : {avg_ind_return:.2f}%")
    print(f"  Combined return         : {combined_return:.2f}%  "
          f"({'↑ better' if combined_return > avg_ind_return else '↓ lower — expected (capital dilution)'})")
    print()
    print("  Verdict:")
    if abs(trade_corr) < 0.4 and combined_dd <= avg_ind_dd:
        print("  ✓ Strategies are COMPLEMENTARY — low trade correlation + reduced drawdown")
        print("    Combining them is worth pursuing in Phase 8.")
    elif combined_sharpe > avg_ind_sharpe:
        print("  ✓ Combination improves Sharpe even if not perfectly decorrelated")
        print("    Worth combining — diversification benefit is real.")
    else:
        print("  ~ Limited complementarity — review regime breakdown above")
    print()


if __name__ == "__main__":
    main()
