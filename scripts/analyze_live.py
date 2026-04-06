#!/usr/bin/env python3
"""
analyze_live.py — Compare live / paper trading results against backtest.

Usage:
    python analyze_live.py
    python analyze_live.py --symbol BTCUSDT --interval 4h
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from datetime import datetime, timezone

import config
from backtest.database import Database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",   default="BTCUSDT")
    parser.add_argument("--interval", default="4h")
    parser.add_argument("--strategy", default="ema_crossover")
    args = parser.parse_args()

    db = Database()

    trades     = db.get_live_trades(args.symbol, args.interval, args.strategy)
    live_only  = [t for t in trades if t["trade_type"] == "live"]
    catchup    = [t for t in trades if t["trade_type"] == "catch_up"]
    position   = db.get_live_position(args.symbol, args.interval, args.strategy)
    last_candle = db.get_last_processed_candle(args.symbol, args.interval)

    print()
    print("=" * 65)
    print(f"  LIVE PAPER TRADING SUMMARY — {args.symbol} {args.interval}")
    print("=" * 65)
    print(f"  Strategy     : {args.strategy}")
    print(f"  Last candle  : {last_candle or 'none'}")
    print(f"  Open position: {'YES — entry @ $' + f'{position[\"entry_price\"]:,.2f}' if position else 'NONE'}")

    if not trades:
        print("\n  No completed trades yet.\n")
        return

    _print_section("ALL TRADES (live + catch_up)", trades)
    if live_only:
        _print_section("LIVE TRADES ONLY", live_only)
    if catchup:
        _print_section("CATCH-UP TRADES (replayed)", catchup)

    # Compare vs backtest benchmark
    print()
    print("  BACKTEST BENCHMARK (3yr BTCUSDT 4h):")
    print("  Win rate  : ~29%  |  Return: +4.83%/3yr  |  Sharpe: 0.41  |  DD: 4.02%")
    print()


def _print_section(title: str, trades: list) -> None:
    if not trades:
        return

    n          = len(trades)
    wins       = sum(1 for t in trades if t["pnl_dollar"] > 0)
    win_rate   = wins / n * 100
    total_net  = sum(t["pnl_dollar"] for t in trades)
    total_gross = sum(t["gross_pnl"]  for t in trades)
    total_fees = sum(t["fees_paid"]   for t in trades)
    avg_net    = total_net / n
    returns    = [t["pnl_pct"] for t in trades]
    avg_ret    = sum(returns) / n
    max_dd     = _compute_max_drawdown(trades)
    sharpe     = _compute_sharpe(trades)
    avg_dur    = _avg_duration_hours(trades)

    exit_counts: dict = {}
    for t in trades:
        exit_counts[t["exit_reason"]] = exit_counts.get(t["exit_reason"], 0) + 1

    print()
    print(f"  {title}")
    print(f"  {'─'*50}")
    print(f"  Trades      : {n}  ({wins} wins / {n-wins} losses)")
    print(f"  Win rate    : {win_rate:.1f}%")
    print(f"  Gross PnL   : ${total_gross:+,.2f}")
    print(f"  Fees paid   : ${total_fees:,.2f}")
    print(f"  Net PnL     : ${total_net:+,.2f}")
    print(f"  Avg PnL/trade: ${avg_net:+,.2f}  ({avg_ret:+.2f}%)")
    print(f"  Max drawdown: {max_dd:.2f}%")
    print(f"  Sharpe      : {sharpe:.4f}")
    print(f"  Avg duration: {avg_dur:.1f}h")
    print(f"  Exit reasons: {exit_counts}")


def _compute_max_drawdown(trades: list) -> float:
    capital = config.BACKTEST_CAPITAL
    peak    = capital
    max_dd  = 0.0
    for t in trades:
        capital += t["pnl_dollar"]
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _compute_sharpe(trades: list) -> float:
    if len(trades) < 2:
        return 0.0
    returns = [t["pnl_pct"] for t in trades]
    n       = len(returns)
    mean_r  = sum(returns) / n
    std_r   = (sum((r - mean_r) ** 2 for r in returns) / (n - 1)) ** 0.5
    if std_r == 0:
        return 0.0
    # Annualise: ~2190 4h bars/year, estimate trades_per_year from sample
    bars_per_year   = 2190
    last_candle_ts  = trades[-1]["exit_ts"]
    first_candle_ts = trades[0]["entry_ts"]
    try:
        t0 = datetime.strptime(first_candle_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        t1 = datetime.strptime(last_candle_ts,  "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        elapsed_bars = max(1, (t1 - t0).total_seconds() / (4 * 3600))
    except ValueError:
        elapsed_bars = n * 10  # rough fallback
    trades_per_year = n / elapsed_bars * bars_per_year
    return round(mean_r / std_r * (trades_per_year ** 0.5), 4)


def _avg_duration_hours(trades: list) -> float:
    durations = []
    for t in trades:
        try:
            t0 = datetime.strptime(t["entry_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            t1 = datetime.strptime(t["exit_ts"],  "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            durations.append((t1 - t0).total_seconds() / 3600)
        except ValueError:
            pass
    return sum(durations) / len(durations) if durations else 0.0


if __name__ == "__main__":
    main()
