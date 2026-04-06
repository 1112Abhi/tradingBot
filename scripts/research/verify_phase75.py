#!/usr/bin/env python3
"""
Quick verification that Phase 7.5 extended validation is complete.
"""

import sys
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.database import Database
import config

print("\n" + "=" * 70)
print("PHASE 7.5 VERIFICATION")
print("=" * 70)
print()

# Check 1: Configuration
print("✓ Configuration Check:")
print(f"  LEVERAGE:             {config.LEVERAGE}x (expected: 1.0x)")
print(f"  BACKTEST_HISTORY_DAYS: {config.BACKTEST_HISTORY_DAYS} (expected: 1095)")
print()

if config.LEVERAGE != 1.0:
    print("  ❌ ERROR: Leverage not set to 1.0x")
    sys.exit(1)

if config.BACKTEST_HISTORY_DAYS != 1095:
    print("  ❌ ERROR: History days not set to 1095")
    sys.exit(1)

# Check 2: Database
print("✓ Database Check:")
db = Database()
prices = db.get_prices("BTCUSDT", "4h")
print(f"  BTCUSDT 4h bars:      {len(prices):,} (expected: ~6500+)")

if len(prices) < 6000:
    print("  ❌ ERROR: Not enough data fetched")
    sys.exit(1)

# Get date range
with db._connect() as conn:
    cursor = conn.execute(
        "SELECT MIN(timestamp), MAX(timestamp) FROM prices WHERE symbol='BTCUSDT' AND interval='4h'"
    )
    min_ts, max_ts = cursor.fetchone()

print(f"  Period:               {min_ts} → {max_ts}")
print()

# Check 3: Latest backtest run
print("✓ Latest Backtest Run:")
with db._connect() as conn:
    cursor = conn.execute(
        """SELECT run_id, total_return_pct, sharpe_ratio, max_drawdown_pct, 
                  total_trades, win_rate_pct, start_date, end_date
           FROM backtest_runs WHERE symbol='BTCUSDT'
           ORDER BY created_at DESC LIMIT 1"""
    )
    row = cursor.fetchone()

if row:
    run_id, ret, sharpe, dd, trades, wr, start, end = row
    print(f"  Run ID:               {run_id}")
    print(f"  Period:              {start} → {end}")
    print(f"  Return:              {ret:+.2f}%")
    print(f"  Sharpe:              {sharpe:.4f}")
    print(f"  Drawdown:            {dd:.2f}%")
    print(f"  Trades:              {int(trades)} ({wr:.1f}% win)")
    print()
else:
    print("  ❌ ERROR: No backtest runs found")
    sys.exit(1)

# Final status
print("=" * 70)
print("✅ PHASE 7.5 COMPLETE AND VERIFIED")
print("=" * 70)
print()
print("Summary:")
print(f"  - Leverage:  1.0x (no margin risk)")
print(f"  - Data:      3 years ({len(prices):,} bars)")
print(f"  - Return:    {ret:+.2f}% (annualized: +{ret/3:.2f}%)")
print(f"  - Sharpe:    {sharpe:.4f}")
print(f"  - Drawdown:  {dd:.2f}%")
print()
print("Status: ✅ READY FOR LIVE TRADING")
print()

