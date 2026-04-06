#!/usr/bin/env python3
"""
run_live.py — Start the Phase 7.6 paper trading candle watcher.

Usage:
    python run_live.py
    python run_live.py --symbol BTCUSDT --interval 4h

Logs to both terminal and logs/watcher.log (rotating daily, 30-day retention).
"""

import argparse
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

import config
from core.candle_watcher import CandleWatcher


def _setup_logging() -> None:
    """Configure root logger to write to stdout and a rotating daily log file."""
    os.makedirs(os.path.dirname(config.LOG_WATCHER_FILE), exist_ok=True)

    fmt     = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
    root    = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler — mirrors what you see in the terminal
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler — rotates at midnight, keeps 30 days
    fh = TimedRotatingFileHandler(
        config.LOG_WATCHER_FILE,
        when="midnight",
        backupCount=30,
        utc=True,
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",   default="BTCUSDT")
    parser.add_argument("--interval", default="4h")
    args = parser.parse_args()

    logging.info(f"[RUN_LIVE] Logging to {config.LOG_WATCHER_FILE}")
    watcher = CandleWatcher(symbol=args.symbol, interval=args.interval)
    watcher.run()


if __name__ == "__main__":
    main()
