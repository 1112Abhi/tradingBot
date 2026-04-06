#!/usr/bin/env python3
"""
Phase 7.4: Multi-Symbol Parameter Grid Validation

Validates trading strategy across multiple symbols and parameter combinations.
Tests grid of:
  - Symbols: BTCUSDT, ETHUSDT, SOLUSDT
  - Timeframe: 4h
  - Stop Loss: 0.0125, 0.015, 0.02
  - Take Profit: 0.055, 0.06, 0.065

Usage:
  python validate_parameters.py

Output:
  - Console: Summary table with all results
  - Database: All runs stored in backtest.db for analysis
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
from typing import List, Dict, Tuple
import config
from backtest.database import Database
from backtest.engine import run_backtest
from backtest.data_loader import DataLoader


# ============================================================================
# Phase 7.4 Configuration (from config pattern, customize here)
# ============================================================================

# Symbols to test
VALIDATION_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Timeframe
VALIDATION_INTERVAL = "4h"

# Parameter grid
STOP_LOSS_GRID = [0.0125, 0.015, 0.02]      # 1.25%, 1.5%, 2%
TAKE_PROFIT_GRID = [0.055, 0.06, 0.065]     # 5.5%, 6%, 6.5%

# Backtest settings
BACKTEST_MODE = "per"  # "per"=per-strategy, "agg"=aggregated, "both"=both


# ============================================================================
# Validation Pipeline
# ============================================================================

def ensure_data_loaded(symbols: List[str], interval: str) -> None:
    """Ensure all symbols have data loaded in database."""
    print(f"\n{'='*80}")
    print("PHASE 7.4: PARAMETER VALIDATION")
    print(f"{'='*80}\n")
    
    print("📊 Step 1: Ensuring data loaded for all symbols...")
    loader = DataLoader()
    
    for symbol in symbols:
        try:
            db = Database()
            conn = sqlite3.connect(config.BACKTEST_DB)
            count = conn.execute(
                f"SELECT COUNT(*) FROM {symbol}_{interval}"
            ).fetchone()[0]
            conn.close()
            
            if count == 0:
                print(f"  ⏳ Syncing {symbol} {interval} data...")
                loader.sync(symbol=symbol, interval=interval)
            else:
                print(f"  ✓ {symbol} {interval}: {count} bars available")
        except Exception as e:
            print(f"  ⚠️  {symbol} sync: {str(e)[:60]}...")


def run_validation_grid(
    symbols: List[str],
    interval: str,
    sl_grid: List[float],
    tp_grid: List[float],
) -> List[Dict]:
    """
    Run backtests for all combinations in parameter grid.
    
    Returns:
        List of result dicts with keys: symbol, sl, tp, run_id, trades, 
        win_rate, return, dd, sharpe
    """
    results = []
    total_runs = len(symbols) * len(sl_grid) * len(tp_grid)
    current = 0
    
    print(f"\n📈 Step 2: Running parameter grid ({total_runs} combinations)...\n")
    
    for symbol in symbols:
        for sl_pct in sl_grid:
            for tp_pct in tp_grid:
                current += 1
                status = f"[{current:2d}/{total_runs}]"
                label = f"{symbol} SL={sl_pct*100:.2f}% TP={tp_pct*100:.2f}%"
                
                try:
                    print(f"  {status} {label}...", end=" ", flush=True)
                    
                    # Run backtest with specific SL/TP
                    run_ids = run_backtest(
                        symbol=symbol,
                        interval=interval,
                        mode=BACKTEST_MODE,
                        sl_pct=sl_pct,
                        tp_pct=tp_pct,
                    )
                    
                    if run_ids:
                        run_id = run_ids[0]
                        db = Database()
                        run_data = db.get_run(run_id)
                        
                        result = {
                            "symbol": symbol,
                            "sl_pct": sl_pct,
                            "tp_pct": tp_pct,
                            "run_id": run_id,
                            "trades": run_data["total_trades"],
                            "win_rate": run_data["win_rate_pct"],
                            "return": run_data["total_return_pct"],
                            "dd": run_data["max_drawdown_pct"],
                            "sharpe": run_data["sharpe_ratio"],
                        }
                        results.append(result)
                        print("✓")
                    else:
                        print("✗ (no run)")
                        
                except Exception as e:
                    print(f"✗ ({str(e)[:40]})")
                    continue
    
    return results


def print_summary_table(results: List[Dict]) -> None:
    """Print formatted summary table of all results."""
    if not results:
        print("\n❌ No results to display")
        return
    
    print(f"\n{'='*120}")
    print("VALIDATION RESULTS SUMMARY")
    print(f"{'='*120}\n")
    
    # Header
    header = (
        f"{'Symbol':<12} "
        f"{'SL %':<8} "
        f"{'TP %':<8} "
        f"{'Return %':<10} "
        f"{'Win %':<8} "
        f"{'Trades':<8} "
        f"{'DD %':<8} "
        f"{'Sharpe':<8}"
    )
    print(header)
    print("-" * 120)
    
    # Results rows
    for r in results:
        row = (
            f"{r['symbol']:<12} "
            f"{r['sl_pct']*100:>7.2f}% "
            f"{r['tp_pct']*100:>7.2f}% "
            f"{r['return']:>9.2f}% "
            f"{r['win_rate']:>7.1f}% "
            f"{r['trades']:>7} "
            f"{r['dd']:>7.2f}% "
            f"{r['sharpe']:>7.4f}"
        )
        print(row)
    
    print("-" * 120)


def print_best_performers(results: List[Dict], top_n: int = 5) -> None:
    """Print top N performers by return and by Sharpe ratio."""
    if not results:
        return
    
    # Best by return
    print(f"\n{'='*120}")
    print(f"🏆 TOP {top_n} BY RETURN")
    print(f"{'='*120}\n")
    
    top_return = sorted(results, key=lambda x: x["return"], reverse=True)[:top_n]
    for i, r in enumerate(top_return, 1):
        print(
            f"{i}. {r['symbol']} (SL {r['sl_pct']*100:.2f}% TP {r['tp_pct']*100:.2f}%) "
            f"→ {r['return']:+.2f}% return | {r['win_rate']:.1f}% win | {r['sharpe']:.4f} Sharpe"
        )
    
    # Best by Sharpe
    print(f"\n{'='*120}")
    print(f"⭐ TOP {top_n} BY SHARPE RATIO")
    print(f"{'='*120}\n")
    
    top_sharpe = sorted(results, key=lambda x: x["sharpe"], reverse=True)[:top_n]
    for i, r in enumerate(top_sharpe, 1):
        print(
            f"{i}. {r['symbol']} (SL {r['sl_pct']*100:.2f}% TP {r['tp_pct']*100:.2f}%) "
            f"→ {r['sharpe']:.4f} Sharpe | {r['return']:+.2f}% return | {r['win_rate']:.1f}% win"
        )


def print_symbol_summary(results: List[Dict]) -> None:
    """Print aggregate statistics by symbol."""
    if not results:
        return
    
    symbols = set(r["symbol"] for r in results)
    
    print(f"\n{'='*120}")
    print("SYMBOL PERFORMANCE SUMMARY")
    print(f"{'='*120}\n")
    
    for symbol in sorted(symbols):
        symbol_results = [r for r in results if r["symbol"] == symbol]
        
        avg_return = sum(r["return"] for r in symbol_results) / len(symbol_results)
        avg_sharpe = sum(r["sharpe"] for r in symbol_results) / len(symbol_results)
        best_return = max(r["return"] for r in symbol_results)
        best_sharpe = max(r["sharpe"] for r in symbol_results)
        
        print(
            f"{symbol:<12} | "
            f"Avg Return: {avg_return:+7.2f}% (best {best_return:+7.2f}%) | "
            f"Avg Sharpe: {avg_sharpe:7.4f} (best {best_sharpe:7.4f})"
        )


def main() -> None:
    """Run Phase 7.4 validation pipeline."""
    
    # Step 1: Ensure data is loaded
    ensure_data_loaded(VALIDATION_SYMBOLS, VALIDATION_INTERVAL)
    
    # Step 2: Run parameter grid
    results = run_validation_grid(
        symbols=VALIDATION_SYMBOLS,
        interval=VALIDATION_INTERVAL,
        sl_grid=STOP_LOSS_GRID,
        tp_grid=TAKE_PROFIT_GRID,
    )
    
    # Step 3: Print results
    print_summary_table(results)
    print_best_performers(results, top_n=5)
    print_symbol_summary(results)
    
    # Final summary
    print(f"\n{'='*120}")
    print(f"✅ VALIDATION COMPLETE: {len(results)} runs executed")
    print(f"{'='*120}\n")
    
    return results


if __name__ == "__main__":
    main()
