#!/usr/bin/env python3
"""
run_live.py — Start the unified multi-symbol candle watcher.

Loads all strategy YAML configs, builds StrategyGroups, and starts the watcher.
To add a new strategy: drop a YAML in config/ and add it to STRATEGY_CONFIGS below.

Usage:
    python run_live.py

Logs to both terminal and logs/watcher.log (rotating daily, 30-day retention).
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler  # noqa: F401

import config
from backtest.database import Database
from core.candle_watcher import CandleWatcher, StrategyGroup
from strategy.ema_crossover import MACrossoverStrategy
from strategy.mean_reversion import MeanReversionStrategy
from strategy.bb_breakout import BBBreakoutStrategy
from strategy.donchian_breakout import DonchianBreakoutStrategy
from utils.config_loader import load_config

# ── Strategy configs to load (order determines heartbeat display order) ──────
STRATEGY_CONFIGS = [
    # Portfolio strategies (real capital)
    "ema_crossover",
    "mean_reversion",
    # Experiment strategies (signals only, no capital)
    "bb_breakout_eth_1h",
    "mean_reversion_eth_4h",
    "mean_reversion_sol_4h",
    "donchian_btc_4h",
]

# ── Strategy class registry ────────────────────────────────────────────────────
STRATEGY_CLASSES = {
    "ema_crossover":     MACrossoverStrategy,
    "mean_reversion":    MeanReversionStrategy,
    "bb_breakout":       BBBreakoutStrategy,
    "donchian_breakout": DonchianBreakoutStrategy,
}


def _setup_logging() -> None:
    os.makedirs(os.path.dirname(config.LOG_WATCHER_FILE), exist_ok=True)
    fmt  = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    fh = TimedRotatingFileHandler(
        config.LOG_WATCHER_FILE, when="midnight", backupCount=30, utc=True,
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def build_groups() -> list:
    """
    Load all strategy YAML configs and group by (symbol, interval).
    Strategies sharing the same symbol+interval are combined into one StrategyGroup.
    """
    # Intermediate: keyed by (symbol, interval) → accumulate strategies + shared risk
    group_map: dict = {}

    for config_name in STRATEGY_CONFIGS:
        cfg = load_config(config_name)

        symbol        = cfg["symbol"]
        interval      = cfg["timeframe"]
        mode          = cfg["mode"]
        sl_pct        = cfg["risk"]["sl"] / 100
        tp_pct        = cfg["risk"]["tp"] / 100
        position_size = cfg["risk"].get("position_size", 0.25)

        strategy_type = cfg["strategy"]
        if strategy_type not in STRATEGY_CLASSES:
            raise ValueError(f"Unknown strategy '{strategy_type}' in {config_name}.yaml")

        strategy = STRATEGY_CLASSES[strategy_type](**cfg["params"])
        key      = (symbol, interval, mode)

        if key not in group_map:
            group_map[key] = {
                "symbol":         symbol,
                "interval":       interval,
                "mode":           mode,
                "strategies":     [],
                "sl_pct":         sl_pct,
                "tp_pct":         tp_pct,
                "position_sizes": {},
            }
        group_map[key]["strategies"].append(strategy)
        group_map[key]["position_sizes"][strategy.name] = position_size

    groups = [
        StrategyGroup(
            symbol         = v["symbol"],
            interval       = v["interval"],
            mode           = v["mode"],
            strategies     = v["strategies"],
            sl_pct         = v["sl_pct"],
            tp_pct         = v["tp_pct"],
            position_sizes = v["position_sizes"],
        )
        for v in group_map.values()
    ]
    return groups


def main() -> None:
    _setup_logging()
    logging.info(f"[RUN_LIVE] Logging to {config.LOG_WATCHER_FILE}")

    groups = build_groups()
    for g in groups:
        names = [s.name for s in g.strategies]
        logging.info(f"[RUN_LIVE] Group: {g.symbol} {g.interval} [{g.mode}] → {names}")

    db      = Database()
    watcher = CandleWatcher(groups=groups, db=db)
    watcher.run()


if __name__ == "__main__":
    main()
