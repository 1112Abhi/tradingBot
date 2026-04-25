"""
scripts/research/regime_research.py — Regime Filter Impact Research

Backtests each strategy WITH and WITHOUT the regime filter, compares:
  - Sharpe ratio
  - Total return
  - Max drawdown
  - Trade count (filter reduces trades)
  - Win rate

Regime filter logic:
  MR / BB strategies  → only enter in RANGING regime
  EMA / Donchian      → only enter in TRENDING regime

Usage:
    python scripts/research/regime_research.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import uuid
from datetime import datetime, timezone
from typing import List, Optional

import config
from backtest.database import Database
from strategy.base import BaseStrategy, MarketData
from strategy.ema_crossover import MACrossoverStrategy
from strategy.mean_reversion import MeanReversionStrategy
from strategy.donchian_breakout import DonchianBreakoutStrategy
from strategy.regime import RegimeDetector, REGIME_TRENDING, REGIME_RANGING

SL_PCT        = 0.015
TP_PCT        = 0.060
POSITION_SIZE = 0.25
MAX_HOLD_BARS = 100

# Strategies and their preferred regime
CONFIGS = [
    ("mean_reversion",    "BTCUSDT", "4h",
     MeanReversionStrategy(rsi_period=14, rsi_oversold=35, rsi_exit=55, trend_period=50),
     REGIME_RANGING),
    ("mean_reversion",    "ETHUSDT", "4h",
     MeanReversionStrategy(rsi_period=14, rsi_oversold=35, rsi_exit=55, trend_period=50),
     REGIME_RANGING),
    ("mean_reversion",    "SOLUSDT", "4h",
     MeanReversionStrategy(rsi_period=14, rsi_oversold=35, rsi_exit=55, trend_period=50),
     REGIME_RANGING),
    ("ema_crossover",     "BTCUSDT", "4h",
     MACrossoverStrategy(fast_period=12, slow_period=26, trend_period=50,
                         rsi_period=14, rsi_buy_min=0, rsi_buy_max=100),
     REGIME_TRENDING),
    ("donchian_breakout", "BTCUSDT", "4h",
     DonchianBreakoutStrategy(period=20),
     REGIME_TRENDING),
]

REGIME_PERIODS    = [20, 30, 50]   # test multiple lookback windows
REGIME_THRESHOLDS = [0.35, 0.45, 0.55]


# ── Core simulation ────────────────────────────────────────────────────────────

def _simulate(bars: list, strategy: BaseStrategy, sl_pct: float, tp_pct: float,
              position_size: float, regime_detector: Optional[RegimeDetector],
              regime_required: Optional[str]) -> dict:
    """Run one backtest pass, optionally gating entries by regime."""
    capital      = config.BACKTEST_CAPITAL
    position     = "NONE"
    entry_price  = None
    entry_bar    = None
    entry_value  = None
    trades       = []
    warmup       = config.BACKTEST_MIN_WINDOW

    for t in range(warmup, len(bars) - 1):
        window     = [dict(b) for b in bars[:t + 1]]
        exec_bar   = bars[t + 1]
        exec_price = exec_bar["mid"]
        exec_ts    = exec_bar["timestamp"]
        prices     = [b["mid"]    for b in window]
        volumes    = [b["volume"] for b in window]

        market_data: MarketData = {
            "prices":      prices,
            "entry_price": entry_price,
            "position":    position,
            "symbol":      "",
            "timestamp":   window[-1]["timestamp"],
            "volumes":     volumes,
        }

        try:
            signal = strategy.generate_signal(market_data)
        except Exception:
            signal = config.SIGNAL_NO_TRADE

        # Regime gate — only applies to entries
        if (signal == config.SIGNAL_BUY and regime_detector and regime_required
                and len(prices) >= regime_detector.period):
            regime = regime_detector.detect(prices)
            if regime != regime_required:
                signal = config.SIGNAL_NO_TRADE

        if signal == config.SIGNAL_BUY and position == "NONE":
            slipped    = exec_price * (1 + config.SLIPPAGE_RATE)
            position   = "LONG"
            entry_price = slipped
            entry_bar  = t
            entry_value = capital * position_size

        elif position == "LONG":
            sl_price = entry_price * (1 - sl_pct)
            tp_price = entry_price * (1 + tp_pct)
            bars_held = t - entry_bar
            reason    = None

            if exec_price >= tp_price:
                reason = "take_profit"
            elif exec_price <= sl_price:
                reason = "stop_loss"
            elif bars_held > MAX_HOLD_BARS:
                reason = "timeout"
            elif signal == config.SIGNAL_SELL:
                reason = "signal_exit"

            if reason:
                slipped_exit = exec_price * (1 - config.SLIPPAGE_RATE)
                gross_pnl    = entry_value * (slipped_exit - entry_price) / entry_price
                fee          = (entry_value + entry_value + gross_pnl) * config.BACKTEST_FEE_PCT
                net_pnl      = gross_pnl - fee
                pnl_pct      = net_pnl / entry_value * 100
                capital     += net_pnl
                trades.append({
                    "pnl_dollar": net_pnl,
                    "pnl_pct":    pnl_pct,
                    "exit_reason": reason,
                })
                position    = "NONE"
                entry_price = None
                entry_bar   = None
                entry_value = None

    return _metrics(trades, capital)


def _metrics(trades: list, final_capital: float) -> dict:
    if not trades:
        return {"n": 0, "return": 0.0, "sharpe": 0.0, "dd": 0.0, "win_rate": 0.0}

    n          = len(trades)
    wins       = sum(1 for t in trades if t["pnl_dollar"] > 0)
    net_return = (final_capital - config.BACKTEST_CAPITAL) / config.BACKTEST_CAPITAL * 100
    returns    = [t["pnl_pct"] for t in trades]
    mean_r     = sum(returns) / n

    sharpe = 0.0
    if n >= 2:
        std_r = (sum((r - mean_r) ** 2 for r in returns) / (n - 1)) ** 0.5
        if std_r > 0:
            sharpe = round(mean_r / std_r * (n ** 0.5), 4)

    capital = config.BACKTEST_CAPITAL
    peak    = capital
    max_dd  = 0.0
    for t in trades:
        capital += t["pnl_dollar"]
        peak     = max(peak, capital)
        dd       = (peak - capital) / peak * 100
        max_dd   = max(max_dd, dd)

    return {
        "n":        n,
        "return":   round(net_return, 2),
        "sharpe":   round(sharpe, 3),
        "dd":       round(max_dd, 2),
        "win_rate": round(wins / n * 100, 1),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    db = Database()

    print()
    print("=" * 70)
    print("  REGIME FILTER RESEARCH")
    print("  Comparing strategy performance: with vs without regime filter")
    print("=" * 70)

    best_improvements = []  # collect for summary

    for strategy_name, symbol, interval, strategy, regime_required in CONFIGS:
        bars = db.get_prices(symbol, interval)
        if len(bars) < config.BACKTEST_MIN_WINDOW + 1:
            print(f"\n  {strategy_name} {symbol} {interval} — insufficient data, skipping")
            continue

        print(f"\n{'─'*70}")
        print(f"  {strategy_name.upper()} | {symbol} {interval} | preferred: {regime_required}")
        print(f"{'─'*70}")

        # Baseline: no filter
        baseline = _simulate(bars, strategy, SL_PCT, TP_PCT, POSITION_SIZE,
                             None, None)
        print(f"\n  BASELINE (no filter):")
        print(f"    trades={baseline['n']}  return={baseline['return']:+.2f}%  "
              f"sharpe={baseline['sharpe']:.3f}  DD={baseline['dd']:.2f}%  "
              f"win%={baseline['win_rate']:.1f}")

        # Test each period + threshold combo
        best = None
        best_key = None
        for period in REGIME_PERIODS:
            for threshold in REGIME_THRESHOLDS:
                detector = RegimeDetector(period=period, threshold=threshold)
                result   = _simulate(bars, strategy, SL_PCT, TP_PCT, POSITION_SIZE,
                                     detector, regime_required)
                if result["n"] < 5:
                    continue
                if best is None or result["sharpe"] > best["sharpe"]:
                    best     = result
                    best_key = (period, threshold)

        if best and best_key:
            period, threshold = best_key
            sharpe_delta = best["sharpe"] - baseline["sharpe"]
            return_delta = best["return"] - baseline["return"]
            trade_delta  = best["n"] - baseline["n"]
            print(f"\n  BEST WITH FILTER (period={period}, threshold={threshold}):")
            print(f"    trades={best['n']}  return={best['return']:+.2f}%  "
                  f"sharpe={best['sharpe']:.3f}  DD={best['dd']:.2f}%  "
                  f"win%={best['win_rate']:.1f}")
            print(f"\n  DELTA vs baseline:")
            print(f"    sharpe {sharpe_delta:+.3f}  |  return {return_delta:+.2f}%  "
                  f"|  trades {trade_delta:+d}")
            verdict = "✅ IMPROVES" if sharpe_delta > 0.05 else (
                      "⚠️  NEUTRAL" if sharpe_delta > -0.05 else "❌ HURTS")
            print(f"    Verdict: {verdict}")
            best_improvements.append({
                "strategy": strategy_name, "symbol": symbol, "interval": interval,
                "baseline_sharpe": baseline["sharpe"], "filtered_sharpe": best["sharpe"],
                "delta": sharpe_delta, "period": period, "threshold": threshold,
                "verdict": verdict,
            })
        else:
            print(f"\n  No valid filtered result (too few trades with filter)")

    # Summary
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    for r in best_improvements:
        print(f"  {r['strategy']:<20} {r['symbol']} {r['interval']}  "
              f"sharpe: {r['baseline_sharpe']:.3f} → {r['filtered_sharpe']:.3f} "
              f"({r['delta']:+.3f})  {r['verdict']}")
    print()


if __name__ == "__main__":
    main()
