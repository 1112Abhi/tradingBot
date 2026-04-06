# utils/config_loader.py — Strategy config loader
#
# Loads a strategy's YAML config from the config/ directory.
# Used by candle_watcher.py to instantiate live strategies.
# Research/backtest scripts continue to pass kwargs directly — no change needed.

import os
import yaml

# Path to config/ directory relative to this file
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load_config(strategy_name: str) -> dict:
    """
    Load strategy config from config/<strategy_name>.yaml.

    Args:
        strategy_name: File stem, e.g. "mean_reversion" or "bb_breakout_eth_1h"

    Returns:
        Parsed YAML as a dict with keys: strategy, symbol, timeframe, params, risk

    Raises:
        FileNotFoundError: if config file does not exist
        ValueError: if required top-level keys are missing
    """
    path = os.path.join(_CONFIG_DIR, f"{strategy_name}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No config file for '{strategy_name}' — expected {path}"
        )

    with open(path) as f:
        cfg = yaml.safe_load(f)

    for key in ("strategy", "symbol", "timeframe", "mode", "params", "risk"):
        if key not in cfg:
            raise ValueError(f"Config '{strategy_name}.yaml' missing required key: '{key}'")

    if cfg["mode"] not in ("portfolio", "experiment"):
        raise ValueError(f"Config '{strategy_name}.yaml' mode must be 'portfolio' or 'experiment', got '{cfg['mode']}'")

    return cfg
