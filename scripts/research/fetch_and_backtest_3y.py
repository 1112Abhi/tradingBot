#!/usr/bin/env python3
"""
Fetch 3 years of BTCUSDT 4h data and run extended validation.
1. Clear existing BTCUSDT 4h data
2. Fetch 3 years from Binance
3. Run backtest
4. Compare results
"""

import sys
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timezone, timedelta
from backtest.data_loader import DataLoader
from backtest.database import Database
from backtest.engine import run_backtest
import config

def fetch_three_year_data():
    """Fetch 3 years of BTCUSDT 4h data."""
    
    print("=" * 70)
    print("FETCHING 3 YEARS OF DATA")
    print("=" * 70)
    print()
    
    db = Database()
    loader = DataLoader(db)
    
    symbol = "BTCUSDT"
    interval = "4h"
    
    # Step 1: Clear existing data
    print(f"Step 1: Clearing existing {symbol} {interval} data...")
    existing_count = len(db.get_prices(symbol, interval))
    print(f"  Before: {existing_count:,} bars")
    
    # Use the context manager to delete data
    with db._connect() as conn:
        conn.execute("DELETE FROM prices WHERE symbol=? AND interval=?", (symbol, interval))
    print(f"  Cleared all {symbol} {interval} data")
    print()
    
    # Step 2: Fetch 3 years
    print(f"Step 2: Fetching 3 years (~1095 days) of {symbol} {interval} data...")
    print(f"  Target: {datetime.now(timezone.utc) - timedelta(days=1095)} → now")
    print()
    
    try:
        count = loader.sync(symbol=symbol, interval=interval)
        print()
        print(f"  ✅ Fetched {count:,} new bars")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Verify data
    print()
    print(f"Step 3: Verifying data...")
    prices = db.get_prices(symbol, interval)
    print(f"  Total bars: {len(prices):,}")
    
    if len(prices) > 0:
        # Get first and last timestamps
        with db._connect() as conn:
            cursor = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM prices WHERE symbol=? AND interval=?",
                (symbol, interval)
            )
            min_ts, max_ts = cursor.fetchone()
        print(f"  Period: {min_ts} → {max_ts}")
        
        # Calculate period in days
        try:
            t1 = datetime.fromisoformat(min_ts.replace('Z', '+00:00'))
            t2 = datetime.fromisoformat(max_ts.replace('Z', '+00:00'))
            days = (t2 - t1).days
            years = days / 365.25
            print(f"  Duration: {days} days (~{years:.2f} years)")
        except:
            pass
    
    print()
    return True


def run_validation():
    """Run backtest on the 3-year data."""
    
    print("=" * 70)
    print("RUNNING 3-YEAR BACKTEST")
    print("=" * 70)
    print()
    
    print(f"Configuration:")
    print(f"  Symbol:             BTCUSDT")
    print(f"  Timeframe:          4h")
    print(f"  Stop Loss:          1.5%")
    print(f"  Take Profit:        6.0%")
    print(f"  Leverage:           {config.LEVERAGE}x")
    print(f"  Fees:               {config.BACKTEST_FEE_PCT*100:.3f}%")
    print(f"  Slippage:           {config.SLIPPAGE_RATE*100:.3f}%")
    print(f"  Initial Capital:    ${config.BACKTEST_CAPITAL:,.2f}")
    print()
    
    print("Running backtest...")
    try:
        result_ids = run_backtest(
            symbol="BTCUSDT",
            interval="4h",
            sl_pct=0.015,  # 1.5%
            tp_pct=0.060,  # 6.0%
            mode="per"
        )
        
        if not result_ids:
            print("ERROR: Backtest failed")
            return False
        
        db = Database()
        run_id = result_ids[0]
        result = db.get_run(run_id)
        
        print()
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        print()
        
        # Extract metrics
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
        
        # Display
        print(f"📊 PERFORMANCE METRICS:")
        print(f"  Period:             {start_date} → {end_date}")
        print(f"  Data Points:        {total_bars:,} bars ({tradeable_bars:,} tradeable)")
        print()
        print(f"  Initial Capital:    ${initial_capital:,.2f}")
        print(f"  Final Capital:      ${final_capital:,.2f}")
        print(f"  Total Return:       {total_return_pct:+.2f}% (${final_capital - initial_capital:+,.2f})")
        print()
        print(f"  Sharpe Ratio:       {sharpe_ratio:.4f}")
        print(f"  Max Drawdown:       {max_drawdown_pct:.2f}%")
        print()
        print(f"  Total Trades:       {total_trades}")
        print(f"  Winning Trades:     {winning_trades}/{total_trades}")
        print(f"  Win Rate:           {win_rate_pct:.1f}%")
        print(f"  Total Fees Paid:    ${total_fees:,.2f}")
        print()
        
        # Annualized
        try:
            t1 = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            t2 = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            years = (t2 - t1).days / 365.25
            annualized_return = ((final_capital / initial_capital) ** (1.0 / max(0.25, years)) - 1) * 100
            print(f"📈 ANNUALIZED (over {years:.2f} years):")
            print(f"  Annualized Return:  {annualized_return:+.2f}%")
            print(f"  Trades per Year:    {total_trades / years:.1f}")
        except:
            pass
        
        print()
        print("=" * 70)
        print(f"Run ID: {run_id}")
        print("=" * 70)
        print()
        
        # Summary
        print("✅ 3-YEAR VALIDATION COMPLETE")
        print()
        
        if total_return_pct > 0:
            print("✅ PROFITABLE: Strategy remains positive on extended period")
        else:
            print("⚠️ UNPROFITABLE: Strategy negative on extended period")
        
        if sharpe_ratio > 0.3:
            print("✅ ACCEPTABLE SHARPE: Risk-adjusted returns are positive")
        else:
            print("⚠️ LOW SHARPE: Risk-adjusted returns are weak")
        
        if max_drawdown_pct < 10:
            print("✅ CONTROLLED DRAWDOWN: Risk well-managed")
        else:
            print("⚠️ HIGH DRAWDOWN: Risk management needs review")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        # Step 1: Fetch data
        if not fetch_three_year_data():
            sys.exit(1)
        
        # Step 2: Run validation
        if not run_validation():
            sys.exit(1)
        
        print("=" * 70)
        print("SUCCESS: 3-Year Extended Validation Complete")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
