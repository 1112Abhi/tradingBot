#!/usr/bin/env python3
"""Test grid of stop/TP combinations"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import subprocess
import sqlite3
import sys

# Test variants
variants = [
    {"name": "V4a (Tight)", "sl": 0.015, "tp": 0.045},   # 1.5% / 4.5%
    {"name": "V4b (Wide)",  "sl": 0.020, "tp": 0.060},   # 2% / 6%
    {"name": "V4c (Base)",  "sl": 0.020, "tp": 0.050},   # 2% / 5% (current)
]

print("\n" + "="*80)
print("🔥 TESTING STOP/TP OPTIMIZATION GRID")
print("="*80)

results = []

for variant in variants:
    # Update config
    with open('config.py', 'r') as f:
        content = f.read()
    
    # Replace stop/TP values
    new_content = content.replace(
        f"BACKTEST_STOP_LOSS_PCT = {variants[-1]['sl']:.3f}",
        f"BACKTEST_STOP_LOSS_PCT = {variant['sl']:.3f}"
    )
    new_content = new_content.replace(
        f"BACKTEST_TAKE_PROFIT_PCT = {variants[-1]['tp']:.3f}",
        f"BACKTEST_TAKE_PROFIT_PCT = {variant['tp']:.3f}"
    )
    
    # Simpler approach - just rewrite the config values
    import re
    new_content = re.sub(
        r'BACKTEST_STOP_LOSS_PCT = [\d.]+',
        f'BACKTEST_STOP_LOSS_PCT = {variant["sl"]}',
        content
    )
    new_content = re.sub(
        r'BACKTEST_TAKE_PROFIT_PCT = [\d.]+',
        f'BACKTEST_TAKE_PROFIT_PCT = {variant["tp"]}',
        new_content
    )
    
    with open('config.py', 'w') as f:
        f.write(new_content)
    
    print(f"\n🧪 Testing {variant['name']}: {variant['sl']*100:.1f}% SL / {variant['tp']*100:.1f}% TP")
    print("-" * 80)
    
    # Run backtest
    result = subprocess.run(
        ['python', 'backtest_runner.py', '--symbol', 'BTCUSDT', '--interval', '1h', '--mode', 'both'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    # Query latest result
    conn = sqlite3.connect('backtest.db')
    c = conn.cursor()
    c.execute('''
        SELECT 
            total_trades, winning_trades, ROUND(win_rate_pct, 1) as win_pct,
            ROUND(total_return_pct, 2) as ret, ROUND(max_drawdown_pct, 2) as dd,
            initial_capital, final_capital
        FROM backtest_runs
        WHERE strategy = 'ema_crossover'
        ORDER BY created_at DESC LIMIT 1
    ''')
    row = c.fetchone()
    conn.close()
    
    if row:
        trades, wins, win_pct, ret, dd, init_cap, final_cap = row
        avg_pnl = (final_cap - init_cap) / trades if trades > 0 else 0
        
        results.append({
            'variant': variant['name'],
            'sl': variant['sl'],
            'tp': variant['tp'],
            'trades': trades,
            'wins': wins,
            'win_pct': win_pct,
            'return': ret,
            'dd': dd,
            'avg_pnl': avg_pnl
        })
        
        print(f"  ✅ Return:     {ret:>7.2f}%")
        print(f"  ✅ Win Rate:   {win_pct:>7.1f}%")
        print(f"  ✅ Trades:     {trades:>7}")
        print(f"  ✅ Avg P&L:    ${avg_pnl:>7.2f}")
        print(f"  ✅ Drawdown:   {dd:>7.2f}%")

print("\n" + "="*80)
print("📊 SUMMARY COMPARISON")
print("="*80)
print(f"{'Variant':<15} {'SL/TP':<10} {'Return':<10} {'Win%':<8} {'Trades':<8} {'Avg PnL':<10} {'DD':<8}")
print("-"*80)

for r in results:
    print(f"{r['variant']:<15} {r['sl']*100:.1f}/{r['tp']*100:.1f}%  {r['return']:>7.2f}%  {r['win_pct']:>6.1f}%  {r['trades']:>7}  ${r['avg_pnl']:>7.2f}  {r['dd']:>6.2f}%")

print("\n" + "="*80)

# Find best
best = max(results, key=lambda x: x['return'])
print(f"\n🏆 BEST: {best['variant']} with {best['return']:.2f}% return")
print("="*80 + "\n")
