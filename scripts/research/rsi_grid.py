#!/usr/bin/env python3
"""
rsi_grid.py — RSI range experiment grid.

Tests multiple RSI buy-zone configurations against 1-year BTCUSDT 1h data.
Everything else is held constant:
  EMA(12,26) entry + EMA50 trend filter
  SL=1.5%, TP=4.5%, timeout=100 bars

Usage:
    python rsi_grid.py
    python rsi_grid.py --symbol BTCUSDT --interval 4h
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import sqlite3
import config
from backtest.database import Database
from backtest.engine import run_backtest
from strategy.ema_crossover import MACrossoverStrategy

VARIANTS = [
    {"label": "V4 baseline (no RSI)",  "rsi_min": 0,  "rsi_max": 100},
    {"label": "V5 (40–65)",            "rsi_min": 40, "rsi_max": 65},
    {"label": "V5a (45–60)",           "rsi_min": 45, "rsi_max": 60},
    {"label": "V5b (50–65)",           "rsi_min": 50, "rsi_max": 65},
    {"label": "V5c (42–58)",           "rsi_min": 42, "rsi_max": 58},
]


def _fetch_result(db_path: str, run_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    c    = conn.cursor()
    c.execute(
        """
        SELECT total_trades, winning_trades, win_rate_pct,
               total_return_pct, max_drawdown_pct, final_capital
        FROM backtest_runs WHERE run_id = ?
        """,
        (run_id,),
    )
    row = c.fetchone()

    exits = {}
    c.execute(
        """
        SELECT exit_reason, COUNT(*), ROUND(AVG(pnl_dollar),2)
        FROM backtest_trades WHERE run_id = ?
        GROUP BY exit_reason
        """,
        (run_id,),
    )
    for reason, cnt, avg in c.fetchall():
        exits[reason] = {"cnt": cnt, "avg": avg}

    conn.close()
    trades, wins, win_pct, ret, dd, final = row
    sl_pct = round(exits.get("stop_loss", {}).get("cnt", 0) / trades * 100, 1) if trades else 0
    return {
        "trades":   trades,
        "wins":     wins,
        "win_pct":  round(win_pct, 1),
        "return":   round(ret, 2),
        "dd":       round(dd, 2),
        "final":    round(final, 2),
        "sl_pct":   sl_pct,
        "sl_avg":   exits.get("stop_loss",   {}).get("avg", 0),
        "tp_avg":   exits.get("take_profit", {}).get("avg", 0),
        "tp_cnt":   exits.get("take_profit", {}).get("cnt", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",   default="BTCUSDT")
    parser.add_argument("--interval", default="1h")
    args = parser.parse_args()

    db      = Database()
    results = []

    print(f"\n{'='*80}")
    print(f"  RSI RANGE GRID — {args.symbol} {args.interval}  (SL=1.5% / TP=4.5% / timeout=100)")
    print(f"{'='*80}\n")

    for v in VARIANTS:
        strat  = MACrossoverStrategy(rsi_buy_min=v["rsi_min"], rsi_buy_max=v["rsi_max"])
        run_ids = run_backtest(
            symbol     = args.symbol,
            interval   = args.interval,
            mode       = "per",
            db         = db,
            strategies = [strat],
        )
        r = _fetch_result(config.BACKTEST_DB, run_ids[0])
        r["label"] = v["label"]
        r["rsi"]   = f"{v['rsi_min']}–{v['rsi_max']}"
        results.append(r)
        print(f"  [{v['label']}]  trades={r['trades']}  win={r['win_pct']}%  "
              f"return={r['return']:+.2f}%  dd={r['dd']:.2f}%  SL%={r['sl_pct']}%")

    # ── Summary table ───────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    hdr = f"{'Variant':<26} {'RSI':<8} {'Trades':>7} {'Win%':>6} {'Return':>8} {'DD':>6} {'SL%':>6} {'SL avg':>8} {'TP avg':>8}"
    print(hdr)
    print("-" * 80)
    for r in results:
        print(
            f"{r['label']:<26} {r['rsi']:<8} {r['trades']:>7} "
            f"{r['win_pct']:>5.1f}% {r['return']:>+7.2f}% "
            f"{r['dd']:>5.2f}% {r['sl_pct']:>5.1f}% "
            f"${r['sl_avg']:>7.2f} ${r['tp_avg']:>7.2f}"
        )

    best_ret = min(results, key=lambda x: x["return"], default=None)  # least negative
    best_ret = max(results, key=lambda x: x["return"])
    best_sl  = min(results, key=lambda x: x["sl_pct"])
    print(f"\n  Best return : {best_ret['label']}  →  {best_ret['return']:+.2f}%")
    print(f"  Lowest SL%  : {best_sl['label']}   →  {best_sl['sl_pct']}% stop-loss rate")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
