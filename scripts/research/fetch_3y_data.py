#!/usr/bin/env python3
"""
Fetch 3 years data with updated config and run backtest.
"""

import sys
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timezone
from backtest.data_loader import DataLoader
from backtest.database import Database
from backtest.engine import run_backtest
import config

print("=" * 70)
print("FETCHING 3-YEAR DATA WITH UPDATED CONFIG")
print("=" * 70)
print()
print(f"Configuration:")
print(f"  BACKTEST_HISTORY_DAYS = {config.BACKTEST_HISTORY_DAYS} days")
print(f"  Target: Last {config.BACKTEST_HISTORY_DAYS} days")
print()

db = Database()
loader = DataLoader(db)

# Clear old data
print("Clearing existing BTCUSDT 4h data...")
with db._connect() as conn:
    conn.execute("DELETE FROM prices WHERE symbol='BTCUSDT' AND interval='4h'")
print("  Cleared")
print()

# Fetch new data
print(f"Fetching BTCUSDT 4h data from Binance...")
try:
    count = loader.sync(symbol="BTCUSDT", interval="4h")
    print(f"  ✅ Fetched {count:,} bars")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

# Verify
print()
print("Verifying data...")
prices = db.get_prices("BTCUSDT", "4h")
print(f"  Total bars: {len(prices):,}")

if len(prices) > 0:
    with db._connect() as conn:
        cursor = conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM prices WHERE symbol='BTCUSDT' AND interval='4h'"
        )
        min_ts, max_ts = cursor.fetchone()
    print(f"  Period: {min_ts} → {max_ts}")
    
    try:
        t1 = datetime.fromisoformat(min_ts.replace('Z', '+00:00'))
        t2 = datetime.fromisoformat(max_ts.replace('Z', '+00:00'))
        days = (t2 - t1).days
        years = days / 365.25
        print(f"  Duration: {days} days (~{years:.2f} years)")
    except:
        pass

print()
print("=" * 70)
print("RUNNING BACKTEST")
print("=" * 70)
print()

try:
    result_ids = run_backtest(
        symbol="BTCUSDT",
        interval="4h",
        sl_pct=0.015,  # 1.5%
        tp_pct=0.060,  # 6.0%
        mode="per"
    )
    
    if result_ids:
        run_id = result_ids[0]
        result = db.get_run(run_id)
        
        print()
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        print()
        
        start_date = result.get("start_date", "N/A")
        end_date = result.get("end_date", "N/A")
        initial_capital = result.get("initial_capital", config.BACKTEST_CAPITAL)
        final_capital = result.get("final_capital", initial_capital)
        total_return_pct = result.get("total_return_pct", 0.0)
        total_trades = result.get("total_trades", 0)
        winning_trades = result.get("winning_trades", 0)
        win_rate_pct = result.get("win_rate_pct", 0.0)
        max_drawdown_pct = result.get("max_drawdown_pct", 0.0)
        sharpe_ratio = result.get("sharpe_ratio", 0.0)
        total_bars = result.get("total_bars", 0)
        tradeable_bars = result.get("tradeable_bars", 0)
        
        # Calculate fees
        trades = db.get_trades(run_id)
        total_fees = sum(t.get("fees_paid", 0) for t in trades if t.get("fees_paid", 0) > 0)
        
        print(f"Period:             {start_date} → {end_date}")
        print(f"Data:               {total_bars:,} bars ({tradeable_bars:,} tradeable)")
        print()
        print(f"Capital:            ${initial_capital:,.2f} → ${final_capital:,.2f}")
        print(f"Return:             {total_return_pct:+.2f}% (${final_capital - initial_capital:+,.2f})")
        print()
        print(f"Sharpe Ratio:       {sharpe_ratio:.4f}")
        print(f"Max Drawdown:       {max_drawdown_pct:.2f}%")
        print()
        print(f"Trades:             {total_trades} ({winning_trades} wins)")
        print(f"Win Rate:           {win_rate_pct:.1f}%")
        print(f"Fees Paid:          ${total_fees:,.2f}")
        print()
        
        # Annualized
        try:
            t1 = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            t2 = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            years = (t2 - t1).days / 365.25
            if years > 0:
                annualized_return = ((final_capital / initial_capital) ** (1.0 / years) - 1) * 100
                print(f"Annualized Return:  {annualized_return:+.2f}% (over {years:.2f} years)")
        except:
            pass
        
        print()
        print("=" * 70)
        print(f"Run ID: {run_id}")
        print("=" * 70)
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
