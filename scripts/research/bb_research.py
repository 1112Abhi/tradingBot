#!/usr/bin/env python3
"""
bb_research.py — Bollinger Band Breakout research across coins and timeframes.

Tests 4 variants on 1h and 30m for BTC, ETH, SOL.
Fetches missing 3yr data automatically.

Viability criteria: Sharpe >= 0.5  AND  Return > 0%  AND  Trades >= 30

Usage:
    python scripts/research/bb_research.py
    python scripts/research/bb_research.py --interval 1h
    python scripts/research/bb_research.py --symbol BTCUSDT --interval 30m
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import argparse
import sqlite3
import config
from backtest.database import Database
from backtest.data_loader import DataLoader
from backtest.engine import run_backtest
from strategy.bb_breakout import BBBreakoutStrategy

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
INTERVALS = ["1h", "30m"]
YEARS_NEEDED = 3

# Variants: (label, bb_period, bb_std, vol_mult)
VARIANTS = [
    {"label": "A — Standard  ", "bb_period": 20, "bb_std": 2.0, "vol_mult": 1.5},
    {"label": "B — Tight     ", "bb_period": 20, "bb_std": 1.5, "vol_mult": 1.5},
    {"label": "C — Loose     ", "bb_period": 20, "bb_std": 2.5, "vol_mult": 1.2},
    {"label": "D — No volume ", "bb_period": 20, "bb_std": 2.0, "vol_mult": 0.0},
]


def ensure_data(db: Database, symbol: str, interval: str) -> int:
    """Ensure 3yr data exists, fetch if not. Returns bar count."""
    from datetime import datetime
    bars = db.get_prices(symbol, interval)
    if bars:
        ts_min = datetime.fromisoformat(bars[0]["timestamp"].replace("Z", "+00:00"))
        ts_max = datetime.fromisoformat(bars[-1]["timestamp"].replace("Z", "+00:00"))
        days = (ts_max - ts_min).days
        if days >= YEARS_NEEDED * 365 - 10:
            print(f"    {symbol} {interval}: {len(bars):,} bars ({days}d) — OK")
            return len(bars)

    print(f"    {symbol} {interval}: fetching 3yr data…")
    with db._connect() as conn:
        conn.execute(f"DELETE FROM prices WHERE symbol='{symbol}' AND interval='{interval}'")
    loader = DataLoader(db)
    count = loader.sync(symbol=symbol, interval=interval)
    print(f"    {symbol} {interval}: fetched {count:,} bars")
    return count


def fetch_result(run_id: str) -> dict:
    conn = sqlite3.connect(config.BACKTEST_DB)
    c = conn.cursor()
    c.execute(
        """SELECT total_trades, win_rate_pct, total_return_pct,
                  max_drawdown_pct, sharpe_ratio
           FROM backtest_runs WHERE run_id=?""",
        (run_id,),
    )
    row = c.fetchone()
    c.execute("SELECT COALESCE(SUM(fees_paid),0) FROM backtest_trades WHERE run_id=?", (run_id,))
    fees = c.fetchone()[0]
    conn.close()
    trades, win_pct, ret, dd, sharpe = row
    return {
        "trades": trades or 0,
        "win_pct": round(win_pct or 0, 1),
        "return": round(ret or 0, 2),
        "dd": round(dd or 0, 2),
        "sharpe": round(sharpe or 0, 4),
        "fees": round(fees, 0),
    }


def run_variants(db: Database, symbol: str, interval: str) -> list:
    results = []
    for v in VARIANTS:
        vol_mult = v["vol_mult"] if v["vol_mult"] > 0 else 0.0
        strat = BBBreakoutStrategy(
            bb_period=v["bb_period"],
            bb_std=v["bb_std"],
            volume_mult=vol_mult,
        )
        run_ids = run_backtest(
            symbol=symbol, interval=interval, mode="per", db=db,
            strategies=[strat],
        )
        r = fetch_result(run_ids[0])
        r["label"] = v["label"]
        r["bb_std"] = v["bb_std"]
        r["vol_mult"] = v["vol_mult"]
        results.append(r)
        ok = "✓" if r["sharpe"] >= 0.5 and r["return"] > 0 else "✗"
        print(f"      {v['label']}  trades={r['trades']:>4}  WR={r['win_pct']:>5.1f}%  "
              f"ret={r['return']:>+7.2f}%  sharpe={r['sharpe']:>7.4f}  {ok}")
    return results


def print_table(symbol: str, interval: str, results: list) -> None:
    print(f"\n  ── {symbol} {interval} ──────────────────────────────────────────────────────")
    print(f"  {'Variant':<16} {'BB±':>5} {'VolX':>5} {'Trades':>7} {'WR':>6} {'Return':>8} {'DD':>7} {'Sharpe':>8} {'Fees':>7}")
    print(f"  {'─'*74}")
    for r in results:
        ok = "✓" if r["sharpe"] >= 0.5 and r["return"] > 0 else "✗"
        vol_str = f"{r['vol_mult']:.1f}x" if r["vol_mult"] > 0 else "off"
        print(
            f"  {r['label']:<16} {r['bb_std']:>4.1f}σ {vol_str:>5}"
            f" {r['trades']:>7} {r['win_pct']:>5.1f}%"
            f" {r['return']:>+7.2f}%"
            f" {r['dd']:>6.2f}%"
            f" {r['sharpe']:>8.4f}"
            f" ${r['fees']:>5.0f}  {ok}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",   default=None, help="Single symbol (default: all 3)")
    parser.add_argument("--interval", default=None, help="Single interval (default: 1h and 30m)")
    args = parser.parse_args()

    symbols   = [args.symbol]   if args.symbol   else SYMBOLS
    intervals = [args.interval] if args.interval else INTERVALS

    print(f"\n{'='*80}")
    print(f"  BB BREAKOUT RESEARCH  |  25% fixed size  1x lev  fee=0.05%")
    print(f"  Variants: BB(20) ± σ  |  volume filter  |  mid-band exit")
    print(f"  Viability: Sharpe ≥ 0.5  AND  Return > 0%  AND  Trades ≥ 30")
    print(f"{'='*80}")

    db = Database()
    all_results = {}

    # ── Ensure data ────────────────────────────────────────────────────────
    print("\n  [1/2] Checking data…")
    for symbol in symbols:
        for interval in intervals:
            try:
                ensure_data(db, symbol, interval)
            except Exception as e:
                print(f"    WARNING: could not fetch {symbol} {interval}: {e}")

    # ── Run backtests ──────────────────────────────────────────────────────
    print("\n  [2/2] Running backtests…\n")
    for interval in intervals:
        for symbol in symbols:
            bars = db.get_prices(symbol, interval)
            if not bars:
                print(f"  SKIP {symbol} {interval} — no data")
                continue
            print(f"  {symbol} {interval} ({len(bars):,} bars):")
            try:
                results = run_variants(db, symbol, interval)
                all_results[(symbol, interval)] = results
            except Exception as e:
                print(f"    ERROR: {e}")

    # ── Summary tables ──────────────────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print(f"  BB BREAKOUT RESULTS SUMMARY")
    print(f"{'='*80}")

    viable = []
    for interval in intervals:
        for symbol in symbols:
            key = (symbol, interval)
            if key not in all_results:
                continue
            results = all_results[key]
            print_table(symbol, interval, results)
            for r in results:
                if r["sharpe"] >= 0.5 and r["return"] > 0 and r["trades"] >= 30:
                    viable.append((symbol, interval, r))

    # ── Benchmark reminder ──────────────────────────────────────────────────
    print(f"\n  4h MR benchmark (live config):  +20.43%  Sharpe=0.8918  DD=6.48%  (BTC 4h)")

    # ── Verdict ────────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    if viable:
        print(f"  VIABLE COMBINATIONS ({len(viable)} found):")
        for symbol, interval, r in sorted(viable, key=lambda x: -x[2]["sharpe"]):
            print(f"    {symbol} {interval}  {r['label'].strip():<14}  "
                  f"Sharpe={r['sharpe']:.4f}  Return={r['return']:+.2f}%  "
                  f"Trades={r['trades']}  DD={r['dd']:.2f}%")
    else:
        print(f"  VERDICT: REJECTED — No variant meets Sharpe ≥ 0.5 + positive return")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
