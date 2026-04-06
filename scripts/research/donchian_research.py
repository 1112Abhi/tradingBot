#!/usr/bin/env python3
"""
donchian_research.py — Donchian Channel Breakout research.

Tests 3 variants on ETHUSDT 1h + BTCUSDT 4h.
Compares against BB Breakout (ETH 1h) and MR benchmark (BTC 4h).

Variants:
  A — Short  (N=20, SL=1.0%, TP=2.5%)
  B — Medium (N=30, SL=1.2%, TP=3.0%)
  C — Long   (N=50, SL=1.5%, TP=4.0%)

Usage:
    python scripts/research/donchian_research.py
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import sqlite3
import math
from datetime import datetime, timezone, timedelta
import config
from backtest.database import Database
from backtest.engine import run_backtest
from strategy.donchian_breakout import DonchianBreakoutStrategy
from strategy.base import MarketData

CAPITAL  = config.BACKTEST_CAPITAL
FEE      = config.BACKTEST_FEE_PCT
SIZE_PCT = config.PORTFOLIO_PER_STRATEGY_FRACTION

VARIANTS = [
    {"label": "A — Short  (N=20)", "period": 20, "sl": 0.010, "tp": 0.025},
    {"label": "B — Medium (N=30)", "period": 30, "sl": 0.012, "tp": 0.030},
    {"label": "C — Long   (N=50)", "period": 50, "sl": 0.015, "tp": 0.040},
]

TARGETS = [
    {"symbol": "ETHUSDT", "interval": "1h"},
    {"symbol": "BTCUSDT", "interval": "4h"},
]


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


def simulate_window(bars: list, period: int, sl: float, tp: float) -> dict:
    """Lightweight per-year simulation (no DB write)."""
    if len(bars) < config.BACKTEST_MIN_WINDOW + 1:
        return {"trades": 0, "win_pct": 0, "return": 0, "sharpe": 0}

    strat    = DonchianBreakoutStrategy(period=period)
    position = None
    equity   = CAPITAL
    trade_returns = []
    trades_list   = []
    MAX_HOLD = 100

    for i in range(config.BACKTEST_MIN_WINDOW, len(bars) - 1):
        prices = [b["mid"] for b in bars[:i + 1]]
        md: MarketData = {
            "prices":      prices,
            "volumes":     None,
            "entry_price": position["entry"] if position else None,
            "position":    "LONG" if position else "NONE",
            "symbol":      "",
            "timestamp":   bars[i]["timestamp"],
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
            entry    = position["entry"]
            cur_exit = exec_price * (1 - config.SLIPPAGE_RATE)
            pnl_pct  = (cur_exit - entry) / entry

            exit_reason = None
            if pnl_pct <= -sl:
                exit_reason = "stop_loss"
                cur_exit = entry * (1 - sl)
            elif pnl_pct >= tp:
                exit_reason = "take_profit"
                cur_exit = entry * (1 + tp)
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


def print_table(symbol: str, interval: str, rows: list) -> None:
    print(f"\n  ── {symbol} {interval} ─────────────────────────────────────────────────────────")
    print(f"  {'Variant':<20} {'N':>4} {'SL':>5} {'TP':>5} {'Trades':>7} {'WR':>6} {'Return':>8} {'DD':>7} {'Sharpe':>8} {'Fees':>7}")
    print(f"  {'─'*84}")
    for r in rows:
        ok = "✓" if r["sharpe"] >= 0.5 and r["return"] > 0 else "✗"
        print(
            f"  {r['label']:<20} {r['period']:>4} {r['sl']*100:>4.1f}% {r['tp']*100:>4.1f}%"
            f" {r['trades']:>7} {r['win_pct']:>5.1f}%"
            f" {r['return']:>+7.2f}%"
            f" {r['dd']:>6.2f}%"
            f" {r['sharpe']:>8.4f}"
            f" ${r['fees']:>5.0f}  {ok}"
        )


def print_yby(label: str, bars: list, period: int, sl: float, tp: float) -> None:
    ts_min = datetime.fromisoformat(bars[0]["timestamp"].replace("Z", "+00:00"))
    ts_max = datetime.fromisoformat(bars[-1]["timestamp"].replace("Z", "+00:00"))

    print(f"\n  Year-by-year — {label}")
    print(f"  {'─'*62}")
    print(f"  {'Period':<24} {'Trades':>7} {'WR':>6} {'Return':>8} {'Sharpe':>8}")
    print(f"  {'─'*62}")

    for yr in range(3, 0, -1):
        y_end   = ts_max - timedelta(days=365 * (yr - 1))
        y_start = y_end  - timedelta(days=365)
        if y_start < ts_min:
            y_start = ts_min

        window = [
            b for b in bars
            if y_start.strftime("%Y-%m-%dT%H:%M:%SZ") <= b["timestamp"]
            <= y_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        ]
        r = simulate_window(window, period, sl, tp)
        lbl = f"Year {4-yr} ({y_start.strftime('%Y-%m')}→{y_end.strftime('%Y-%m')})"
        print(f"  {lbl:<24} {r['trades']:>7} {r['win_pct']:>5.1f}%"
              f" {r['return']:>+7.2f}%  {r['sharpe']:>8.4f}")

    r_all = simulate_window(bars, period, sl, tp)
    print(f"  {'─'*62}")
    print(f"  {'3-YEAR TOTAL':<24} {r_all['trades']:>7} {r_all['win_pct']:>5.1f}%"
          f" {r_all['return']:>+7.2f}%  {r_all['sharpe']:>8.4f}")


def main() -> None:
    print(f"\n{'='*88}")
    print(f"  DONCHIAN CHANNEL BREAKOUT RESEARCH  |  25% size  1x lev  fee=0.05%")
    print(f"  Viability: Sharpe ≥ 0.5  AND  Return > 0%  AND  no single-year collapse")
    print(f"{'='*88}")

    db = Database()
    all_results = {}

    # ── 3-year backtests ────────────────────────────────────────────────────
    print("\n  [1/2] Running 3-year backtests…\n")
    for target in TARGETS:
        symbol, interval = target["symbol"], target["interval"]
        rows = []
        print(f"  {symbol} {interval}:")
        for v in VARIANTS:
            strat = DonchianBreakoutStrategy(period=v["period"])
            run_ids = run_backtest(
                symbol=symbol, interval=interval, mode="per", db=db,
                strategies=[strat], sl_pct=v["sl"], tp_pct=v["tp"],
            )
            r = fetch_result(run_ids[0])
            r.update({"label": v["label"], "period": v["period"], "sl": v["sl"], "tp": v["tp"]})
            rows.append(r)
            ok = "✓" if r["sharpe"] >= 0.5 and r["return"] > 0 else "✗"
            print(f"    {v['label']}  trades={r['trades']}  WR={r['win_pct']}%  "
                  f"ret={r['return']:+.2f}%  sharpe={r['sharpe']:.4f}  {ok}")
        all_results[(symbol, interval)] = rows

    # ── Year-by-year for best ETH 1h variant ──────────────────────────────
    print("\n  [2/2] Year-by-year breakdown…")
    eth_bars = db.get_prices("ETHUSDT", "1h")
    btc_bars = db.get_prices("BTCUSDT", "4h")

    # Pick best ETH variant by sharpe
    eth_rows = all_results[("ETHUSDT", "1h")]
    best_eth = max(eth_rows, key=lambda x: x["sharpe"])
    print_yby(
        f"ETH 1h — {best_eth['label'].strip()} (best Sharpe)",
        eth_bars, best_eth["period"], best_eth["sl"], best_eth["tp"],
    )

    # Also show year-by-year for all ETH variants
    for v in VARIANTS:
        if v["label"] == best_eth["label"]:
            continue
        print_yby(f"ETH 1h — {v['label'].strip()}", eth_bars, v["period"], v["sl"], v["tp"])

    # BTC 4h best variant
    btc_rows = all_results[("BTCUSDT", "4h")]
    best_btc = max(btc_rows, key=lambda x: x["sharpe"])
    print_yby(
        f"BTC 4h — {best_btc['label'].strip()} (best Sharpe)",
        btc_bars, best_btc["period"], best_btc["sl"], best_btc["tp"],
    )

    # ── Summary tables ────────────────────────────────────────────────────
    print(f"\n\n{'='*88}")
    print(f"  DONCHIAN RESULTS SUMMARY")
    print(f"{'='*88}")

    for target in TARGETS:
        key = (target["symbol"], target["interval"])
        print_table(key[0], key[1], all_results[key])

    # ── Comparison vs BB ─────────────────────────────────────────────────
    print(f"\n  COMPARISON vs ETH 1h BB Breakout (from prior research):")
    print(f"  {'─'*60}")
    print(f"  BB Variant A (2.0σ, vol=1.5x)  220 trades  +13.88%  Sharpe=0.7480")
    print(f"  BB Variant B (1.5σ, vol=1.5x)  259 trades  +21.46%  Sharpe=0.9948")
    print(f"  BB Variant D (2.0σ, no vol)    272 trades  +18.44%  Sharpe=0.8784")

    print(f"\n  COMPARISON vs BTC 4h MR benchmark (live):")
    print(f"  {'─'*60}")
    print(f"  MR (RSI<35, SL=1.5%, TP=6.0%)  166 trades  +20.43%  Sharpe=0.8918")

    # ── Verdict ───────────────────────────────────────────────────────────
    print(f"\n{'='*88}")
    viable_eth = [r for r in all_results[("ETHUSDT", "1h")] if r["sharpe"] >= 0.5 and r["return"] > 0]
    viable_btc = [r for r in all_results[("BTCUSDT", "4h")] if r["sharpe"] >= 0.5 and r["return"] > 0]

    if viable_eth:
        best = max(viable_eth, key=lambda x: x["sharpe"])
        print(f"  ETH 1h Donchian: VIABLE — best {best['label'].strip()}  "
              f"Sharpe={best['sharpe']:.4f}  Return={best['return']:+.2f}%")
    else:
        print(f"  ETH 1h Donchian: REJECTED — no variant reaches Sharpe ≥ 0.5 + positive return")

    if viable_btc:
        best = max(viable_btc, key=lambda x: x["sharpe"])
        print(f"  BTC 4h Donchian: VIABLE — best {best['label'].strip()}  "
              f"Sharpe={best['sharpe']:.4f}  Return={best['return']:+.2f}%")
    else:
        print(f"  BTC 4h Donchian: REJECTED")
    print(f"{'='*88}\n")


if __name__ == "__main__":
    main()
