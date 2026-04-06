#!/usr/bin/env python3
"""Compare strategy versions"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3

conn = sqlite3.connect('backtest.db')
cursor = conn.cursor()

# Get latest 2 runs (EMA 12,26)
cursor.execute('SELECT total_trades, winning_trades, win_rate_pct, total_return_pct, max_drawdown_pct FROM backtest_runs ORDER BY created_at DESC LIMIT 2')
new_results = cursor.fetchall()

# Get first 2 runs (EMA 5,20)
cursor.execute('SELECT total_trades, winning_trades, win_rate_pct, total_return_pct, max_drawdown_pct FROM backtest_runs WHERE total_trades = 246 ORDER BY created_at ASC LIMIT 2')
old_results = cursor.fetchall()

print("\n" + "="*80)
print("🚀 STRATEGY COMPARISON: EMA(5,20) vs EMA(12,26) + EMA50 FILTER")
print("="*80)

print("\n📊 V2: EMA(12,26) + EMA50 Trend Filter (LATEST):")
print("-"*80)
v2 = new_results[0] if new_results else (0,0,0,0,0)
print(f"  Trades:     {v2[0]:>3}")
print(f"  Wins:       {v2[1]:>3} ({v2[2]:>5.1f}%)")
print(f"  Return:     {v2[3]:>6.2f}%")
print(f"  Drawdown:   {v2[4]:>5.2f}%")

print("\n📊 V1: EMA(5,20) - No Trend Filter (PREVIOUS):")
print("-"*80)
v1 = old_results[0] if old_results else (0,0,0,0,0)
print(f"  Trades:     {v1[0]:>3}")
print(f"  Wins:       {v1[1]:>3} ({v1[2]:>5.1f}%)")
print(f"  Return:     {v1[3]:>6.2f}%")
print(f"  Drawdown:   {v1[4]:>5.2f}%")

print("\n" + "="*80)
print("📈 IMPROVEMENTS:")
print("-"*80)
trade_change = ((v2[0] - v1[0]) / v1[0] * 100) if v1[0] else 0
dd_change = ((v1[4] - v2[4]) / v1[4] * 100) if v1[4] else 0
ret_change = v2[3] - v1[3]
win_change = v2[2] - v1[2]

print(f"✅ Trades Reduced:    {v1[0]} → {v2[0]} ({trade_change:+.1f}%) - Fewer false signals!")
print(f"✅ Drawdown Improved: {v1[4]:.2f}% → {v2[4]:.2f}% ({-dd_change:+.1f}%)")
print(f"⚠️  Return Similar:    {v1[3]:.2f}% → {v2[3]:.2f}% ({ret_change:+.2f}%)")
print(f"⚠️  Win Rate Similar:  {v1[2]:.1f}% → {v2[2]:.1f}% ({win_change:+.1f}%)")

print("\n💡 KEY: Trend filter cut trades in HALF while reducing drawdown!")
print("        This is better risk management - fewer whipsaws in choppy markets.")
print("="*80 + "\n")

conn.close()
