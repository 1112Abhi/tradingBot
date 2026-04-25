#!/usr/bin/env python3
"""
analyze_live.py — Multi-strategy live paper trading analysis.

Shows all active strategies grouped by mode (portfolio / experiment),
with metrics and comparison against the latest backtest benchmark.

Usage:
    python scripts/analyze_live.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

import config
from backtest.database import Database


# ── Interval → hours (for Sharpe annualisation) ────────────────────────────────

def _interval_hours(interval: str) -> float:
    if interval.endswith("h"):
        return float(interval[:-1])
    if interval.endswith("m"):
        return float(interval[:-1]) / 60
    return 1.0


# ── Metrics ────────────────────────────────────────────────────────────────────

def _metrics(trades: list, interval: str) -> dict:
    if not trades:
        return {}

    n           = len(trades)
    wins        = sum(1 for t in trades if t["pnl_dollar"] > 0)
    total_net   = sum(t["pnl_dollar"] for t in trades)
    total_gross = sum(t["gross_pnl"]  for t in trades)
    total_fees  = sum(t["fees_paid"]  for t in trades)
    returns     = [t["pnl_pct"] for t in trades]
    mean_r      = sum(returns) / n

    # Sharpe (annualised, trade-frequency adjusted)
    if n >= 2:
        std_r = (sum((r - mean_r) ** 2 for r in returns) / (n - 1)) ** 0.5
        if std_r > 0:
            bars_per_year = 8760 / _interval_hours(interval)
            try:
                t0 = datetime.strptime(trades[0]["entry_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                t1 = datetime.strptime(trades[-1]["exit_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                elapsed_bars = max(1, (t1 - t0).total_seconds() / (3600 * _interval_hours(interval)))
            except ValueError:
                elapsed_bars = n * 10
            trades_per_year = n / elapsed_bars * bars_per_year
            sharpe = mean_r / std_r * (trades_per_year ** 0.5)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # Max drawdown
    capital = config.BACKTEST_CAPITAL
    peak    = capital
    max_dd  = 0.0
    for t in trades:
        capital += t["pnl_dollar"]
        peak     = max(peak, capital)
        dd       = (peak - capital) / peak * 100
        max_dd   = max(max_dd, dd)

    # Avg duration
    durations = []
    for t in trades:
        try:
            t0 = datetime.strptime(t["entry_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            t1 = datetime.strptime(t["exit_ts"],  "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            durations.append((t1 - t0).total_seconds() / 3600)
        except ValueError:
            pass
    avg_dur = sum(durations) / len(durations) if durations else 0.0

    # Exit breakdown
    exit_counts: dict = {}
    for t in trades:
        exit_counts[t["exit_reason"]] = exit_counts.get(t["exit_reason"], 0) + 1

    return {
        "n":           n,
        "wins":        wins,
        "win_rate":    wins / n * 100,
        "net_pnl":     total_net,
        "gross_pnl":   total_gross,
        "fees":        total_fees,
        "avg_pnl":     total_net / n,
        "avg_ret_pct": mean_r,
        "sharpe":      sharpe,
        "max_dd":      max_dd,
        "avg_dur_h":   avg_dur,
        "exits":       exit_counts,
    }


# ── Printing ───────────────────────────────────────────────────────────────────

PASS_CRITERIA = {
    "min_trades":      5,      # need at least this many trades to assess
    "min_win_rate":    25.0,   # % — below this is a concern
    "min_sharpe":      0.3,    # annualised
    "max_dd_factor":   2.0,    # live DD should be < 2x backtest DD
}


def _verdict(m: dict, bt: dict) -> str:
    if m["n"] < PASS_CRITERIA["min_trades"]:
        return f"⏳ WAIT  (only {m['n']} trades — need {PASS_CRITERIA['min_trades']}+)"
    issues = []
    if m["win_rate"] < PASS_CRITERIA["min_win_rate"]:
        issues.append(f"win rate {m['win_rate']:.0f}% < {PASS_CRITERIA['min_win_rate']:.0f}%")
    if m["sharpe"] < PASS_CRITERIA["min_sharpe"]:
        issues.append(f"Sharpe {m['sharpe']:.2f} < {PASS_CRITERIA['min_sharpe']:.1f}")
    if bt and m["max_dd"] > bt["max_drawdown_pct"] * PASS_CRITERIA["max_dd_factor"]:
        issues.append(f"DD {m['max_dd']:.1f}% > 2x backtest DD {bt['max_drawdown_pct']:.1f}%")
    if issues:
        return "⚠️  WATCH  — " + ", ".join(issues)
    return "✅ PASS"


def _print_strategy(key: dict, trades: list, db: Database) -> None:
    symbol   = key["symbol"]
    interval = key["interval"]
    strategy = key["strategy"]
    mode     = key["strategy_mode"]
    mode_tag = "[EXPERIMENT]" if mode == "experiment" else "[PORTFOLIO]"

    live_only = [t for t in trades if t["trade_type"] == "live"]
    catchup   = [t for t in trades if t["trade_type"] == "catch_up"]
    position  = None  # we show open position from live_position table below
    bt        = db.get_latest_backtest_run(symbol, interval, strategy)
    m         = _metrics(live_only, interval)

    print()
    print(f"  {'─'*62}")
    print(f"  {strategy.upper()}  |  {symbol} {interval}  {mode_tag}")
    print(f"  {'─'*62}")

    if not live_only:
        print(f"  No live trades yet.  (catch-up: {len(catchup)})")
        if bt:
            print(f"  Backtest ref: return={bt['total_return_pct']:+.2f}%  "
                  f"sharpe={bt['sharpe_ratio']:.2f}  DD={bt['max_drawdown_pct']:.1f}%  "
                  f"trades={bt['total_trades']}")
        return

    # Live metrics
    exits_str = "  ".join(f"{k.replace('_','')[:2].upper()}={v}" for k, v in m["exits"].items())
    print(f"  Trades      : {m['n']}  ({m['wins']}W / {m['n']-m['wins']}L)  [{exits_str}]")
    print(f"  Win rate    : {m['win_rate']:.1f}%")
    print(f"  Net P&L     : ${m['net_pnl']:+,.2f}  (gross ${m['gross_pnl']:+,.2f}  fees ${m['fees']:,.2f})")
    print(f"  Avg/trade   : ${m['avg_pnl']:+,.2f}  ({m['avg_ret_pct']:+.2f}%)")
    print(f"  Sharpe      : {m['sharpe']:.2f}")
    print(f"  Max DD      : {m['max_dd']:.2f}%")
    print(f"  Avg duration: {m['avg_dur_h']:.1f}h")

    if catchup:
        cm = _metrics(catchup, interval)
        print(f"  Catch-up    : {cm['n']} trades  net ${cm['net_pnl']:+,.2f}")

    # Backtest comparison
    if bt:
        print()
        print(f"  Backtest (3yr):  return={bt['total_return_pct']:+.2f}%  "
              f"sharpe={bt['sharpe_ratio']:.2f}  DD={bt['max_drawdown_pct']:.1f}%  "
              f"win%={bt['win_rate_pct']:.1f}  trades={bt['total_trades']}")
        # Delta vs backtest
        wr_delta = m["win_rate"] - bt["win_rate_pct"]
        sh_delta = m["sharpe"]   - bt["sharpe_ratio"]
        print(f"  vs Backtest:     win rate {wr_delta:+.1f}pp  |  sharpe {sh_delta:+.2f}")

    # Verdict
    print()
    print(f"  Verdict: {_verdict(m, bt)}")


def _portfolio_total(db: Database, keys: list) -> None:
    """Print combined portfolio P&L across all portfolio strategies."""
    all_live = []
    for k in keys:
        if k["strategy_mode"] == "portfolio":
            trades = db.get_live_trades(k["symbol"], k["interval"], k["strategy"])
            all_live.extend(t for t in trades if t["trade_type"] == "live")

    if not all_live:
        return

    total_net  = sum(t["pnl_dollar"] for t in all_live)
    total_fees = sum(t["fees_paid"]  for t in all_live)
    n          = len(all_live)
    wins       = sum(1 for t in all_live if t["pnl_dollar"] > 0)

    print()
    print(f"  {'═'*62}")
    print(f"  PORTFOLIO TOTAL")
    print(f"  {'═'*62}")
    print(f"  Trades   : {n}  ({wins}W / {n-wins}L)")
    print(f"  Net P&L  : ${total_net:+,.2f}  (fees ${total_fees:,.2f})")
    print(f"  Capital  : ${config.BACKTEST_CAPITAL:,.0f}  → return {total_net/config.BACKTEST_CAPITAL*100:+.2f}%")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    db   = Database()
    keys = db.get_all_live_strategy_keys()

    if not keys:
        print("\n  No live trades in DB yet.\n")
        return

    portfolio_keys   = [k for k in keys if k["strategy_mode"] == "portfolio"]
    experiment_keys  = [k for k in keys if k["strategy_mode"] == "experiment"]

    print()
    print("=" * 65)
    print("  LIVE PAPER TRADING ANALYSIS")
    print("=" * 65)
    print(f"  Pass criteria: {PASS_CRITERIA['min_trades']}+ trades | "
          f"win%>{PASS_CRITERIA['min_win_rate']:.0f} | "
          f"sharpe>{PASS_CRITERIA['min_sharpe']:.1f} | "
          f"DD<{PASS_CRITERIA['max_dd_factor']:.0f}x backtest DD")

    if portfolio_keys:
        print()
        print("  ══ PORTFOLIO STRATEGIES (capital deployed) ══")
        for k in portfolio_keys:
            trades = db.get_live_trades(k["symbol"], k["interval"], k["strategy"])
            _print_strategy(k, trades, db)
        _portfolio_total(db, keys)

    if experiment_keys:
        print()
        print()
        print("  ══ EXPERIMENT STRATEGIES (paper signals only) ══")
        for k in experiment_keys:
            trades = db.get_live_trades(k["symbol"], k["interval"], k["strategy"])
            _print_strategy(k, trades, db)

    print()
    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
