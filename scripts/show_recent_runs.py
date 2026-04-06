#!/usr/bin/env python3
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
from datetime import datetime

conn = sqlite3.connect('/Users/abhi/jupyter_env/tradingBot/backtest.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('''
SELECT symbol, total_return_pct, win_rate_pct, total_trades, 
       max_drawdown_pct, sharpe_ratio, created_at
FROM backtest_runs 
WHERE created_at >= datetime('now', '-2 hours')
ORDER BY symbol, created_at DESC
''')

print("=" * 100)
print("PHASE 7.4: RECENT BACKTEST RESULTS (24 Completed Combinations)")
print("=" * 100)
print(f"{'Symbol':<10} {'Return%':>10} {'WinRate%':>10} {'Trades':>8} {'DD%':>8} {'Sharpe':>10} {'Time':>20}")
print("-" * 100)

rows = cursor.fetchall()
for row in rows:
    time_str = datetime.fromisoformat(row['created_at']).strftime('%H:%M:%S')
    print(f"{row['symbol']:<10} {row['total_return_pct']:>10.2f} {row['win_rate_pct']:>10.1f} "
          f"{row['total_trades']:>8} {row['max_drawdown_pct']:>8.2f} {row['sharpe_ratio']:>10.4f} {time_str:>20}")

print("=" * 100)
print(f"Total runs: {len(rows)}/27 completed")
print("=" * 100)

# Best by return
print("\nBEST BY RETURN (Top 5):")
cursor.execute('''
SELECT symbol, total_return_pct, win_rate_pct, total_trades, sharpe_ratio
FROM backtest_runs 
WHERE created_at >= datetime('now', '-2 hours')
ORDER BY total_return_pct DESC LIMIT 5
''')
for i, row in enumerate(cursor.fetchall(), 1):
    print(f"  {i}. {row['symbol']:10} → Return: {row['total_return_pct']:>8.2f}% | WinRate: {row['win_rate_pct']:>6.1f}% | Sharpe: {row['sharpe_ratio']:>8.4f}")

# Best by Sharpe
print("\nBEST BY SHARPE (Top 5):")
cursor.execute('''
SELECT symbol, total_return_pct, win_rate_pct, total_trades, sharpe_ratio
FROM backtest_runs 
WHERE created_at >= datetime('now', '-2 hours')
ORDER BY sharpe_ratio DESC LIMIT 5
''')
for i, row in enumerate(cursor.fetchall(), 1):
    print(f"  {i}. {row['symbol']:10} → Sharpe: {row['sharpe_ratio']:>8.4f} | Return: {row['total_return_pct']:>8.2f}% | WinRate: {row['win_rate_pct']:>6.1f}%")

conn.close()
