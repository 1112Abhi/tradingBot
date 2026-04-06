#!/usr/bin/env python3
"""
mr_1h_research.py — 1h Mean Reversion research.

Fetches 3yr BTCUSDT 1h data then tests 4 variants:
  A — Balanced     RSI<30, SL=0.8%, TP=2.0%
  B — Conservative RSI<25, SL=0.6%, TP=1.5%
  C — Aggressive   RSI<35, SL=1.0%, TP=2.5%
  D — 4h-params    RSI<35, SL=1.5%, TP=6.0%  (benchmark — same params as live 4h MR)

Viability criteria: Sharpe >= 0.7  AND  Return > 0%  AND  Trades >= 50

Usage:
    python scripts/research/mr_1h_research.py
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import sqlite3
import config
from backtest.database import Database
from backtest.data_loader import DataLoader
from backtest.engine import run_backtest
from strategy.mean_reversion import MeanReversionStrategy

SYMBOL   = "BTCUSDT"
INTERVAL = "1h"
YEARS_NEEDED = 3

VARIANTS = [
    {"label": "A — Balanced    ", "rsi_entry": 30, "sl": 0.008, "tp": 0.020},
    {"label": "B — Conservative", "rsi_entry": 25, "sl": 0.006, "tp": 0.015},
    {"label": "C — Aggressive  ", "rsi_entry": 35, "sl": 0.010, "tp": 0.025},
    {"label": "D — 4h-params   ", "rsi_entry": 35, "sl": 0.015, "tp": 0.060},
]


def ensure_3yr_data(db: Database) -> int:
    bars = db.get_prices(SYMBOL, INTERVAL)
    if bars:
        from datetime import datetime
        ts_min = datetime.fromisoformat(bars[0]["timestamp"].replace("Z", "+00:00"))
        ts_max = datetime.fromisoformat(bars[-1]["timestamp"].replace("Z", "+00:00"))
        days = (ts_max - ts_min).days
        if days >= YEARS_NEEDED * 365 - 10:
            print(f"  1h data OK: {days} days ({len(bars):,} bars)")
            return len(bars)

    print(f"  Clearing old 1h data and fetching {YEARS_NEEDED}yr from Binance…")
    with db._connect() as conn:
        conn.execute(f"DELETE FROM prices WHERE symbol='{SYMBOL}' AND interval='{INTERVAL}'")
    loader = DataLoader(db)
    count = loader.sync(symbol=SYMBOL, interval=INTERVAL)
    print(f"  Fetched {count:,} bars")
    return count


def fetch_result(run_id: str) -> dict:
    conn = sqlite3.connect(config.BACKTEST_DB)
    c = conn.cursor()
    c.execute(
        """SELECT total_trades, win_rate_pct, total_return_pct,
                  max_drawdown_pct, sharpe_ratio, start_date, end_date
           FROM backtest_runs WHERE run_id=?""",
        (run_id,),
    )
    row = c.fetchone()
    c.execute("SELECT COALESCE(SUM(fees_paid),0) FROM backtest_trades WHERE run_id=?", (run_id,))
    fees = c.fetchone()[0]
    conn.close()
    trades, win_pct, ret, dd, sharpe, start, end = row
    return {
        "trades": trades or 0,
        "win_pct": round(win_pct or 0, 1),
        "return": round(ret or 0, 2),
        "dd": round(dd or 0, 2),
        "sharpe": round(sharpe or 0, 4),
        "fees": round(fees, 0),
        "start": (start or "")[:10],
        "end": (end or "")[:10],
    }


def main() -> None:
    print(f"\n{'='*90}")
    print(f"  1h MEAN REVERSION RESEARCH — {SYMBOL}  |  25% fixed size  1x lev  fee=0.05%")
    print(f"{'='*90}")

    db = Database()

    # ── Ensure 3yr data ────────────────────────────────────────────────────
    print("\n  [1/2] Data…")
    n = ensure_3yr_data(db)
    bars = db.get_prices(SYMBOL, INTERVAL)
    ts_min, ts_max = bars[0]["timestamp"][:10], bars[-1]["timestamp"][:10]
    print(f"  Period: {ts_min} → {ts_max}  ({n:,} bars)\n")

    # ── Run variants ────────────────────────────────────────────────────────
    print("  [2/2] Running variants…\n")
    results = []
    for v in VARIANTS:
        strat = MeanReversionStrategy(rsi_oversold=v["rsi_entry"])
        run_ids = run_backtest(
            symbol=SYMBOL, interval=INTERVAL, mode="per", db=db,
            strategies=[strat], sl_pct=v["sl"], tp_pct=v["tp"],
        )
        r = fetch_result(run_ids[0])
        r.update({"label": v["label"], "rsi": v["rsi_entry"], "sl": v["sl"], "tp": v["tp"]})
        results.append(r)
        ok = "✓" if r["sharpe"] >= 0.7 and r["return"] > 0 else "✗"
        print(f"    {v['label']}  trades={r['trades']}  WR={r['win_pct']}%  "
              f"ret={r['return']:+.2f}%  DD={r['dd']:.2f}%  sharpe={r['sharpe']:.4f}  {ok}")

    # ── Table ────────────────────────────────────────────────────────────────
    print(f"\n\n{'='*90}")
    print(f"  1h MEAN REVERSION RESEARCH — {SYMBOL}  |  {ts_min} → {ts_max}")
    print(f"{'='*90}")
    print(f"  {'Variant':<22} {'RSI':>5} {'SL':>6} {'TP':>6} {'Trades':>7} {'WR':>6} {'Return':>8} {'DD':>7} {'Sharpe':>8} {'Fees':>7}")
    print(f"  {'─'*88}")
    for r in results:
        ok = "✓" if r["sharpe"] >= 0.7 and r["return"] > 0 else "✗"
        print(
            f"  {r['label']:<22} {r['rsi']:>5} {r['sl']*100:>5.1f}% {r['tp']*100:>5.1f}%"
            f" {r['trades']:>7} {r['win_pct']:>5.1f}%"
            f" {r['return']:>+7.2f}%"
            f" {r['dd']:>6.2f}%"
            f" {r['sharpe']:>8.4f}"
            f" ${r['fees']:>5.0f}  {ok}"
        )
    print(f"  {'─'*88}")

    # ── 4h benchmark reminder ────────────────────────────────────────────────
    print(f"\n  4h MR benchmark (live config): RSI<35  SL=1.5%  TP=6.0%")
    print(f"  166 trades  32.5% WR  +20.43%  DD=6.48%  Sharpe=0.8918  (3yr BTCUSDT 4h)")

    # ── Verdict ──────────────────────────────────────────────────────────────
    print(f"\n{'='*90}")
    viable = [r for r in results if r["sharpe"] >= 0.7 and r["return"] > 0 and r["trades"] >= 50]
    if viable:
        best = max(viable, key=lambda x: x["sharpe"])
        print(f"  VERDICT: VIABLE")
        print(f"  Best variant: {best['label'].strip()}  "
              f"Sharpe={best['sharpe']:.4f}  Return={best['return']:+.2f}%  Trades={best['trades']}")
    else:
        passing = [r for r in results if r["return"] > 0]
        if passing:
            best = max(passing, key=lambda x: x["return"])
            print(f"  VERDICT: MARGINAL — No variant reaches Sharpe ≥ 0.7")
            print(f"  Closest: {best['label'].strip()}  Sharpe={best['sharpe']:.4f}  Return={best['return']:+.2f}%")
        else:
            print(f"  VERDICT: REJECTED — All variants show negative returns on 1h timeframe")
    print(f"{'='*90}\n")


if __name__ == "__main__":
    main()
