#!/usr/bin/env python3
"""
tp_grid.py — Take-profit optimisation grid.

Holds everything constant and sweeps TP values:
  Entry : EMA(12,26) + EMA50 trend filter  (no RSI filter)
  SL    : 1.5% (fixed)
  TP    : 4.5% / 6% / 7.5%
  TF    : 4h (default)

Usage:
    python tp_grid.py
    python tp_grid.py --symbol BTCUSDT --interval 4h
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import sqlite3
import config
from backtest.database import Database
from backtest.engine import run_backtest
from strategy.ema_crossover import MACrossoverStrategy

SL_FIXED = 0.015  # held constant across all variants

VARIANTS = [
    {"label": "TP 4.5% (baseline)", "tp": 0.045},
    {"label": "TP 6.0%",            "tp": 0.060},
    {"label": "TP 7.5%",            "tp": 0.075},
]

# No RSI filter: wide-open range so every EMA crossover is eligible
_NO_RSI = MACrossoverStrategy(rsi_buy_min=0, rsi_buy_max=100)


def _fetch_result(run_id: str) -> dict:
    conn = sqlite3.connect(config.BACKTEST_DB)
    c    = conn.cursor()
    c.execute(
        """
        SELECT total_trades, winning_trades, win_rate_pct,
               total_return_pct, max_drawdown_pct, final_capital
        FROM backtest_runs WHERE run_id = ?
        """,
        (run_id,),
    )
    trades, wins, win_pct, ret, dd, final = c.fetchone()

    c.execute(
        """
        SELECT exit_reason, COUNT(*), ROUND(AVG(pnl_dollar), 2)
        FROM backtest_trades WHERE run_id = ?
        GROUP BY exit_reason
        """,
        (run_id,),
    )
    exits = {row[0]: {"cnt": row[1], "avg": row[2]} for row in c.fetchall()}
    conn.close()

    sl_cnt  = exits.get("stop_loss",   {}).get("cnt", 0)
    tp_cnt  = exits.get("take_profit", {}).get("cnt", 0)
    to_cnt  = exits.get("timeout",     {}).get("cnt", 0)
    sl_pct  = round(sl_cnt / trades * 100, 1) if trades else 0

    return {
        "trades":   trades,
        "wins":     wins,
        "win_pct":  round(win_pct, 1),
        "return":   round(ret, 2),
        "dd":       round(dd, 2),
        "final":    round(final, 2),
        "sl_pct":   sl_pct,
        "sl_cnt":   sl_cnt,
        "tp_cnt":   tp_cnt,
        "to_cnt":   to_cnt,
        "sl_avg":   exits.get("stop_loss",   {}).get("avg", 0.0),
        "tp_avg":   exits.get("take_profit", {}).get("avg", 0.0),
        "win_avg":  round(exits.get("take_profit", {}).get("avg", 0.0), 2),
        "loss_avg": round(exits.get("stop_loss",   {}).get("avg", 0.0), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",   default="BTCUSDT")
    parser.add_argument("--interval", default="4h")
    args = parser.parse_args()

    db      = Database()
    results = []

    print(f"\n{'='*80}")
    print(f"  TP OPTIMISATION GRID — {args.symbol} {args.interval}  (SL fixed at {SL_FIXED*100:.1f}%)")
    print(f"{'='*80}\n")

    for v in VARIANTS:
        run_ids = run_backtest(
            symbol     = args.symbol,
            interval   = args.interval,
            mode       = "per",
            db         = db,
            strategies = [_NO_RSI],
            sl_pct     = SL_FIXED,
            tp_pct     = v["tp"],
        )
        r = _fetch_result(run_ids[0])
        r["label"] = v["label"]
        r["tp"]    = f"{v['tp']*100:.1f}%"
        results.append(r)

        ev = round(r["win_pct"] / 100 * abs(r["tp_avg"]) +
                   (1 - r["win_pct"] / 100) * r["loss_avg"], 2)
        print(f"  [{v['label']}]  trades={r['trades']}  win={r['win_pct']}%  "
              f"return={r['return']:+.2f}%  dd={r['dd']:.2f}%  EV/trade=${ev:.2f}")

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  FULL SUMMARY")
    print(f"{'='*80}")
    hdr = (f"{'Variant':<22} {'TP':>5} {'Trades':>7} {'Win%':>6} {'Return':>8} "
           f"{'DD':>6} {'SL%':>6} {'SL hits':>8} {'TP hits':>8} "
           f"{'Avg win':>9} {'Avg loss':>10}")
    print(hdr)
    print("-" * 80)
    for r in results:
        print(
            f"{r['label']:<22} {r['tp']:>5} {r['trades']:>7} "
            f"{r['win_pct']:>5.1f}% {r['return']:>+7.2f}% "
            f"{r['dd']:>5.2f}% {r['sl_pct']:>5.1f}% "
            f"{r['sl_cnt']:>8} {r['tp_cnt']:>8} "
            f"${r['win_avg']:>8.2f} ${r['loss_avg']:>9.2f}"
        )

    print()
    best_ret = max(results, key=lambda x: x["return"])
    best_dd  = min(results, key=lambda x: x["dd"])
    print(f"  Best return  : {best_ret['label']}  →  {best_ret['return']:+.2f}%")
    print(f"  Lowest DD    : {best_dd['label']}  →  {best_dd['dd']:.2f}%")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
