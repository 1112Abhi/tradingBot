"""
scripts/research/sizing_comparison.py — Phase 8.3 Sizing Comparison

Compares equal-weight sizing (EMA 25%, MR 25%) vs Sharpe-weighted sizing
(EMA 15%, MR 25%) on BTCUSDT 4h, 3-year historical data.

Usage:
    python scripts/research/sizing_comparison.py
"""

import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backtest.database import Database
from backtest.engine import run_backtest
from strategy.ema_crossover import MACrossoverStrategy
from strategy.mean_reversion import MeanReversionStrategy

SYMBOL   = "BTCUSDT"
INTERVAL = "4h"
SL_PCT   = 0.015
TP_PCT   = 0.060

# Scenarios: (label, ema_size, mr_size)
SCENARIOS = [
    ("Equal-weight  (EMA=25%, MR=25%)", 0.25, 0.25),
    ("Sharpe-weight (EMA=15%, MR=25%)", 0.15, 0.25),
]

ema_strategy = MACrossoverStrategy(
    fast_period=12, slow_period=26, trend_period=50,
    rsi_period=14, rsi_buy_min=0, rsi_buy_max=100,
)
mr_strategy = MeanReversionStrategy(
    rsi_period=14, rsi_oversold=35, rsi_exit=55, trend_period=50,
)


def run_scenario(label: str, ema_size: float, mr_size: float, db: Database) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    for strategy, size, name in [
        (ema_strategy, ema_size, "EMA Crossover"),
        (mr_strategy,  mr_size,  "Mean Reversion"),
    ]:
        run_ids = run_backtest(
            symbol        = SYMBOL,
            interval      = INTERVAL,
            mode          = "per",
            db            = db,
            strategies    = [strategy],
            sl_pct        = SL_PCT,
            tp_pct        = TP_PCT,
            position_size = size,
        )
        if run_ids:
            row = db.get_run(run_ids[0])
            print(
                f"  {name:<20} size={size*100:.0f}%  "
                f"return={row['total_return_pct']:+.2f}%  "
                f"sharpe={row['sharpe_ratio']:.2f}  "
                f"DD={row['max_drawdown_pct']:.2f}%  "
                f"trades={row['total_trades']}"
            )


def main() -> None:
    db = Database()
    print(f"\nPhase 8.3 — Position Sizing Comparison")
    print(f"Symbol: {SYMBOL}  Interval: {INTERVAL}  SL={SL_PCT*100}%  TP={TP_PCT*100}%")

    for label, ema_size, mr_size in SCENARIOS:
        run_scenario(label, ema_size, mr_size, db)

    print(f"\n{'='*60}")
    print("Done.")


if __name__ == "__main__":
    main()
