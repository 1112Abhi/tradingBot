# state.py - Signal State Management Module

import json
import os
from typing import Any, Dict

import config


def get_state() -> Dict[str, Any]:
    """
    Load persisted bot state from STATE_FILE.

    Returns:
        Dict with keys "last_signal" (str), "last_price" (float), 
        "price_history" (list), "entry_price" (float or None),
        and "position" (str: "LONG" or "NONE").
        Returns defaults if file is absent or unreadable.
    """
    defaults: Dict[str, Any] = {
        "last_signal": None, 
        "last_price": None,
        "price_history": [],
        "entry_price": None,
        "position": "NONE"
    }

    if not os.path.exists(config.STATE_FILE):
        return defaults

    try:
        with open(config.STATE_FILE, "r") as fh:
            data = json.load(fh)
        return {**defaults, **data}
    except (json.JSONDecodeError, OSError):
        return defaults


def save_state(
    last_signal: str, 
    last_price: float, 
    price_history: list = None,
    entry_price: float = None,
    position: str = "NONE"
) -> None:
    """
    Persist current signal, price, history, entry price, and position to STATE_FILE.

    Args:
        last_signal: Most recent signal string (e.g. "BUY").
        last_price:  Most recent fetched price.
        price_history: List of recent prices for EMA calculation.
        entry_price: Price at which position was entered (for stop loss).
        position: Current position state ("LONG" or "NONE").
    """
    state = {
        "last_signal": last_signal, 
        "last_price": last_price,
        "price_history": price_history or [],
        "entry_price": entry_price,
        "position": position
    }
    with open(config.STATE_FILE, "w") as fh:
        json.dump(state, fh, indent=2)


def update_price_history(current_price: float) -> list:
    """
    Add new price to history buffer, maintaining max size.
    
    Args:
        current_price: Latest price to add
        
    Returns:
        Updated price history (list of floats, max PRICE_HISTORY_SIZE)
    """
    state = get_state()
    history = state.get("price_history", [])
    
    # Add new price
    history.append(current_price)
    
    # Trim to max size (keep newest)
    if len(history) > config.PRICE_HISTORY_SIZE:
        history = history[-config.PRICE_HISTORY_SIZE:]
    
    return history


def should_send_alert(new_signal: str, last_signal: str | None) -> bool:
    """
    Determine whether a Telegram alert should be sent.

    Alerts fire only when the signal has changed, preventing
    repeated notifications for the same condition.

    Args:
        new_signal:  Freshly generated signal.
        last_signal: Signal from the previous cycle (or None on first run).

    Returns:
        True if the signal is new or has changed.
    """
    return new_signal != last_signal
