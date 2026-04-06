# aggregator.py - Signal Aggregation Engine

from typing import Dict, List
import config


def aggregate(signals: Dict[str, str]) -> str:
    """
    Combine per-strategy signals into a single actionable signal.

    Args:
        signals: Mapping of strategy name → signal string.
                 e.g. {"ema_crossover": "BUY", "rsi": "NO_TRADE"}

    Returns:
        One of "BUY", "SELL", or "NO_TRADE".
    """
    if not signals:
        return config.SIGNAL_NO_TRADE

    method = config.AGGREGATION_METHOD
    values = list(signals.values())

    if method == "unanimous":
        return _unanimous(values)
    if method == "majority":
        return _majority(values)
    if method == "any":
        return _any(values)
    if method == "conservative":
        return _conservative(values)
    if method == "weighted":
        return _weighted(signals)

    raise ValueError(
        f"Unknown AGGREGATION_METHOD '{method}'. "
        f"Choose: unanimous, majority, any, conservative, weighted."
    )


# ---------------------------------------------------------------------------
# Aggregation methods
# ---------------------------------------------------------------------------

def _unanimous(signals: List[str]) -> str:
    """Act only when every strategy agrees."""
    if all(s == config.SIGNAL_BUY  for s in signals): 
        return config.SIGNAL_BUY
    if all(s == config.SIGNAL_SELL for s in signals): 
        return config.SIGNAL_SELL
    return config.SIGNAL_NO_TRADE


def _majority(signals: List[str]) -> str:
    """Act on whichever signal holds a strict majority. SELL beats ties."""
    n         = len(signals)
    buy_count  = signals.count(config.SIGNAL_BUY)
    sell_count = signals.count(config.SIGNAL_SELL)

    if sell_count > n / 2:  
        return config.SIGNAL_SELL
    if buy_count  > n / 2:  
        return config.SIGNAL_BUY
    # Tie-break: SELL > BUY > NO_TRADE (risk-first)
    if sell_count > 0 and sell_count == buy_count: 
        return config.SIGNAL_SELL
    return config.SIGNAL_NO_TRADE


def _any(signals: List[str]) -> str:
    """Act on any non-neutral signal. SELL takes priority over BUY (risk-first)."""
    if config.SIGNAL_SELL in signals: 
        return config.SIGNAL_SELL
    if config.SIGNAL_BUY  in signals: 
        return config.SIGNAL_BUY
    return config.SIGNAL_NO_TRADE


def _conservative(signals: List[str]) -> str:
    """
    Default method. Cautious on entry, aggressive on exit.
    BUY only when unanimous; SELL if any strategy says SELL.
    """
    if config.SIGNAL_SELL in signals:
        return config.SIGNAL_SELL
    if all(s == config.SIGNAL_BUY for s in signals):
        return config.SIGNAL_BUY
    return config.SIGNAL_NO_TRADE


def _weighted(signals: Dict[str, str]) -> str:
    """
    Score-based aggregation using STRATEGY_WEIGHTS.

    Each strategy contributes a signed score:
        BUY      → +weight
        SELL     → -weight
        NO_TRADE →  0

    Weights are auto-normalized to sum to 1.0.
    If STRATEGY_WEIGHTS is empty, all strategies receive equal weight.

    Score ranges:
        ≥ +config.WEIGHTED_BUY_THRESHOLD  → BUY
        ≤ -config.WEIGHTED_SELL_THRESHOLD → SELL
        otherwise                          → NO_TRADE
    """
    weights = dict(config.STRATEGY_WEIGHTS)  # shallow copy

    # Auto-assign equal weights for any strategy not explicitly listed
    for name in signals:
        if name not in weights:
            weights[name] = 1.0

    # Normalize so weights sum to 1.0
    total = sum(weights[name] for name in signals)
    if total == 0:
        return config.SIGNAL_NO_TRADE
    normalized = {name: weights[name] / total for name in signals}

    score_map  = {
        config.SIGNAL_BUY:      +1.0,
        config.SIGNAL_SELL:     -1.0,
        config.SIGNAL_NO_TRADE:  0.0,
    }
    score = sum(normalized[name] * score_map[sig] for name, sig in signals.items())

    if score >=  config.WEIGHTED_BUY_THRESHOLD:  
        return config.SIGNAL_BUY
    if score <= -config.WEIGHTED_SELL_THRESHOLD: 
        return config.SIGNAL_SELL
    return config.SIGNAL_NO_TRADE


# ---------------------------------------------------------------------------
# Telegram breakdown formatter
# ---------------------------------------------------------------------------

def format_breakdown(signals: Dict[str, str], final: str) -> str:
    """
    Format per-strategy signals and final decision for Telegram.

    Example output:
        🧪 Strategy Signals:
        EMA_CROSSOVER: BUY
        RSI: NO_TRADE

        ⚙️ Aggregation: conservative
        🚨 FINAL SIGNAL: BUY
    """
    lines = ["🧪 Strategy Signals:"]
    for name, sig in signals.items():
        lines.append(f"  {name.upper()}: {sig}")
    lines.append("")
    lines.append(f"⚙️  Aggregation: {config.AGGREGATION_METHOD}")
    lines.append(f"🚨 FINAL SIGNAL: {final}")
    return "\n".join(lines)
