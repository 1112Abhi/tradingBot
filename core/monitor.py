# monitor.py - Live Price Monitoring Module

import time
from datetime import datetime, timezone
from typing import Optional

import config
from strategy.aggregator import aggregate, format_breakdown
from core.data_fetch import fetch_price
from logger import log_activity, purge_old_logs
from core.state import get_state, save_state, should_send_alert
from strategy.base import MarketData
from strategy.factory import get_strategies
from telegram.bot import send_message


def watch_price(
    symbol: str = config.SYMBOL,
    interval: int = config.MONITOR_INTERVAL,
    duration_seconds: Optional[int] = None,
) -> None:
    """
    Monitor asset price in a loop, sending alerts when the aggregated signal changes.

    Args:
        symbol:           Asset to monitor (e.g. "bitcoin").
        interval:         Seconds between each price check.
        duration_seconds: Total run time; None runs indefinitely.
    """
    purge_old_logs()
    strategies = get_strategies()
    state      = get_state()
    elapsed    = 0

    while _should_continue(elapsed, duration_seconds):
        price, final_signal, action = _run_cycle(symbol, strategies, state)
        state = {"last_signal": final_signal, "last_price": price, "position": state.get("position", "NONE")}
        save_state(final_signal, price)
        log_activity(price, final_signal, action)

        time.sleep(interval)
        elapsed += interval


def _run_cycle(symbol: str, strategies, state: dict) -> tuple:
    """
    Single fetch → analyse → aggregate → (maybe) alert cycle.

    Returns:
        Tuple of (price, final_signal, action_taken).
    """
    try:
        price = fetch_price(symbol=symbol, source=config.DATA_SOURCE)
    except Exception as exc:
        print(f"[MONITOR] Fetch error: {exc}")
        return 0.0, config.SIGNAL_NO_TRADE, "fetch_error"

    timestamp   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry_price = state.get("last_price")
    position    = state.get("position", "NONE")

    market_data: MarketData = {
        "prices":      [price],   # single-bar list for Phase 3; monitor.py can
        "entry_price": entry_price,  # accumulate bars in Phase 4+
        "position":    position,
        "symbol":      symbol,
        "timestamp":   timestamp,
    }

    # Collect per-strategy signals
    per_strategy: dict[str, str] = {}
    for strategy in strategies:
        try:
            per_strategy[strategy.name] = strategy.generate_signal(market_data)
        except ValueError as exc:
            print(f"[MONITOR] {strategy.name} skipped: {exc}")
            per_strategy[strategy.name] = config.SIGNAL_NO_TRADE

    final_signal = aggregate(per_strategy)

    if should_send_alert(final_signal, state.get("last_signal")):
        if config.SEND_STRATEGY_BREAKDOWN:
            message = format_breakdown(per_strategy, final_signal)
        else:
            message = f"📊 {symbol.upper()} | Signal: {final_signal} | Price: ${price:,.2f}"
        success = send_message(message)
        action  = "alert_sent" if success else "alert_failed"
    else:
        action = "skipped"

    print(f"[MONITOR] price={price:.2f}  signals={per_strategy}  final={final_signal}  action={action}")
    return price, final_signal, action


def _should_continue(elapsed: int, duration_seconds: Optional[int]) -> bool:
    if duration_seconds is None:
        return True
    return elapsed < duration_seconds
