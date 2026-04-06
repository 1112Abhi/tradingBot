# backtest_runner.py - CLI Entry Point

import argparse
import sys
from backtest.data_loader import DataLoader
from backtest.engine import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading Bot Backtest Runner")
    parser.add_argument("--symbol",   default="BTCUSDT",  help="Binance pair (default: BTCUSDT)")
    parser.add_argument("--interval", default="1h",        help="Candle interval (default: 1h)")
    parser.add_argument("--mode",     default="both",      choices=["per", "agg", "both"],
                        help="per=per-strategy, agg=aggregated, both=both (default: both)")
    parser.add_argument("--sync",     action="store_true", help="Sync latest data before backtesting")
    args = parser.parse_args()

    if args.sync:
        print(f"[Runner] Syncing {args.symbol} {args.interval} data...")
        loader   = DataLoader()
        inserted = loader.sync(symbol=args.symbol, interval=args.interval)
        print(f"[Runner] Sync complete: {inserted} new bars inserted")

    print(f"[Runner] Starting backtest: {args.symbol} {args.interval} mode={args.mode}")
    run_ids = run_backtest(symbol=args.symbol, interval=args.interval, mode=args.mode)
    print(f"[Runner] Done. {len(run_ids)} run(s) stored.")
    for rid in run_ids:
        print(f"  run_id: {rid}")


if __name__ == "__main__":
    main()
