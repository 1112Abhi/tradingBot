#!/usr/bin/env python3
"""
bb_eth_yby.py — Year-by-year breakdown for ETH 1h BB Breakout top variants.

Tests Variant B (1.5σ, 1.5x vol) and D (2.0σ, no vol) year by year.

Usage:
    python scripts/research/bb_eth_yby.py
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import sqlite3
from datetime import datetime, timezone, timedelta
import math
import config
from backtest.database import Database
from backtest.engine import run_backtest
from strategy.bb_breakout import BBBreakoutStrategy
from strategy.base import MarketData

SYMBOL   = "ETHUSDT"
INTERVAL = "1h"
CAPITAL  = config.BACKTEST_CAPITAL
FEE      = config.BACKTEST_FEE_PCT
SIZE_PCT = config.PORTFOLIO_PER_STRATEGY_FRACTION

VARIANTS = [
    {"label": "B — Tight (1.5σ, vol=1.5x)", "bb_std": 1.5, "vol_mult": 1.5},
    {"label": "D — No volume (2.0σ, no vol)", "bb_std": 2.0, "vol_mult": 0.0},
    {"label": "A — Standard (2.0σ, vol=1.5x)", "bb_std": 2.0, "vol_mult": 1.5},
]

SL_PCT = config.BACKTEST_STOP_LOSS_PCT   # 1.5%
TP_PCT = config.BACKTEST_TAKE_PROFIT_PCT # 6.0%


def simulate_window(bars: list, bb_std: float, vol_mult: float) -> dict:
    """Run a lightweight simulation on a bar slice, returns stats."""
    if len(bars) < config.BACKTEST_MIN_WINDOW + 1:
        return {"trades": 0, "win_pct": 0, "return": 0, "sharpe": 0}

    strat    = BBBreakoutStrategy(bb_std=bb_std, volume_mult=vol_mult)
    position = None
    equity   = CAPITAL
    trade_returns = []
    trades_list   = []
    MAX_HOLD = 100

    for i in range(config.BACKTEST_MIN_WINDOW, len(bars) - 1):
        window = bars[:i + 1]
        prices  = [b["mid"]    for b in window]
        volumes = [b["volume"] for b in window]

        md: MarketData = {
            "prices":      prices,
            "volumes":     volumes,
            "entry_price": position["entry"] if position else None,
            "position":    "LONG" if position else "NONE",
            "symbol":      SYMBOL,
            "timestamp":   window[-1]["timestamp"],
        }

        try:
            sig = strat.generate_signal(md)
        except Exception:
            sig = config.SIGNAL_NO_TRADE

        exec_price = bars[i + 1]["mid"]

        if position is None and sig == config.SIGNAL_BUY:
            entry = exec_price * (1 + config.SLIPPAGE_RATE)
            size  = equity * SIZE_PCT
            qty   = size / entry
            equity -= size * FEE
            position = {"entry": entry, "qty": qty, "size": size, "bar": i}

        elif position is not None:
            entry  = position["entry"]
            cur_exit = exec_price * (1 - config.SLIPPAGE_RATE)
            pnl_pct  = (cur_exit - entry) / entry

            exit_reason = None
            if sig == config.SIGNAL_SELL:
                exit_reason = "signal"
            elif pnl_pct <= -SL_PCT:
                exit_reason = "stop_loss"
                cur_exit = entry * (1 - SL_PCT)
            elif pnl_pct >= TP_PCT:
                exit_reason = "take_profit"
                cur_exit = entry * (1 + TP_PCT)
            elif (i - position["bar"]) > MAX_HOLD:
                exit_reason = "timeout"

            if exit_reason:
                gross   = position["qty"] * (cur_exit - entry)
                fee_out = (position["qty"] * cur_exit) * FEE
                net     = gross - fee_out
                equity += net
                trade_returns.append(net / position["size"])
                trades_list.append(net > 0)
                position = None

    if not trades_list:
        return {"trades": 0, "win_pct": 0, "return": 0, "sharpe": 0}

    total_ret = (equity - CAPITAL) / CAPITAL * 100
    win_pct   = sum(trades_list) / len(trades_list) * 100
    mean  = sum(trade_returns) / len(trade_returns)
    std   = math.sqrt(sum((x - mean) ** 2 for x in trade_returns) / len(trade_returns))
    sharpe = float(mean / std * (252 ** 0.5)) if std > 0 else 0.0
    return {
        "trades":  len(trades_list),
        "win_pct": round(win_pct, 1),
        "return":  round(total_ret, 2),
        "sharpe":  round(sharpe, 4),
    }


def main() -> None:
    print(f"\n{'='*72}")
    print(f"  ETH 1h BB BREAKOUT — YEAR-BY-YEAR BREAKDOWN")
    print(f"  SL={SL_PCT*100:.1f}%  TP={TP_PCT*100:.1f}%  size=25%  fee=0.05%")
    print(f"{'='*72}")

    db   = Database()
    bars = db.get_prices(SYMBOL, INTERVAL)
    ts_min = datetime.fromisoformat(bars[0]["timestamp"].replace("Z", "+00:00"))
    ts_max = datetime.fromisoformat(bars[-1]["timestamp"].replace("Z", "+00:00"))
    print(f"  Data: {ts_min.date()} → {ts_max.date()}  ({len(bars):,} bars)\n")

    for v in VARIANTS:
        print(f"  {v['label']}")
        print(f"  {'─'*60}")
        print(f"  {'Period':<22} {'Trades':>7} {'WR':>6} {'Return':>8} {'Sharpe':>8}")
        print(f"  {'─'*60}")

        for yr in range(3, 0, -1):
            y_end   = ts_max - timedelta(days=365 * (yr - 1))
            y_start = y_end  - timedelta(days=365)
            if y_start < ts_min:
                y_start = ts_min

            window_bars = [
                b for b in bars
                if y_start.strftime("%Y-%m-%dT%H:%M:%SZ") <= b["timestamp"]
                <= y_end.strftime("%Y-%m-%dT%H:%M:%SZ")
            ]

            r = simulate_window(window_bars, v["bb_std"], v["vol_mult"])
            label = f"Year {4-yr} ({y_start.strftime('%Y-%m')}→{y_end.strftime('%Y-%m')})"
            print(f"  {label:<22} {r['trades']:>7} {r['win_pct']:>5.1f}%"
                  f" {r['return']:>+7.2f}%  {r['sharpe']:>8.4f}")

        # Full 3-year
        r_all = simulate_window(bars, v["bb_std"], v["vol_mult"])
        print(f"  {'─'*60}")
        print(f"  {'3-YEAR TOTAL':<22} {r_all['trades']:>7} {r_all['win_pct']:>5.1f}%"
              f" {r_all['return']:>+7.2f}%  {r_all['sharpe']:>8.4f}")
        print()

    print(f"  4h MR benchmark (BTC, live): +20.43%  Sharpe=0.8918  (for reference)")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    main()
