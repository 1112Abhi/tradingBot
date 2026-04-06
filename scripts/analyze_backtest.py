#!/usr/bin/env python3
"""Analyze backtest results"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import sys

conn = sqlite3.connect('backtest.db')
cursor = conn.cursor()

print("\n" + "="*80)
print("BACKTEST STRATEGY ANALYSIS - BTCUSDT 1H")
print("="*80)

# Get summary by strategy from backtest_runs
cursor.execute('''
SELECT strategy, 
       total_trades as trades, 
       winning_trades as wins,
       win_rate_pct,
       total_return_pct,
       initial_capital,
       final_capital,
       max_drawdown_pct,
       start_date,
       end_date
FROM backtest_runs 
ORDER BY strategy
''')

rows = cursor.fetchall()
for row in rows:
    strategy, trades, wins, win_pct, return_pct, init_cap, final_cap, max_dd, start, end = row
    profit = final_cap - init_cap
    profit_str = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
    
    print(f"\n{'STRATEGY':<20}: {strategy.upper()}")
    print(f"{'Period':<20}: {start} to {end}")
    print(f"{'Total Trades':<20}: {trades}")
    print(f"{'Winning Trades':<20}: {wins} ({win_pct:.1f}%)")
    print(f"{'Total Return':<20}: {return_pct:.2f}%")
    print(f"{'Capital':<20}: ${init_cap:.2f} → ${final_cap:.2f} ({profit_str})")
    print(f"{'Max Drawdown':<20}: {max_dd:.2f}%")

# Individual trades from the most recent run
print("\n" + "-"*80)
print("RECENT TRADES (Last backtest run):")
print("-"*80)

# Get the most recent run_id
cursor.execute('SELECT run_id FROM backtest_runs ORDER BY created_at DESC LIMIT 1')
run_id = cursor.fetchone()[0]

cursor.execute(f'''
SELECT trade_num, entry_ts, exit_ts, entry_price, exit_price, 
       pnl_dollar, pnl_pct, exit_reason
FROM backtest_trades
WHERE run_id = '{run_id}'
ORDER BY trade_num ASC
LIMIT 10
''')

print(f"{'#':<4} {'Entry Time':<20} {'Exit Time':<20} {'Entry':<10} {'Exit':<10} {'P&L $':<10} {'P&L %':<8} {'Reason':<12}")
print("-"*104)
for row in cursor.fetchall():
    trade_num, entry_ts, exit_ts, entry_price, exit_price, pnl_dollar, pnl_pct, reason = row
    pnl_str = f"+${pnl_dollar:.2f}" if pnl_dollar >= 0 else f"-${abs(pnl_dollar):.2f}"
    pnl_pct_str = f"+{pnl_pct:.2f}%" if pnl_pct >= 0 else f"{pnl_pct:.2f}%"
    print(f"{trade_num:<4} {entry_ts:<20} {exit_ts:<20} ${entry_price:<9.2f} ${exit_price:<9.2f} {pnl_str:<10} {pnl_pct_str:<8} {reason:<12}")

# Distribution analysis
print("\n" + "-"*80)
print("TRADE DISTRIBUTION:")
print("-"*80)
cursor.execute(f'''
SELECT exit_reason, COUNT(*) as count, 
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM backtest_trades WHERE run_id = '{run_id}'), 1) as pct,
       ROUND(SUM(pnl_dollar), 2) as total_pnl,
       ROUND(AVG(pnl_dollar), 2) as avg_pnl
FROM backtest_trades
WHERE run_id = '{run_id}'
GROUP BY exit_reason
ORDER BY count DESC
''')

print(f"{'Exit Reason':<15} {'Count':<8} {'%':<8} {'Total P&L':<12} {'Avg P&L':<12}")
for row in cursor.fetchall():
    reason, count, pct, total_pnl, avg_pnl = row
    total_str = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):.2f}"
    avg_str = f"+${avg_pnl:.2f}" if avg_pnl >= 0 else f"-${abs(avg_pnl):.2f}"
    print(f"{reason:<15} {count:<8} {pct:>6.1f}%  {total_str:<12} {avg_str:<12}")

print("\n" + "="*80)
conn.close()
